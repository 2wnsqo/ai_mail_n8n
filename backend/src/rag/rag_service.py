"""
Email RAG Service (Phase 3-Lite + Advanced RAG)

ChromaDB 벡터 저장소를 활용하여 이메일 분석 및 답변 생성을 개선합니다.

Phase 3-Lite 개선사항:
- 프롬프트 간소화 (복잡한 CoT, Negative Examples 제거)
- "기타" 카테고리 명확화 (자동 알림 메일 분류 개선)
- 중요도 앵커링 균형 조정 (낮은 점수 강화)
- Few-shot 예시 최적화

Advanced RAG 고도화 (Phase 4):
1. 유사도 임계값 (Distance Threshold) - 관련없는 결과 필터링
2. 하이브리드 검색 (Vector + BM25) - 의미 + 키워드 검색 결합
3. Cross-Encoder Reranking - 2단계 정밀 재순위
4. MMR (Maximal Marginal Relevance) - 관련성 + 다양성 균형
"""

import os
import re
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging
import numpy as np

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer, CrossEncoder
except ImportError as e:
    raise ImportError(f"RAG 패키지를 설치해주세요: pip install chromadb sentence-transformers. 오류: {e}")

# BM25 (선택적 - 없으면 하이브리드 검색 비활성화)
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logging.warning("rank_bm25를 설치하면 하이브리드 검색을 사용할 수 있습니다: pip install rank-bm25")

logger = logging.getLogger(__name__)

# 경로 설정
RAG_DIR = Path(__file__).parent
VECTORDB_DIR = RAG_DIR / "vectordb"


# ============================================================
# Advanced RAG 설정 클래스
# ============================================================

@dataclass
class AdvancedRAGConfig:
    """
    Advanced RAG 검색 설정

    4가지 고도화 기법의 파라미터를 관리합니다.
    """
    # 1. 유사도 임계값 (Distance Threshold)
    # 참고: L2 distance 범위는 임베딩 모델과 데이터에 따라 다름
    # - paraphrase-multilingual-MiniLM-L12-v2 + Enron: 8~15 범위
    # - 한국어 이메일 데이터는 더 낮은 거리값 예상
    use_threshold: bool = True
    distance_threshold: float = 12.0  # L2 distance, 낮을수록 더 유사 (Enron 데이터 기준)

    # 2. 하이브리드 검색 (Vector + BM25)
    use_hybrid: bool = True
    vector_weight: float = 0.7  # 벡터 검색 가중치
    bm25_weight: float = 0.3    # BM25 검색 가중치

    # 3. Cross-Encoder Reranking
    use_reranking: bool = True
    rerank_top_k: int = 10      # 재순위 대상 후보 수
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # 4. MMR (Maximal Marginal Relevance)
    use_mmr: bool = True
    mmr_lambda: float = 0.7     # 관련성 vs 다양성 (1.0=관련성만, 0.0=다양성만)

    # 일반 설정
    final_top_k: int = 3        # 최종 반환 결과 수


# 기본 설정 (모든 고도화 기법 활성화)
DEFAULT_RAG_CONFIG = AdvancedRAGConfig()

# 빠른 검색용 설정 (임계값만 사용)
FAST_RAG_CONFIG = AdvancedRAGConfig(
    use_threshold=True,
    use_hybrid=False,
    use_reranking=False,
    use_mmr=False
)

# 고품질 검색용 설정 (모든 기법 + 높은 후보 수)
QUALITY_RAG_CONFIG = AdvancedRAGConfig(
    use_threshold=True,
    distance_threshold=15.0,  # Enron 데이터 기준 조정
    use_hybrid=True,
    use_reranking=True,
    rerank_top_k=15,
    use_mmr=True,
    mmr_lambda=0.6,
    final_top_k=5
)

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

        # Advanced RAG: Cross-Encoder (지연 로딩)
        self._cross_encoder = None
        self._cross_encoder_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"

        # Advanced RAG: BM25 인덱스 캐시
        self._bm25_indices = {}  # {collection_name: (BM25Okapi, documents)}

        # 기본 RAG 설정
        self.config = DEFAULT_RAG_CONFIG

        logger.info("EmailRAGService 초기화됨 (Advanced RAG 지원)")

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

    @property
    def cross_encoder(self) -> CrossEncoder:
        """Cross-Encoder 모델 (지연 로딩) - Reranking용"""
        if self._cross_encoder is None:
            logger.info(f"Cross-Encoder 모델 로딩: {self._cross_encoder_model}")
            self._cross_encoder = CrossEncoder(self._cross_encoder_model)
        return self._cross_encoder

    def set_config(self, config: AdvancedRAGConfig):
        """RAG 설정 변경"""
        self.config = config
        logger.info(f"RAG 설정 변경: threshold={config.use_threshold}, "
                   f"hybrid={config.use_hybrid}, reranking={config.use_reranking}, "
                   f"mmr={config.use_mmr}")

    # ============================================================
    # Advanced RAG: 4가지 고도화 메서드
    # ============================================================

    def _build_bm25_index(self, collection_name: str) -> Optional[Tuple]:
        """
        BM25 인덱스 빌드 (하이브리드 검색용)

        Args:
            collection_name: 컬렉션 이름

        Returns:
            (BM25Okapi, documents, ids) 튜플 또는 None
        """
        if not BM25_AVAILABLE:
            return None

        if collection_name in self._bm25_indices:
            return self._bm25_indices[collection_name]

        collection = self.get_collection(collection_name)
        if collection is None:
            return None

        try:
            # 컬렉션의 모든 문서 가져오기
            all_data = collection.get()
            documents = all_data['documents']
            ids = all_data['ids']

            if not documents:
                return None

            # 토큰화 (한국어 + 영어 지원)
            tokenized_docs = [self._tokenize(doc) for doc in documents]

            # BM25 인덱스 빌드
            bm25 = BM25Okapi(tokenized_docs)

            self._bm25_indices[collection_name] = (bm25, documents, ids)
            logger.info(f"BM25 인덱스 빌드 완료: {collection_name} ({len(documents)}개 문서)")

            return self._bm25_indices[collection_name]

        except Exception as e:
            logger.error(f"BM25 인덱스 빌드 실패: {e}")
            return None

    def _tokenize(self, text: str) -> List[str]:
        """
        텍스트 토큰화 (한국어 + 영어 지원)

        Args:
            text: 토큰화할 텍스트

        Returns:
            토큰 리스트
        """
        # 소문자 변환 및 특수문자 제거
        text = text.lower()
        text = re.sub(r'[^\w\s가-힣]', ' ', text)
        # 공백으로 분리
        tokens = text.split()
        # 2글자 이상만
        return [t for t in tokens if len(t) >= 2]

    def _apply_threshold(
        self,
        results: List[Dict],
        threshold: float
    ) -> List[Dict]:
        """
        1. 유사도 임계값 적용 - 관련없는 결과 필터링

        Args:
            results: 검색 결과 리스트
            threshold: 거리 임계값 (L2 distance)

        Returns:
            임계값 이하의 결과만 필터링된 리스트
        """
        filtered = [r for r in results if r.get('distance', float('inf')) <= threshold]
        logger.debug(f"임계값 필터링: {len(results)} → {len(filtered)} (threshold={threshold})")
        return filtered

    def _hybrid_search(
        self,
        query: str,
        collection_name: str,
        n_results: int,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3
    ) -> List[Dict]:
        """
        2. 하이브리드 검색 (Vector + BM25)

        벡터 의미 검색과 BM25 키워드 검색을 결합합니다.

        Args:
            query: 검색 쿼리
            collection_name: 컬렉션 이름
            n_results: 반환할 결과 수
            vector_weight: 벡터 검색 가중치
            bm25_weight: BM25 검색 가중치

        Returns:
            하이브리드 점수로 정렬된 결과 리스트
        """
        # 벡터 검색
        vector_results = self.search_similar_emails(
            query, collection_name, n_results=n_results * 2
        )

        if not BM25_AVAILABLE:
            logger.debug("BM25 비활성화 - 벡터 검색만 사용")
            return vector_results[:n_results]

        # BM25 인덱스
        bm25_data = self._build_bm25_index(collection_name)
        if bm25_data is None:
            return vector_results[:n_results]

        bm25, documents, ids = bm25_data

        # BM25 검색
        tokenized_query = self._tokenize(query)
        bm25_scores = bm25.get_scores(tokenized_query)

        # 정규화 (0-1 범위)
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
        bm25_scores_norm = bm25_scores / max_bm25

        # 벡터 점수 정규화 (distance → similarity)
        vector_scores = {}
        for r in vector_results:
            # L2 distance를 similarity로 변환 (1 / (1 + distance))
            similarity = 1 / (1 + r['distance'])
            vector_scores[r['id']] = {
                'similarity': similarity,
                'data': r
            }

        # BM25 점수 매핑
        bm25_score_map = {ids[i]: bm25_scores_norm[i] for i in range(len(ids))}

        # 하이브리드 점수 계산
        hybrid_results = []
        seen_ids = set()

        # 벡터 결과에서 하이브리드 점수 계산
        for doc_id, v_data in vector_scores.items():
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)

            v_score = v_data['similarity']
            b_score = bm25_score_map.get(doc_id, 0)
            hybrid_score = vector_weight * v_score + bm25_weight * b_score

            result = v_data['data'].copy()
            result['hybrid_score'] = hybrid_score
            result['vector_score'] = v_score
            result['bm25_score'] = b_score
            hybrid_results.append(result)

        # 하이브리드 점수로 정렬
        hybrid_results.sort(key=lambda x: x['hybrid_score'], reverse=True)

        logger.debug(f"하이브리드 검색: {len(hybrid_results)}개 결과 (v={vector_weight}, b={bm25_weight})")
        return hybrid_results[:n_results]

    def _rerank_with_cross_encoder(
        self,
        query: str,
        results: List[Dict],
        top_k: int = 5
    ) -> List[Dict]:
        """
        3. Cross-Encoder Reranking - 정밀 재순위

        Bi-Encoder로 빠르게 후보를 추출한 후,
        Cross-Encoder로 정밀하게 재순위합니다.

        Args:
            query: 검색 쿼리
            results: 재순위할 후보 리스트
            top_k: 최종 반환할 결과 수

        Returns:
            Cross-Encoder 점수로 재순위된 결과 리스트
        """
        if not results:
            return []

        # Cross-Encoder 입력 쌍 생성
        pairs = [(query, r['text']) for r in results if r.get('text')]

        if not pairs:
            return results[:top_k]

        try:
            # Cross-Encoder 점수 계산
            ce_scores = self.cross_encoder.predict(pairs)

            # 점수 추가 및 정렬
            for i, result in enumerate(results):
                if i < len(ce_scores):
                    result['cross_encoder_score'] = float(ce_scores[i])

            reranked = sorted(
                results,
                key=lambda x: x.get('cross_encoder_score', -float('inf')),
                reverse=True
            )

            logger.debug(f"Cross-Encoder 재순위: {len(results)} → top {top_k}")
            return reranked[:top_k]

        except Exception as e:
            logger.error(f"Cross-Encoder 재순위 실패: {e}")
            return results[:top_k]

    def _apply_mmr(
        self,
        query_embedding: List[float],
        results: List[Dict],
        lambda_param: float = 0.7,
        top_k: int = 3
    ) -> List[Dict]:
        """
        4. MMR (Maximal Marginal Relevance) - 관련성 + 다양성 균형

        이미 선택된 결과와 유사한 문서는 점수를 낮춰서
        다양한 결과를 반환합니다.

        Args:
            query_embedding: 쿼리 임베딩 벡터
            results: MMR 적용할 결과 리스트
            lambda_param: 관련성 vs 다양성 (1.0=관련성만, 0.0=다양성만)
            top_k: 최종 반환할 결과 수

        Returns:
            MMR로 선택된 다양한 결과 리스트
        """
        if not results or len(results) <= top_k:
            return results[:top_k]

        # 결과 문서들의 임베딩 계산
        doc_embeddings = []
        for r in results:
            if r.get('text'):
                emb = self.embed_text(r['text'])
                doc_embeddings.append(np.array(emb))
            else:
                doc_embeddings.append(None)

        query_emb = np.array(query_embedding)
        selected = []
        selected_indices = set()

        for _ in range(min(top_k, len(results))):
            best_score = -float('inf')
            best_idx = -1

            for i, (result, doc_emb) in enumerate(zip(results, doc_embeddings)):
                if i in selected_indices or doc_emb is None:
                    continue

                # 쿼리와의 관련성 (cosine similarity)
                relevance = self._cosine_similarity(query_emb, doc_emb)

                # 이미 선택된 문서들과의 최대 유사도
                max_sim_to_selected = 0
                if selected:
                    for sel_idx in selected_indices:
                        if doc_embeddings[sel_idx] is not None:
                            sim = self._cosine_similarity(doc_emb, doc_embeddings[sel_idx])
                            max_sim_to_selected = max(max_sim_to_selected, sim)

                # MMR 점수: λ * 관련성 - (1-λ) * 기존과의 유사도
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            if best_idx >= 0:
                results[best_idx]['mmr_score'] = best_score
                selected.append(results[best_idx])
                selected_indices.add(best_idx)

        logger.debug(f"MMR 적용: {len(results)} → {len(selected)} (λ={lambda_param})")
        return selected

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """코사인 유사도 계산"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    # ============================================================
    # 통합 고급 검색 메서드
    # ============================================================

    def advanced_search(
        self,
        query: str,
        collection_name: str = "email_classification",
        config: Optional[AdvancedRAGConfig] = None
    ) -> List[Dict]:
        """
        고급 RAG 검색 (4가지 기법 통합)

        설정에 따라 다음 기법들을 순차적으로 적용합니다:
        1. 하이브리드 검색 (Vector + BM25) 또는 기본 벡터 검색
        2. 유사도 임계값 필터링
        3. Cross-Encoder 재순위
        4. MMR 다양성 적용

        Args:
            query: 검색 쿼리
            collection_name: 검색할 컬렉션
            config: RAG 설정 (None이면 기본 설정 사용)

        Returns:
            고급 검색 결과 리스트
        """
        cfg = config or self.config

        # Step 1: 초기 검색 (하이브리드 또는 벡터)
        if cfg.use_hybrid and BM25_AVAILABLE:
            results = self._hybrid_search(
                query, collection_name,
                n_results=cfg.rerank_top_k if cfg.use_reranking else cfg.final_top_k * 2,
                vector_weight=cfg.vector_weight,
                bm25_weight=cfg.bm25_weight
            )
        else:
            results = self.search_similar_emails(
                query, collection_name,
                n_results=cfg.rerank_top_k if cfg.use_reranking else cfg.final_top_k * 2
            )

        if not results:
            return []

        # Step 2: 임계값 필터링
        if cfg.use_threshold:
            results = self._apply_threshold(results, cfg.distance_threshold)

        if not results:
            return []

        # Step 3: Cross-Encoder 재순위
        if cfg.use_reranking:
            results = self._rerank_with_cross_encoder(
                query, results,
                top_k=cfg.final_top_k * 2 if cfg.use_mmr else cfg.final_top_k
            )

        # Step 4: MMR 다양성 적용
        if cfg.use_mmr and len(results) > cfg.final_top_k:
            query_embedding = self.embed_text(query)
            results = self._apply_mmr(
                query_embedding, results,
                lambda_param=cfg.mmr_lambda,
                top_k=cfg.final_top_k
            )

        return results[:cfg.final_top_k]

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
        n_examples: int = 2,
        use_advanced: bool = True
    ) -> str:
        """
        이메일 분류를 위한 RAG 컨텍스트 생성 (Phase 3-Lite + Advanced RAG)

        Args:
            email_subject: 이메일 제목
            email_body: 이메일 본문
            n_examples: 예시 수 (기본 2개로 축소)
            use_advanced: 고급 RAG 검색 사용 여부

        Returns:
            분류 참조용 컨텍스트 문자열 (간소화)
        """
        query = f"{email_subject} {email_body[:500]}"

        # Advanced RAG 또는 기본 검색
        if use_advanced:
            # 고급 검색 설정 (Enron 데이터 기준 임계값)
            search_config = AdvancedRAGConfig(
                use_threshold=True,
                distance_threshold=12.0,  # Enron 데이터 기준
                use_hybrid=BM25_AVAILABLE,
                use_reranking=True,
                rerank_top_k=8,
                use_mmr=True,
                mmr_lambda=0.7,
                final_top_k=n_examples
            )
            similar = self.advanced_search(
                query,
                collection_name="email_classification",
                config=search_config
            )
        else:
            similar = self.search_similar_emails(
                query,
                collection_name="email_classification",
                n_results=n_examples
            )

        if not similar:
            return ""

        # Phase 3-Lite: 간소화된 Few-shot 예시
        context_parts = ["## 유사 이메일 참조 (Advanced RAG)\n"]

        for i, email in enumerate(similar, 1):
            metadata = email['metadata']
            email_type = metadata.get('email_type', '기타')
            subject = metadata.get('subject', 'N/A')[:50]
            importance = metadata.get('importance_score', 5)

            # 고급 검색 점수 정보 추가
            score_info = ""
            if 'cross_encoder_score' in email:
                score_info = f" [CE:{email['cross_encoder_score']:.2f}]"
            elif 'hybrid_score' in email:
                score_info = f" [H:{email['hybrid_score']:.2f}]"

            context_parts.append(
                f"- 예시{i}: [{email_type}] \"{subject}\" (중요도 {importance}){score_info}\n"
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


    # ============================================================
    # 피드백 학습 시스템 (Phase 5)
    # ============================================================

    def add_user_feedback(
        self,
        email_id: int,
        email_subject: str,
        email_body: str,
        email_type: str,
        original_draft: str,
        final_reply: str,
        selected_tone: str,
        was_modified: bool
    ) -> bool:
        """
        사용자 피드백을 RAG DB에 추가하여 학습

        사용자가 AI 답변을 수정하거나 승인하면 해당 데이터를
        reply_templates 컬렉션에 추가하여 향후 답변 생성 시 참조합니다.

        Args:
            email_id: 원본 이메일 ID
            email_subject: 이메일 제목
            email_body: 이메일 본문
            email_type: 이메일 유형
            original_draft: AI 원본 답변
            final_reply: 최종 발송된 답변 (수정됨 또는 원본)
            selected_tone: 선택된 톤 (formal/casual/brief)
            was_modified: 사용자가 수정했는지 여부

        Returns:
            성공 여부
        """
        try:
            collection = self.get_collection("reply_templates")
            if collection is None:
                # 컬렉션이 없으면 생성
                collection = self.client.get_or_create_collection(
                    name="reply_templates",
                    metadata={"description": "Reply templates with user feedback"}
                )
                self._collections["reply_templates"] = collection

            # 피드백 ID 생성
            feedback_id = f"feedback_{email_id}_{selected_tone}"

            # 텍스트: 이메일 내용 + 답변 내용 결합
            combined_text = f"[이메일] {email_subject}\n{email_body[:500]}\n\n[답변] {final_reply}"

            # 임베딩 생성
            embedding = self.embed_text(combined_text)

            # 메타데이터
            metadata = {
                "email_id": email_id,
                "email_type": email_type,
                "subject": email_subject[:100],
                "tone": selected_tone,
                "was_modified": was_modified,
                "feedback_type": "modified" if was_modified else "accepted",
                "reply_text": final_reply[:1000],  # 답변 텍스트 저장
                "source": "user_feedback"
            }

            # ChromaDB에 추가 (기존 있으면 업데이트)
            collection.upsert(
                ids=[feedback_id],
                embeddings=[embedding],
                documents=[combined_text],
                metadatas=[metadata]
            )

            logger.info(f"피드백 학습 완료: email_id={email_id}, tone={selected_tone}, modified={was_modified}")
            return True

        except Exception as e:
            logger.error(f"피드백 학습 실패: {e}")
            return False

    def get_feedback_enhanced_reply_prompt(
        self,
        email_subject: str,
        email_body: str,
        email_type: str,
        sender_name: str = "",
        preferred_tone: str = "formal",
        n_feedback_examples: int = 2
    ) -> str:
        """
        피드백 학습 데이터를 활용한 향상된 답변 프롬프트 생성

        사용자가 과거에 수정/승인한 답변들을 참조하여
        더 사용자 스타일에 맞는 답변을 생성합니다.

        Args:
            email_subject: 이메일 제목
            email_body: 이메일 본문
            email_type: 이메일 유형
            sender_name: 발신자 이름
            preferred_tone: 선호 톤
            n_feedback_examples: 참조할 피드백 예시 수

        Returns:
            피드백 컨텍스트가 포함된 답변 프롬프트
        """
        # 기존 템플릿 검색
        templates = self.get_reply_templates(email_subject, email_body, email_type)

        # 피드백 기반 검색 (사용자가 수정/승인한 답변)
        feedback_examples = self._search_feedback_examples(
            email_subject, email_body, email_type, preferred_tone, n_feedback_examples
        )

        # 컨텍스트 구성
        template_context = ""
        if templates:
            template_context = "## 유사 이메일 참조:\n"
            for i, t in enumerate(templates[:2], 1):
                template_context += f"{i}. [{t['metadata'].get('email_type', 'N/A')}] {t['metadata'].get('subject', '')[:50]}...\n"

        feedback_context = ""
        if feedback_examples:
            feedback_context = "\n## 📚 사용자 선호 답변 스타일 (학습됨):\n"
            for i, fb in enumerate(feedback_examples, 1):
                meta = fb['metadata']
                reply_text = meta.get('reply_text', '')[:200]
                feedback_type = "✅ 승인됨" if not meta.get('was_modified') else "✏️ 수정됨"
                feedback_context += f"\n### 예시 {i} ({feedback_type}):\n"
                feedback_context += f"```\n{reply_text}...\n```\n"

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
{feedback_context}

## 답변 요청
- 어조: {tone_guide.get(preferred_tone, '격식 있는')}
- 한국어로 답변 작성
- 적절한 인사와 마무리 포함
{"- 위 사용자 선호 스타일을 참고하여 비슷한 톤과 형식으로 작성" if feedback_examples else ""}
"""
        return prompt

    def _search_feedback_examples(
        self,
        email_subject: str,
        email_body: str,
        email_type: str,
        preferred_tone: str,
        n_results: int = 2
    ) -> List[Dict]:
        """
        피드백 기반 유사 답변 검색

        Args:
            email_subject: 이메일 제목
            email_body: 이메일 본문
            email_type: 이메일 유형
            preferred_tone: 선호 톤
            n_results: 반환할 결과 수

        Returns:
            유사 피드백 예시 리스트
        """
        try:
            collection = self.get_collection("reply_templates")
            if collection is None:
                return []

            query = f"{email_subject} {email_body[:500]}"
            query_embedding = self.embed_text(query)

            # 피드백 데이터만 필터링
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results * 2,  # 필터링 고려해서 더 많이 가져옴
                where={
                    "$and": [
                        {"source": {"$eq": "user_feedback"}},
                        {"tone": {"$eq": preferred_tone}}
                    ]
                }
            )

            # 결과가 없으면 톤 필터 제거하고 재검색
            if not results['ids'][0]:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where={"source": {"$eq": "user_feedback"}}
                )

            feedback_examples = []
            for i in range(len(results['ids'][0])):
                feedback_examples.append({
                    "id": results['ids'][0][i],
                    "text": results['documents'][0][i] if results['documents'] else "",
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "distance": results['distances'][0][i] if results['distances'] else 0
                })

            return feedback_examples[:n_results]

        except Exception as e:
            logger.debug(f"피드백 검색 실패 (정상 상황일 수 있음): {e}")
            return []

    def get_feedback_statistics(self) -> Dict:
        """
        피드백 학습 통계 조회

        Returns:
            피드백 통계 딕셔너리
        """
        try:
            collection = self.get_collection("reply_templates")
            if collection is None:
                return {"total_feedback": 0, "message": "컬렉션 없음"}

            # 모든 피드백 데이터 조회
            all_data = collection.get(
                where={"source": {"$eq": "user_feedback"}}
            )

            if not all_data['ids']:
                return {"total_feedback": 0, "by_tone": {}, "by_type": {}, "modification_rate": 0}

            total = len(all_data['ids'])
            modified_count = 0
            by_tone = {}
            by_type = {}

            for meta in all_data['metadatas']:
                # 수정 여부
                if meta.get('was_modified'):
                    modified_count += 1

                # 톤별 집계
                tone = meta.get('tone', 'unknown')
                by_tone[tone] = by_tone.get(tone, 0) + 1

                # 유형별 집계
                email_type = meta.get('email_type', '기타')
                by_type[email_type] = by_type.get(email_type, 0) + 1

            return {
                "total_feedback": total,
                "accepted_count": total - modified_count,
                "modified_count": modified_count,
                "modification_rate": round(modified_count / total * 100, 1) if total > 0 else 0,
                "by_tone": by_tone,
                "by_type": by_type
            }

        except Exception as e:
            logger.error(f"피드백 통계 조회 실패: {e}")
            return {"error": str(e)}


# 전역 인스턴스
email_rag_service = EmailRAGService()
