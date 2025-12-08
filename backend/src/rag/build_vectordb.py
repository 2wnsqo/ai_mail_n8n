"""
ChromaDB 벡터 저장소 구축 스크립트

전처리된 Enron 이메일을 임베딩하여 ChromaDB에 저장합니다.

사용법:
    python -m src.rag.build_vectordb
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    print(f"필요한 패키지를 설치해주세요: pip install chromadb sentence-transformers")
    print(f"오류: {e}")
    exit(1)


# 경로 설정
RAG_DIR = Path(__file__).parent
DATA_DIR = RAG_DIR / "data"
VECTORDB_DIR = RAG_DIR / "vectordb"


class EmailVectorDBBuilder:
    """이메일 벡터 DB 빌더"""

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        """
        Args:
            model_name: 임베딩 모델 (다국어 지원 모델 사용)
        """
        print(f"🔄 임베딩 모델 로딩: {model_name}")
        self.model = SentenceTransformer(model_name)
        print("✅ 모델 로딩 완료")

        # ChromaDB 설정
        VECTORDB_DIR.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(VECTORDB_DIR),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

    def create_collection(self, name: str, reset: bool = False) -> chromadb.Collection:
        """컬렉션 생성"""
        if reset:
            try:
                self.client.delete_collection(name)
                print(f"🗑️ 기존 컬렉션 삭제: {name}")
            except:
                pass

        collection = self.client.get_or_create_collection(
            name=name,
            metadata={"description": f"Email {name} collection for RAG"}
        )
        print(f"📁 컬렉션 생성/로드: {name}")
        return collection

    def embed_texts(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """텍스트 임베딩 생성"""
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self.model.encode(batch, show_progress_bar=False)
            all_embeddings.extend(embeddings.tolist())

            if (i + batch_size) % 500 == 0:
                print(f"  임베딩 생성 중: {min(i + batch_size, len(texts))}/{len(texts)}")

        return all_embeddings

    def build_email_type_collection(self, emails: List[Dict], reset: bool = True):
        """
        이메일 유형 분류용 컬렉션 구축

        유사 이메일을 검색하여 분류에 참조
        """
        print("\n" + "=" * 50)
        print("📊 이메일 유형 분류 컬렉션 구축")
        print("=" * 50)

        collection = self.create_collection("email_classification", reset=reset)

        # 유형별로 균형있게 샘플링
        type_emails = {}
        for email in emails:
            t = email['email_type']
            if t not in type_emails:
                type_emails[t] = []
            type_emails[t].append(email)

        # 각 유형별 최대 200개 선택
        selected_emails = []
        for t, t_emails in type_emails.items():
            selected = t_emails[:200]
            selected_emails.extend(selected)
            print(f"  {t}: {len(selected)}개 선택")

        print(f"\n총 {len(selected_emails)}개 이메일 임베딩 중...")

        # 임베딩 생성
        texts = [f"{e['subject']} {e['text'][:500]}" for e in selected_emails]
        embeddings = self.embed_texts(texts)

        # ChromaDB에 저장
        ids = [e['id'] for e in selected_emails]
        metadatas = [{
            "email_type": e['email_type'],
            "importance_score": e['importance_score'],
            "needs_reply": e['needs_reply'],
            "subject": e['subject'][:100]
        } for e in selected_emails]
        documents = [e['text'][:1000] for e in selected_emails]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

        print(f"✅ 이메일 유형 컬렉션 완료: {collection.count()}개 문서")

    def build_reply_template_collection(self, emails: List[Dict], reset: bool = True):
        """
        답변 템플릿용 컬렉션 구축

        답변이 필요한 이메일과 유사 템플릿 검색용
        """
        print("\n" + "=" * 50)
        print("✍️ 답변 템플릿 컬렉션 구축")
        print("=" * 50)

        collection = self.create_collection("reply_templates", reset=reset)

        # 답변이 필요한 이메일만 선택
        reply_emails = [e for e in emails if e.get('needs_reply', False)][:500]

        if not reply_emails:
            # needs_reply가 없으면 중요도 높은 것 선택
            reply_emails = sorted(emails, key=lambda x: -x.get('importance_score', 0))[:500]

        print(f"답변 필요 이메일: {len(reply_emails)}개")

        # 임베딩 생성
        texts = [f"{e['subject']} {e['text'][:500]}" for e in reply_emails]
        embeddings = self.embed_texts(texts)

        # 저장
        ids = [e['id'] for e in reply_emails]
        metadatas = [{
            "email_type": e['email_type'],
            "importance_score": e['importance_score'],
            "subject": e['subject'][:100]
        } for e in reply_emails]
        documents = [e['text'][:1000] for e in reply_emails]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

        print(f"✅ 답변 템플릿 컬렉션 완료: {collection.count()}개 문서")

    def build_importance_collection(self, emails: List[Dict], reset: bool = True):
        """
        중요도 판단용 컬렉션 구축

        중요도 점수별 이메일 예시
        """
        print("\n" + "=" * 50)
        print("⭐ 중요도 판단 컬렉션 구축")
        print("=" * 50)

        collection = self.create_collection("email_importance", reset=reset)

        # 중요도별로 균형있게 샘플링
        importance_emails = {}
        for email in emails:
            score = email['importance_score']
            # 1-3: 낮음, 4-6: 보통, 7-10: 높음
            if score <= 3:
                level = "low"
            elif score <= 6:
                level = "medium"
            else:
                level = "high"

            if level not in importance_emails:
                importance_emails[level] = []
            importance_emails[level].append(email)

        selected_emails = []
        for level, level_emails in importance_emails.items():
            selected = level_emails[:150]
            selected_emails.extend(selected)
            print(f"  {level}: {len(selected)}개 선택")

        print(f"\n총 {len(selected_emails)}개 이메일 임베딩 중...")

        # 임베딩 생성
        texts = [f"{e['subject']} {e['text'][:500]}" for e in selected_emails]
        embeddings = self.embed_texts(texts)

        # 저장
        ids = [e['id'] for e in selected_emails]
        metadatas = [{
            "email_type": e['email_type'],
            "importance_score": e['importance_score'],
            "importance_level": "low" if e['importance_score'] <= 3 else ("medium" if e['importance_score'] <= 6 else "high"),
            "subject": e['subject'][:100]
        } for e in selected_emails]
        documents = [e['text'][:1000] for e in selected_emails]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

        print(f"✅ 중요도 컬렉션 완료: {collection.count()}개 문서")

    def verify_collections(self):
        """컬렉션 검증"""
        print("\n" + "=" * 50)
        print("🔍 컬렉션 검증")
        print("=" * 50)

        collections = self.client.list_collections()
        for col in collections:
            print(f"  - {col.name}: {col.count()}개 문서")

        # 테스트 쿼리
        print("\n📝 테스트 쿼리 실행...")

        test_query = "I need to schedule a meeting for next week"
        query_embedding = self.model.encode([test_query]).tolist()

        classification_col = self.client.get_collection("email_classification")
        results = classification_col.query(
            query_embeddings=query_embedding,
            n_results=3
        )

        print(f"  쿼리: '{test_query}'")
        print("  결과:")
        for i, (id_, metadata) in enumerate(zip(results['ids'][0], results['metadatas'][0])):
            print(f"    {i+1}. [{metadata['email_type']}] {metadata['subject'][:50]}...")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🗄️ ChromaDB 벡터 저장소 구축")
    print("=" * 60)

    # 전처리된 데이터 로드
    data_path = DATA_DIR / "enron_processed.json"

    if not data_path.exists():
        print(f"❌ 전처리된 데이터가 없습니다: {data_path}")
        print("   먼저 실행: python -m src.rag.download_dataset")
        return

    print(f"📂 데이터 로드: {data_path}")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    emails = data['emails']
    print(f"   - {len(emails)}개 이메일 로드")

    # 벡터 DB 빌더 생성
    builder = EmailVectorDBBuilder()

    # 컬렉션 구축
    builder.build_email_type_collection(emails, reset=True)
    builder.build_reply_template_collection(emails, reset=True)
    builder.build_importance_collection(emails, reset=True)

    # 검증
    builder.verify_collections()

    print("\n" + "=" * 60)
    print("✅ 벡터 저장소 구축 완료!")
    print(f"   저장 위치: {VECTORDB_DIR}")
    print("   다음 단계: RAG 서비스 테스트")
    print("=" * 60)


if __name__ == "__main__":
    main()
