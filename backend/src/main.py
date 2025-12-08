from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.append(str(Path(__file__).parent.parent))

from src.models.schemas import (
    EmailInDB,
    EmailAnalysis,
    ReplyRequest,
    ReplyResponse,
    AnalyzeRequest,
    SendReplyRequest
)
from src.services.db_service import db
from src.config import settings
from src.agents.email_processor import email_processor
from src.tools.n8n_tools import n8n_tools

# RAG 서비스 (지연 로딩)
_rag_service = None

def get_rag_service():
    """RAG 서비스 인스턴스 가져오기 (지연 로딩)"""
    global _rag_service
    if _rag_service is None:
        try:
            from src.rag.rag_service import EmailRAGService
            _rag_service = EmailRAGService()
        except Exception as e:
            logger.warning(f"RAG 서비스 로드 실패: {e}")
            _rag_service = None
    return _rag_service

app = FastAPI(
    title="AI Email Assistant API",
    description="LangGraph + n8n 하이브리드 AI 메일 비서 시스템",
    version="2.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "AI Email Assistant API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """헬스 체크"""
    try:
        # DB 연결 테스트
        conn = db.get_connection()
        conn.close()

        # RAG 상태 확인
        rag = get_rag_service()
        rag_status = "ready" if rag and rag.is_ready() else "not_ready"

        return {
            "status": "healthy",
            "database": "connected",
            "rag": rag_status
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

# ========== 메일 동기화 API ==========

@app.post("/sync-emails")
async def sync_emails():
    """
    네이버 메일함에서 오늘의 이메일 동기화 + LangGraph 자동 처리

    LangGraph Supervisor가 다음을 수행:
    1. n8n FetchEmailAgent로 메일 가져오기
    2. Gemini로 이메일 분류 (중요도, 유형, 감정 분석)
    3. 중요한 이메일(>=7점)은 자동으로 답변 초안 생성
    4. 사용자에게 결과 반환 (승인 대기)
    """
    try:
        from datetime import date

        # LangGraph Supervisor 실행
        result = email_processor.process_new_emails()

        # 결과 정리
        new_emails = len(result.get("email_ids", []))
        important_count = len(result.get("important_emails", []))
        reply_drafts_count = len(result.get("reply_drafts", {}))

        return {
            "success": True,
            "message": "메일 동기화 및 자동 분석 완료",
            "new_emails": new_emails,
            "important_emails": important_count,
            "reply_drafts_generated": reply_drafts_count,
            "sync_date": date.today().isoformat(),
            "classifications": result.get("classifications", []),
            "important_email_ids": result.get("important_emails", []),
            "current_step": result.get("current_step"),
            "errors": result.get("errors", [])
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"이메일 처리 실패: {str(e)}"
        )

# ========== 이메일 조회 API ==========

@app.get("/emails", response_model=List[dict])
async def get_emails(
    limit: int = 50,
    offset: int = 0,
    analyzed_only: bool = False
):
    """
    이메일 목록 조회

    - **limit**: 조회할 이메일 개수 (기본 50)
    - **offset**: 시작 위치 (페이징)
    - **analyzed_only**: True이면 분석된 이메일만 조회
    """
    try:
        emails = db.get_emails(limit=limit, offset=offset, analyzed_only=analyzed_only)
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/{email_id}")
async def get_email(email_id: int):
    """특정 이메일 상세 조회"""
    try:
        email = db.get_email_by_id(email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        return email
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/unanalyzed")
async def get_unanalyzed_emails(limit: int = 10):
    """미분석 이메일 목록 조회"""
    try:
        emails = db.get_unanalyzed_emails(limit=limit)
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== 이메일 분석 API ==========

@app.post("/analyze/{email_id}")
async def analyze_email(email_id: int):
    """
    이메일 분석 (LangGraph → n8n → Gemini)

    - 이메일 유형 분류 (채용/마케팅/공지/개인/기타)
    - 중요도 점수 (0-10)
    - 답변 필요 여부
    - 감정 분석
    """
    try:
        # 이메일 존재 여부 확인
        email = db.get_email_by_id(email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # LangGraph Supervisor를 통해 분석 (n8n → Gemini 호출)
        result = email_processor.analyze_single_email(email_id)

        if result.get("success") is False:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "분석 실패")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"분석 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-all")
async def analyze_all_unanalyzed():
    """미분석 이메일 전체 분석 (LangGraph → n8n → Gemini)"""
    try:
        # 미분석 이메일 조회
        unanalyzed = db.get_unanalyzed_emails(limit=100)
        email_ids = [email['id'] for email in unanalyzed]

        if not email_ids:
            return {
                "total": 0,
                "results": []
            }

        # LangGraph Supervisor를 통해 분석 (n8n → Gemini 호출)
        result = email_processor.analyze_multiple_emails(email_ids)

        return result

    except Exception as e:
        logger.error(f"analyze-all 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== 답변 생성 API ==========

@app.post("/generate-reply/{email_id}")
async def generate_reply(email_id: int, preferred_tone: str = "formal"):
    """
    이메일 답변 생성 (n8n 워크플로우 호출)

    - 3가지 톤으로 답변 생성: formal(격식), casual(친근함), brief(간결함)
    - **preferred_tone**: 선호하는 톤 (기본값: formal)
    """
    try:
        import requests

        # 이메일 존재 여부 확인
        email = db.get_email_by_id(email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # n8n 워크플로우 호출
        webhook_url = "http://n8n:5678/webhook/generate-reply"
        payload = {
            "email_id": email_id,
            "preferred_tone": preferred_tone
        }

        logger.info(f"n8n 워크플로우 호출 시작: email_id={email_id}, preferred_tone={preferred_tone}")

        response = requests.post(webhook_url, json=payload, timeout=90)

        if response.status_code == 200:
            logger.info(f"n8n 워크플로우 성공: email_id={email_id}")
            return {
                "success": True,
                **response.json()
            }
        else:
            logger.error(f"n8n 워크플로우 실패: status={response.status_code}, text={response.text}")
            raise HTTPException(
                status_code=500,
                detail=f"n8n 워크플로우 실행 실패: {response.text}"
            )

    except requests.exceptions.Timeout:
        logger.error(f"n8n 워크플로우 timeout: email_id={email_id}")
        raise HTTPException(status_code=504, detail="답변 생성 시간 초과 (90초)")
    except requests.exceptions.RequestException as e:
        logger.error(f"n8n 연결 실패: {e}")
        raise HTTPException(status_code=503, detail=f"n8n 연결 실패: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답변 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== 답변 발송 API ==========

@app.post("/send-reply")
async def send_reply(request: SendReplyRequest):
    """
    답변 이메일 발송 (n8n Webhook 호출)

    - n8n의 "답변 메일 발송" 워크플로우를 호출합니다
    """
    try:
        import requests

        # n8n Webhook URL
        webhook_url = "http://n8n:5678/webhook/send-reply"

        payload = {
            "to_email": request.to_email,
            "to_name": request.to_name or "",
            "subject": f"Re: {db.get_email_by_id(request.email_id)['subject']}",
            "reply_body": request.reply_text,
            "sender_name": settings.NAVER_NAME,
            "sender_email": settings.NAVER_EMAIL
        }

        # n8n Webhook 호출
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            # DB에 발송 기록 저장
            db.save_sent_email({
                'original_email_id': request.email_id,
                'to_email': request.to_email,
                'to_name': request.to_name,
                'subject': payload['subject'],
                'reply_body': request.reply_text,
                'sender_name': settings.NAVER_NAME,
                'sender_email': settings.NAVER_EMAIL,
                'status': 'sent'
            })

            # 원본 이메일을 답변 완료로 표시
            db.mark_as_replied(request.email_id)

            return {
                "success": True,
                "message": "Reply sent successfully",
                "email_id": request.email_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send email via n8n")

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"n8n webhook error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== 일일 요약 API ==========

@app.get("/summary/today")
async def get_today_summary():
    """오늘의 이메일 요약 조회"""
    try:
        from datetime import date
        summary = db.get_daily_summary(date.today())

        if not summary:
            return {
                "message": "No summary available for today",
                "summary": None
            }

        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summary/generate")
async def generate_daily_summary():
    """
    오늘 수신된 이메일의 일일 요약 생성 (LangGraph Supervisor)

    - LangGraph가 n8n SummarizeEmailAgent 호출
    - 오늘 날짜의 모든 이메일을 Gemini로 요약
    - daily_summaries 테이블에 저장
    """
    try:
        # LangGraph Supervisor 실행
        result = email_processor.generate_daily_summary()

        # email_ids 개수 계산
        email_count = len(result.get("email_ids", []))

        return {
            "success": True,
            "message": "일일 요약 생성 완료",
            "email_count": email_count,
            "summary": result.get("summary"),
            "current_step": result.get("current_step"),
            "errors": result.get("errors", [])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"요약 생성 실패: {str(e)}")

# ========== 고급 멀티 에이전트 API (제거됨 - n8n으로 이관) ==========
# v2 API는 더 이상 사용하지 않습니다.
# 모든 분석/답변 생성 로직은 n8n 워크플로우에서 처리합니다.


@app.get("/v2/suggestions/{email_id}")
async def get_suggestion(email_id: int):
    """답변 제안 조회 (이메일 ID 기준)"""
    try:
        conn = db.get_connection()
        cur = conn.cursor()

        # 이메일 정보 조회
        cur.execute("""
            SELECT id, subject, sender_name, sender_address
            FROM email
            WHERE id = %s
        """, (email_id,))

        email = cur.fetchone()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # 3가지 톤의 답변 초안 조회
        cur.execute("""
            SELECT tone, reply_text, confidence_score, status, created_at
            FROM reply_drafts
            WHERE email_id = %s
            ORDER BY created_at DESC
        """, (email_id,))

        drafts = cur.fetchall()
        cur.close()
        conn.close()

        if not drafts:
            raise HTTPException(status_code=404, detail="No reply drafts found for this email")

        # 응답 포맷 (기존 스키마와 호환되도록)
        result = {
            "email_id": email['id'],
            "subject": email['subject'],
            "sender_name": email['sender_name'],
            "sender_address": email['sender_address'],
            "drafts": {}
        }

        for draft in drafts:
            result['drafts'][draft['tone']] = {
                "reply_text": draft['reply_text'],
                "confidence_score": draft['confidence_score'],
                "status": draft['status'],
                "created_at": str(draft['created_at'])
            }

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v2/approve-reply/{email_id}")
async def approve_and_send_reply(email_id: int, selected_tone: str, modified_text: Optional[str] = None):
    """
    답변 승인 및 발송 (Human-in-the-Loop)

    Args:
        email_id: 이메일 ID
        selected_tone: 선택한 톤 (formal/casual/brief)
        modified_text: 사용자 수정본 (선택)

    Flow:
        1. 사용자가 선택/수정한 답변 조회
        2. n8n Webhook으로 메일 발송
        3. sent_emails 테이블에 저장
        4. 피드백 학습 (FeedbackAgent)
    """
    try:
        import requests

        # 1. 이메일 및 답변 초안 조회
        conn = db.get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, subject, sender_address, sender_name
            FROM email
            WHERE id = %s
        """, (email_id,))

        email = cur.fetchone()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # 2. 선택한 톤의 답변 초안 조회
        cur.execute("""
            SELECT reply_text, status
            FROM reply_drafts
            WHERE email_id = %s AND tone = %s
        """, (email_id, selected_tone))

        draft = cur.fetchone()

        if not draft:
            raise HTTPException(status_code=404, detail=f"No draft found for tone '{selected_tone}'")

        if draft['status'] != 'generated':
            raise HTTPException(status_code=400, detail="Draft already processed")

        original_draft = draft['reply_text']
        final_reply = modified_text if modified_text else original_draft

        # 3. n8n Webhook 호출 (메일 발송)
        webhook_url = "http://n8n:5678/webhook-test/send-reply"
        payload = {
            "to_email": email['sender_address'],
            "to_name": email['sender_name'] or "",
            "subject": f"Re: {email['subject']}",
            "reply_body": final_reply,
            "sender_name": settings.NAVER_NAME,
            "sender_email": settings.NAVER_EMAIL
        }

        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            # 4. sent_emails 저장
            cur.execute("""
                INSERT INTO sent_emails
                (original_email_id, to_email, to_name, subject, reply_body,
                 sender_name, sender_email, status, approved_by, approved_at,
                 original_draft, user_modifications)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'sent', 'user', NOW(), %s, %s)
                RETURNING id
            """, (
                email_id,
                email['sender_address'],
                email['sender_name'],
                payload['subject'],
                final_reply,
                settings.NAVER_NAME,
                settings.NAVER_EMAIL,
                original_draft,
                modified_text
            ))

            sent_id = cur.fetchone()['id']

            # 5. email 테이블 업데이트
            cur.execute("""
                UPDATE email
                SET is_replied_to = TRUE,
                    processing_status = 'replied',
                    updated_at = NOW()
                WHERE id = %s
            """, (email_id,))

            # 6. draft 상태 업데이트
            cur.execute("""
                UPDATE reply_drafts
                SET status = 'approved'
                WHERE email_id = %s AND tone = %s
            """, (email_id, selected_tone))

            conn.commit()

            # 7. 피드백 학습 (비동기) - 현재는 비활성화
            # feedback_type = 'modified' if modified_text else 'accepted'
            # supervisor.execute(
            #     task="process_feedback",
            #     email_id=email_id,
            #     original_draft=original_draft,
            #     modified_draft=final_reply,
            #     feedback_type=feedback_type
            # )

            cur.close()
            conn.close()

            return {
                "success": True,
                "message": "답변이 발송되었습니다",
                "sent_id": sent_id,
                "feedback_learned": True
            }
        else:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(status_code=500, detail="Failed to send email via n8n")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/agent-logs/{email_id}")
async def get_agent_logs(email_id: int):
    """에이전트 실행 로그 조회 (디버깅용)"""
    try:
        conn = db.get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT agent_name, node_name, started_at, completed_at,
                   duration_ms, status, error_message
            FROM agent_execution_logs
            WHERE email_id = %s
            ORDER BY started_at ASC
        """, (email_id,))

        logs = cur.fetchall()
        cur.close()
        conn.close()

        return {"email_id": email_id, "logs": logs}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== RAG API ==========

@app.get("/rag/status")
async def get_rag_status():
    """RAG 서비스 상태 확인"""
    try:
        rag = get_rag_service()
        if rag is None:
            return {
                "status": "unavailable",
                "message": "RAG 서비스를 로드할 수 없습니다. 패키지를 확인해주세요."
            }

        is_ready = rag.is_ready()
        collections = []

        if is_ready:
            try:
                for col in rag.client.list_collections():
                    collections.append({
                        "name": col.name,
                        "count": col.count()
                    })
            except:
                pass

        return {
            "status": "ready" if is_ready else "not_initialized",
            "collections": collections,
            "message": "RAG 서비스가 준비되었습니다." if is_ready else "벡터 DB를 초기화해주세요."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/rag/enhance-prompt")
async def enhance_prompt_with_rag(email_id: int):
    """
    RAG로 강화된 분석 프롬프트 생성

    n8n 워크플로우에서 Gemini 호출 전에 이 API를 호출하여
    RAG 컨텍스트가 포함된 프롬프트를 받아 사용합니다.
    """
    try:
        rag = get_rag_service()
        if rag is None or not rag.is_ready():
            raise HTTPException(
                status_code=503,
                detail="RAG 서비스가 준비되지 않았습니다."
            )

        # 이메일 조회
        email = db.get_email_by_id(email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # RAG 강화 프롬프트 생성
        enhanced_prompt = rag.get_enhanced_analysis_prompt(
            email_subject=email.get('subject', ''),
            email_body=email.get('body_text', ''),
            sender_name=email.get('sender_name', ''),
            sender_address=email.get('sender_address', '')
        )

        return {
            "success": True,
            "email_id": email_id,
            "enhanced_prompt": enhanced_prompt
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG 프롬프트 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/similar-emails")
async def find_similar_emails(
    subject: str,
    body: str,
    collection: str = "email_classification",
    n_results: int = 5
):
    """
    유사 이메일 검색

    Args:
        subject: 이메일 제목
        body: 이메일 본문
        collection: 검색할 컬렉션 (email_classification, reply_templates, email_importance)
        n_results: 반환할 결과 수
    """
    try:
        rag = get_rag_service()
        if rag is None or not rag.is_ready():
            raise HTTPException(
                status_code=503,
                detail="RAG 서비스가 준비되지 않았습니다."
            )

        query_text = f"{subject} {body[:500]}"
        similar = rag.search_similar_emails(
            query_text,
            collection_name=collection,
            n_results=n_results
        )

        return {
            "success": True,
            "query": query_text[:100] + "...",
            "collection": collection,
            "results": similar
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"유사 이메일 검색 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/reply-context")
async def get_reply_context(email_id: int, preferred_tone: str = "formal"):
    """
    답변 생성을 위한 RAG 컨텍스트 조회

    n8n 워크플로우에서 답변 생성 전에 이 API를 호출하여
    유사 답변 템플릿을 참조합니다.
    """
    try:
        rag = get_rag_service()
        if rag is None or not rag.is_ready():
            raise HTTPException(
                status_code=503,
                detail="RAG 서비스가 준비되지 않았습니다."
            )

        # 이메일 조회
        email = db.get_email_by_id(email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # 유사 템플릿 검색
        templates = rag.get_reply_templates(
            email_subject=email.get('subject', ''),
            email_body=email.get('body_text', ''),
            email_type=email.get('email_type'),
            n_templates=3
        )

        # RAG 강화 답변 프롬프트 생성
        enhanced_prompt = rag.get_enhanced_reply_prompt(
            email_subject=email.get('subject', ''),
            email_body=email.get('body_text', ''),
            email_type=email.get('email_type', '기타'),
            sender_name=email.get('sender_name', ''),
            preferred_tone=preferred_tone
        )

        return {
            "success": True,
            "email_id": email_id,
            "similar_templates": templates,
            "enhanced_prompt": enhanced_prompt
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답변 컨텍스트 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
