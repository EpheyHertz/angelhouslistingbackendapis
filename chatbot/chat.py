import os
import requests
from langchain_chroma import Chroma
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceInferenceAPIEmbeddings
from dotenv import load_dotenv

from app.config import GEMINI_API_KEY, HUGGINGFACE_API_KEY

# Load API keys from environment variables
load_dotenv()
gemini_api_key = GEMINI_API_KEY
huggingface_api_key = HUGGINGFACE_API_KEY

# Load embeddings model
try:
    hf_embeddings = HuggingFaceInferenceAPIEmbeddings(
        api_key=huggingface_api_key,
        model_name="sentence-transformers/all-MiniLM-l6-v2"
    )
except Exception as e:
    print(f"Error loading embeddings model: {e}")
    hf_embeddings = None

# Load ChromaDB vector database
try:
    persist_directory = "db"
    vectordb = Chroma(persist_directory=persist_directory, embedding_function=hf_embeddings)
    retriever = vectordb.as_retriever(search_kwargs={"k": 3})
except Exception as e:
    print(f"Error loading ChromaDB: {e}")
    vectordb = None
    retriever = None

# Define chatbot prompt
real_estate_prompt = PromptTemplate(
    template="""You are a highly knowledgeable and professional real estate expert. 
    Your task is to provide expert insights on real estate topics, including property buying, selling, rentals, and investments. 
    You are also a chatbot for the Angel Housing platform created by Ephey Nyaga, a Generative AI Engineer and a Computer Science student from EMBU University, Kenya. 
    You assist users with matters related to the website (angelhouslistingwebsite.vercel.app).
    
    Always respond in a professional and engaging manner. 

    Here is some relevant information that may help:
    {context}

    Question: {question}
    """,
    input_variables=["context", "question"]
)

# Define the LLM model (Gemini AI)
try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-001",
        api_key=gemini_api_key,
        temperature=0.3
    )
except Exception as e:
    print(f"Error initializing Gemini AI: {e}")
    llm = None

# Initialize memory to keep track of conversations
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# Create a Conversational Retrieval Chain
if llm and retriever:
    try:
        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            memory=memory,
            combine_docs_chain_kwargs={"prompt": real_estate_prompt}
        )
    except Exception as e:
        print(f"Error creating Conversational Retrieval Chain: {e}")
        qa_chain = None
else:
    qa_chain = None

# **Step 1: LLM Determines Whether to Fetch Listings or Use Knowledge Base**
action_classification_prompt = PromptTemplate(
    template="""
    You are an AI assistant helping users with real estate inquiries.

    User query: "{query}"

    Your task is to determine whether the user is:
    1. **Requesting house listings** (e.g., searching for available properties)
    2. **Seeking general real estate advice** (e.g., investment guidance, legal matters, mortgage advice)

    **Rules for Decision:**
    - If the query includes any mention of **houses, apartments, villas, properties, rentals, or real estate** AND 
      specifies both a **location** and a **price**, ALWAYS respond with "FETCH_LISTINGS".
    - If the query is about general real estate knowledge (e.g., "Is it a good time to invest?" or "How do I get a mortgage?"), respond with "USE_KNOWLEDGE".
    - If uncertain, assume the user is looking for listings and default to "FETCH_LISTINGS".

    **Response Format:**
    - Reply with ONLY "FETCH_LISTINGS" or "USE_KNOWLEDGE" and nothing else.
    """,
    input_variables=["query"]
)


# **Step 2: Extract Relevant Filters for Listings**
extract_details_prompt = PromptTemplate(
    template="""Extract relevant details from the user's request.

    User query: "{query}"
    
    Extracted details:
    - Location: (if mentioned, otherwise return "None")
    - Price: (if mentioned, otherwise return "None")
    - Bedrooms: (if mentioned, otherwise return "None")
    - Type: (e.g., Apartment, Villa, etc., otherwise return "None")
    - Amenities: (if mentioned, otherwise return "None")
    remember the type should be in lowercase and without spaces and the price should be in numbers only without any currency symbol
    Provide only the extracted details in the format:
    Location: <location> eg.embu
    Price: <price>eg.500
    Type: <type>eg.apartment

    """,
    input_variables=["query"]
)

# **Step 3: Fetch Houses from API**
def fetch_houses_from_api(location=None, price=None, house_type=None, amenities=None, limit=5):
    """
    Fetch houses from the API based on user-provided filters.
    """
    base_url = " http://127.0.0.1:8000/houses/"
    params = {}

    if location and location.lower() != "none":
        params["location"] = location
    if price and price.lower() != "none":
        params["max_price"] = price
    if house_type and house_type.lower() != "none":
        params["house_type"] = house_type
    if amenities and amenities.lower() != "none":
        params["amenities"] = amenities

    params["limit"] = limit  # Default limit

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()  # Return the list of houses
    except requests.exceptions.RequestException as e:
        print(f"Error fetching houses from API: {e}")
        return {"error": "Failed to fetch houses"}

# **Step 4: Format API Response for Chatbot**
def format_housing_response(houses):
    """
    Converts a list of houses into a chatbot-friendly response.
    """
    if "error" in houses:
        return "Sorry, I couldn't fetch the house listings right now. Please try again later."

    response_text = "Here are some available properties based on your search:\n\n"

    for house in houses[:5]:  # Show top 5 results
        response_text += (
            f"🏡 **{house['title']}**\n"
            f"📍 Location: {house['location']}\n"
            f"💰 Price: ${house['price']}\n"
            f"🏠 Type: {house['house_type']}\n"
            f"✨ Amenities: {', '.join(house['amenities']) if house['amenities'] else 'None'}\n"
            f"🔗 More info: {house['url']}\n\n"
        )

    return response_text

# **Main Chatbot Function**
def real_estate_chatbot(user_input: str):
    """
    Handles user queries related to real estate, deciding dynamically whether to fetch house listings or provide general advice.
    """
    if not llm:
        return "Error: Language model is not initialized."

    try:
        # **Step 1: Ask the LLM if we need to fetch listings or use knowledge**
        action_decision = llm.invoke(action_classification_prompt.format(query=user_input))
        print(f"Action Decision: {action_decision}")

        if action_decision.content == "FETCH_LISTINGS":
            # Extract details only if house listings are required
            details = llm.invoke(extract_details_prompt.format(query=user_input))
            extracted_details = details.content
            print(f"Extracted Details: {extracted_details}")

            # Parse extracted details
            details = {
                "location": extracted_details.split("Location: ")[1].split("\n")[0],
                "price": extracted_details.split("Price: ")[1].split("\n")[0],
                "house_type": extracted_details.split("Type: ")[1].split("\n")[0],
            }

            # Fetch and return listings
            house_list = fetch_houses_from_api(**details)
            return format_housing_response(house_list)

        else:
            # Use knowledge base for answering general real estate questions
            if qa_chain:
                response = qa_chain.invoke({"question": user_input})
                return response["answer"]
            else:
                return "Error: Conversational Retrieval Chain is not initialized."
    except Exception as e:
        return f"An error occurred while processing your request: {e}"

