from project.adapters.routers.route_exchange import RouteExchange


class ReviewRequest(RouteExchange):
    interaction_id: str
    #: "defect" (a real problem) or "noise" (working as intended).
    verdict: str
    rationale: str | None = None
    reviewer: str = "human"


class ReviewResponse(RouteExchange):
    review_id: int

    @classmethod
    def create(cls, review_id: int):
        return ReviewResponse(review_id=review_id)
