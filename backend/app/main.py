from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 导入我们在 core/config.py 里定义的 get_settings() 函数，用于读取配置
from backend.app.api.routes import router as api_router
from backend.app.core.config import get_settings

# 路由导入
from backend.app.api.materials import router as material_router
from backend.app.api.kp import router as kp_router

# 建表引擎导入
from backend.app.core.database import create_db_and_tables

settings = get_settings()

# 定义生命周期：在应用启动前自动执行建表
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend MVP for the Feynman companion demo.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "msg": "invalid request body",
            "data": None,
        },
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "llm_provider": settings.llm_provider,
        "deepseek_configured": settings.deepseek_configured,
    }


app.include_router(api_router, prefix="/api/v1")
app.include_router(material_router, prefix="/api/v1")
app.include_router(kp_router, prefix="/api/v1")