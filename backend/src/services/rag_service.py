"""
RAG 서비스: 유사 이메일 검색 및 패턴 학습
"""
import psycopg2
from typing import List, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from ..config import settings
from .db_service import db

class RAGService:
    """유사 이메일 검색 및 답변 패턴 학습"""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 2))

    def search_similar_emails(
        self,
        email_id: int,
        limit: int = 5,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        현재 이메일과 유사한 과거 이메일 검색

        Args:
            email_id: 현재 이메일 ID
            limit: 반환할 최대 개수
            min_similarity: 최소 유사도 (0.0 ~ 1.0)

        Returns:
            유사한 이메일 리스트
        """
        # 1. 현재 이메일 조회
        current_email = db.get_email_by_id(email_id)
        if not current_email:
            return []

        # 2. 같은 유형의 과거 이메일 조회 (이미 분석된 것만)
        conn = db.get_connection()
        cur = conn.cursor()

        query = """
            SELECT id, subject, body_text, sender_name, sender_address,
                   email_type, importance_score, needs_reply,
                   ai_analysis
            FROM email
            WHERE id != %s
              AND email_type = %s
              AND email_type IS NOT NULL
              AND is_replied_to = TRUE
            ORDER BY received_at DESC
            LIMIT 50
        """

        cur.execute(query, (email_id, current_email.get('email_type', '기타')))
        past_emails = cur.fetchall()
        cur.close()
        conn.close()

        if not past_emails:
            return []

        # 3. TF-IDF 벡터화 및 유사도 계산
        current_text = f"{current_email['subject']} {current_email['body_text'][:500]}"
        past_texts = [f"{e['subject']} {e['body_text'][:500]}" for e in past_emails]

        all_texts = [current_text] + past_texts

        try:
            # TF-IDF 벡터화
            tfidf_matrix = self.vectorizer.fit_transform(all_texts)

            # 코사인 유사도 계산
            similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

            # 유사도가 높은 순으로 정렬
            similar_indices = np.argsort(similarities)[::-1]

            # 결과 생성
            results = []
            for idx in similar_indices[:limit]:
                similarity_score = float(similarities[idx])

                if similarity_score < min_similarity:
                    continue

                email_data = past_emails[idx]
                results.append({
                    'email_id': email_data['id'],
                    'subject': email_data['subject'],
                    'sender': email_data['sender_name'] or email_data['sender_address'],
                    'email_type': email_data['email_type'],
                    'importance_score': email_data['importance_score'],
                    'similarity_score': similarity_score,
                    'ai_analysis': email_data['ai_analysis']
                })

            # 4. similar_emails 테이블에 저장
            self._save_similar_emails(email_id, results)

            return results

        except Exception as e:
            print(f"[RAG] 유사 이메일 검색 실패: {e}")
            return []

    def _save_similar_emails(self, email_id: int, similar_emails: List[Dict]):
        """유사 이메일 매핑을 DB에 저장"""
        if not similar_emails:
            return

        conn = db.get_connection()
        cur = conn.cursor()

        try:
            for sim_email in similar_emails:
                cur.execute("""
                    INSERT INTO similar_emails (email_id, similar_email_id, similarity_score, similarity_method)
                    VALUES (%s, %s, %s, 'tfidf')
                    ON CONFLICT (email_id, similar_email_id) DO UPDATE
                    SET similarity_score = EXCLUDED.similarity_score
                """, (email_id, sim_email['email_id'], sim_email['similarity_score']))

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[RAG] 유사 이메일 저장 실패: {e}")
        finally:
            cur.close()
            conn.close()

    def get_reply_pattern(self, email_type: str, sender_category: str = None) -> Optional[Dict[str, Any]]:
        """
        학습된 답변 패턴 조회

        Args:
            email_type: 이메일 유형
            sender_category: 발신자 카테고리 (선택)

        Returns:
            답변 패턴 딕셔너리
        """
        conn = db.get_connection()
        cur = conn.cursor()

        query = """
            SELECT id, email_type, sender_category, reply_template,
                   preferred_tone, common_phrases, usage_count, success_rate
            FROM reply_patterns
            WHERE email_type = %s
        """

        params = [email_type]

        if sender_category:
            query += " AND sender_category = %s"
            params.append(sender_category)

        query += " ORDER BY success_rate DESC, usage_count DESC LIMIT 1"

        cur.execute(query, params)
        pattern = cur.fetchone()
        cur.close()
        conn.close()

        return pattern

    def learn_from_feedback(self, feedback_id: int):
        """
        사용자 피드백으로부터 학습

        Args:
            feedback_id: 피드백 ID
        """
        conn = db.get_connection()
        cur = conn.cursor()

        # 1. 피드백 조회
        cur.execute("""
            SELECT uf.*, e.email_type, e.sender_address
            FROM user_feedback uf
            JOIN email e ON uf.email_id = e.id
            WHERE uf.id = %s
        """, (feedback_id,))

        feedback = cur.fetchone()

        if not feedback or feedback['feedback_type'] == 'rejected':
            cur.close()
            conn.close()
            return

        # 2. 답변 패턴 업데이트 또는 생성
        email_type = feedback['email_type']

        # 기존 패턴 조회
        cur.execute("""
            SELECT id, usage_count, success_rate
            FROM reply_patterns
            WHERE email_type = %s
            LIMIT 1
        """, (email_type,))

        existing_pattern = cur.fetchone()

        if existing_pattern:
            # 기존 패턴 업데이트
            new_usage = existing_pattern['usage_count'] + 1
            new_success_rate = (
                (existing_pattern['success_rate'] * existing_pattern['usage_count'] +
                 (1.0 if feedback['feedback_type'] == 'accepted' else 0.8)) / new_usage
            )

            cur.execute("""
                UPDATE reply_patterns
                SET usage_count = %s,
                    success_rate = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_usage, new_success_rate, existing_pattern['id']))
        else:
            # 새 패턴 생성
            cur.execute("""
                INSERT INTO reply_patterns
                (email_type, reply_template, preferred_tone, usage_count, success_rate)
                VALUES (%s, %s, 'formal', 1, 1.0)
            """, (email_type, feedback['modified_draft']))

        conn.commit()
        cur.close()
        conn.close()

        print(f"[RAG] 피드백 {feedback_id}로부터 학습 완료")

    def get_past_replies_to_sender(self, sender_address: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        특정 발신자에게 보낸 과거 답변 조회

        Args:
            sender_address: 발신자 이메일
            limit: 최대 개수

        Returns:
            과거 답변 리스트
        """
        conn = db.get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT se.subject, se.reply_body, se.sent_at, e.email_type
            FROM sent_emails se
            JOIN email e ON se.original_email_id = e.id
            WHERE se.to_email = %s
              AND se.status = 'sent'
            ORDER BY se.sent_at DESC
            LIMIT %s
        """, (sender_address, limit))

        past_replies = cur.fetchall()
        cur.close()
        conn.close()

        return past_replies

# 싱글톤 인스턴스
rag_service = RAGService()
