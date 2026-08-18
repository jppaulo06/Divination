from fastapi import APIRouter
from project.ports.routers.Router import Router
from project.ports.monitoring.InteractionLookup import NullInteractionLookup
from project.adapters.routers.dto.chat_dto import (
    CreateChatResponse,
    ShowChatResponse,
    ListChatsResponse,
)
from project.adapters.database.ChatRepository import ChatRepository
from project.adapters.routers.chat_history_view import serialise_history


class ChatRouter(Router):
    def __init__(
        self,
        chat_repository: ChatRepository,
        interaction_lookup=None,
    ):
        self.chat_repository = chat_repository
        self.interaction_lookup = (
            interaction_lookup or NullInteractionLookup()
        )

    def create(self):
        router = APIRouter()

        @router.post("/v1/chats")
        def create_chat() -> CreateChatResponse:
            new_chat_id = self.chat_repository.create()

            return CreateChatResponse.create(new_chat_id)

        @router.get("/v1/chats/:id")
        def show_chat(id: str) -> ShowChatResponse:
            history = self.chat_repository.get_history(id)
            return ShowChatResponse.create(self._serialise(id, history))

        @router.get("/v1/chats")
        def list_chats() -> ListChatsResponse:
            chats = self.chat_repository.get_all()

            return ListChatsResponse.create(
                {
                    chat_id: {"messages": self._serialise(chat_id, history)}
                    for chat_id, history in chats.items()
                }
            )

        return router

    def _serialise(self, chat_id, history):
        return serialise_history(
            history, self.interaction_lookup.ids_by_answer(chat_id)
        )
