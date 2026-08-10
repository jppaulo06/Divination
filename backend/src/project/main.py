from dotenv import load_dotenv

load_dotenv()

from project.adapters.routers.AnswerRouter import AnswerRouter
from project.adapters.routers.ChatRouter import ChatRouter

from project.adapters.Settings import Settings
from project.adapters.answerers.MaritacaLLM import MaritacaLLM

from project.adapters.enrichers.VectorDatabaseEnricher import (
    VectorDatabaseEnricher,
)
from project.adapters.enrichers.AnswerEnricher import AnswerEnricher

from project.core.ChatService import ChatService
from project.adapters.database.ChatRepository import ChatRepository

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager


def _inject_routers(
    api: FastAPI, answer_router: AnswerRouter, chat_router: ChatRouter
):
    api.include_router(answer_router.create())
    api.include_router(chat_router.create())


@asynccontextmanager
async def _setup(api: FastAPI, settings: Settings):
    context_enricher = VectorDatabaseEnricher()
    llm_answerer = MaritacaLLM()
    template = AnswerEnricher()
    chat_repository = ChatRepository()
    service = ChatService(
        context_enricher, llm_answerer, template, chat_repository, settings
    )
    answer_router = AnswerRouter(service, chat_repository)
    chat_router = ChatRouter(chat_repository)
    _inject_routers(api, answer_router, chat_router)
    yield


def _create_api(settings: Settings):
    project_api = FastAPI(
        title="D&D answerer API",
        version="0.1",
        lifespan=lambda api: _setup(api, settings),
    )

    project_api.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=settings.api.allowed_origins,
        allow_methods=settings.api.allowed_methods,
        allow_headers=settings.api.allowed_headers,
    )

    return project_api


def _run_uvicorn(settings: Settings):
    uvicorn.run(
        app="project.main:project_api",
        host=str(settings.api.host),
        port=settings.api.port,
    )


project_settings = Settings.load()
project_api = _create_api(project_settings)

if __name__ == "__main__":
    _run_uvicorn(project_settings)
