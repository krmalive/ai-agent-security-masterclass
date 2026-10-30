from dotenv import load_dotenv

load_dotenv()

from json import load
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.schema import Document
from llama_index.core import StorageContext, Settings
from llama_index.core.vector_stores import (
    MetadataFilter,
    MetadataFilters,
    FilterOperator
)
import chromadb
from llama_index.llms.openai_like import OpenAILike
from llama_index.core import PromptTemplate
import openai
import os

openai.base_url=os.getenv("OPENAI_API_BASE")
openai.api_key=os.getenv("OPENAI_API_KEY")

chroma_client = chromadb.PersistentClient(path="./chroma_db")
chroma_collection = chroma_client.get_or_create_collection("docs")

embeddings = OpenAIEmbedding(
    model_name="openai/text-embedding-3-small",
    api_base=openai.base_url,
    api_key=openai.api_key
)

llm = OpenAILike(
    model="openai/gpt-5.6-luna",
    api_base = os.getenv("OPENAI_API_BASE"),
    api_key=os.getenv("OPENAI_API_KEY"),
    is_chat_model=True,
    is_function_calling_model=True,
    context_window=128000,
)


Settings.embed_model = embeddings

vectorstore = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vectorstore)


index = VectorStoreIndex.from_vector_store(
    vectorstore,
    embed_model=embeddings,
)

def query_rag_insecure(query: str, department: str = None):
    query_engine = index.as_query_engine(llm=llm)
    response = query_engine.query(query)
    return str(response)

def query_rag_secure(query: str, department: str):
    tpl_str = """
    Context information is given below.
    ---------------------
    {context_str}
    ---------------------
    Given the context information and NOT prior knowledge,
    answer the query for the user.
    If there's no context or you don't know the answer, just say "I am not allowed to answer that question".
    Query: {query_str}
    Answer:
    """
    tpl = PromptTemplate(tpl_str)
    filters = MetadataFilters(
        filters=[
            MetadataFilter(
                key="department",
                value=department,
                operator=FilterOperator.EQ,
            )
        ]
    )
    query_engine = index.as_query_engine(
        filters=filters,
        llm=llm
    )
    query_engine.update_prompts(
        {
            "response_synthesizer:summary_template": tpl,
        }
    )
    response = query_engine.query(query)
    return response.response
