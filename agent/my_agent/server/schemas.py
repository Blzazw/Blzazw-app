"""
数据模型定义。
"""

from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: str = "default"
    mode: str = "safe"  # safe | trusted | sovereign


class ConfirmRequest(BaseModel):
    """确认请求"""
    session_id: str
    tool_call_id: str
    approved: bool


class NewSessionRequest(BaseModel):
    """新建会话请求"""
    session_id: Optional[str] = None


class ModeRequest(BaseModel):
    """切换模式请求"""
    session_id: str
    mode: str  # safe | trusted | sovereign
