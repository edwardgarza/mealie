"""Build the trimmed nutrition dataset that ships with Mealie.

Reads the public-domain USDA FoodData Central downloads (SR Legacy CSV zip and Foundation Foods
JSON zip) and the Open Tandoor Data export, and writes two compact files next to the nutrition
service:

- usda_foods.json.gz: one record per food with the nutrients Mealie tracks (per 100 g) and its
  portion weights
- curated_foods.json: common kitchen foods already linked to a USDA id by the Tandoor community

Usage: python dev/scripts/nutrition_build_dataset.py [raw_dir]
"""

import csv
import gzip
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from rich.console import Console

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mealie.services.nutrition.nutrients import NUTRIENTS  # noqa: E402

console = Console(highlight=False)
OUT_DIR = ROOT / "mealie" / "services" / "nutrition" / "data"
SR_ZIP = "FoodData_Central_sr_legacy_food_csv_2018-04.zip"
FF_ZIP = "FoodData_Central_foundation_food_json_2025-12-18.zip"
TANDOOR = "open-tandoor-data.en.json"

# FDC nutrient id -> (our key, priority); a lower priority wins when a food has several
FDC_TO_KEY: dict[int, tuple[str, int]] = {
    fdc_id: (n.key, priority) for n in NUTRIENTS for priority, fdc_id in enumerate(n.fdc_ids)
}


def _round(value: float) -> float:
    return round(value, 3)


def _pick(found: dict[str, tuple[int, float]]) -> dict[str, float]:
    nutrients = {key: _round(value) for key, (_, value) in found.items()}
    if "energy_kcal" not in nutrients and {"protein_g", "fat_g", "carbohydrate_g"} <= nutrients.keys():
        # Some Foundation foods publish no energy value at all; fall back to the general factors
        nutrients["energy_kcal"] = _round(
            4 * nutrients["protein_g"] + 9 * nutrients["fat_g"] + 4 * nutrients["carbohydrate_g"]
        )
    return nutrients


def _csv(archive: zipfile.ZipFile, name: str):
    member = next(n for n in archive.namelist() if n.endswith("/" + name))
    return csv.DictReader(io.TextIOWrapper(archive.open(member), encoding="utf-8"))


def read_sr_legacy(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        categories = {row["id"]: row["description"] for row in _csv(archive, "food_category.csv")}

        nutrients: dict[str, dict[str, tuple[int, float]]] = defaultdict(dict)
        for row in _csv(archive, "food_nutrient.csv"):
            mapped = FDC_TO_KEY.get(int(row["nutrient_id"]))
            if not mapped or row["amount"] == "":
                continue
            key, priority = mapped
            current = nutrients[row["fdc_id"]].get(key)
            if current is None or priority < current[0]:
                nutrients[row["fdc_id"]][key] = (priority, float(row["amount"]))

        portions: dict[str, list] = defaultdict(list)
        for row in sorted(_csv(archive, "food_portion.csv"), key=lambda r: (r["fdc_id"], int(r["seq_num"] or 0))):
            amount, grams = float(row["amount"] or 1), float(row["gram_weight"] or 0)
            if amount > 0 and grams > 0:
                # SR Legacy stores the unit as free text in `modifier`, e.g. "cup, chopped"
                portions[row["fdc_id"]].append([amount, row["modifier"].strip(), _round(grams)])

        return [
            {
                "id": int(row["fdc_id"]),
                "src": "sr_legacy",
                "name": row["description"],
                "cat": categories.get(row["food_category_id"], ""),
                "n": _pick(nutrients.get(row["fdc_id"], {})),
                "p": portions.get(row["fdc_id"], []),
            }
            for row in _csv(archive, "food.csv")
        ]


def read_foundation(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        data = json.load(archive.open(archive.namelist()[0]))["FoundationFoods"]

    records = []
    for food in data:
        found: dict[str, tuple[int, float]] = {}
        for entry in food.get("foodNutrients", []):
            mapped = FDC_TO_KEY.get(entry.get("nutrient", {}).get("id"))
            amount = entry.get("amount")
            if not mapped or amount is None:
                continue
            key, priority = mapped
            if key not in found or priority < found[key][0]:
                found[key] = (priority, float(amount))

        portions = []
        for portion in sorted(food.get("foodPortions", []), key=lambda p: p.get("sequenceNumber", 0)):
            amount, grams = float(portion.get("amount") or 1), float(portion.get("gramWeight") or 0)
            unit = (portion.get("measureUnit") or {}).get("name", "")
            modifier = (portion.get("modifier") or "").strip()
            # Foundation Foods name the unit separately; fold it into the same text form as SR Legacy
            text = modifier if unit in ("", "undetermined") else ", ".join(t for t in (unit, modifier) if t)
            if amount > 0 and grams > 0 and text:
                portions.append([amount, text, _round(grams)])

        records.append(
            {
                "id": int(food["fdcId"]),
                "src": "foundation",
                "name": food["description"],
                "cat": (food.get("foodCategory") or {}).get("description", ""),
                "n": _pick(found),
                "p": portions,
            }
        )
    return records


TANDOOR_PROPERTIES = {
    "property-calories": "energy_kcal",
    "property-proteins": "protein_g",
    "property-fats": "fat_g",
    "property-carbohydrates": "carbohydrate_g",
}


def read_tandoor(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    conversions: dict[str, list] = defaultdict(list)
    for conversion in data["conversion"].values() if isinstance(data["conversion"], dict) else data["conversion"]:
        conversions[conversion["food"]].append(
            [
                conversion["base_amount"],
                conversion["base_unit"].removeprefix("unit-"),
                conversion["converted_amount"],
                conversion["converted_unit"].removeprefix("unit-"),
            ]
        )

    curated = []
    for slug, food in data["food"].items():
        properties = food.get("properties") or {}
        per_100g: dict[str, float] = {}
        if properties.get("food_unit") == "unit-g" and properties.get("food_amount"):
            scale = 100 / properties["food_amount"]
            for value in properties.get("type_values", []):
                key = TANDOOR_PROPERTIES.get(value["property_type"])
                if key and value.get("property_value") is not None:
                    per_100g[key] = _round(value["property_value"] * scale)
        curated.append(
            {
                "slug": slug.removeprefix("food-"),
                "name": food["name"],
                "plural_name": food.get("plural_name") or "",
                "fdc_id": food.get("fdc_id"),
                "n": per_100g,
                "conversions": conversions.get(slug, []),
            }
        )
    return curated


def main() -> None:
    raw_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dev" / "data" / "nutrition_raw"
    foods = read_sr_legacy(raw_dir / SR_ZIP) + read_foundation(raw_dir / FF_ZIP)
    # A record without an energy value would count as 0 kcal wherever it is linked. `_pick` already
    # derives energy from the macros when it can, so what is left here has nothing to go on.
    foods = [f for f in foods if "energy_kcal" in f["n"]]
    curated = read_tandoor(raw_dir / TANDOOR)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    foods_path = OUT_DIR / "usda_foods.json.gz"
    with gzip.open(foods_path, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(foods, f, separators=(",", ":"), ensure_ascii=False)
    curated_path = OUT_DIR / "curated_foods.json"
    curated_path.write_text(json.dumps(curated, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")

    known = {f["id"] for f in foods}
    console.print(f"{len(foods)} foods -> {foods_path.name} ({foods_path.stat().st_size / 1e6:.2f} MB)")
    console.print(
        f"{len(curated)} curated foods -> {curated_path.name} ({curated_path.stat().st_size / 1e3:.0f} KB), "
        f"{sum(1 for c in curated if c['fdc_id'] in known)} with an id present in the USDA files"
    )


if __name__ == "__main__":
    main()
