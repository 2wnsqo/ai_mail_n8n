import google.generativeai as genai
from typing import Dict, Any
from ..config import settings
import json

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')

    def analyze_email(self, subject: str, body: str, sender: str) -> Dict[str, Any]:
        """
        이메일 분석 (유형, 중요도, 답변 필요 여부, 감정)
        """
        prompt = f"""
다음 이메일을 분석하고 JSON 형식으로 답변해주세요:

발신자: {sender}
제목: {subject}
본문:
{body[:1000]}

다음 형식으로 답변해주세요:
{{
    "email_type": "채용" 또는 "마케팅" 또는 "공지" 또는 "개인" 또는 "기타",
    "importance_score": 0-10 사이의 정수 (10이 가장 중요),
    "needs_reply": true 또는 false,
    "sentiment": "positive" 또는 "neutral" 또는 "negative",
    "key_points": ["핵심 내용 1", "핵심 내용 2", ...]
}}

분석 기준:
- 채용: 취업, 면접, 채용 관련
- 마케팅: 광고, 프로모션, 상품 판매
- 공지: 공식 알림, 시스템 메시지
- 개인: 개인적인 대화, 문의
- 중요도: 긴급성, 업무 관련성, 발신자 중요도 고려
"""

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            # JSON 파싱 시도
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            analysis = json.loads(result_text)
            return analysis

        except json.JSONDecodeError as e:
            # JSON 파싱 실패 시 기본값 반환
            return {
                "email_type": "기타",
                "importance_score": 5,
                "needs_reply": False,
                "sentiment": "neutral",
                "key_points": ["분석 실패"]
            }
        except Exception as e:
            raise e

    def generate_reply(self, subject: str, body: str, sender: str, tone: str = "formal") -> str:
        """
        이메일 답변 생성
        tone: formal(격식), casual(친근함), brief(간결함)
        """
        tone_instructions = {
            "formal": "격식 있고 공손한 어조로 답변을 작성해주세요.",
            "casual": "친근하고 편안한 어조로 답변을 작성해주세요.",
            "brief": "간결하고 요점만 담은 답변을 작성해주세요."
        }

        prompt = f"""
다음 이메일에 대한 답변을 작성해주세요:

발신자: {sender}
제목: {subject}
본문:
{body[:1000]}

요구사항:
- {tone_instructions.get(tone, tone_instructions['formal'])}
- 본문의 핵심 내용에 대해 답변
- 한국어로 작성
- 답변만 출력 (인사말 포함)

답변:
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            raise e

    def generate_multiple_replies(self, subject: str, body: str, sender: str) -> Dict[str, str]:
        """
        3가지 톤으로 답변 생성 (formal, casual, brief)
        """
        tones = ["formal", "casual", "brief"]
        replies = {}

        for tone in tones:
            try:
                reply = self.generate_reply(subject, body, sender, tone)
                replies[tone] = reply
            except Exception as e:
                replies[tone] = f"답변 생성 실패: {str(e)}"

        return replies

# 싱글톤 인스턴스
gemini = GeminiService()
