from langchain.chains import create_retrieval_chain
from langchain_core.runnables.history import RunnableWithMessageHistory


class RagChain:
    def __init__(
        self, chat_repository, history_retriever, question_answer_chain
    ):
        self.chat_repository = chat_repository
        self.history_retriever = history_retriever
        self.question_answer_chain = question_answer_chain

    def answer(self, query, chat_id):
        return self._invoke(query, chat_id)["answer"]

    def answer_with_context(self, query, chat_id, callbacks=None):
        """Same as answer(), but also returns the retrieved documents.

        Used by the eval suite to build retrieval_context for grounding
        metrics without changing the production answer() contract.
        """
        result = self._invoke(query, chat_id, callbacks=callbacks)
        return result["answer"], result.get("context", [])

    def _invoke(self, query, chat_id, callbacks=None):
        rag_chain = create_retrieval_chain(
            self.history_retriever, self.question_answer_chain
        )

        conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain,
            self.chat_repository.get_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )

        config = {"configurable": {"session_id": chat_id}}
        if callbacks:
            config["callbacks"] = callbacks

        return conversational_rag_chain.invoke({"input": query}, config=config)
