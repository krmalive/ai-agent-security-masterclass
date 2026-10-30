import os
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

REQUESTY_API_KEY = os.getenv("REQUESTY_API_KEY")
BASE_URL = os.getenv("BASE_URL")

# --- Load all resumes ---
loader = PyPDFDirectoryLoader("resumes/")
docs = loader.load()

# --- Create embeddings (Requesty routed) ---
embeddings = OpenAIEmbeddings(model="openai/text-embedding-3-small")

# --- Build and persist vector database ---
vectordb = Chroma.from_documents(docs, embedding=embeddings, persist_directory=".")
print("✅ Vector store created and persisted successfully.")