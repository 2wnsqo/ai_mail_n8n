"""
LangGraph Supervisor Agent for Email Processing

n8n 기본 에이전트들을 orchestration하여 복잡한 이메일 처리 워크플로우를 수행합니다.
"""

from typing import TypedDict, List, Dict, Literal, Optional
from langgraph.graph import StateGraph, END
from datetime import date
import logging
import json

from ..tools.n8n_tools import n8n_tools
from ..services.db_service import db
from ..config import settings

logger = logging.getLogger(__name__)


# ========== State 정의 ==========

class EmailProcessingState(TypedDict):
    """이메일 처리 워크플로우 상태"""

    # 작업 타입
    task: Literal["process_new_emails", "daily_summary", "reply_to_email"]

    # 이메일 데이터
    email_ids: List[int]
    emails: List[dict]

    # 분석 결과
    classifications: List[dict]
    important_emails: List[int]  # 중요도 >= 7

    # 답변 데이터
    reply_drafts: Dict[int, dict]  # {email_id: {formal, casual, brief}}
    approved_replies: List[dict]

    # 요약
    summary: Optional[str]

    # 상태 추적
    current_step: str
    errors: List[str]


# ========== Node 함수들 ==========

def fetch_emails_node(state: EmailProcessingState) -> Dict:
    """
    Step 1: n8n FetchEmailAgent 호출
    """
    logger.info("[Node] fetch_emails_node 시작")

    try:
        # n8n 워크플로우 호출
        result = n8n_tools.fetch_emails()

        return {
            "email_ids": result.get("email_ids", []),
            "current_step": "fetched",
            "errors": []
        }

    except Exception as e:
        logger.error(f"[Node] fetch_emails_node 실패: {e}")
        return {
            "email_ids": [],
            "current_step": "fetch_failed",
            "errors": [str(e)]
        }


def classify_emails_node(state: EmailProcessingState) -> Dict:
    """
    Step 2: n8n_tools를 통해 이메일 분류 (RAG 적용)

    Phase 3 개선: 직접 webhook 호출 대신 n8n_tools.analyze_email() 사용
    → RAG 프롬프트 엔지니어링이 자동으로 적용됨
    """
    logger.info(f"[Node] classify_emails_node 시작: {len(state['email_ids'])}개 이메일 (RAG 적용)")

    if not state["email_ids"]:
        return {
            "classifications": [],
            "important_emails": [],
            "current_step": "classified_empty"
        }

    try:
        # PostgreSQL에서 이메일 조회
        emails = db.get_emails_by_ids(state["email_ids"])

        classifications = []
        important_emails = []

        for email in emails:
            try:
                # n8n_tools를 통해 분석 (RAG 프롬프트 자동 적용)
                result = n8n_tools.analyze_email(
                    email_id=email['id'],
                    email_data=email,
                    use_rag=True  # RAG 프롬프트 엔지니어링 적용
                )

                if result.get("success", True):
                    # n8n 응답에서 분석 결과 추출
                    analysis = {
                        "email_id": email['id'],
                        "email_type": result.get("email_type", "기타"),
                        "importance_score": int(result.get("importance_score", 5)),
                        "needs_reply": result.get("needs_reply", "false").lower() == "true" if isinstance(result.get("needs_reply"), str) else result.get("needs_reply", False),
                        "sentiment": result.get("sentiment", "neutral"),
                        "key_points": result.get("key_points", [])
                    }

                    classifications.append(analysis)

                    # 중요도 >= 7이면 important 리스트에 추가
                    if analysis.get('importance_score', 0) >= 7:
                        important_emails.append(email['id'])

                    logger.info(
                        f"[Node] 이메일 {email['id']} 분류 (RAG): "
                        f"{analysis.get('email_type')}, "
                        f"중요도 {analysis.get('importance_score')}"
                    )
                else:
                    logger.error(f"[Node] n8n 분석 실패: email_id={email['id']}, error={result.get('error')}")

            except Exception as e:
                logger.error(f"[Node] 이메일 {email['id']} 분석 실패: {e}")

        return {
            "emails": emails,
            "classifications": classifications,
            "important_emails": important_emails,
            "current_step": "classified"
        }

    except Exception as e:
        logger.error(f"[Node] classify_emails_node 실패: {e}")
        return {
            "classifications": [],
            "important_emails": [],
            "current_step": "classify_failed",
            "errors": state.get("errors", []) + [str(e)]
        }


def generate_replies_node(state: EmailProcessingState) -> Dict:
    """
    Step 3: n8n GenerateReplyAgent 호출 (중요한 이메일만)
    """
    logger.info(f"[Node] generate_replies_node 시작: {len(state['important_emails'])}개 이메일")

    if not state["important_emails"]:
        return {
            "reply_drafts": {},
            "current_step": "no_replies_needed"
        }

    try:
        reply_drafts = {}

        for email_id in state["important_emails"]:
            # n8n 워크플로우 호출
            result = n8n_tools.generate_reply(email_id=email_id)

            if result.get("success"):
                reply_drafts[email_id] = result.get("reply_drafts", {})
                logger.info(f"[Node] 이메일 {email_id} 답변 생성 완료")

        return {
            "reply_drafts": reply_drafts,
            "current_step": "replies_generated"
        }

    except Exception as e:
        logger.error(f"[Node] generate_replies_node 실패: {e}")
        return {
            "reply_drafts": {},
            "current_step": "reply_generation_failed",
            "errors": state.get("errors", []) + [str(e)]
        }


def send_replies_node(state: EmailProcessingState) -> Dict:
    """
    Step 4: n8n SendEmailAgent 호출 (사용자 승인된 답변만)
    """
    logger.info(f"[Node] send_replies_node 시작: {len(state['approved_replies'])}개 답변")

    if not state["approved_replies"]:
        return {
            "current_step": "no_sends_needed"
        }

    try:
        for reply in state["approved_replies"]:
            # n8n 워크플로우 호출
            n8n_tools.send_email(
                to_email=reply["to_email"],
                subject=reply["subject"],
                body=reply["body"],
                to_name=reply.get("to_name")
            )

            logger.info(f"[Node] {reply['to_email']}로 답변 발송 완료")

        return {
            "current_step": "sent"
        }

    except Exception as e:
        logger.error(f"[Node] send_replies_node 실패: {e}")
        return {
            "current_step": "send_failed",
            "errors": state.get("errors", []) + [str(e)]
        }


def summarize_emails_node(state: EmailProcessingState) -> Dict:
    """
    Step 5: n8n SummarizeEmailAgent 호출
    """
    logger.info(f"[Node] summarize_emails_node 시작")

    try:
        # n8n 워크플로우 호출
        result = n8n_tools.summarize_emails(
            email_ids=state.get("email_ids")
        )

        return {
            "summary": result.get("summary", ""),
            "current_step": "summarized"
        }

    except Exception as e:
        logger.error(f"[Node] summarize_emails_node 실패: {e}")
        return {
            "summary": None,
            "current_step": "summarize_failed",
            "errors": state.get("errors", []) + [str(e)]
        }


# ========== Conditional Edge ==========

def should_generate_replies(state: EmailProcessingState) -> str:
    """
    답변 생성 여부 결정
    """
    if len(state.get("important_emails", [])) > 0:
        logger.info("[Edge] 중요한 이메일 있음 → 답변 생성")
        return "generate_replies"
    else:
        logger.info("[Edge] 중요한 이메일 없음 → 종료")
        return "end"


def should_send_replies(state: EmailProcessingState) -> str:
    """
    답변 발송 여부 결정 (사용자 승인 있을 때만)
    """
    if len(state.get("approved_replies", [])) > 0:
        logger.info("[Edge] 승인된 답변 있음 → 발송")
        return "send_replies"
    else:
        logger.info("[Edge] 승인된 답변 없음 → 종료")
        return "end"


# ========== Graph 구성 ==========

def create_email_processing_graph():
    """이메일 처리 그래프 생성"""

    workflow = StateGraph(EmailProcessingState)

    # 노드 추가
    workflow.add_node("fetch_emails", fetch_emails_node)
    workflow.add_node("classify_emails", classify_emails_node)
    workflow.add_node("generate_replies", generate_replies_node)
    workflow.add_node("send_replies", send_replies_node)

    # 엣지 추가
    workflow.set_entry_point("fetch_emails")
    workflow.add_edge("fetch_emails", "classify_emails")

    # 조건부 엣지: 중요한 이메일 있으면 답변 생성
    workflow.add_conditional_edges(
        "classify_emails",
        should_generate_replies,
        {
            "generate_replies": "generate_replies",
            "end": END
        }
    )

    # 조건부 엣지: 승인된 답변 있으면 발송
    workflow.add_conditional_edges(
        "generate_replies",
        should_send_replies,
        {
            "send_replies": "send_replies",
            "end": END
        }
    )

    workflow.add_edge("send_replies", END)

    return workflow.compile()


def create_daily_summary_graph():
    """일일 요약 그래프 생성"""

    workflow = StateGraph(EmailProcessingState)

    # 노드 추가
    workflow.add_node("summarize_emails", summarize_emails_node)

    # 간단한 그래프
    workflow.set_entry_point("summarize_emails")
    workflow.add_edge("summarize_emails", END)

    return workflow.compile()


# ========== EmailProcessor 클래스 ==========

class EmailProcessor:
    """
    LangGraph Supervisor Agent

    n8n 기본 에이전트들을 orchestration하여 이메일 처리
    """

    def __init__(self):
        self.email_processing_graph = create_email_processing_graph()
        self.daily_summary_graph = create_daily_summary_graph()

    def process_new_emails(self) -> Dict:
        """
        새 이메일 처리 워크플로우

        Returns:
            {
                "email_ids": [1, 2, 3],
                "classifications": [...],
                "important_emails": [1, 3],
                "reply_drafts": {...},
                "current_step": "replies_generated"
            }
        """
        logger.info("[Supervisor] process_new_emails 시작")

        initial_state: EmailProcessingState = {
            "task": "process_new_emails",
            "email_ids": [],
            "emails": [],
            "classifications": [],
            "important_emails": [],
            "reply_drafts": {},
            "approved_replies": [],
            "summary": None,
            "current_step": "init",
            "errors": []
        }

        final_state = self.email_processing_graph.invoke(initial_state)

        logger.info(f"[Supervisor] process_new_emails 완료: {final_state['current_step']}")

        return final_state

    def generate_daily_summary(self) -> Dict:
        """
        일일 요약 생성 워크플로우

        Returns:
            {
                "summary": "...",
                "current_step": "summarized"
            }
        """
        logger.info("[Supervisor] generate_daily_summary 시작")

        initial_state: EmailProcessingState = {
            "task": "daily_summary",
            "email_ids": [],
            "emails": [],
            "classifications": [],
            "important_emails": [],
            "reply_drafts": {},
            "approved_replies": [],
            "summary": None,
            "current_step": "init",
            "errors": []
        }

        final_state = self.daily_summary_graph.invoke(initial_state)

        logger.info(f"[Supervisor] generate_daily_summary 완료")

        return final_state

    def analyze_single_email(self, email_id: int) -> Dict:
        """
        단일 이메일 분석 워크플로우 (n8n을 통해 Gemini 호출)

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
                    "key_points": [...]
                }
            }
        """
        logger.info(f"[Supervisor] analyze_single_email 시작: email_id={email_id}")

        try:
            # n8n_tools를 통해 분석 (n8n → Gemini)
            result = n8n_tools.analyze_email(email_id)

            logger.info(f"[Supervisor] analyze_single_email 완료: {result.get('analysis', {}).get('email_type')}")

            return result

        except Exception as e:
            logger.error(f"[Supervisor] analyze_single_email 실패: {e}")
            return {
                "success": False,
                "email_id": email_id,
                "error": str(e)
            }

    def analyze_multiple_emails(self, email_ids: List[int]) -> Dict:
        """
        여러 이메일 분석 워크플로우 (n8n을 통해 Gemini 호출)

        Args:
            email_ids: 분석할 이메일 ID 리스트

        Returns:
            {
                "total": 10,
                "results": [
                    {"email_id": 1, "success": true, "analysis": {...}},
                    {"email_id": 2, "success": true, "analysis": {...}}
                ]
            }
        """
        logger.info(f"[Supervisor] analyze_multiple_emails 시작: {len(email_ids)}개 이메일")

        results = []

        for email_id in email_ids:
            try:
                result = n8n_tools.analyze_email(email_id)
                results.append({
                    "email_id": email_id,
                    "success": result.get("success", True),
                    "analysis": result.get("analysis", {})
                })
                logger.info(f"[Supervisor] 이메일 {email_id} 분석 완료")

            except Exception as e:
                logger.error(f"[Supervisor] 이메일 {email_id} 분석 실패: {e}")
                results.append({
                    "email_id": email_id,
                    "success": False,
                    "error": str(e)
                })

        logger.info(f"[Supervisor] analyze_multiple_emails 완료: 성공={sum(1 for r in results if r['success'])}, 실패={sum(1 for r in results if not r['success'])}")

        return {
            "total": len(email_ids),
            "results": results
        }


# 전역 인스턴스
email_processor = EmailProcessor()
