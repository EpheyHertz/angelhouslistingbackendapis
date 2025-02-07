import os
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceInferenceAPIEmbeddings
from dotenv import load_dotenv
from app.config import GEMINI_API_KEY,HUGGINGFACE_API_KEY

# Load API keys from environment variables
load_dotenv()
gemini_api_key =GEMINI_API_KEY
huggingface_api_key =HUGGINGFACE_API_KEY

# Load embeddings model
hf_embeddings = HuggingFaceInferenceAPIEmbeddings(
    api_key=huggingface_api_key,
    model_name="sentence-transformers/all-MiniLM-l6-v2"
)

# Load ChromaDB vector database
persist_directory = "db"
vectordb = Chroma(persist_directory=persist_directory, embedding_function=hf_embeddings)
retriever = vectordb.as_retriever(search_kwargs={"k": 3})

# Define a professional real estate chatbot prompt
real_estate_prompt = PromptTemplate(
    template="""You are a highly knowledgeable and professional real estate expert. 
    Your task is to provide expert insights on real estate topics, including property buying, selling, rentals, and investments. 
    You are also a chatbot for the Angel Housing platform created by Ephey Nyaga, aGenerative AI Engineer and a Computer Science student from EMBU University, Kenya. 
    You assist users with matters related to the website (angelhouslistingwebsite.vercel.app).
    
    Always respond in a professional and engaging manner. 

    Here is some relevant information that may help:
    {context}

    Question: {question}
    """,
    input_variables=["context", "question"]  # Ensure "context" is included
)



# Define the LLM model (Gemini AI)
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    api_key=gemini_api_key,
    temperature=0.5
)

# Initialize memory to keep track of conversations
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# Create a Conversational Retrieval Chain
qa_chain = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=retriever,
    memory=memory,
    combine_docs_chain_kwargs={"prompt": real_estate_prompt}
)

# Define a chatbot function to handle user queries
def real_estate_chatbot(user_input: str):
    """
    Handles user queries related to real estate and returns a professional response.
    """
    response = qa_chain.invoke({"question": user_input})
    return response["answer"]

