import { BaseCRUDAPI } from "../base/base-clients";
import type { FoodNutritionLinkUpdate, IngredientFoodCreate, IngredientFoodOut, NutritionRecordSummary } from "~/lib/api/types/recipe";

const prefix = "/api";

const routes = {
  food: `${prefix}/foods`,
  foodsFood: (tag: string) => `${prefix}/foods/${tag}`,
  foodsEmpty: `${prefix}/foods/empty`,
  merge: `${prefix}/foods/merge`,
  nutritionSearch: `${prefix}/foods/nutrition/search`,
  foodsFoodNutritionLink: (id: string) => `${prefix}/foods/${id}/nutrition-link`,
};

export class FoodAPI extends BaseCRUDAPI<IngredientFoodCreate, IngredientFoodOut> {
  baseRoute: string = routes.food;
  itemRoute = routes.foodsFood;

  async getEmpty() {
    return await this.requests.get<IngredientFoodOut[]>(routes.foodsEmpty);
  }

  merge(fromId: string, toId: string) {
    return this.requests.put<IngredientFoodOut>(routes.merge, { fromFood: fromId, toFood: toId });
  }

  async searchNutrition(query: string, limit = 20) {
    return await this.requests.get<NutritionRecordSummary[]>(
      `${routes.nutritionSearch}?q=${encodeURIComponent(query)}&limit=${limit}`,
    );
  }

  /** Pass null to go back to automatic matching */
  async setNutritionLink(foodId: string, recordId: string | null) {
    return await this.requests.put<IngredientFoodOut, FoodNutritionLinkUpdate>(
      routes.foodsFoodNutritionLink(foodId),
      { recordId },
    );
  }
}
