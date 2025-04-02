# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

from .routers import telemetry
from .utils.logger import get_logger

# 加载环境变量
load_dotenv()

# 初始化 FastAPI 应用
app = FastAPI(
    title="OpenHands Telemetry API",
    description="API for receiving and analyzing OpenHands installation telemetry",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含路由
app.include_router(telemetry.router)

# 根路由
@app.get("/")
async def root():
    return {
        "message": "Welcome to OpenHands Telemetry API",
        "documentation": "/docs",
    }

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 9999))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)