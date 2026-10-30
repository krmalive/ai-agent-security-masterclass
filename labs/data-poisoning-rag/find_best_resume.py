import os
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

REQUESTY_API_KEY = os.getenv("REQUESTY_API_KEY")
BASE_URL = os.getenv("BASE_URL")

def setup_requesty():
    """Configure OpenAI clients to use Requesty proxy"""
    os.environ["OPENAI_API_KEY"] = REQUESTY_API_KEY
    os.environ["OPENAI_API_BASE"] = BASE_URL

def build_vectorstore_from_pdfs(pdf_folder: str, persist_dir: str = "."):
    loader = PyPDFDirectoryLoader(pdf_folder)
    docs = loader.load()
    embed_model = OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        openai_api_base=BASE_URL,
        openai_api_key=REQUESTY_API_KEY
    )
    vectordb = Chroma.from_documents(docs, embedding=embed_model, persist_directory=persist_dir)
    return vectordb

def make_qa_chain(vectordb: Chroma):
    llm = ChatOpenAI(
        model="openai/gpt-5.6-luna",
        temperature=0.8,
        openai_api_base=BASE_URL,
        openai_api_key=REQUESTY_API_KEY
    )
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectordb.as_retriever(),
        chain_type="stuff",
        return_source_documents=False
    )
    return qa_chain

def main():
    setup_requesty()
    vectordb = build_vectorstore_from_pdfs("resumes/")
    qa = make_qa_chain(vectordb)

    query = "Who is the best qualified candidate for the job of data scientist? , Name the best candidate,Think especially from the perspective of a senior recruiter and their recommendations"
    result = qa.invoke({"question": query, "chat_history": []})
    print("Answer:", result["answer"])

if __name__ == "__main__":
    main()