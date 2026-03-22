"""API 路由

提供 REST 接口，支持前端扩展。
"""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.models.score import DifficultyLevel
from backend.config import OUTPUT_DIR

router = APIRouter(prefix="/api", tags=["scores"])

# 内存存储（生产环境应使用数据库）
_scores_store: dict[str, dict] = {}


class GenerateRequest(BaseModel):
    """生成乐谱请求。
    
    Attributes:
        song_name: 歌曲名称
        midi_path: 可选的本地 MIDI 文件路径
        difficulties: 要生成的难度列表
    """
    song_name: str
    midi_path: Optional[str] = None
    difficulties: list[str] = ["easy", "medium", "hard"]


class ScoreResponse(BaseModel):
    """乐谱响应。
    
    Attributes:
        id: 乐谱 ID
        song_name: 歌曲名称
        difficulties: 已生成的难度列表
        status: 状态（pending/generating/completed/failed）
        message: 状态消息
    """
    id: str
    song_name: str
    difficulties: list[str]
    status: str
    message: str = ""


@router.post("/generate", response_model=ScoreResponse)
async def generate_scores(request: GenerateRequest):
    """生成三种难度的钢琴乐谱。
    
    接收歌曲名称，自动获取 MIDI 文件并生成乐谱。
    
    Args:
        request: 生成请求
        
    Returns:
        乐谱生成结果
    """
    score_id = str(uuid.uuid4())[:8]

    # 验证难度值
    valid_difficulties = {"easy", "medium", "hard"}
    for d in request.difficulties:
        if d not in valid_difficulties:
            raise HTTPException(
                status_code=400,
                detail=f"无效的难度: {d}，可选值: {valid_difficulties}",
            )

    _scores_store[score_id] = {
        "id": score_id,
        "song_name": request.song_name,
        "difficulties": request.difficulties,
        "status": "pending",
        "midi_path": request.midi_path,
        "files": {},
    }

    return ScoreResponse(
        id=score_id,
        song_name=request.song_name,
        difficulties=request.difficulties,
        status="pending",
        message="乐谱生成任务已创建，请调用 GET /api/scores/{id} 查看状态",
    )


@router.get("/scores/{score_id}", response_model=ScoreResponse)
async def get_score(score_id: str):
    """获取乐谱详情。
    
    Args:
        score_id: 乐谱 ID
        
    Returns:
        乐谱信息
    """
    if score_id not in _scores_store:
        raise HTTPException(status_code=404, detail="乐谱不存在")

    score_info = _scores_store[score_id]
    return ScoreResponse(
        id=score_info["id"],
        song_name=score_info["song_name"],
        difficulties=score_info["difficulties"],
        status=score_info["status"],
        message=score_info.get("message", ""),
    )


@router.get("/scores/{score_id}/pdf")
async def download_pdf(score_id: str, difficulty: str = "easy"):
    """下载乐谱 PDF。
    
    Args:
        score_id: 乐谱 ID
        difficulty: 难度（easy/medium/hard）
        
    Returns:
        PDF 文件
    """
    if score_id not in _scores_store:
        raise HTTPException(status_code=404, detail="乐谱不存在")

    score_info = _scores_store[score_id]

    # 查找对应的文件
    file_key = f"{difficulty}_pdf"
    if file_key in score_info["files"]:
        pdf_path = Path(score_info["files"][file_key])
        if pdf_path.exists():
            return FileResponse(
                path=str(pdf_path),
                media_type="application/pdf",
                filename=pdf_path.name,
            )

    # 也尝试 XML 文件
    xml_key = f"{difficulty}_xml"
    if xml_key in score_info["files"]:
        xml_path = Path(score_info["files"][xml_key])
        if xml_path.exists():
            return FileResponse(
                path=str(xml_path),
                media_type="application/xml",
                filename=xml_path.name,
            )

    raise HTTPException(status_code=404, detail=f"未找到 {difficulty} 难度的乐谱文件")


@router.get("/health")
async def health_check():
    """健康检查接口。
    
    Returns:
        服务状态
    """
    return {"status": "ok", "service": "piano-score-gen"}
