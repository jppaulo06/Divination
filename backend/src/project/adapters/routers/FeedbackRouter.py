from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from project.adapters.routers.dto.feedback_dto import (
    FeedbackRequest,
    FeedbackResponse,
)
from project.ports.routers.Router import Router


class FeedbackRouter(Router):
    """Explicit user ratings on a specific answer."""

    def __init__(self, interaction_sink):
        self.interaction_sink = interaction_sink

    def create(self):
        router = APIRouter()

        @router.post("/v1/feedback")
        def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
            try:
                feedback_id = self.interaction_sink.record_feedback(
                    interaction_id=request.interaction_id,
                    rating=request.rating,
                    comment=request.comment,
                )
            except LookupError:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"unknown interaction {request.interaction_id!r}"
                    ),
                )
            except RuntimeError as failure:
                raise HTTPException(status_code=503, detail=str(failure))
            except SQLAlchemyError:
                raise HTTPException(
                    status_code=503,
                    detail="monitoring database is unavailable",
                )

            return FeedbackResponse.create(feedback_id)

        return router
