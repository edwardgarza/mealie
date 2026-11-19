from functools import cached_property

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.routes._base.mixins import HttpRepo
from mealie.routes._base.permissions import Perm, require
from mealie.routes._base.routers import MealieCrudRoute
from mealie.schema import mapper
from mealie.schema.recipe.recipe_ingredient import (
    IngredientFoodCreate,
    IngredientFoodMerge,
    IngredientFoodOut,
    IngredientFoodPagination,
    IngredientFoodSave,
)
from mealie.schema.recipe.recipe_nutrition_calculated import FoodNutritionLinkUpdate, NutritionRecordSummary
from mealie.schema.response.pagination import PaginationQuery
from mealie.schema.response.responses import SuccessResponse
from mealie.services.nutrition.nutrition_service import (
    NUTRITION_SOURCE_USDA,
    nutrition_record_exists,
    search_nutrition_records,
)

router = APIRouter(prefix="/foods", tags=["Recipes: Foods"], route_class=MealieCrudRoute)


@controller(router)
class IngredientFoodsController(BaseUserController):
    @cached_property
    def repo(self):
        return self.repos.ingredient_foods

    @cached_property
    def mixins(self):
        return HttpRepo[IngredientFoodSave, IngredientFoodOut, IngredientFoodCreate](
            self.repo,
            self.logger,
            self.registered_exceptions,
        )

    @router.get("", response_model=IngredientFoodPagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery), search: str | None = None):
        response = self.repo.page_all(
            pagination=q,
            override=IngredientFoodOut,
            search=search,
        )

        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=IngredientFoodOut, status_code=201, dependencies=[require(Perm.GROUP_ORGANIZE)])
    def create_one(self, data: IngredientFoodCreate):
        save_data = mapper.cast(data, IngredientFoodSave, group_id=self.group_id)
        return self.mixins.create_one(save_data)

    @router.get("/empty", response_model=list[IngredientFoodOut])
    def get_all_empty(self):
        """Returns a list of foods that are not used by any recipe"""
        return self.repo.get_empty()

    @router.get("/nutrition/search", response_model=list[NutritionRecordSummary])
    def search_nutrition(self, q: str, limit: int = 20):
        """Search the bundled food database for an entry to take a food's nutrition from"""
        return search_nutrition_records(q, max(1, min(limit, 50)))

    @router.put(
        "/{item_id}/nutrition-link", response_model=IngredientFoodOut, dependencies=[require(Perm.GROUP_ORGANIZE)]
    )
    def set_nutrition_link(self, item_id: UUID4, data: FoodNutritionLinkUpdate):
        """Choose the food database entry a food's nutrition comes from, or clear the choice"""
        if data.record_id is not None and not nutrition_record_exists(data.record_id):
            raise HTTPException(404, "nutrition record not found")

        source = NUTRITION_SOURCE_USDA if data.record_id is not None else None
        food = self.repo.set_nutrition_link(item_id, source, data.record_id)
        if food is None:
            raise HTTPException(404, "food not found")
        return food

    @router.put("/merge", response_model=SuccessResponse, dependencies=[require(Perm.GROUP_ORGANIZE)])
    def merge_one(self, data: IngredientFoodMerge):
        try:
            self.repo.merge(data.from_food, data.to_food)
            return SuccessResponse.respond("Successfully merged foods")
        except Exception as e:
            self.logger.error(e)
            raise HTTPException(500, "Failed to merge foods") from e

    @router.get("/{item_id}", response_model=IngredientFoodOut)
    def get_one(self, item_id: UUID4):
        return self.mixins.get_one(item_id)

    @router.put("/{item_id}", response_model=IngredientFoodOut, dependencies=[require(Perm.GROUP_ORGANIZE)])
    def update_one(self, item_id: UUID4, data: IngredientFoodCreate):
        data = mapper.cast(data, IngredientFoodSave, group_id=self.group_id)
        return self.mixins.update_one(data, item_id)

    @router.delete("/{item_id}", response_model=IngredientFoodOut, dependencies=[require(Perm.GROUP_ORGANIZE)])
    def delete_one(self, item_id: UUID4):
        return self.mixins.delete_one(item_id)
