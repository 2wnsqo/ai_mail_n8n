import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from ..config import settings

class DatabaseService:
    def __init__(self):
        self.host = settings.POSTGRES_HOST
        self.database = settings.POSTGRES_DB
        self.user = settings.POSTGRES_USER
        self.password = settings.POSTGRES_PASSWORD
        self.port = settings.POSTGRES_PORT

    def get_connection(self):
        """PostgreSQL 연결"""
        return psycopg2.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password,
            port=self.port,
            cursor_factory=RealDictCursor
        )

    def get_emails(self, limit: int = 50, offset: int = 0, analyzed_only: bool = False) -> List[Dict[str, Any]]:
        """이메일 목록 조회"""
        conn = self.get_connection()
        cur = conn.cursor()

        query = """
            SELECT * FROM email
            WHERE 1=1
        """
        if analyzed_only:
            query += " AND email_type IS NOT NULL"

        query += " ORDER BY received_at DESC LIMIT %s OFFSET %s"

        cur.execute(query, (limit, offset))
        emails = cur.fetchall()
        cur.close()
        conn.close()
        return emails

    def get_email_by_id(self, email_id: int) -> Optional[Dict[str, Any]]:
        """특정 이메일 조회"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM email WHERE id = %s", (email_id,))
        email = cur.fetchone()
        cur.close()
        conn.close()
        return email

    def get_unanalyzed_emails(self, limit: int = 10) -> List[Dict[str, Any]]:
        """미분석 이메일 조회"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM email
            WHERE email_type IS NULL
            ORDER BY received_at DESC
            LIMIT %s
        """, (limit,))
        emails = cur.fetchall()
        cur.close()
        conn.close()
        return emails

    def get_emails_by_ids(self, email_ids: List[int]) -> List[Dict[str, Any]]:
        """특정 ID 리스트의 이메일 조회"""
        if not email_ids:
            return []

        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM email
            WHERE id = ANY(%s)
            ORDER BY received_at DESC
        """, (email_ids,))
        emails = cur.fetchall()
        cur.close()
        conn.close()
        return emails

    def update_email_analysis(self, email_id: int, analysis: Dict[str, Any]) -> bool:
        """이메일 분석 결과 저장"""
        conn = self.get_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                UPDATE email
                SET email_type = %s,
                    importance_score = %s,
                    needs_reply = %s,
                    sentiment = %s,
                    ai_analysis = %s
                WHERE id = %s
            """, (
                analysis.get('email_type'),
                analysis.get('importance_score'),
                analysis.get('needs_reply'),
                analysis.get('sentiment'),
                psycopg2.extras.Json(analysis),
                email_id
            ))
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            raise e

    def get_daily_summary(self, summary_date: date = None) -> Optional[Dict[str, Any]]:
        """일일 요약 조회"""
        if summary_date is None:
            summary_date = date.today()

        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM daily_summaries
            WHERE summary_date = %s
        """, (summary_date,))
        summary = cur.fetchone()
        cur.close()
        conn.close()
        return summary

    def save_sent_email(self, email_data: Dict[str, Any]) -> int:
        """발송된 이메일 저장"""
        conn = self.get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO sent_emails
            (original_email_id, to_email, to_name, subject, reply_body, sender_name, sender_email, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            email_data.get('original_email_id'),
            email_data.get('to_email'),
            email_data.get('to_name'),
            email_data.get('subject'),
            email_data.get('reply_body'),
            email_data.get('sender_name'),
            email_data.get('sender_email'),
            email_data.get('status', 'sent')
        ))

        sent_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        return sent_id

    def mark_as_replied(self, email_id: int) -> bool:
        """이메일을 답변 완료로 표시"""
        conn = self.get_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                UPDATE email
                SET is_replied_to = TRUE
                WHERE id = %s
            """, (email_id,))
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            raise e

    # ========== 테스트용 메서드 ==========

    def insert_test_email(self, email_data: Dict[str, Any]) -> int:
        """테스트 이메일 삽입 (평가용)"""
        conn = self.get_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO email
                (id, subject, sender_name, sender_address, body_text, received_at, original_uid, is_replied_to)
                VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
                ON CONFLICT (id) DO UPDATE SET
                    subject = EXCLUDED.subject,
                    sender_name = EXCLUDED.sender_name,
                    sender_address = EXCLUDED.sender_address,
                    body_text = EXCLUDED.body_text,
                    received_at = EXCLUDED.received_at
                RETURNING id
            """, (
                email_data.get('id'),
                email_data.get('subject'),
                email_data.get('sender_name'),
                email_data.get('sender_address'),
                email_data.get('body_text'),
                email_data.get('received_at', datetime.now()),
                f"test_{email_data.get('id')}",  # original_uid
            ))
            result = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            return result['id']
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            raise e

    def delete_test_emails(self, email_ids: List[int]) -> int:
        """테스트 이메일 삭제 (평가용)"""
        if not email_ids:
            return 0

        conn = self.get_connection()
        cur = conn.cursor()

        try:
            # 관련 reply_drafts 먼저 삭제
            cur.execute("""
                DELETE FROM reply_drafts
                WHERE email_id = ANY(%s)
            """, (email_ids,))

            # 이메일 삭제
            cur.execute("""
                DELETE FROM email
                WHERE id = ANY(%s)
                RETURNING id
            """, (email_ids,))
            deleted = cur.fetchall()
            conn.commit()
            cur.close()
            conn.close()
            return len(deleted)
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            raise e

    def get_max_email_id(self) -> int:
        """현재 최대 이메일 ID 조회"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) as max_id FROM email")
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result['max_id']


# 싱글톤 인스턴스
db = DatabaseService()
