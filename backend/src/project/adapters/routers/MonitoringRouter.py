from typing import Optional

from fastapi import APIRouter, Query

from project.ports.routers.Router import Router


class MonitoringRouter(Router):
    """Read surface over the monitoring tables.

    Responses are the `Candidate` dataclasses as-is, so field names are
    snake_case rather than the camelCase the chat DTOs use.
    """

    def __init__(self, candidate_query):
        self.candidate_query = candidate_query

    def create(self):
        router = APIRouter(prefix="/v1/monitoring", tags=["monitoring"])

        @router.get("/candidates")
        def list_candidates(
            limit: int = Query(50, ge=1, le=500),
            signal_type: Optional[str] = None,
            source: Optional[str] = None,
        ):
            return self.candidate_query.pending(
                limit=limit, signal_type=signal_type, source=source
            )

        @router.get("/summary")
        def signal_summary():
            return self.candidate_query.summary()

        return router
