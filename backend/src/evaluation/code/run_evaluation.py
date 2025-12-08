"""
성능 측정 실행 스크립트

Phase 1: Baseline (현재 시스템)
Phase 2: With RAG (RAG DB 적용 후)

사용법:
    # 테스트 데이터 생성
    python run_evaluation.py --generate-data

    # Phase 1 측정 (5개만 테스트)
    python run_evaluation.py --phase phase1_baseline --limit 5

    # Phase 1 측정 (전체)
    python run_evaluation.py --phase phase1_baseline

    # Phase 비교
    python run_evaluation.py --compare
"""

import json
import sys
import os
import argparse
import requests
import psycopg2
import time
from psycopg2.extras import RealDictCursor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 경로 설정
EVAL_DIR = Path(__file__).parent.parent
DATA_DIR = EVAL_DIR / "data"
RESULTS_DIR = EVAL_DIR / "results"
REPORTS_DIR = EVAL_DIR / "reports"

# 평가 모듈 임포트
sys.path.insert(0, str(Path(__file__).parent))
from performance_evaluator import PerformanceEvaluator, evaluator
from dataset_generator import dataset_generator

# 테스트용 ID 시작 번호 (기존 데이터와 충돌 방지)
TEST_ID_START = 90000


class TestDatabaseManager:
    """테스트용 DB 관리자 (직접 연결)"""

    def __init__(self):
        # 환경변수 또는 기본값 사용 (MY_POSTGRES_* 환경변수 우선)
        self.host = os.getenv("MY_POSTGRES_HOST", os.getenv("POSTGRES_HOST", "localhost"))
        self.database = os.getenv("MY_POSTGRES_DB", os.getenv("POSTGRES_DB", "mail"))
        self.user = os.getenv("MY_POSTGRES_USER", os.getenv("POSTGRES_USER", "admin"))
        self.password = os.getenv("MY_POSTGRES_PASSWORD", os.getenv("POSTGRES_PASSWORD", "1234"))
        self.port = int(os.getenv("MY_POSTGRES_PORT", os.getenv("POSTGRES_PORT", "5432")))

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

    def insert_test_emails(self, emails: List[Dict]) -> List[int]:
        """테스트 이메일들을 DB에 삽입"""
        conn = self.get_connection()
        cur = conn.cursor()
        inserted_ids = []

        try:
            for i, email in enumerate(emails):
                # synthetic_001 -> 90001 형식으로 ID 변환
                test_id = TEST_ID_START + i + 1

                cur.execute("""
                    INSERT INTO email
                    (id, subject, sender_name, sender_address, body_text, received_at, original_uid, is_replied_to)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
                    ON CONFLICT (id) DO UPDATE SET
                        subject = EXCLUDED.subject,
                        sender_name = EXCLUDED.sender_name,
                        sender_address = EXCLUDED.sender_address,
                        body_text = EXCLUDED.body_text,
                        received_at = EXCLUDED.received_at,
                        email_type = NULL,
                        importance_score = NULL,
                        needs_reply = NULL,
                        sentiment = NULL,
                        ai_analysis = NULL,
                        processing_status = NULL
                    RETURNING id
                """, (
                    test_id,
                    email.get('subject'),
                    email.get('sender_name'),
                    email.get('sender_address'),
                    email.get('body_text'),
                    email.get('received_at', datetime.now().isoformat()),
                    f"test_{email.get('id')}",
                ))
                result = cur.fetchone()
                inserted_ids.append(result['id'])

            conn.commit()
            print(f"✅ {len(inserted_ids)}개 테스트 이메일 DB 삽입 완료")
            return inserted_ids

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    def delete_test_emails(self, email_ids: List[int]) -> int:
        """테스트 이메일 삭제"""
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
            print(f"🗑️ {len(deleted)}개 테스트 이메일 삭제 완료")
            return len(deleted)

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    def cleanup_all_test_emails(self) -> int:
        """모든 테스트 이메일 삭제 (ID >= TEST_ID_START)"""
        conn = self.get_connection()
        cur = conn.cursor()

        try:
            # 관련 reply_drafts 먼저 삭제
            cur.execute("""
                DELETE FROM reply_drafts
                WHERE email_id >= %s
            """, (TEST_ID_START,))

            # 테스트 이메일 삭제
            cur.execute("""
                DELETE FROM email
                WHERE id >= %s
                RETURNING id
            """, (TEST_ID_START,))
            deleted = cur.fetchall()
            conn.commit()
            print(f"🗑️ 모든 테스트 이메일 삭제 완료: {len(deleted)}개")
            return len(deleted)

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()


class EvaluationRunner:
    """성능 측정 실행기"""

    # 문제가 되는 특수문자 매핑 (n8n JSON 파싱 호환성)
    SPECIAL_CHAR_MAP = {
        '·': '-',      # middle dot -> hyphen
        '–': '-',      # en dash -> hyphen
        '—': '-',      # em dash -> hyphen
        ''': "'",      # fancy single quote -> simple quote
        ''': "'",      # fancy single quote -> simple quote
        '"': '"',      # fancy double quote -> simple quote
        '"': '"',      # fancy double quote -> simple quote
        '…': '...',    # ellipsis -> three dots
        '\r\n': '\n',  # Windows line ending -> Unix
        '\r': '\n',    # old Mac line ending -> Unix
    }

    def __init__(self, phase: str = "phase1_baseline", n8n_url: str = None):
        # n8n URL 환경변수 또는 기본값 사용 (Docker 네트워크 내에서는 n8n 컨테이너 이름 사용)
        if n8n_url is None:
            n8n_url = os.getenv("N8N_URL", "http://n8n:5678")
        self.phase = phase
        self.n8n_url = n8n_url
        self.evaluator = PerformanceEvaluator()
        self.db_manager = TestDatabaseManager()

        self.test_email_ids = []  # 삽입된 테스트 이메일 ID 추적
        self.id_mapping = {}  # synthetic_id -> db_id 매핑
        self.results = {
            "phase": phase,
            "started_at": datetime.now().isoformat(),
            "n8n_url": n8n_url,
            "analysis_results": [],
            "reply_results": [],
            "errors": []
        }

    def sanitize_text(self, text: str) -> str:
        """n8n JSON 파싱 호환성을 위한 특수문자 정제"""
        if not text:
            return text
        for char, replacement in self.SPECIAL_CHAR_MAP.items():
            text = text.replace(char, replacement)
        return text

    def load_test_data(self) -> Dict:
        """테스트 데이터 로드"""
        dataset_path = DATA_DIR / "test_dataset.json"

        if not dataset_path.exists():
            print("테스트 데이터셋이 없습니다. 생성 중...")
            dataset_generator.save_test_dataset()
            dataset_generator.save_ground_truth()

        with open(dataset_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_ground_truth(self) -> Dict:
        """Ground Truth 로드"""
        gt_path = DATA_DIR / "ground_truth.json"

        with open(gt_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # id를 키로 하는 딕셔너리로 변환
            return {gt["id"]: gt for gt in data["ground_truths"]}

    def setup_test_data(self, emails: List[Dict]) -> List[Dict]:
        """테스트 데이터를 DB에 삽입하고 ID 매핑 생성"""
        print("\n📥 테스트 데이터 DB 삽입 중...")

        # DB에 삽입
        self.test_email_ids = self.db_manager.insert_test_emails(emails)

        # ID 매핑 생성 (synthetic_001 -> 90001)
        for i, email in enumerate(emails):
            db_id = self.test_email_ids[i]
            self.id_mapping[email["id"]] = db_id
            # 이메일 데이터에 실제 DB ID 추가
            email["db_id"] = db_id

        print(f"📊 ID 매핑: {len(self.id_mapping)}개")
        return emails

    def cleanup_test_data(self):
        """테스트 데이터 정리"""
        if self.test_email_ids:
            print("\n🧹 테스트 데이터 정리 중...")
            self.db_manager.delete_test_emails(self.test_email_ids)
            self.test_email_ids = []
            self.id_mapping = {}

    def call_analyze_api(self, email_data: Dict) -> Optional[Dict]:
        """n8n analyze webhook 호출 (실제 DB ID 사용)"""
        try:
            webhook_url = f"{self.n8n_url}/webhook/analyze"

            # 실제 DB ID 사용
            db_id = email_data.get("db_id", email_data["id"])

            # 특수문자 정제 적용
            payload = {
                "email_id": db_id,
                "subject": self.sanitize_text(email_data["subject"]),
                "sender_name": self.sanitize_text(email_data["sender_name"]),
                "sender_address": email_data["sender_address"],
                "body_text": self.sanitize_text(email_data["body_text"])
            }

            # 명시적으로 UTF-8 인코딩 및 Content-Type 설정
            headers = {'Content-Type': 'application/json; charset=utf-8'}
            response = requests.post(
                webhook_url,
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers=headers,
                timeout=60
            )

            if response.status_code == 200:
                # 빈 응답 처리
                if not response.text or response.text.strip() == '':
                    print(f"  [ERROR] 빈 응답 수신")
                    return None
                return response.json()
            else:
                print(f"  [ERROR] 분석 실패: {response.status_code} - {response.text[:100]}")
                return None

        except requests.exceptions.Timeout:
            print(f"  [ERROR] 타임아웃: {email_data['id']}")
            return None
        except json.JSONDecodeError as e:
            print(f"  [ERROR] JSON 파싱 실패: {e}")
            return None
        except Exception as e:
            print(f"  [ERROR] 예외: {e}")
            return None

    def call_reply_api(self, email_data: Dict, tone: str = "formal") -> Optional[Dict]:
        """n8n generate-reply webhook 호출"""
        try:
            webhook_url = f"{self.n8n_url}/webhook/generate-reply"

            # 실제 DB ID 사용
            db_id = email_data.get("db_id", email_data["id"])

            # 특수문자 정제 적용
            payload = {
                "email_id": db_id,
                "subject": self.sanitize_text(email_data["subject"]),
                "sender_name": self.sanitize_text(email_data["sender_name"]),
                "sender_address": email_data["sender_address"],
                "body_text": self.sanitize_text(email_data["body_text"]),
                "preferred_tone": tone
            }

            # 명시적으로 UTF-8 인코딩 및 Content-Type 설정
            headers = {'Content-Type': 'application/json; charset=utf-8'}
            response = requests.post(
                webhook_url,
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers=headers,
                timeout=90
            )

            if response.status_code == 200:
                # 빈 응답 처리
                if not response.text or response.text.strip() == '':
                    print(f"  [ERROR] 빈 응답 수신")
                    return None
                return response.json()
            else:
                print(f"  [ERROR] 답변 생성 실패: {response.status_code}")
                return None

        except json.JSONDecodeError as e:
            print(f"  [ERROR] JSON 파싱 실패: {e}")
            return None
        except Exception as e:
            print(f"  [ERROR] 예외: {e}")
            return None

    def run_analysis_evaluation(self, limit: Optional[int] = None, cleanup: bool = True):
        """이메일 분석 성능 평가 실행"""
        print("\n" + "=" * 60)
        print(f"📊 이메일 분석 평가 시작 (Phase: {self.phase})")
        print("=" * 60)

        dataset = self.load_test_data()
        ground_truths = self.load_ground_truth()

        emails = dataset["emails"]
        if limit:
            emails = emails[:limit]

        # 테스트 데이터 DB 삽입
        emails = self.setup_test_data(emails)

        total = len(emails)
        success = 0
        failed = 0

        # Gemini 무료 tier Rate Limit: 분당 20회
        # 안전하게 4초 딜레이 (60초 / 15회 = 4초)
        REQUEST_DELAY = 4  # seconds
        RETRY_DELAY = 45  # seconds (Rate Limit 에러 시 - 넉넉하게)

        try:
            for i, email in enumerate(emails):
                synthetic_id = email["id"]  # 원본 ID (synthetic_001)
                db_id = email["db_id"]  # DB ID (90001)

                print(f"\n[{i + 1}/{total}] 분석 중: {email['subject'][:40]}... (DB ID: {db_id})")

                # Rate Limit 방지: 첫 번째 요청 이후부터 딜레이 적용
                if i > 0:
                    print(f"  ⏳ Rate Limit 대기 중... ({REQUEST_DELAY}초)")
                    time.sleep(REQUEST_DELAY)

                # API 호출 (실패 시 1회 재시도)
                ai_result = self.call_analyze_api(email)

                # 빈 응답이면 Rate Limit 가능성 - 재시도
                if ai_result is None:
                    print(f"  🔄 재시도 중... ({RETRY_DELAY}초 대기)")
                    time.sleep(RETRY_DELAY)
                    ai_result = self.call_analyze_api(email)

                if ai_result and ai_result.get("success") is not False:
                    # Ground Truth 가져오기
                    gt = ground_truths.get(synthetic_id, {})

                    # 분석 결과 파싱
                    analysis = ai_result.get("analysis", {})

                    # 평가 실행
                    evaluation = self.evaluator.evaluate_analysis(
                        email_id=synthetic_id,
                        ai_result={
                            "email_type": analysis.get("email_type"),
                            "importance_score": analysis.get("importance_score"),
                            "needs_reply": analysis.get("needs_reply"),
                            "sentiment": analysis.get("sentiment")
                        },
                        ground_truth={
                            "email_type": gt.get("email_type"),
                            "importance_score": gt.get("importance_score"),
                            "needs_reply": gt.get("needs_reply"),
                            "sentiment": gt.get("sentiment")
                        }
                    )

                    self.results["analysis_results"].append({
                        "email_id": synthetic_id,
                        "db_id": db_id,
                        "subject": email["subject"],
                        "ai_result": analysis,
                        "ground_truth": gt,
                        "score": evaluation.total_score,
                        "notes": evaluation.evaluation_notes
                    })

                    success += 1
                    print(f"  ✅ 점수: {evaluation.total_score}/100 - {evaluation.evaluation_notes or 'OK'}")

                else:
                    failed += 1
                    self.results["errors"].append({
                        "email_id": synthetic_id,
                        "db_id": db_id,
                        "error": "API 호출 실패"
                    })
                    print(f"  ❌ 실패")

            # 통계 계산
            stats = self.evaluator.get_analysis_statistics()
            self.results["analysis_statistics"] = stats

            print("\n" + "-" * 60)
            print(f"📈 분석 평가 완료: 성공 {success}/{total}, 실패 {failed}")
            print(f"📊 평균 점수: {stats.get('average_score', 0)}점")
            print("-" * 60)

            return stats

        finally:
            # 테스트 데이터 정리
            if cleanup:
                self.cleanup_test_data()

    def run_reply_evaluation(self, limit: Optional[int] = None, cleanup: bool = True):
        """답변 생성 성능 평가 실행"""
        print("\n" + "=" * 60)
        print(f"✍️ 답변 생성 평가 시작 (Phase: {self.phase})")
        print("=" * 60)

        dataset = self.load_test_data()

        # needs_reply가 True인 이메일만 선택
        emails = [e for e in dataset["emails"] if e["ground_truth"].get("needs_reply")]
        if limit:
            emails = emails[:limit]

        # 테스트 데이터 DB 삽입 (아직 안했으면)
        if not self.test_email_ids:
            emails = self.setup_test_data(emails)
        else:
            # 이미 삽입된 경우 db_id 매핑
            for email in emails:
                if email["id"] in self.id_mapping:
                    email["db_id"] = self.id_mapping[email["id"]]

        total = len(emails)
        success = 0

        try:
            for i, email in enumerate(emails):
                synthetic_id = email["id"]
                db_id = email.get("db_id", self.id_mapping.get(synthetic_id))

                print(f"\n[{i + 1}/{total}] 답변 생성 중: {email['subject'][:40]}... (DB ID: {db_id})")

                # API 호출
                reply_result = self.call_reply_api(email)

                if reply_result and reply_result.get("success") is not False:
                    self.results["reply_results"].append({
                        "email_id": synthetic_id,
                        "db_id": db_id,
                        "subject": email["subject"],
                        "reply_drafts": reply_result.get("reply_drafts", {}),
                        "generated_at": datetime.now().isoformat()
                    })
                    success += 1
                    print(f"  ✅ 3가지 톤 답변 생성 완료")
                else:
                    print(f"  ❌ 실패")

            print("\n" + "-" * 60)
            print(f"✍️ 답변 생성 완료: 성공 {success}/{total}")
            print("-" * 60)

        finally:
            # 테스트 데이터 정리
            if cleanup:
                self.cleanup_test_data()

    def save_results(self):
        """결과 저장"""
        self.results["completed_at"] = datetime.now().isoformat()

        # 결과 파일 저장
        results_file = RESULTS_DIR / f"{self.phase}.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)

        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"\n💾 결과 저장: {results_file}")

        return results_file

    def generate_report(self) -> str:
        """마크다운 리포트 생성"""
        stats = self.results.get("analysis_statistics", {})
        breakdown = stats.get("breakdown", {})

        report = f"""# 성능 평가 리포트: {self.phase}

## 개요
- **평가 일시**: {self.results.get('started_at', 'N/A')}
- **완료 일시**: {self.results.get('completed_at', 'N/A')}
- **Phase**: {self.phase}

---

## 이메일 분석 성능

### 전체 통계
| 항목 | 값 |
|------|-----|
| 평가 건수 | {stats.get('count', 0)} |
| 평균 점수 | {stats.get('average_score', 0)}/100 |
| 중앙값 | {stats.get('median_score', 0)} |
| 최소/최대 | {stats.get('min_score', 0)} / {stats.get('max_score', 0)} |
| 표준편차 | {stats.get('std_dev', 0)} |

### 항목별 점수 (25점 만점)
| 항목 | 평균 점수 | 정확도 |
|------|----------|--------|
| email_type | {breakdown.get('email_type_avg', 0)} | {breakdown.get('email_type_avg', 0) / 25 * 100:.1f}% |
| importance_score | {breakdown.get('importance_avg', 0)} | {breakdown.get('importance_avg', 0) / 25 * 100:.1f}% |
| needs_reply | {breakdown.get('needs_reply_avg', 0)} | {breakdown.get('needs_reply_avg', 0) / 25 * 100:.1f}% |
| sentiment | {breakdown.get('sentiment_avg', 0)} | {breakdown.get('sentiment_avg', 0) / 25 * 100:.1f}% |

### 시각화
```
email_type      {'█' * int(breakdown.get('email_type_avg', 0))}{'░' * (25 - int(breakdown.get('email_type_avg', 0)))} {breakdown.get('email_type_avg', 0)}/25
importance      {'█' * int(breakdown.get('importance_avg', 0))}{'░' * (25 - int(breakdown.get('importance_avg', 0)))} {breakdown.get('importance_avg', 0)}/25
needs_reply     {'█' * int(breakdown.get('needs_reply_avg', 0))}{'░' * (25 - int(breakdown.get('needs_reply_avg', 0)))} {breakdown.get('needs_reply_avg', 0)}/25
sentiment       {'█' * int(breakdown.get('sentiment_avg', 0))}{'░' * (25 - int(breakdown.get('sentiment_avg', 0)))} {breakdown.get('sentiment_avg', 0)}/25
```

---

## 상세 결과

### 오류 발생 건
"""
        if self.results.get("errors"):
            for error in self.results["errors"]:
                report += f"- `{error['email_id']}`: {error['error']}\n"
        else:
            report += "없음\n"

        report += f"""
---

## 개선 제안

1. **email_type 정확도 개선**: {"프롬프트에 분류 예시 추가 필요" if breakdown.get('email_type_avg', 0) < 20 else "양호"}
2. **importance 정확도 개선**: {"중요도 기준 명확화 필요" if breakdown.get('importance_avg', 0) < 20 else "양호"}
3. **sentiment 정확도 개선**: {"감정 분석 프롬프트 보강 필요" if breakdown.get('sentiment_avg', 0) < 20 else "양호"}

---

*Generated at {datetime.now().isoformat()}*
"""

        # 리포트 저장
        report_dir = REPORTS_DIR / self.phase
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / "analysis_report.md"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"📝 리포트 저장: {report_file}")

        return report


def compare_phases(phase1: str = "phase1_baseline", phase2: str = "phase2_with_rag"):
    """두 Phase 비교 리포트 생성"""
    print("\n" + "=" * 60)
    print(f"📊 Phase 비교: {phase1} vs {phase2}")
    print("=" * 60)

    # 결과 로드
    phase1_file = RESULTS_DIR / f"{phase1}.json"
    phase2_file = RESULTS_DIR / f"{phase2}.json"

    if not phase1_file.exists():
        print(f"❌ {phase1} 결과 파일 없음")
        return

    if not phase2_file.exists():
        print(f"❌ {phase2} 결과 파일 없음")
        return

    with open(phase1_file, 'r', encoding='utf-8') as f:
        p1_data = json.load(f)

    with open(phase2_file, 'r', encoding='utf-8') as f:
        p2_data = json.load(f)

    p1_stats = p1_data.get("analysis_statistics", {})
    p2_stats = p2_data.get("analysis_statistics", {})

    # 비교 리포트 생성
    p1_avg = p1_stats.get('average_score', 0)
    p2_avg = p2_stats.get('average_score', 0)
    improvement = p2_avg - p1_avg
    improvement_pct = (improvement / p1_avg * 100) if p1_avg > 0 else 0

    comparison_report = f"""# Phase 비교 리포트

## 개요
- **Phase 1**: {phase1}
- **Phase 2**: {phase2}
- **비교 일시**: {datetime.now().isoformat()}

---

## 전체 점수 비교

| 항목 | {phase1} | {phase2} | 변화 |
|------|----------|----------|------|
| 평균 점수 | {p1_avg} | {p2_avg} | {improvement:+.1f} ({improvement_pct:+.1f}%) |
| 평가 건수 | {p1_stats.get('count', 0)} | {p2_stats.get('count', 0)} | - |

---

## 항목별 비교

| 항목 | {phase1} | {phase2} | 변화 |
|------|----------|----------|------|
"""

    p1_breakdown = p1_stats.get('breakdown', {})
    p2_breakdown = p2_stats.get('breakdown', {})

    for key in ['email_type_avg', 'importance_avg', 'needs_reply_avg', 'sentiment_avg']:
        p1_val = p1_breakdown.get(key, 0)
        p2_val = p2_breakdown.get(key, 0)
        diff = p2_val - p1_val
        comparison_report += f"| {key} | {p1_val} | {p2_val} | {diff:+.1f} |\n"

    comparison_report += f"""
---

## 시각화

### {phase1} (Baseline)
```
평균: {'█' * int(p1_avg / 4)}{'░' * (25 - int(p1_avg / 4))} {p1_avg}/100
```

### {phase2} (개선)
```
평균: {'█' * int(p2_avg / 4)}{'░' * (25 - int(p2_avg / 4))} {p2_avg}/100
```

### 개선율
```
{'🔺' if improvement > 0 else '🔻'} {abs(improvement_pct):.1f}% {'향상' if improvement > 0 else '하락'}
```

---

## 결론

{"✅ RAG 적용으로 성능이 개선되었습니다." if improvement > 0 else "⚠️ 추가 튜닝이 필요합니다."}

*Generated at {datetime.now().isoformat()}*
"""

    # 비교 리포트 저장
    comparison_file = REPORTS_DIR / "phase_comparison.md"
    with open(comparison_file, 'w', encoding='utf-8') as f:
        f.write(comparison_report)

    print(f"📝 비교 리포트 저장: {comparison_file}")
    print(comparison_report)


def cleanup_test_data():
    """모든 테스트 데이터 정리"""
    print("\n🧹 테스트 데이터 정리 중...")
    db_manager = TestDatabaseManager()
    deleted = db_manager.cleanup_all_test_emails()
    print(f"✅ 완료: {deleted}개 삭제")


def main():
    parser = argparse.ArgumentParser(description="AI 메일 비서 성능 평가")
    parser.add_argument(
        "--phase",
        choices=["phase1_baseline", "phase2_with_rag"],
        default="phase1_baseline",
        help="평가 Phase 선택"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="평가할 이메일 수 제한"
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="이메일 분석만 평가"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Phase 1과 Phase 2 비교"
    )
    parser.add_argument(
        "--generate-data",
        action="store_true",
        help="테스트 데이터 생성만 수행"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="테스트 데이터 정리 (DB에서 삭제)"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="평가 후 테스트 데이터 유지 (디버깅용)"
    )

    args = parser.parse_args()

    if args.generate_data:
        print("📦 테스트 데이터 생성 중...")
        dataset_generator.save_test_dataset()
        dataset_generator.save_ground_truth()
        print("✅ 완료!")
        print(f"   - {DATA_DIR / 'test_dataset.json'}")
        print(f"   - {DATA_DIR / 'ground_truth.json'}")
        return

    if args.cleanup:
        cleanup_test_data()
        return

    if args.compare:
        compare_phases()
        return

    # 평가 실행
    runner = EvaluationRunner(phase=args.phase)

    # cleanup 여부 결정
    should_cleanup = not args.no_cleanup

    # 분석 평가
    runner.run_analysis_evaluation(limit=args.limit, cleanup=False)

    # 답변 생성 평가 (옵션)
    if not args.analysis_only:
        runner.run_reply_evaluation(limit=args.limit, cleanup=should_cleanup)
    elif should_cleanup:
        runner.cleanup_test_data()

    # 결과 저장
    runner.save_results()

    # 리포트 생성
    runner.generate_report()

    print("\n✅ 평가 완료!")


if __name__ == "__main__":
    main()
