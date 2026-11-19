<template>
  <div>
    <v-btn
      class="mt-2"
      variant="tonal"
      block
      :prepend-icon="$globals.icons.foods"
      @click="open"
    >
      {{ $t("recipe.calculated-nutrition.open") }}
    </v-btn>

    <BaseDialog
      v-model="dialog"
      :icon="$globals.icons.foods"
      :title="$t('recipe.calculated-nutrition.title')"
      width="96%"
      max-width="1400px"
    >
      <v-card-text v-if="loading" class="text-center py-10">
        <v-progress-circular indeterminate />
      </v-card-text>

      <v-card-text v-else-if="data">
        <div class="d-flex flex-wrap align-center ga-3 mb-3">
          <v-chip
            :color="data.countedLines === data.countableLines ? 'success' : 'warning'"
            variant="tonal"
            label
          >
            {{ $t("recipe.calculated-nutrition.lines-counted", { counted: data.countedLines, countable: data.countableLines }) }}
          </v-chip>
          <span v-if="data.servings" class="text-medium-emphasis">
            {{ $t("recipe.calculated-nutrition.servings", { servings: data.servings }) }}
          </span>
          <span v-else class="text-warning">
            {{ $t("recipe.calculated-nutrition.no-servings") }}
          </span>
        </div>
        <p class="text-medium-emphasis text-body-2 mb-4">
          {{ $t("recipe.calculated-nutrition.description") }}
        </p>

        <!-- Health scores -->
        <v-row v-if="data.nutriScore || data.nrf" class="mb-4">
          <v-col
            v-if="data.nutriScore"
            cols="12"
            md="6"
          >
            <v-card variant="outlined" class="h-100">
              <div class="d-flex align-center ga-3 pa-4">
                <v-chip
                  :color="gradeColor(data.nutriScore.grade)"
                  variant="flat"
                  label
                  size="large"
                  class="font-weight-bold"
                >
                  {{ data.nutriScore.grade }}
                </v-chip>
                <div>
                  <div class="text-subtitle-1 font-weight-medium">
                    {{ $t("recipe.calculated-nutrition.scores.nutri-score") }}
                  </div>
                  <div class="text-body-2 text-medium-emphasis">
                    {{ $t("recipe.calculated-nutrition.scores.nutri-score-points", {
                      score: data.nutriScore.score,
                      negative: data.nutriScore.negative,
                      positive: data.nutriScore.positive,
                    }) }}
                  </div>
                </div>
              </div>
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>{{ $t("recipe.calculated-nutrition.scores.per-100-g") }}</th>
                    <th class="text-right">
                      {{ $t("recipe.calculated-nutrition.scores.amount") }}
                    </th>
                    <th class="text-right">
                      {{ $t("recipe.calculated-nutrition.scores.points") }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="component in data.nutriScore.components"
                    :key="component.key"
                    :class="{ 'text-medium-emphasis': !component.counted }"
                  >
                    <td>
                      {{ $t(`recipe.calculated-nutrition.scores.components.${component.key}`) }}
                      <span v-if="!component.counted" class="text-caption">
                        ({{ $t("recipe.calculated-nutrition.scores.not-counted") }})
                      </span>
                    </td>
                    <td class="text-right text-no-wrap">
                      {{ formatScoreValue(component.value) }} {{ component.unit }}
                    </td>
                    <td
                      class="text-right text-no-wrap font-weight-medium"
                      :class="component.kind === 'negative' ? 'text-error' : 'text-success'"
                    >
                      {{ component.kind === "negative" ? "+" : "−" }}{{ component.points }}
                      <span class="text-caption text-medium-emphasis">/ {{ component.maxPoints }}</span>
                    </td>
                  </tr>
                </tbody>
              </v-table>
              <v-card-text class="text-caption text-medium-emphasis">
                {{ $t("recipe.calculated-nutrition.scores.nutri-score-note", { weight: format(data.nutriScore.weight, "grams") }) }}
              </v-card-text>
            </v-card>
          </v-col>

          <v-col
            v-if="data.nrf"
            cols="12"
            md="6"
          >
            <v-card variant="outlined" class="h-100">
              <div class="d-flex align-center ga-3 pa-4">
                <v-chip
                  color="primary"
                  variant="flat"
                  label
                  size="large"
                  class="font-weight-bold"
                >
                  {{ Math.round(data.nrf.score) }}
                </v-chip>
                <div>
                  <div class="text-subtitle-1 font-weight-medium">
                    {{ $t("recipe.calculated-nutrition.scores.nrf") }}
                  </div>
                  <div class="text-body-2 text-medium-emphasis">
                    {{ $t("recipe.calculated-nutrition.scores.nrf-points", {
                      encourage: Math.round(data.nrf.encourage),
                      limit: Math.round(data.nrf.limit),
                    }) }}
                  </div>
                </div>
              </div>
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>{{ $t("recipe.calculated-nutrition.scores.per-100-kcal") }}</th>
                    <th class="text-right">
                      {{ $t("recipe.calculated-nutrition.scores.amount") }}
                    </th>
                    <th class="text-right">
                      {{ $t("recipe.calculated-nutrition.scores.daily-value") }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="component in data.nrf.components"
                    :key="component.key"
                  >
                    <td>
                      {{ nutrientLabel(component.key) }}
                      <span v-if="component.missingLines" class="text-caption text-warning">
                        ({{ $t("recipe.calculated-nutrition.scores.missing-lines", { count: component.missingLines }) }})
                      </span>
                    </td>
                    <td class="text-right text-no-wrap">
                      {{ formatScoreValue(component.amount) }} {{ unitOf(component.key) }}
                    </td>
                    <td
                      class="text-right text-no-wrap font-weight-medium"
                      :class="component.kind === 'limit' ? 'text-error' : 'text-success'"
                    >
                      {{ component.kind === "limit" ? "−" : "+" }}{{ Math.round(component.percent) }}%
                    </td>
                  </tr>
                </tbody>
              </v-table>
              <v-card-text class="text-caption text-medium-emphasis">
                {{ $t("recipe.calculated-nutrition.scores.nrf-note") }}
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- Calculated vs saved -->
        <div v-if="comparison.length" class="text-h6 mb-2">
          {{ $t("recipe.calculated-nutrition.compared-with-saved") }}
        </div>
        <v-table
          v-if="comparison.length"
          density="compact"
          class="mb-6 comparison-table"
        >
          <thead>
            <tr>
              <th>{{ $t("recipe.per-serving") }}</th>
              <th
                v-for="row in comparison"
                :key="row.key"
                class="text-right"
              >
                {{ nutrientLabel(row.key) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{{ $t("recipe.calculated-nutrition.calculated") }}</td>
              <td
                v-for="row in comparison"
                :key="row.key"
                class="text-right"
              >
                {{ format(row.calculated, row.key) }}
              </td>
            </tr>
            <tr>
              <td>{{ $t("recipe.calculated-nutrition.saved") }}</td>
              <td
                v-for="row in comparison"
                :key="row.key"
                class="text-right"
              >
                {{ format(row.stored, row.key) }}
              </td>
            </tr>
            <tr>
              <td>{{ $t("recipe.calculated-nutrition.difference") }}</td>
              <td
                v-for="row in comparison"
                :key="row.key"
                class="text-right font-weight-medium"
                :class="differenceClass(row.ratio)"
              >
                {{ formatDifference(row.ratio) }}
              </td>
            </tr>
          </tbody>
        </v-table>

        <!-- One row per ingredient -->
        <div class="d-flex flex-wrap align-center ga-3 mb-2">
          <div class="text-h6">
            {{ $t("recipe.ingredients") }}
          </div>
          <v-spacer />
          <span class="text-body-2 text-medium-emphasis">{{ $t("recipe.calculated-nutrition.show-amounts") }}</span>
          <v-btn-toggle
            v-model="mode"
            mandatory
            density="compact"
            variant="outlined"
            color="primary"
            divided
          >
            <v-btn value="serving" :disabled="!data.servings">
              {{ $t("recipe.calculated-nutrition.per-serving") }}
            </v-btn>
            <v-btn value="recipe">
              {{ $t("recipe.calculated-nutrition.whole-recipe") }}
            </v-btn>
          </v-btn-toggle>
        </div>
        <v-table density="compact" class="ingredient-table">
          <thead>
            <tr>
              <th>{{ $t("recipe.ingredient") }}</th>
              <th>{{ $t("recipe.calculated-nutrition.linked-to") }}</th>
              <th class="text-right">
                {{ $t("recipe.calculated-nutrition.weight") }}
              </th>
              <th
                v-for="key in mainKeys"
                :key="key"
                class="text-right"
              >
                {{ nutrientLabel(key) }}
              </th>
              <th>{{ $t("recipe.calculated-nutrition.status") }}</th>
            </tr>
          </thead>
          <tbody>
            <template
              v-for="(line, index) in data.ingredients"
              :key="index"
            >
              <tr
                :class="rowClass(line)"
                style="cursor: pointer"
                @click="toggle(index)"
              >
                <td class="ingredient-cell">
                  {{ line.display || line.foodName }}
                </td>
                <td>
                  <template v-if="line.match">
                    <div>{{ line.match.name }}</div>
                    <div class="text-caption text-medium-emphasis">
                      {{ $t(`recipe.calculated-nutrition.match-method.${line.matchMethod}`) }}
                      <span v-if="line.matchAssumed"> · {{ $t("recipe.calculated-nutrition.assumed") }}</span>
                      · {{ line.match.source }}
                    </div>
                  </template>
                  <span v-else class="text-medium-emphasis">
                    {{ $t("recipe.calculated-nutrition.not-linked") }}
                  </span>
                </td>
                <td class="text-right text-no-wrap">
                  <template v-if="line.grams !== null && line.grams !== undefined">
                    <div>{{ format(line.grams * scale, "grams") }} g</div>
                    <div class="text-caption text-medium-emphasis">
                      {{ line.basis }}
                    </div>
                  </template>
                </td>
                <td
                  v-for="key in mainKeys"
                  :key="key"
                  class="text-right"
                  :class="{ 'text-medium-emphasis': !line.counted }"
                >
                  {{ line.nutrients[key] !== undefined ? format(line.nutrients[key]! * scale, key) : "" }}
                </td>
                <td>
                  <v-chip
                    size="small"
                    label
                    variant="tonal"
                    :color="statusColor(line.status)"
                  >
                    {{ $t(`recipe.calculated-nutrition.status-label.${line.status}`) }}
                  </v-chip>
                </td>
              </tr>
              <tr v-if="expanded.has(index)" class="detail-row">
                <td :colspan="4 + mainKeys.length">
                  <div v-if="line.alternatives.length" class="mb-2 d-flex flex-wrap align-center ga-2">
                    <span class="font-weight-medium">{{ $t("recipe.calculated-nutrition.other-candidates") }}:</span>
                    <template v-if="canEdit && line.foodId">
                      <v-chip
                        v-for="alternative in line.alternatives"
                        :key="alternative.id"
                        size="small"
                        variant="outlined"
                        :disabled="saving"
                        @click.stop="setLink(line.foodId, alternative.id)"
                      >
                        {{ alternative.name }}
                      </v-chip>
                    </template>
                    <span v-else>{{ line.alternatives.map(a => a.name).join(" · ") }}</span>
                  </div>
                  <div v-if="canEdit && line.foodId" class="mb-2 d-flex flex-wrap align-center ga-2">
                    <v-btn
                      size="small"
                      variant="tonal"
                      color="primary"
                      :disabled="saving"
                      @click.stop="openPicker(line)"
                    >
                      {{ $t("recipe.calculated-nutrition.picker.choose") }}
                    </v-btn>
                    <v-btn
                      v-if="line.matchMethod === 'manual'"
                      size="small"
                      variant="text"
                      :disabled="saving"
                      @click.stop="setLink(line.foodId, null)"
                    >
                      {{ $t("recipe.calculated-nutrition.picker.reset") }}
                    </v-btn>
                    <span class="text-caption text-medium-emphasis">
                      {{ $t("recipe.calculated-nutrition.picker.applies-to", { food: line.foodName }) }}
                    </span>
                  </div>
                  <div v-if="Object.keys(line.nutrients).length" class="nutrient-list">
                    <template
                      v-for="info in data.nutrients"
                      :key="info.key"
                    >
                      <span v-if="line.nutrients[info.key] !== undefined" class="text-caption">
                        {{ nutrientLabel(info.key) }}:
                        <strong>{{ format(line.nutrients[info.key]! * scale, info.key) }}</strong> {{ info.unit }}
                      </span>
                    </template>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
          <tfoot>
            <tr class="font-weight-bold">
              <td colspan="3">
                {{ $t("recipe.calculated-nutrition.total") }}
                ({{ mode === "serving" ? $t("recipe.calculated-nutrition.per-serving") : $t("recipe.calculated-nutrition.whole-recipe") }})
              </td>
              <td
                v-for="key in mainKeys"
                :key="key"
                class="text-right"
              >
                {{ format(totals[key], key) }}
              </td>
              <td />
            </tr>
          </tfoot>
        </v-table>

        <!-- Every nutrient -->
        <v-expansion-panels class="mt-4" variant="accordion">
          <v-expansion-panel :title="$t('recipe.calculated-nutrition.all-nutrients')">
            <v-expansion-panel-text>
              <div class="nutrient-list">
                <span
                  v-for="info in data.nutrients"
                  :key="info.key"
                  style="min-width: 220px"
                >
                  {{ nutrientLabel(info.key) }}:
                  <strong>{{ format(totals[info.key], info.key) }}</strong> {{ info.unit }}
                </span>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>
    </BaseDialog>

    <!-- Choose the database entry for one food -->
    <BaseDialog
      v-model="pickerOpen"
      :icon="$globals.icons.foods"
      :title="$t('recipe.calculated-nutrition.picker.title', { food: pickerFoodName })"
      width="96%"
      max-width="900px"
    >
      <v-card-text>
        <v-text-field
          v-model="pickerQuery"
          :label="$t('recipe.calculated-nutrition.picker.search')"
          :loading="pickerLoading"
          :hint="$t('recipe.calculated-nutrition.picker.hint')"
          persistent-hint
          autofocus
          clearable
          variant="outlined"
          density="comfortable"
        />
        <v-table density="compact" class="mt-3">
          <thead>
            <tr>
              <th>{{ $t("recipe.calculated-nutrition.picker.entry") }}</th>
              <th
                v-for="key in pickerKeys"
                :key="key"
                class="text-right"
              >
                {{ nutrientLabel(key) }}
              </th>
              <th>{{ $t("recipe.calculated-nutrition.picker.measures") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="result in pickerResults"
              :key="result.id"
              style="cursor: pointer"
              @click="choose(result.id)"
            >
              <td>
                <div>{{ result.name }}</div>
                <div class="text-caption text-medium-emphasis">
                  {{ result.category }} · {{ result.source }}
                </div>
              </td>
              <td class="text-right">
                {{ format(result.energyKcal, "energy_kcal") }}
              </td>
              <td class="text-right">
                {{ format(result.proteinG, "protein_g") }}
              </td>
              <td class="text-right">
                {{ format(result.fatG, "fat_g") }}
              </td>
              <td class="text-right">
                {{ format(result.carbohydrateG, "carbohydrate_g") }}
              </td>
              <td class="text-no-wrap">
                <v-chip
                  v-if="result.hasVolumeWeight"
                  size="x-small"
                  label
                  class="mr-1"
                >
                  {{ $t("recipe.calculated-nutrition.picker.volume") }}
                </v-chip>
                <v-chip
                  v-if="result.hasCountWeight"
                  size="x-small"
                  label
                >
                  {{ $t("recipe.calculated-nutrition.picker.count") }}
                </v-chip>
              </td>
            </tr>
            <tr v-if="!pickerResults.length && !pickerLoading">
              <td colspan="6" class="text-medium-emphasis text-center py-4">
                {{ $t("recipe.calculated-nutrition.picker.no-results") }}
              </td>
            </tr>
          </tbody>
        </v-table>
        <p class="text-caption text-medium-emphasis mt-3">
          {{ $t("recipe.calculated-nutrition.picker.per-100-g") }}
        </p>
      </v-card-text>
    </BaseDialog>
  </div>
</template>

<script setup lang="ts">
import { usePublicExploreApi, useUserApi } from "~/composables/api";
import { useDebounceFn } from "@vueuse/core";
import type { CalculatedIngredientOut, CalculatedNutritionOut, NutritionRecordSummary } from "~/lib/api/types/recipe";

const props = defineProps<{ slug: string }>();

const i18n = useI18n();
const route = useRoute();
const { isOwnGroup } = useLoggedInState();

const dialog = ref(false);
const loading = ref(false);
const data = ref<CalculatedNutritionOut | null>(null);
const mode = ref<"serving" | "recipe">("serving");
const expanded = ref(new Set<number>());

const mainKeys = ["energy_kcal", "protein_g", "fat_g", "carbohydrate_g", "sodium_mg"];

// Choosing a food's database entry changes the food, so it needs a signed-in member of the group
const canEdit = computed(() => isOwnGroup.value);
const saving = ref(false);

async function load() {
  // a visitor on a public recipe page has no session, so read it through the explore API
  const { data: response } = isOwnGroup.value
    ? await useUserApi().recipes.getCalculatedNutrition(props.slug)
    : await usePublicExploreApi(route.params.groupSlug as string).explore.recipes.getCalculatedNutrition(props.slug);
  data.value = response ?? null;
  if (data.value && !data.value.servings) {
    mode.value = "recipe";
  }
}

async function open() {
  dialog.value = true;
  loading.value = true;
  expanded.value = new Set();
  await load();
  loading.value = false;
}

async function setLink(foodId: string | null | undefined, recordId: string | null) {
  if (!foodId) {
    return;
  }
  saving.value = true;
  await useUserApi().foods.setNutritionLink(foodId, recordId);
  // rows keep their order, so the expanded ones stay open on the refreshed numbers
  await load();
  saving.value = false;
}

const pickerOpen = ref(false);
const pickerFoodId = ref<string | null>(null);
const pickerFoodName = ref("");
const pickerQuery = ref("");
const pickerResults = ref<NutritionRecordSummary[]>([]);
const pickerLoading = ref(false);
const pickerKeys = ["energy_kcal", "protein_g", "fat_g", "carbohydrate_g"];

function openPicker(line: CalculatedIngredientOut) {
  pickerFoodId.value = line.foodId ?? null;
  pickerFoodName.value = line.foodName ?? "";
  pickerResults.value = [];
  pickerQuery.value = line.foodName ?? "";
  pickerOpen.value = true;
}

const searchRecords = useDebounceFn(async (query: string) => {
  if (!query || query.trim().length < 2) {
    pickerResults.value = [];
    return;
  }
  pickerLoading.value = true;
  const { data: results } = await useUserApi().foods.searchNutrition(query.trim());
  // ignore a response that arrives after the text has moved on
  if (query === pickerQuery.value) {
    pickerResults.value = results ?? [];
  }
  pickerLoading.value = false;
}, 250);

watch(pickerQuery, query => searchRecords(query ?? ""));

async function choose(recordId: string) {
  pickerOpen.value = false;
  await setLink(pickerFoodId.value, recordId);
}

function toggle(index: number) {
  const next = new Set(expanded.value);
  if (next.has(index)) {
    next.delete(index);
  }
  else {
    next.add(index);
  }
  expanded.value = next;
}

const scale = computed(() => {
  const servings = data.value?.servings;
  return mode.value === "serving" && servings ? 1 / servings : 1;
});

const totals = computed<Record<string, number | undefined>>(() => {
  if (!data.value) {
    return {};
  }
  return (mode.value === "serving" ? data.value.perServing : data.value.total) ?? {};
});

// Only per-serving values are saved on a recipe, so the comparison is always per serving
const comparison = computed(() => {
  const perServing = data.value?.perServing;
  const stored = data.value?.storedPerServing ?? {};
  if (!perServing) {
    return [];
  }
  return Object.keys(stored)
    .filter(key => perServing[key] !== undefined)
    .map((key) => {
      const calculated = perServing[key]!;
      const saved = stored[key]!;
      return { key, calculated, stored: saved, ratio: saved > 0 ? calculated / saved : null };
    });
});

function nutrientLabel(key: string) {
  return i18n.t(`recipe.calculated-nutrition.nutrients.${key}`);
}

function format(value: number | undefined | null, key: string) {
  if (value === undefined || value === null) {
    return "";
  }
  // calories, milligrams and micrograms read better whole; small gram amounts need a decimal
  const whole = key === "energy_kcal" || key.endsWith("_mg") || key.endsWith("_ug") || Math.abs(value) >= 10;
  return value.toLocaleString(undefined, { maximumFractionDigits: whole ? 0 : 1 });
}

function formatScoreValue(value: number) {
  return value.toLocaleString(undefined, { maximumFractionDigits: Math.abs(value) >= 100 ? 0 : 1 });
}

function unitOf(key: string) {
  return data.value?.nutrients.find(info => info.key === key)?.unit ?? "";
}

function gradeColor(grade: string) {
  const colors: Record<string, string> = { A: "success", B: "light-green", C: "amber", D: "orange", E: "error" };
  return colors[grade] ?? undefined;
}

function formatDifference(ratio: number | null) {
  if (ratio === null) {
    return "";
  }
  const percent = Math.round((ratio - 1) * 100);
  return `${percent > 0 ? "+" : ""}${percent}%`;
}

function differenceClass(ratio: number | null) {
  if (ratio === null) {
    return "";
  }
  const off = Math.abs(ratio - 1);
  return off <= 0.15 ? "text-success" : off <= 0.3 ? "text-warning" : "text-error";
}

function statusColor(status: string) {
  if (status === "ok") {
    return "success";
  }
  if (status === "weak_match") {
    return "warning";
  }
  return status === "no_quantity" || status === "no_food" ? undefined : "error";
}

function rowClass(line: CalculatedIngredientOut) {
  if (line.status === "ok") {
    return "";
  }
  if (line.status === "weak_match") {
    return "row-warning";
  }
  return line.status === "no_quantity" || line.status === "no_food" ? "row-muted" : "row-error";
}
</script>

<style lang="scss" scoped>
.ingredient-cell {
  max-width: 320px;
}

.nutrient-list {
  display: flex;
  flex-wrap: wrap;
  column-gap: 20px;
  row-gap: 4px;
}

.row-warning {
  background-color: rgba(var(--v-theme-warning), 0.08);
}

.row-error {
  background-color: rgba(var(--v-theme-error), 0.08);
}

.row-muted {
  opacity: 0.7;
}

.detail-row td {
  padding-top: 8px !important;
  padding-bottom: 8px !important;
  background-color: rgba(var(--v-theme-on-surface), 0.03);
}
</style>
