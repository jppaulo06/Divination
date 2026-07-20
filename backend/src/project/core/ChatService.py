class ChatService:
    def __init__(
        self, context_enricher, answerer, template, chat_repository, settings
    ):
        self.context_enricher = context_enricher
        self.llm_answerer = answerer
        self.answer_template = template
        self.chat_repository = chat_repository
        self.project_settings = settings

    def get_answer(self, query, chat_id):
        context = self.context_enricher.getData(query)
        template = self.answer_template.get_template()
        history_template = self.answer_template.get_history_template()
        return self.llm_answerer.get_answer(
            chat_id,
            query,
            context,
            self.chat_repository,
            template,
            history_template,
            self.project_settings,
        )

    def get_answer_with_context(self, query, chat_id, callbacks=None):
        """Same as get_answer(), but also returns retrieved documents and
        accepts tracing callbacks. Used by the eval suite only."""
        context = self.context_enricher.getData(query)
        template = self.answer_template.get_template()
        history_template = self.answer_template.get_history_template()
        return self.llm_answerer.get_answer_with_context(
            chat_id,
            query,
            context,
            self.chat_repository,
            template,
            history_template,
            self.project_settings,
            callbacks=callbacks,
        )
