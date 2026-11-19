"""Run the nutrition prototype against the dev database and write a review report.

Usage: python dev/scripts/nutrition_report.py [path/to/mealie.db]
Reads only. Writes dev/data/nutrition_report/{links,ingredients,recipes}.tsv
"""

import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rich.console import Console

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mealie.services.nutrition.calculator import IngredientInput, UnitInfo, recipe_nutrition  # noqa: E402
from mealie.services.nutrition.matching import FoodMatcher  # noqa: E402

console = Console(highlight=False)
OUT = ROOT / "dev" / "data" / "nutrition_report"


def number(text: str | None) -> float | None:
    try:
        return float(text) if text not in (None, "") else None
    except ValueError:
        return None


def main() -> None:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dev" / "data" / "mealie.db"
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    OUT.mkdir(parents=True, exist_ok=True)

    aliases: dict[str, list[str]] = defaultdict(list)
    for row in db.execute("select food_id, name from ingredient_foods_aliases"):
        aliases[row["food_id"]].append(row["name"])

    rows = db.execute(
        """select i.recipe_id, i.quantity, i.note, i.original_text, i.food_id, i.referenced_recipe_id,
                  f.name food, f.plural_name food_plural, u.name unit, u.standard_quantity sq, u.standard_unit su
           from recipes_ingredients i
           left join ingredient_foods f on f.id = i.food_id
           left join ingredient_units u on u.id = i.unit_id
           order by i.recipe_id, i.position"""
    ).fetchall()

    matcher = FoodMatcher()
    usage = Counter(row["food_id"] for row in rows if row["food_id"])
    links = {}
    food_names = {}
    for row in rows:
        if row["food_id"] and row["food_id"] not in links:
            others = tuple(n for n in [row["food_plural"], *aliases[row["food_id"]]] if n)
            links[row["food_id"]] = matcher.link(row["food"], others)
            food_names[row["food_id"]] = row["food"]

    with (OUT / "links.tsv").open("w", newline="", encoding="utf-8") as f:
        out = csv.writer(f, delimiter="\t")
        out.writerow(["lines", "food", "method", "assumed", "linked_to", "source", "nutrients", "next_best"])
        for food_id, n in usage.most_common():
            link = links[food_id]
            out.writerow(
                [
                    n,
                    food_names[food_id],
                    link.method,
                    "assumed" if link.assumed_default else "",
                    link.record.name if link.record else "",
                    link.record.source if link.record else "",
                    len(link.record.nutrients) if link.record else 0,
                    " | ".join(h.record.name for h in link.suggestions[1:3]),
                ]
            )

    by_recipe: dict[str, list] = defaultdict(list)
    for row in rows:
        if row["referenced_recipe_id"]:
            continue
        unit = UnitInfo(row["unit"], row["sq"], row["su"]) if row["unit"] else None
        context = " ".join(t for t in (row["note"], row["original_text"]) if t)
        ingredient = IngredientInput(row["quantity"], unit, row["food"], context)
        by_recipe[row["recipe_id"]].append((ingredient, links.get(row["food_id"]), row))

    status_lines: Counter = Counter()
    method_lines: Counter = Counter()
    unresolved: Counter = Counter()
    recipes = db.execute(
        """select r.id, r.name, r.recipe_servings, r.org_url, n.calories, n.protein_content, n.fat_content,
                  n.carbohydrate_content, n.sodium_content
           from recipes r left join recipe_nutrition n on n.recipe_id = r.id order by r.name"""
    ).fetchall()

    with (
        (OUT / "ingredients.tsv").open("w", newline="", encoding="utf-8") as fi,
        (OUT / "recipes.tsv").open("w", newline="", encoding="utf-8") as fr,
    ):
        ing_out = csv.writer(fi, delimiter="\t")
        ing_out.writerow(["recipe", "line", "status", "grams", "kcal", "method", "basis", "linked_to"])
        rec_out = csv.writer(fr, delimiter="\t")
        rec_out.writerow(
            ["recipe", "servings", "counted", "countable", "calc_kcal", "site_kcal", "ratio", "calc_protein",
             "site_protein", "calc_fat", "site_fat", "calc_carb", "site_carb", "calc_sodium", "site_sodium"]
        )  # fmt: skip
        for recipe in recipes:
            items = by_recipe.get(recipe["id"], [])
            result = recipe_nutrition([(i, link) for i, link, _ in items], recipe["recipe_servings"])
            for (ingredient, link, row), res in zip(items, result.results, strict=True):
                status_lines[res.status] += 1
                if res.status == "ok":
                    method_lines[res.method] += 1
                elif res.status not in ("no_food", "no_quantity"):
                    unresolved[(res.status, ingredient.food_name, ingredient.unit.name if ingredient.unit else "")] += 1
                ing_out.writerow(
                    [
                        recipe["name"],
                        (row["original_text"] or row["note"] or ingredient.food_name or "")[:70],
                        res.status,
                        f"{res.grams:.0f}" if res.grams else "",
                        f"{res.nutrients.get('energy_kcal', 0):.0f}" if res.nutrients else "",
                        res.method,
                        res.basis,
                        link.record.name if link and link.record else "",
                    ]
                )
            per = result.per_serving or {}
            site = number(recipe["calories"])
            calc = per.get("energy_kcal")

            def cell(value: float | None) -> str:
                return f"{value:.0f}" if value is not None else ""

            rec_out.writerow(
                [
                    recipe["name"], recipe["recipe_servings"] or "", result.counted, result.countable,
                    cell(calc), cell(site), f"{calc / site:.2f}" if calc and site else "",
                    cell(per.get("protein_g")), cell(number(recipe["protein_content"])),
                    cell(per.get("fat_g")), cell(number(recipe["fat_content"])),
                    cell(per.get("carbohydrate_g")), cell(number(recipe["carbohydrate_content"])),
                    cell(per.get("sodium_mg")), cell(number(recipe["sodium_content"])),
                ]
            )  # fmt: skip

    total = sum(status_lines.values())
    console.print(f"foods used: {len(links)}")
    by_method = Counter(
        ("needs review: " if link.needs_review else "auto: ")
        + link.method
        + (" (assumed)" if link.assumed_default else "")
        for link in links.values()
    )
    for key, n in sorted(by_method.items()):
        console.print(f"  {n:4}  {key}")
    console.print(f"\ningredient lines: {total}")
    for status, n in status_lines.most_common():
        console.print(f"  {n:4}  {100 * n / total:3.0f}%  {status}")
    console.print("  resolved by:", dict(method_lines))
    console.print("\nmost common unresolved (status, food, unit):")
    for key, n in unresolved.most_common(25):
        console.print(f"  {n:3}  {key}")


if __name__ == "__main__":
    main()
