from project.adapters.routers.route_exchange import RouteExchange


class CreateChatResponse(RouteExchange):
    chat_id: str

    @classmethod
    def create(self, new_chat_id: str):
        return CreateChatResponse(chat_id=new_chat_id)


class ShowChatResponse(RouteExchange):
    chat_history: list

    @classmethod
    def create(self, messages: list):
        return ShowChatResponse(chat_history=messages)


class ListChatsResponse(RouteExchange):
    project_history: dict

    @classmethod
    def create(self, chats):
        return ListChatsResponse(project_history=chats)
