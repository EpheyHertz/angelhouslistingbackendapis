from fastapi import APIRouter, HTTPException, Depends,status
from chatbot.chat import real_estate_chatbot
from app.schemas import ChatRequest

router = APIRouter(prefix="/chat", tags=["Chat With Us"])



@router.post("/us",status_code=status.HTTP_200_OK)
async def chat_endpoint(request: ChatRequest):
    try:
       response = real_estate_chatbot(request.message)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="An error occured! Please try again later!")
    return {"response": response}