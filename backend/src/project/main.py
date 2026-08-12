from dotenv import load_dotenv

load_dotenv()

from project.adapters.routers.AnswerRouter import AnswerRouter
from project.adapters.routers.ChatRouter import ChatRouter
from project.adapters.routers.FeedbackRouter import FeedbackRouter
from project.adapters.routers.MonitoringRouter import MonitoringRouter

from project.adapters.Settings import Settings
from project.adapters.answerers.MaritacaLLM import MaritacaLLM

from project.adapters.enrichers.VectorDatabaseEnricher import (
    VectorDatabaseEnricher,
)
from project.adapters.enrichers.AnswerEnricher import AnswerEnricher

from project.adapters.monitoring.CandidateQuery import CandidateQuery
from project.adapters.monitoring.Database import MonitoringDatabase
from project.adapters.monitoring.DetectorRunner import DetectorRunner
from project.adapters.monitoring.SqlInteractionSink import SqlInteractionSink

from project.core.ChatService import ChatService
from project.adapters.database.ChatRepository import ChatRepository

import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

#: Labels every interaction this process records. Set to "synthetic" when
#: running the traffic generator against a demo instance.
MONITORING_SOURCE = os.environ.get("MONITORING_SOURCE", "production")


def _setup_monitoring():
    """Build the monitoring layer, or return Nones if it can't start."""
    try:
        database = MonitoringDatabase()
        database.create_schema()
        return (
            SqlInteractionSink(database),
            DetectorRunner(database),
            CandidateQuery(database),
        )
    except Exception:
        logger.exception("monitoring unavailable; continuing without it")
        return None, None, None


def _inject_routers(api: FastAPI, *routers):
    for router in routers:
        api.include_router(router.create())


@asynccontextmanager
async def _setup(api: FastAPI, settings: Settings):
    interaction_sink, detector_runner, candidate_query = _setup_monitoring()

    context_enricher = VectorDatabaseEnricher()
    llm_answerer = MaritacaLLM()
    template = AnswerEnricher()
    chat_repository = ChatRepository()
    service = ChatService(
        context_enricher,
        llm_answerer,
        template,
        chat_repository,
        settings,
        interaction_sink=interaction_sink,
        source=MONITORING_SOURCE,
    )

    routers = [
        AnswerRouter(service, chat_repository, detector_runner),
        ChatRouter(chat_repository),
    ]
    if interaction_sink is not None:
        routers.append(FeedbackRouter(interaction_sink))
    if candidate_query is not None:
        routers.append(MonitoringRouter(candidate_query))

    _inject_routers(api, *routers)
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
