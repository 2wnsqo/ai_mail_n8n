"""
Email RAG Service

ChromaDB 벡터 저장소를 활용하여 이메일 분석 및 답변 생성을 개선합니다.
"""

import os
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
        n_examples: int = 3
    ) -> str:
        """
        이메일 분류를 위한 RAG 컨텍스트 생성

        유사 이메일의 분류 결과를 참조하여 프롬프트에 추가

        Args:
            email_subject: 이메일 제목
            email_body: 이메일 본문
            n_examples: 예시 수

        Returns:
            분류 참조용 컨텍스트 문자열
        """
        query = f"{email_subject} {email_body[:500]}"
        similar = self.search_similar_emails(
            query,
            collection_name="email_classification",
            n_results=n_examples
        )

        if not similar:
            return ""

        context_parts = ["다음은 유사한 이메일의 분류 예시입니다:\n"]

        for i, email in enumerate(similar, 1):
            metadata = email['metadata']
            context_parts.append(
                f"예시 {i}:\n"
                f"- 제목: {metadata.get('subject', 'N/A')}\n"
                f"- 유형: {metadata.get('email_type', 'N/A')}\n"
                f"- 중요도: {metadata.get('importance_score', 'N/A')}\n"
            )

        context_parts.append("\n위 예시를 참고하여 분류해주세요.")

        return "\n".join(context_parts)

    def get_importance_context(
        self,
        email_subject: str,
        email_body: str,
        n_examples: int = 3
    ) -> Tuple[str, List[int]]:
        """
        중요도 판단을 위한 RAG 컨텍스트 생성

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

        if not similar:
            return "", []

        scores = []
        context_parts = ["유사 이메일의 중요도 예시:\n"]

        for i, email in enumerate(similar, 1):
            metadata = email['metadata']
            score = metadata.get('importance_score', 5)
            scores.append(score)

            context_parts.append(
                f"- [{metadata.get('importance_level', 'medium')}] "
                f"중요도 {score}/10: {metadata.get('subject', 'N/A')[:50]}"
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

    def get_enhanced_analysis_prompt(
        self,
        email_subject: str,
        email_body: str,
        sender_name: str = "",
        sender_address: str = ""
    ) -> str:
        """
        RAG로 강화된 분석 프롬프트 생성

        Args:
            email_subject: 이메일 제목
            email_body: 이메일 본문
            sender_name: 발신자 이름
            sender_address: 발신자 주소

        Returns:
            RAG 컨텍스트가 포함된 분석 프롬프트
        """
        # RAG 컨텍스트 수집
        classification_context = self.get_classification_context(email_subject, email_body)
        importance_context, importance_scores = self.get_importance_context(email_subject, email_body)

        # 유사 이메일 기반 중요도 힌트
        importance_hint = ""
        if importance_scores:
            avg_score = sum(importance_scores) / len(importance_scores)
            importance_hint = f"\n(참고: 유사 이메일들의 평균 중요도는 {avg_score:.1f}점입니다)"

        prompt = f"""다음 이메일을 분석해주세요.

## 이메일 정보
- 제목: {email_subject}
- 발신자: {sender_name} <{sender_address}>
- 본문:
{email_body[:1500]}

## 참조 정보 (RAG)
{classification_context}

{importance_context}{importance_hint}

## 분석 요청
위 이메일을 분석하여 다음 JSON 형식으로 응답해주세요:
{{
    "email_type": "채용|마케팅|공지|개인|기타 중 하나",
    "importance_score": 1-10 사이의 정수,
    "needs_reply": true 또는 false,
    "sentiment": "positive|negative|neutral 중 하나",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", ...]
}}
"""
        return prompt

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
