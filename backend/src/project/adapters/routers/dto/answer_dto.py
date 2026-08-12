from project.adapters.routers.route_exchange import RouteExchange


class AnswerRequest(RouteExchange):
    user_question: str
    chat_id: str


class AnswerResponse(RouteExchange):
    project_answer: str
    #: Sent back with POST /v1/feedback to rate this answer.
    interaction_id: str | None = None

    @classmethod
    def create_answer(self, answer: str, interaction_id: str | None = None):
        return AnswerResponse(
            project_answer=answer, interaction_id=interaction_id
        )


class ChangeTemplate(RouteExchange):
    new_template: str
