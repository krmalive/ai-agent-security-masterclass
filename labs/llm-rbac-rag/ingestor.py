from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.schema import Document
from llama_index.core import StorageContext
from llama_index.embeddings.openai import OpenAIEmbedding
import chromadb
from dotenv import load_dotenv
import os

load_dotenv()

chroma_client = chromadb.PersistentClient(path="./chroma_db")
chroma_collection = chroma_client.get_or_create_collection("docs")

API_KEY = os.getenv("OPENAI_API_KEY")  
BASE_URL = os.getenv("OPENAI_API_BASE") 


em = OpenAIEmbedding(
    model_name="openai/text-embedding-3-small",
    api_base=BASE_URL,
    api_key=API_KEY,
)

all_docs = []
eng_docs = SimpleDirectoryReader("./docs/engineering").load_data()

for doc in eng_docs:
    doc.metadata["department"] = "engineering"
    all_docs.append(doc)

sales_docs = SimpleDirectoryReader("./docs/sales").load_data()


for doc in sales_docs:
    doc.metadata["department"] = "sales"
    all_docs.append(doc)

vectorstore = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vectorstore)


eng_index = VectorStoreIndex.from_documents(
    all_docs,
    storage_context=storage_context,
    embed_model=em,
)