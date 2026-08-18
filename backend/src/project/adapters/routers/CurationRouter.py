from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from project.adapters.monitoring.models import VERDICT_DEFECT, VERDICT_NOISE
from project.adapters.routers.dto.curation_dto import (
    ReviewRequest,
    ReviewResponse,
)
from project.ports.routers.Router import Router

VERDICTS = (VERDICT_DEFECT, VERDICT_NOISE)
_UNAVAILABLE = "monitoring database is unavailable"


class CurationRouter(Router):
    """Sampling and review — the human arm of curation."""

    def __init__(self, curation_store):
        self.curation_store = curation_store

    def create(self):
        router = APIRouter(prefix="/v1/curation", tags=["curation"])

        @router.get("/sample")
        def draw_sample(
            size: int = Query(20, ge=1, le=200),
            flagged_share: float = Query(0.5, ge=0.0, le=1.0),
        ):
            try:
                return self.curation_store.sample(
                    size=size, flagged_share=flagged_share
                )
            except SQLAlchemyError:
                raise HTTPException(status_code=503, detail=_UNAVAILABLE)

        @router.post("/reviews")
        def record_review(request: ReviewRequest) -> ReviewResponse:
            if request.verdict not in VERDICTS:
                raise HTTPException(
                    status_code=422,
                    detail=f"verdict must be one of {list(VERDICTS)}",
                )

            try:
                review_id = self.curation_store.record_review(
                    interaction_id=request.interaction_id,
                    verdict=request.verdict,
                    rationale=request.rationale,
                    reviewer=request.reviewer,
                )
            except LookupError:
                raise HTTPException(
                    status_code=404,
                    detail=f"unknown interaction {request.interaction_id!r}",
                )
            except SQLAlchemyError:
                raise HTTPException(status_code=503, detail=_UNAVAILABLE)

            return ReviewResponse.create(review_id)

        @router.get("/defects")
        def list_defects(limit: int = Query(100, ge=1, le=500)):
            def read():
                defects = self.curation_store.defects(limit=limit)
                return {
                    "summary": self.curation_store.defect_summary(defects),
                    "defects": defects,
                }

            try:
                return read()
            except SQLAlchemyError:
                raise HTTPException(status_code=503, detail=_UNAVAILABLE)

        @router.get("/stats")
        def review_stats():
            try:
                return self.curation_store.stats()
            except SQLAlchemyError:
                raise HTTPException(status_code=503, detail=_UNAVAILABLE)

        return router
