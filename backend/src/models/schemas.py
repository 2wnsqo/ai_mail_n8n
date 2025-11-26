from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class EmailBase(BaseModel):
    subject: str
    body_text: str
    sender_name: Optional[str] = None
    sender_address: str

class EmailAnalysis(BaseModel):
    email_type: str  # 채용/마케팅/공지/개인/기타
    importance_score: int  # 0-10
    needs_reply: bool
    sentiment: Optional[str] = None  # positive/neutral/negative
    key_points: Optional[list[str]] = None

class EmailInDB(EmailBase):
    id: int
    received_at: Optional[datetime] = None
    original_uid: Optional[str] = None
    is_replied_to: bool = False
    email_type: Optional[str] = None
    importance_score: Optional[int] = None
    needs_reply: Optional[bool] = None
    sentiment: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ReplyDraft(BaseModel):
    tone: str  # formal/casual/brief
    content: str
    confidence_score: Optional[float] = None

class ReplyRequest(BaseModel):
    email_id: int
    preferred_tone: Optional[str] = "formal"  # formal/casual/brief

class ReplyResponse(BaseModel):
    email_id: int
    drafts: list[ReplyDraft]
    original_subject: str
    original_body: str

class SendReplyRequest(BaseModel):
    email_id: int
    reply_text: str
    to_email: str
    to_name: Optional[str] = None

class AnalyzeRequest(BaseModel):
    email_id: int
