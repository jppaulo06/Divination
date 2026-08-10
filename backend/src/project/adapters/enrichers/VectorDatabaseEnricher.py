import shutil

from project.ports.enrichers.ContextEnricher import ContextEnricher

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader


class VectorDatabaseEnricher(ContextEnricher):
    def __init__(self):
        filepath = "src/project/database/texts/freerules-dnd.pdf"
        loader = PyPDFLoader(filepath)
        documento = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        splits = text_splitter.split_documents(documento)

        # Rebuilt from the source PDF on every startup, so the persisted
        # collection must be cleared first - otherwise every restart (or
        # any new process constructing this class) re-adds all chunks with
        # fresh random IDs, and the collection grows with duplicates,
        # degrading retrieval quality.
        persist_directory = "../database/chroma_db"
        shutil.rmtree(persist_directory, ignore_errors=True)

        self.vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=OpenAIEmbeddings(),
            persist_directory=persist_directory,
            collection_name="vector_database",
        )

    def getData(self, query):
        retriever = self.vectorstore.as_retriever()
        return retriever
