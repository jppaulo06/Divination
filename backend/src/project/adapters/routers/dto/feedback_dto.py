from project.adapters.routers.route_exchange import RouteExchange


class FeedbackRequest(RouteExchange):
    interaction_id: str
    #: -1 for thumbs down, +1 for thumbs up.
    rating: int
    comment: str | None = None


class FeedbackResponse(RouteExchange):
    feedback_id: int

    @classmethod
    def create(cls, feedback_id: int):
        return FeedbackResponse(feedback_id=feedback_id)
