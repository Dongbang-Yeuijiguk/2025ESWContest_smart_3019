from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers.dashboard import router as dashboard_router
from routers.routine import router as routine_router
from routers.device import router as device_router
from routers.user import router as user_router
from dotenv import load_dotenv


load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 또는 ["*"] (개발 환경에서만) 우리 도메인에서만
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(routine_router)
app.include_router(device_router)
app.include_router(user_router)
