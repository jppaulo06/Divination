from project.ports.answerers.LLMAnswerer import LLMAnswerer
from project.core.RagChain import RagChain
from langchain_openai import ChatOpenAI
from langchain.chains import create_history_aware_retriever
from langchain.chains.combine_documents import create_stuff_documents_chain
import os

MARITACA_BASE_URL = "https://chat.maritaca.ai/api"
MARITACA_MODEL = "sabia-4"


class MaritacaLLM(LLMAnswerer):
    model_name = MARITACA_MODEL

    def get_answer(
        self,
        chat_id,
        query,
        context,
        chat_repository,
        template,
        history_template,
        settings,
    ):
        answer, _ = self._answer(
            chat_id,
            query,
            context,
            chat_repository,
            template,
            history_template,
            settings,
        )
        return answer

    def get_answer_with_context(
        self,
        chat_id,
        query,
        context,
        chat_repository,
        template,
        history_template,
        settings,
        callbacks=None,
    ):
        """Same as get_answer(), but also returns retrieved documents and
        accepts tracing callbacks. Used by the eval suite only."""
        return self._answer(
            chat_id,
            query,
            context,
            chat_repository,
            template,
            history_template,
            settings,
            callbacks=callbacks,
        )

    def _answer(
        self,
        chat_id,
        query,
        context,
        chat_repository,
        template,
        history_template,
        settings,
        callbacks=None,
    ):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.security.LANGCHAIN_API_KEY

        llm = ChatOpenAI(
            model=MARITACA_MODEL,
            api_key=settings.security.MARITACA_API_KEY,
            base_url=MARITACA_BASE_URL,
        )

        history_retriever = create_history_aware_retriever(
            llm, context, history_template
        )

        question_answer_chain = create_stuff_documents_chain(llm, template)

        ragchain = RagChain(
            chat_repository, history_retriever, question_answer_chain
        )
        return ragchain.answer_with_context(query, chat_id, callbacks=callbacks)
