"""FastAPI 应用入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router

app = FastAPI(
    title="Piano Score Generator",
    description="输入歌曲名字，自动产出简单、中等、难三种难度的钢琴乐谱",
    version="1.0.0",
)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


@app.get("/")
async def root():
    """根路径，返回服务信息。"""
    return {
        "service": "Piano Score Generator",
        "version": "1.0.0",
        "docs": "/docs",
    }
