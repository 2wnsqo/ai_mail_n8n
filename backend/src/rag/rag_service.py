"""
Email RAG Service (Phase 3-Lite - Simplified Prompt Engineering)

ChromaDB 벡터 저장소를 활용하여 이메일 분석 및 답변 생성을 개선합니다.

Phase 3-Lite 개선사항:
- 프롬프트 간소화 (복잡한 CoT, Negative Examples 제거)
- "기타" 카테고리 명확화 (자동 알림 메일 분류 개선)
- 중요도 앵커링 균형 조정 (낮은 점수 강화)
- Few-shot 예시 최적화
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    raise ImportError(f"RAG 패키지를 설치해주세요: pip install chromadb sentence-transformers. 오류: {e}")

logger = logging.getLogger(__name__)

# 경로 설정
RAG_DIR = Path(__file__).parent
VECTORDB_DIR = RAG_DIR / "vectordb"

# ============================================================
# 프롬프트 엔지니어링 상수 정의
# ============================================================

# 이메일 유형별 키워드 및 판단 근거 (Phase 3-Lite: 기타 카테고리 강화)
EMAIL_TYPE_PATTERNS = {
    "채용": {
        "keywords": ["면접", "채용", "지원", "입사", "이력서", "합격", "불합격", "서류", "recruit", "interview", "resume", "job", "position", "hire"],
        "reasoning": "채용 프로세스 관련 키워드 포함 → 인사/채용 업무",
        "priority": 2  # 높은 우선순위
    },
    "마케팅": {
        "keywords": ["할인", "프로모션", "세일", "구독", "뉴스레터", "광고", "이벤트", "쿠폰", "무료", "혜택", "sale", "discount", "offer", "subscribe", "promotion"],
        "reasoning": "판촉/홍보 목적의 키워드 포함 → 마케팅 콘텐츠",
        "priority": 3
    },
    "공지": {
        # Phase 3-Lite: 공지 키워드 축소 (자동 알림과 구분)
        "keywords": ["공지사항", "사내공지", "전체공지", "정책변경", "시스템점검", "서비스중단", "policy change", "system maintenance"],
        "reasoning": "조직 전체 대상 공식 안내 → 공지사항",
        "priority": 4  # 낮은 우선순위 (기타보다 먼저 체크하지만 엄격)
    },
    "개인": {
        "keywords": ["요청드립니다", "문의드립니다", "확인부탁", "검토부탁", "의견주세요", "협의", "미팅요청", "회의요청"],
        "reasoning": "특정인에게 보내는 요청/협의 → 1:1 업무 커뮤니케이션",
        "priority": 1  # 가장 높은 우선순위
    },
    "기타": {
        # Phase 3-Lite: 기타 카테고리 명확화 (자동 알림 메일 포함)
        "keywords": ["배송", "택배", "발송", "결제", "승인", "인증", "로그인", "비밀번호", "계정", "영수증",
                     "delivery", "shipped", "payment", "receipt", "verification", "password", "account",
                     "카드", "출금", "입금", "이체", "거래"],
        "reasoning": "자동 발송 알림, 시스템 알림, 거래 확인 → 기타 (정보성 메일)",
        "priority": 5  # 기본값
    }
}

# 자동 알림 메일 패턴 (기타로 분류해야 함)
AUTO_NOTIFICATION_PATTERNS = [
    "배송", "택배", "발송완료", "배달완료",  # 배송
    "결제", "승인", "거래", "출금", "입금",  # 금융
    "인증", "인증번호", "verification",  # 인증
    "비밀번호", "password", "로그인",  # 계정
    "영수증", "receipt", "내역"  # 거래 내역
]

# 중요도 기준 앵커 (Phase 3-Lite: 낮은 점수 강화)
IMPORTANCE_ANCHORS = {
    "very_low": {
        "range": "1-2",
        "description": "매우 낮음: 스팸, 광고, 자동 발송 알림(배송/결제/인증)",
        "examples": ["택배 배송 완료", "카드 결제 알림", "비밀번호 변경 완료", "뉴스레터"],
        "auto_assign_keywords": ["배송", "결제", "인증", "비밀번호", "뉴스레터"]
    },
    "low": {
        "range": "3-4",
        "description": "낮음: 정보성 알림, FYI, 긴급하지 않은 공지",
        "examples": ["시스템 업데이트 안내", "서비스 이용 안내", "주간 리포트"],
        "auto_assign_keywords": []
    },
    "medium": {
        "range": "5-6",
        "description": "보통: 일반 업무, 참조용 정보, 급하지 않은 요청",
        "examples": ["일반 업무 공유", "참고용 문서", "정기 보고서"],
        "auto_assign_keywords": []
    },
    "high": {
        "range": "7-8",
        "description": "높음: 답변/조치 필요, 기한 있음, 중요한 결정",
        "examples": ["프로젝트 마감 안내", "승인 요청", "미팅 일정 확정"],
        "auto_assign_keywords": ["마감", "승인", "확정"]
    },
    "urgent": {
        "range": "9-10",
        "description": "긴급: 즉시 대응 필요, 오늘 마감, 면접 일정",
        "examples": ["오늘 마감", "면접 일정 확정", "긴급 장애"],
        "auto_assign_keywords": ["긴급", "오늘", "즉시", "면접"]
    }
}

# 발신자 도메인 패턴
SENDER_DOMAIN_HINTS = {
    "noreply": {"type_hint": "마케팅/공지", "importance_modifier": -2},
    "newsletter": {"type_hint": "마케팅", "importance_modifier": -3},
    "support": {"type_hint": "공지/개인", "importance_modifier": 0},
    "hr": {"type_hint": "채용", "importance_modifier": +2},
    "recruit": {"type_hint": "채용", "importance_modifier": +2},
    "ceo": {"type_hint": "개인", "importance_modifier": +3},
    "admin": {"type_hint": "공지", "importance_modifier": +1},
}


class EmailRAGService:
    """
    이메일 RAG 서비스

    벡터 유사도 검색을 통해 이메일 분석 품질을 향상시킵니다.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """싱글톤 패턴"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        """
        Args:
            model_name: 임베딩 모델 (다국어 지원)
        """
        if self._initialized:
            return

        self.model_name = model_name
        self._model = None
        self._client = None
        self._collections = {}
        self._initialized = True

        logger.info("EmailRAGService 초기화됨")

    @property
    def model(self) -> SentenceTransformer:
        """임베딩 모델 (지연 로딩)"""
        if self._model is None:
            logger.info(f"임베딩 모델 로딩: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def client(self) -> chromadb.PersistentClient:
        """ChromaDB 클라이언트 (지연 로딩)"""
        if self._client is None:
            if not VECTORDB_DIR.exists():
                logger.warning(f"VectorDB 디렉토리가 없습니다: {VECTORDB_DIR}")
                VECTORDB_DIR.mkdir(parents=True, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=str(VECTORDB_DIR),
                settings=Settings(anonymized_telemetry=False)
            )
        return self._client

    def get_collection(self, name: str) -> Optional[chromadb.Collection]:
        """컬렉션 가져오기"""
        if name not in self._collections:
            try:
                self._collections[name] = self.client.get_collection(name)
            except Exception as e:
                logger.warning(f"컬렉션 '{name}'을 찾을 수 없습니다: {e}")
                return None
        return self._collections[name]

    def is_ready(self) -> bool:
        """RAG 서비스 준비 상태 확인"""
        try:
            collections = self.client.list_collections()
            required = ["email_classification", "reply_templates", "email_importance"]
            existing = [c.name for c in collections]
            return all(c in existing for c in required)
        except Exception:
            return False

    def embed_text(self, text: str) -> List[float]:
        """텍스트를 벡터로 변환"""
        return self.model.encode([text]).tolist()[0]

    # ============================================================
    # Phase 3: 프롬프트 엔지니어링 헬퍼 함수들
    # ============================================================

    def _get_type_reasoning(self, email_type: str, subject: str, body: str = "") -> str:
        """
        이메일 유형 분류에 대한 판단 근거 생성 (Few-shot Reasoning)

        Args:
            email_type: 분류된 이메일 유형
            subject: 이메일 제목
            body: 이메일 본문 (선택)

        Returns:
            판단 근거 문자열
        """
        text = f"{subject} {body[:200]}".lower()

        if email_type not in EMAIL_TYPE_PATTERNS:
            return "일반 이메일 패턴"

        pattern = EMAIL_TYPE_PATTERNS[email_type]
        matched_keywords = []

        for keyword in pattern["keywords"]:
            if keyword.lower() in text:
                matched_keywords.append(keyword)

        if matched_keywords:
            keywords_str = ", ".join(matched_keywords[:3])
            return f"키워드 '{keywords_str}' 감지 → {pattern['reasoning']}"

        return pattern["reasoning"]

    def _get_importance_reasoning(self, score: int, subject: str, sender: str = "") -> str:
        """
        중요도 점수에 대한 판단 근거 생성 (Phase 3-Lite: 5단계 레벨)

        Args:
            score: 중요도 점수 (1-10)
            subject: 이메일 제목
            sender: 발신자 정보

        Returns:
            판단 근거 문자열
        """
        # Phase 3-Lite: 5단계 중요도 레벨
        if score <= 2:
            level = "very_low"
        elif score <= 4:
            level = "low"
        elif score <= 6:
            level = "medium"
        elif score <= 8:
            level = "high"
        else:
            level = "urgent"

        anchor = IMPORTANCE_ANCHORS[level]
        return f"{anchor['description'].split(':')[0]} ({score}점)"

    def _analyze_sender_pattern(self, sender_address: str) -> Dict:
        """
        발신자 주소 패턴 분석

        Args:
            sender_address: 발신자 이메일 주소

        Returns:
            분석 결과 딕셔너리
        """
        result = {
            "type_hint": None,
            "importance_modifier": 0,
            "is_noreply": False,
            "domain": ""
        }

        if not sender_address:
            return result

        sender_lower = sender_address.lower()

        # 도메인 추출
        if "@" in sender_lower:
            result["domain"] = sender_lower.split("@")[1]

        # noreply 체크
        if "noreply" in sender_lower or "no-reply" in sender_lower:
            result["is_noreply"] = True
            result["importance_modifier"] = -2

        # 패턴 매칭
        for pattern, hints in SENDER_DOMAIN_HINTS.items():
            if pattern in sender_lower:
                result["type_hint"] = hints["type_hint"]
                result["importance_modifier"] = hints["importance_modifier"]
                break

        return result

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """
        텍스트에서 주요 키워드 추출

        Args:
            text: 분석할 텍스트
            max_keywords: 최대 키워드 수

        Returns:
            키워드 리스트
        """
        # 모든 유형의 키워드 수집
        all_keywords = []
        for patterns in EMAIL_TYPE_PATTERNS.values():
            all_keywords.extend(patterns["keywords"])

        text_lower = text.lower()
        found_keywords = []

        for keyword in all_keywords:
            if keyword.lower() in text_lower and keyword not in found_keywords:
                found_keywords.append(keyword)
                if len(found_keywords) >= max_keywords:
                    break

        return found_keywords

    def search_similar_emails(
        self,
        query_text: str,
        collection_name: str = "email_classification",
        n_results: int = 5,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        유사 이메일 검색

        Args:
            query_text: 검색할 이메일 텍스트
            collection_name: 검색할 컬렉션
            n_results: 반환할 결과 수
            filter_metadata: 메타데이터 필터

        Returns:
            유사 이메일 리스트 [{id, text, metadata, distance}, ...]
        """
        collection = self.get_collection(collection_name)
        if collection is None:
            logger.warning(f"컬렉션 없음: {collection_name}")
            return []

        try:
            query_embedding = self.embed_text(query_text)

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=filter_metadata
            )

            similar_emails = []
            for i in range(len(results['ids'][0])):
                similar_emails.append({
                    "id": results['ids'][0][i],
                    "text": results['documents'][0][i] if results['documents'] else "",
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "distance": results['distances'][0][i] if results['distances'] else 0
                })

            return similar_emails

        except Exception as e:
            logger.error(f"유사 이메일 검색 실패: {e}")
            return []

    def get_classification_context(
        self,
        email_subject: str,
        email_body: str,
        n_examples: int = 2
    ) -> str:
        """
        이메일 분류를 위한 RAG 컨텍스트 생성 (Phase 3-Lite: 간소화)

        Args:
            email_subject: 이메일 제목
            email_body: 이메일 본문
            n_examples: 예시 수 (기본 2개로 축소)

        Returns:
            분류 참조용 컨텍스트 문자열 (간소화)
        """
        query = f"{email_subject} {email_body[:500]}"
        similar = self.search_similar_emails(
            query,
            collection_name="email_classification",
            n_results=n_examples
        )

        if not similar:
            return ""

        # Phase 3-Lite: 간소화된 Few-shot 예시
        context_parts = ["## 유사 이메일 참조\n"]

        for i, email in enumerate(similar, 1):
            metadata = email['metadata']
            email_type = metadata.get('email_type', '기타')
            subject = metadata.get('subject', 'N/A')[:50]
            importance = metadata.get('importance_score', 5)

            context_parts.append(
                f"- 예시{i}: [{email_type}] \"{subject}\" (중요도 {importance})\n"
            )

        return "\n".join(context_parts)

    def get_importance_context(
        self,
        email_subject: str,
        email_body: str,
        n_examples: int = 3
    ) -> Tuple[str, List[int]]:
        """
        중요도 판단을 위한 RAG 컨텍스트 생성 (Phase 3: Anchoring 기법 적용)

        Args:
            email_subject: 이메일 제목
            email_body: 이메일 본문
            n_examples: 예시 수

        Returns:
            (컨텍스트 문자열, 유사 이메일들의 중요도 점수 리스트)
        """
        query = f"{email_subject} {email_body[:500]}"
        similar = self.search_similar_emails(
            query,
            collection_name="email_importance",
            n_results=n_examples
        )

        # Phase 3: 중요도 기준 앵커 포인트 추가
        context_parts = [
            "## 중요도 판단 기준 (Anchoring)\n",
            "다음 기준에 따라 중요도를 판단하세요:\n"
        ]

        # 앵커 포인트 추가
        for level, anchor in IMPORTANCE_ANCHORS.items():
            examples_str = ", ".join(anchor["examples"][:2])
            context_parts.append(
                f"- **{anchor['range']}점**: {anchor['description']}\n"
                f"  예시: {examples_str}\n"
            )

        if not similar:
            return "\n".join(context_parts), []

        scores = []
        context_parts.append("\n## 유사 이메일 중요도 참조\n")

        for i, email in enumerate(similar, 1):
            metadata = email['metadata']
            score = metadata.get('importance_score', 5)
            scores.append(score)
            subject = metadata.get('subject', 'N/A')[:50]
            level = metadata.get('importance_level', 'medium')

            # 판단 근거 생성
            reasoning = self._get_importance_reasoning(score, subject)

            context_parts.append(
                f"- **{score}/10** [{level}]: {subject}\n"
                f"  └ 근거: {reasoning}\n"
            )

        # 유사 이메일 기반 추천 범위
        if scores:
            avg_score = sum(scores) / len(scores)
            min_score = min(scores)
            max_score = max(scores)
            context_parts.append(
                f"\n**참고**: 유사 이메일 평균 {avg_score:.1f}점 (범위: {min_score}-{max_score}점)"
            )

        return "\n".join(context_parts), scores

    def get_reply_templates(
        self,
        email_subject: str,
        email_body: str,
        email_type: Optional[str] = None,
        n_templates: int = 3
    ) -> List[Dict]:
        """
        답변 생성을 위한 템플릿 검색

        Args:
            email_subject: 이메일 제목
            email_body: 이메일 본문
            email_type: 이메일 유형 필터
            n_templates: 템플릿 수

        Returns:
            유사 템플릿 리스트
        """
        query = f"{email_subject} {email_body[:500]}"

        filter_metadata = None
        if email_type:
            filter_metadata = {"email_type": email_type}

        return self.search_similar_emails(
            query,
            collection_name="reply_templates",
            n_results=n_templates,
            filter_metadata=filter_metadata
        )

    def _is_auto_notification(self, subject: str, body: str) -> bool:
        """
        자동 알림 메일 여부 판단 (Phase 3-Lite)

        Args:
            subject: 이메일 제목
            body: 이메일 본문

        Returns:
            자동 알림 메일이면 True
        """
        text = f"{subject} {body[:300]}".lower()
        return any(pattern in text for pattern in AUTO_NOTIFICATION_PATTERNS)

    def get_enhanced_analysis_prompt(
        self,
        email_subject: str,
        email_body: str,
        sender_name: str = "",
        sender_address: str = ""
    ) -> str:
        """
        RAG로 강화된 분석 프롬프트 생성 (Phase 3-Lite: 간소화)

        Phase 3-Lite 개선:
        - 프롬프트 길이 축소 (복잡한 CoT, Negative Examples 제거)
        - 자동 알림 메일 분류 개선 (기타 + 낮은 중요도)
        - 핵심 정보만 포함

        Args:
            email_subject: 이메일 제목
            email_body: 이메일 본문
            sender_name: 발신자 이름
            sender_address: 발신자 주소

        Returns:
            RAG 컨텍스트가 포함된 간소화된 분석 프롬프트
        """
        # 자동 알림 메일 체크
        is_auto = self._is_auto_notification(email_subject, email_body)

        # RAG 컨텍스트 (간소화)
        classification_context = self.get_classification_context(email_subject, email_body, n_examples=2)

        # 중요도 기준 (간소화)
        importance_guide = self._generate_importance_guide_lite()

        # 자동 알림 힌트
        auto_hint = ""
        if is_auto:
            auto_hint = """
⚠️ **자동 알림 감지**: 배송/결제/인증 관련 자동 발송 메일로 판단됩니다.
→ 유형: **기타**, 중요도: **1-3점**, 답변필요: **false**"""

        # noreply 체크
        noreply_hint = ""
        if sender_address and ("noreply" in sender_address.lower() or "no-reply" in sender_address.lower()):
            noreply_hint = "\n📌 noreply 발신자 → 자동 발송 메일일 가능성 높음"

        prompt = f"""이메일을 분석하여 JSON으로 응답하세요.

## 분석 대상
- **제목**: {email_subject}
- **발신자**: {sender_name} <{sender_address}>{noreply_hint}
- **본문**:
{email_body[:1000]}
{auto_hint}

## 분류 기준

### 이메일 유형 (email_type)
- **채용**: 면접, 입사, 채용, 이력서 관련
- **마케팅**: 할인, 프로모션, 광고, 뉴스레터
- **공지**: 조직 전체 대상 공식 안내 (사내공지, 정책변경)
- **개인**: 특정인에게 보내는 요청, 문의, 협의
- **기타**: 자동 알림(배송/결제/인증), 시스템 알림, 위 4개에 해당 안 됨

### 중요도 (importance_score)
{importance_guide}

{classification_context}

## 출력 (JSON만)
```json
{{
    "email_type": "채용|마케팅|공지|개인|기타",
    "importance_score": 1-10,
    "needs_reply": true|false,
    "sentiment": "positive|negative|neutral",
    "key_points": ["핵심1", "핵심2"]
}}
```"""

        return prompt

    def _generate_importance_guide_lite(self) -> str:
        """Phase 3-Lite: 간소화된 중요도 가이드"""
        return """- **1-2점**: 자동 알림(배송완료, 결제알림, 비밀번호변경), 스팸, 광고
- **3-4점**: 정보성 안내, 뉴스레터, FYI
- **5-6점**: 일반 업무, 참조용 정보
- **7-8점**: 답변/조치 필요, 기한 있음
- **9-10점**: 긴급, 면접일정, 오늘 마감"""

    def _generate_type_criteria(self) -> str:
        """이메일 유형별 분류 기준 생성"""
        criteria_parts = ["## 이메일 유형별 분류 기준\n"]

        for email_type, patterns in EMAIL_TYPE_PATTERNS.items():
            if patterns["keywords"]:
                keywords_sample = ", ".join(patterns["keywords"][:5])
                criteria_parts.append(
                    f"### {email_type}\n"
                    f"- **키워드**: {keywords_sample}\n"
                    f"- **판단 기준**: {patterns['reasoning']}\n"
                )

        return "\n".join(criteria_parts)

    def _generate_negative_examples(self) -> str:
        """잘못된 분류 방지를 위한 Negative Examples 생성"""
        negative_examples = [
            "1. **채용 공고 광고** → 채용(X) → **마케팅**(O)\n"
            "   - 채용 관련 키워드가 있어도 대량 발송된 광고성 이메일은 마케팅",

            "2. **할인 쿠폰이 포함된 개인 요청** → 마케팅(X) → **개인**(O)\n"
            "   - 할인 키워드가 있어도 특정인에게 보낸 요청은 개인",

            "3. **시스템 점검 안내 (noreply)** → 기타(X) → **공지**(O)\n"
            "   - noreply 발신이어도 공식 시스템 안내는 공지",

            "4. **면접 일정 확정** → 낮은 중요도(X) → **높은 중요도 9-10**(O)\n"
            "   - 면접 일정은 시간 민감 정보로 높은 중요도 부여",

            "5. **주간 뉴스레터** → 높은 중요도(X) → **낮은 중요도 1-3**(O)\n"
            "   - 정기 뉴스레터는 긴급하지 않음"
        ]

        return "\n".join(negative_examples)

    def get_enhanced_reply_prompt(
        self,
        email_subject: str,
        email_body: str,
        email_type: str,
        sender_name: str = "",
        preferred_tone: str = "formal"
    ) -> str:
        """
        RAG로 강화된 답변 생성 프롬프트

        Args:
            email_subject: 이메일 제목
            email_body: 이메일 본문
            email_type: 이메일 유형
            sender_name: 발신자 이름
            preferred_tone: 선호 톤 (formal/casual/brief)

        Returns:
            RAG 컨텍스트가 포함된 답변 생성 프롬프트
        """
        # 유사 템플릿 검색
        templates = self.get_reply_templates(email_subject, email_body, email_type)

        template_context = ""
        if templates:
            template_context = "## 참조할 유사 이메일 패턴:\n"
            for i, t in enumerate(templates, 1):
                template_context += f"{i}. [{t['metadata'].get('email_type', 'N/A')}] {t['metadata'].get('subject', '')[:50]}...\n"

        tone_guide = {
            "formal": "격식 있고 정중한 어조",
            "casual": "친근하고 따뜻한 어조",
            "brief": "간결하고 핵심만 전달하는 어조"
        }

        prompt = f"""다음 이메일에 대한 답변을 작성해주세요.

## 원본 이메일
- 제목: {email_subject}
- 발신자: {sender_name}
- 유형: {email_type}
- 본문:
{email_body[:1500]}

{template_context}

## 답변 요청
- 어조: {tone_guide.get(preferred_tone, '격식 있는')}
- 한국어로 답변 작성
- 적절한 인사와 마무리 포함
"""
        return prompt


# 전역 인스턴스
email_rag_service = EmailRAGService()
