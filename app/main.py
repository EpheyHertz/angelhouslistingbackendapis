from fastapi import FastAPI
import sendlk
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from upstash_workflow.fastapi import Serve
from .config import SENDLK_TOKEN,SECRET_KEY
sendlk.initialize(SENDLK_TOKEN, SECRET_KEY)
# models.Base.metadata.create_all(bind=engine)
from app.routers.workflows import lifespan
app = FastAPI(lifespan=lifespan)
from app.routers import auth, social_auth, house,mpesa, reviews, admin,tokens,booking,code,workflows
serve = Serve(app)
# Add SessionMiddleware
# Replace 'your-secret-key' with a strong secret key or use an environment variable
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with a list of allowed origins in production
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


# Include routers
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add route to serve favicon.ico
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")

@app.get("/", tags=["Welcome"])
def read_root():
    return {"message": "Welcome to the House Listing API"}

app.include_router(auth.router)
app.include_router(social_auth.router)
app.include_router(house.router)
app.include_router(booking.router)
app.include_router(reviews.router)
app.include_router(admin.router)
app.include_router(tokens.router)
app.include_router(mpesa.router)
app.include_router(workflows.router)
app.include_router(code.router, prefix="/phone")

