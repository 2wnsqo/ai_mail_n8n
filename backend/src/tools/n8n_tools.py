"""
n8n 워크플로우를 LangGraph Tools로 래핑

n8n의 4가지 기본 에이전트를 Python 함수로 호출할 수 있게 합니다:
1. FetchEmailAgent - 메일 가져오기
2. SendEmailAgent - 메일 발송
3. SummarizeEmailAgent - 메일 요약
4. GenerateReplyAgent - 답변 생성
"""

import requests
from typing import List, Dict, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)


class N8nToolWrapper:
    """n8n 워크플로우를 LangGraph Tools로 래핑하는 클래스"""

    def __init__(self, base_url: str = "http://n8n:5678"):
        """
        Args:
            base_url: n8n 서버 URL (기본값: http://n8n:5678)
        """
        self.base_url = base_url

    def fetch_emails(self, since_date: Optional[str] = None) -> Dict:
        """
        워크플로우 #1: 메일 가져오기 (FetchEmailAgent)

        Args:
            since_date: 이 날짜 이후의 이메일만 가져오기 (YYYY-MM-DD)
                       None이면 오늘 날짜

        Returns:
            {
                "success": true,
                "new_emails": 5,
                "email_ids": [1, 2, 3, 4, 5],
                "total_emails": 10
            }
        """
        if since_date is None:
            since_date = date.today().isoformat()

        url = f"{self.base_url}/webhook/mail"
        payload = {
            "sync_date": since_date,
            "trigger_source": "langgraph"
        }

        logger.info(f"[n8n] FetchEmailAgent 호출: {payload}")

        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()

            # n8n 응답의 success 필드 확인
            if not result.get('success', True):
                error_msg = result.get('message', 'n8n 워크플로우 실패')
                logger.error(f"[n8n] FetchEmailAgent 실패: {error_msg}")
                raise Exception(error_msg)

            logger.info(f"[n8n] FetchEmailAgent 성공: {result.get('new_emails', 0)}개 새 이메일")

            return result

        except requests.exceptions.Timeout:
            logger.error("[n8n] FetchEmailAgent 타임아웃")
            raise Exception("메일 가져오기 시간 초과 (60초)")

        except requests.exceptions.RequestException as e:
            logger.error(f"[n8n] FetchEmailAgent 실패: {e}")
            raise Exception(f"n8n 연결 실패: {str(e)}")

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        to_name: Optional[str] = None,
        sender_name: str = "AI 메일 비서",
        sender_email: Optional[str] = None
    ) -> Dict:
        """
        워크플로우 #2: 메일 발송 (SendEmailAgent)

        Args:
            to_email: 수신자 이메일
            subject: 이메일 제목
            body: 이메일 본문
            to_name: 수신자 이름 (선택)
            sender_name: 발신자 이름 (기본: AI 메일 비서)
            sender_email: 발신자 이메일 (선택, 기본값은 .env에서)

        Returns:
            {
                "success": true,
                "message_id": "abc123",
                "sent_at": "2025-11-15T10:30:00"
            }
        """
        url = f"{self.base_url}/webhook/send-reply"
        payload = {
            "to_email": to_email,
            "to_name": to_name or "",
            "subject": subject,
            "reply_body": body,
            "sender_name": sender_name,
            "sender_email": sender_email or ""
        }

        logger.info(f"[n8n] SendEmailAgent 호출: to={to_email}, subject={subject}")

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            logger.info(f"[n8n] SendEmailAgent 성공: {to_email}로 발송")

            return result

        except requests.exceptions.Timeout:
            logger.error("[n8n] SendEmailAgent 타임아웃")
            raise Exception("메일 발송 시간 초과 (30초)")

        except requests.exceptions.RequestException as e:
            logger.error(f"[n8n] SendEmailAgent 실패: {e}")
            raise Exception(f"n8n 연결 실패: {str(e)}")

    def summarize_emails(self, email_ids: Optional[List[int]] = None) -> Dict:
        """
        워크플로우 #3: 메일 요약 (SummarizeEmailAgent)

        Args:
            email_ids: 요약할 이메일 ID 리스트
                      None이면 오늘의 모든 이메일

        Returns:
            {
                "success": true,
                "email_count": 5,
                "summary": "오늘 총 5개의 이메일이 수신되었습니다...",
                "summary_date": "2025-11-15"
            }
        """
        url = f"{self.base_url}/webhook/summary"
        payload = {
            "summary_date": date.today().isoformat(),
            "trigger_source": "langgraph"
        }

        if email_ids:
            payload["email_ids"] = email_ids

        logger.info(f"[n8n] SummarizeEmailAgent 호출: {len(email_ids) if email_ids else '전체'} 이메일")

        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()

            result = response.json()
            logger.info(f"[n8n] SummarizeEmailAgent 성공: {result.get('email_count', 0)}개 이메일 요약")

            return result

        except requests.exceptions.Timeout:
            logger.error("[n8n] SummarizeEmailAgent 타임아웃")
            raise Exception("메일 요약 시간 초과 (120초)")

        except requests.exceptions.RequestException as e:
            logger.error(f"[n8n] SummarizeEmailAgent 실패: {e}")
            raise Exception(f"n8n 연결 실패: {str(e)}")

    def generate_reply(
        self,
        email_id: int,
        preferred_tone: str = "formal"
    ) -> Dict:
        """
        워크플로우 #4: 답변 생성 (GenerateReplyAgent)

        Args:
            email_id: 답변할 이메일 ID
            preferred_tone: 선호하는 톤 (formal/casual/brief)

        Returns:
            {
                "success": true,
                "email_id": 123,
                "reply_drafts": {
                    "formal": { "tone": "격식체", "reply_text": "..." },
                    "casual": { "tone": "친근함", "reply_text": "..." },
                    "brief": { "tone": "간결함", "reply_text": "..." }
                },
                "preferred_tone": "formal"
            }
        """
        url = f"{self.base_url}/webhook/generate-reply"
        payload = {
            "email_id": email_id,
            "preferred_tone": preferred_tone
        }

        logger.info(f"[n8n] GenerateReplyAgent 호출: email_id={email_id}, tone={preferred_tone}")

        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()
            logger.info(f"[n8n] GenerateReplyAgent 성공: 3가지 톤 답변 생성")

            return result

        except requests.exceptions.Timeout:
            logger.error("[n8n] GenerateReplyAgent 타임아웃")
            raise Exception("답변 생성 시간 초과 (60초)")

        except requests.exceptions.RequestException as e:
            logger.error(f"[n8n] GenerateReplyAgent 실패: {e}")
            raise Exception(f"n8n 연결 실패: {str(e)}")

    def analyze_email(self, email_id: int) -> Dict:
        """
        워크플로우 #5: 이메일 분석 (AnalyzeEmailAgent)

        Args:
            email_id: 분석할 이메일 ID

        Returns:
            {
                "success": true,
                "email_id": 123,
                "analysis": {
                    "email_type": "채용",
                    "importance_score": 8,
                    "needs_reply": true,
                    "sentiment": "positive",
                    "key_points": [...],
                    "recommended_action": "..."
                }
            }
        """
        url = f"{self.base_url}/webhook-test/analyze"
        payload = {"email_id": email_id}

        logger.info(f"[n8n] AnalyzeEmailAgent 호출: email_id={email_id}")

        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()
            logger.info(f"[n8n] AnalyzeEmailAgent 성공: {result.get('analysis', {}).get('email_type', 'unknown')}")

            return result

        except requests.exceptions.Timeout:
            logger.error("[n8n] AnalyzeEmailAgent 타임아웃")
            raise Exception("이메일 분석 시간 초과 (60초)")

        except requests.exceptions.RequestException as e:
            logger.error(f"[n8n] AnalyzeEmailAgent 실패: {e}")
            raise Exception(f"n8n 연결 실패: {str(e)}")


# 전역 인스턴스
n8n_tools = N8nToolWrapper()
