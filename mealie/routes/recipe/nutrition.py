from fastapi import HTTPException, status

from mealie.routes._base import BaseUserController, controller
from mealie.routes._base.routers import UserAPIRouter
from mealie.schema.recipe.recipe_nutrition_calculated import CalculatedNutritionOut
from mealie.services.nutrition.nutrition_service import calculate_recipe_nutrition

router = UserAPIRouter()


@controller(router)
class RecipeNutritionController(BaseUserController):
    @router.get("/{slug}/nutrition/calculated", response_model=CalculatedNutritionOut)
    def get_calculated_nutrition(self, slug: str):
        """Estimate nutrition from the recipe's ingredients, broken out per ingredient"""
        recipe = self.repos.recipes.get_one(slug)
        if recipe is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        return calculate_recipe_nutrition(recipe)
