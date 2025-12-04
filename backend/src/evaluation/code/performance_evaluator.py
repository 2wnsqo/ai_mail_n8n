"""
AI Email Assistant 성능 평가 시스템

이메일 분석, 답변 생성, 요약 품질을 측정하고 시각화합니다.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class AnalysisEvaluation:
    """이메일 분석 평가 결과"""
    email_id: int
    email_type_score: float  # 0-25
    importance_score_accuracy: float  # 0-25
    needs_reply_score: float  # 0-25
    sentiment_score: float  # 0-25
    total_score: float  # 0-100
    evaluation_notes: str = ""


@dataclass
class ReplyEvaluation:
    """답변 생성 평가 결과"""
    email_id: int
    context_understanding: float  # 0-25
    tone_consistency: float  # 0-25
    response_appropriateness: float  # 0-25
    korean_naturalness: float  # 0-25
    total_score: float  # 0-100
    evaluation_notes: str = ""


@dataclass
class SummaryEvaluation:
    """요약 평가 결과"""
    summary_date: str
    information_completeness: float  # 0-30
    conciseness: float  # 0-20
    accuracy: float  # 0-30
    readability: float  # 0-20
    total_score: float  # 0-100
    evaluation_notes: str = ""


class PerformanceEvaluator:
    """성능 평가 클래스"""

    def __init__(self):
        self.analysis_results: List[AnalysisEvaluation] = []
        self.reply_results: List[ReplyEvaluation] = []
        self.summary_results: List[SummaryEvaluation] = []

    # ========== 이메일 분석 평가 ==========

    def evaluate_analysis(
        self,
        email_id: int,
        ai_result: Dict,
        ground_truth: Dict
    ) -> AnalysisEvaluation:
        """
        이메일 분석 결과를 평가합니다.

        Args:
            email_id: 이메일 ID
            ai_result: AI 분석 결과 {email_type, importance_score, needs_reply, sentiment}
            ground_truth: 정답 데이터 (같은 형식)

        Returns:
            AnalysisEvaluation 객체
        """
        notes = []

        # 1. email_type 평가 (25점)
        email_type_score = 25 if ai_result.get('email_type') == ground_truth.get('email_type') else 0
        if email_type_score == 0:
            notes.append(f"유형 불일치: AI={ai_result.get('email_type')}, 정답={ground_truth.get('email_type')}")

        # 2. importance_score 평가 (25점) - ±2 이내면 만점, ±3이면 15점, 그 외 0점
        ai_importance = int(ai_result.get('importance_score', 0) or 0)
        gt_importance = int(ground_truth.get('importance_score', 0) or 0)
        importance_diff = abs(ai_importance - gt_importance)

        if importance_diff <= 2:
            importance_score_accuracy = 25
        elif importance_diff <= 3:
            importance_score_accuracy = 15
        else:
            importance_score_accuracy = 0
            notes.append(f"중요도 차이 큼: AI={ai_importance}, 정답={gt_importance}")

        # 3. needs_reply 평가 (25점)
        ai_needs_reply = str(ai_result.get('needs_reply', '')).lower() in ['true', '1', 'yes']
        gt_needs_reply = str(ground_truth.get('needs_reply', '')).lower() in ['true', '1', 'yes']
        needs_reply_score = 25 if ai_needs_reply == gt_needs_reply else 0
        if needs_reply_score == 0:
            notes.append(f"답변필요 불일치: AI={ai_needs_reply}, 정답={gt_needs_reply}")

        # 4. sentiment 평가 (25점)
        sentiment_score = 25 if ai_result.get('sentiment') == ground_truth.get('sentiment') else 0
        if sentiment_score == 0:
            notes.append(f"감정 불일치: AI={ai_result.get('sentiment')}, 정답={ground_truth.get('sentiment')}")

        total_score = email_type_score + importance_score_accuracy + needs_reply_score + sentiment_score

        evaluation = AnalysisEvaluation(
            email_id=email_id,
            email_type_score=email_type_score,
            importance_score_accuracy=importance_score_accuracy,
            needs_reply_score=needs_reply_score,
            sentiment_score=sentiment_score,
            total_score=total_score,
            evaluation_notes="; ".join(notes)
        )

        self.analysis_results.append(evaluation)
        return evaluation

    # ========== 답변 생성 평가 (LLM-as-Judge) ==========

    def create_reply_evaluation_prompt(
        self,
        original_email: Dict,
        generated_reply: str,
        target_tone: str
    ) -> str:
        """답변 평가를 위한 프롬프트 생성"""

        return f"""다음 이메일에 대한 AI 생성 답변을 평가해주세요.

## 원본 이메일
- 발신자: {original_email.get('sender_name', 'Unknown')} <{original_email.get('sender_address', '')}>
- 제목: {original_email.get('subject', '')}
- 본문:
{original_email.get('body_text', '')[:1000]}

## AI 생성 답변 (목표 톤: {target_tone})
{generated_reply}

## 평가 기준 (각 항목 0-25점)

1. **문맥 이해도** (0-25점): 원본 이메일의 핵심 내용을 정확히 파악했는가?
2. **톤 일관성** (0-25점): 요청된 톤({target_tone})을 잘 유지했는가?
3. **응답 적절성** (0-25점): 이메일에 대한 답변으로 적절한가? (질문에 답변, 요청 처리 등)
4. **한국어 자연스러움** (0-25점): 문법, 어휘, 경어체 사용이 자연스러운가?

## 출력 형식 (JSON)
```json
{{
    "context_understanding": <점수>,
    "tone_consistency": <점수>,
    "response_appropriateness": <점수>,
    "korean_naturalness": <점수>,
    "total_score": <총점>,
    "evaluation_notes": "<평가 의견>"
}}
```
"""

    def parse_reply_evaluation(
        self,
        email_id: int,
        llm_response: str
    ) -> ReplyEvaluation:
        """LLM 응답을 파싱하여 ReplyEvaluation 생성"""

        try:
            # JSON 블록 추출
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # JSON 블록이 없으면 전체에서 찾기
                json_str = llm_response

            data = json.loads(json_str)

            evaluation = ReplyEvaluation(
                email_id=email_id,
                context_understanding=float(data.get('context_understanding', 0)),
                tone_consistency=float(data.get('tone_consistency', 0)),
                response_appropriateness=float(data.get('response_appropriateness', 0)),
                korean_naturalness=float(data.get('korean_naturalness', 0)),
                total_score=float(data.get('total_score', 0)),
                evaluation_notes=data.get('evaluation_notes', '')
            )

            self.reply_results.append(evaluation)
            return evaluation

        except Exception as e:
            logger.error(f"답변 평가 파싱 실패: {e}")
            # 기본값 반환
            return ReplyEvaluation(
                email_id=email_id,
                context_understanding=0,
                tone_consistency=0,
                response_appropriateness=0,
                korean_naturalness=0,
                total_score=0,
                evaluation_notes=f"파싱 오류: {str(e)}"
            )

    # ========== 통계 및 시각화 ==========

    def get_analysis_statistics(self) -> Dict:
        """이메일 분석 평가 통계"""
        if not self.analysis_results:
            return {"message": "평가 데이터 없음"}

        total_scores = [r.total_score for r in self.analysis_results]

        return {
            "count": len(self.analysis_results),
            "average_score": round(statistics.mean(total_scores), 2),
            "median_score": round(statistics.median(total_scores), 2),
            "min_score": min(total_scores),
            "max_score": max(total_scores),
            "std_dev": round(statistics.stdev(total_scores), 2) if len(total_scores) > 1 else 0,
            "breakdown": {
                "email_type_avg": round(statistics.mean([r.email_type_score for r in self.analysis_results]), 2),
                "importance_avg": round(statistics.mean([r.importance_score_accuracy for r in self.analysis_results]), 2),
                "needs_reply_avg": round(statistics.mean([r.needs_reply_score for r in self.analysis_results]), 2),
                "sentiment_avg": round(statistics.mean([r.sentiment_score for r in self.analysis_results]), 2)
            }
        }

    def get_reply_statistics(self) -> Dict:
        """답변 생성 평가 통계"""
        if not self.reply_results:
            return {"message": "평가 데이터 없음"}

        total_scores = [r.total_score for r in self.reply_results]

        return {
            "count": len(self.reply_results),
            "average_score": round(statistics.mean(total_scores), 2),
            "median_score": round(statistics.median(total_scores), 2),
            "min_score": min(total_scores),
            "max_score": max(total_scores),
            "breakdown": {
                "context_understanding_avg": round(statistics.mean([r.context_understanding for r in self.reply_results]), 2),
                "tone_consistency_avg": round(statistics.mean([r.tone_consistency for r in self.reply_results]), 2),
                "response_appropriateness_avg": round(statistics.mean([r.response_appropriateness for r in self.reply_results]), 2),
                "korean_naturalness_avg": round(statistics.mean([r.korean_naturalness for r in self.reply_results]), 2)
            }
        }

    def generate_comparison_report(
        self,
        before_stats: Dict,
        after_stats: Dict,
        evaluation_type: str = "analysis"
    ) -> str:
        """개선 전후 비교 리포트 생성"""

        before_avg = before_stats.get('average_score', 0)
        after_avg = after_stats.get('average_score', 0)
        improvement = after_avg - before_avg
        improvement_pct = (improvement / before_avg * 100) if before_avg > 0 else 0

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║            {evaluation_type.upper()} 성능 개선 비교 리포트              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  📊 전체 점수 비교                                            ║
║  ┌────────────┬────────────┬────────────┬────────────┐       ║
║  │   항목     │   Before   │   After    │   개선율   │       ║
║  ├────────────┼────────────┼────────────┼────────────┤       ║
║  │ 평균 점수  │  {before_avg:>6.1f}점  │  {after_avg:>6.1f}점  │  {improvement_pct:>+6.1f}%  │       ║
║  └────────────┴────────────┴────────────┴────────────┘       ║
║                                                              ║
"""

        if 'breakdown' in before_stats and 'breakdown' in after_stats:
            report += "║  📈 항목별 상세                                              ║\n"

            for key in before_stats['breakdown'].keys():
                before_val = before_stats['breakdown'].get(key, 0)
                after_val = after_stats['breakdown'].get(key, 0)
                item_improvement = after_val - before_val

                # 시각화 바
                bar_length = int(after_val)
                bar = "█" * bar_length + "░" * (25 - bar_length)

                report += f"║  {key:<20} {bar} {after_val:>5.1f} ({item_improvement:>+5.1f}) ║\n"

        report += """║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
        return report

    def export_results(self, filepath: str):
        """결과를 JSON 파일로 내보내기"""
        data = {
            "exported_at": datetime.now().isoformat(),
            "analysis_evaluations": [asdict(r) for r in self.analysis_results],
            "reply_evaluations": [asdict(r) for r in self.reply_results],
            "summary_evaluations": [asdict(r) for r in self.summary_results],
            "statistics": {
                "analysis": self.get_analysis_statistics(),
                "reply": self.get_reply_statistics()
            }
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"평가 결과 내보내기 완료: {filepath}")


# ========== Ground Truth 생성 도우미 ==========

def create_ground_truth_template(emails: List[Dict]) -> List[Dict]:
    """Ground Truth 입력을 위한 템플릿 생성"""

    templates = []
    for email in emails:
        templates.append({
            "email_id": email.get('id'),
            "subject": email.get('subject'),
            "sender": email.get('sender_address'),
            "body_preview": email.get('body_text', '')[:200],
            "ground_truth": {
                "email_type": "",  # 채용/마케팅/공지/개인/기타
                "importance_score": 0,  # 1-10
                "needs_reply": False,  # True/False
                "sentiment": ""  # positive/neutral/negative
            }
        })

    return templates


# 싱글톤 인스턴스
evaluator = PerformanceEvaluator()
