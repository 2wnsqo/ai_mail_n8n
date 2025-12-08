"""
Enron Email Dataset 다운로드 및 전처리 스크립트

HuggingFace의 lilac-enron-emails 데이터셋을 다운로드하고
RAG용으로 전처리합니다.

사용법:
    python -m src.rag.download_dataset
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import re

# HuggingFace datasets
try:
    from datasets import load_dataset
except ImportError:
    print("datasets 패키지를 설치해주세요: pip install datasets")
    exit(1)


# 경로 설정
RAG_DIR = Path(__file__).parent
DATA_DIR = RAG_DIR / "data"


def clean_email_text(text: str) -> str:
    """이메일 텍스트 정제"""
    if not text:
        return ""

    # 이메일 헤더 제거 (From:, To:, Subject: 등)
    lines = text.split('\n')
    content_started = False
    content_lines = []

    for line in lines:
        # 헤더 영역 건너뛰기
        if not content_started:
            if line.strip() == '' and len(content_lines) == 0:
                continue
            # 헤더 패턴 확인
            if re.match(r'^(From:|To:|Cc:|Bcc:|Subject:|Date:|Message-ID:|X-|Mime-Version:|Content-)', line, re.I):
                continue
            content_started = True

        content_lines.append(line)

    text = '\n'.join(content_lines)

    # 연속 공백/줄바꿈 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


def classify_email_type(text: str, subject: str = "") -> str:
    """이메일 유형 자동 분류 (규칙 기반)"""
    combined = f"{subject} {text}".lower()

    # 채용 관련
    if any(kw in combined for kw in ['interview', 'resume', 'job', 'position', 'hire', 'candidate', 'recruitment']):
        return "채용"

    # 마케팅/프로모션
    if any(kw in combined for kw in ['sale', 'discount', 'offer', 'promotion', 'subscribe', 'newsletter', 'unsubscribe']):
        return "마케팅"

    # 공지/알림
    if any(kw in combined for kw in ['announcement', 'notice', 'update', 'reminder', 'alert', 'notification', 'policy']):
        return "공지"

    # 개인적 메시지
    if any(kw in combined for kw in ['thank', 'please', 'help', 'question', 'meeting', 'lunch', 'dinner', 'call']):
        return "개인"

    return "기타"


def estimate_importance(text: str, subject: str = "") -> int:
    """중요도 추정 (1-10)"""
    combined = f"{subject} {text}".lower()
    score = 5  # 기본 점수

    # 긴급/중요 키워드
    if any(kw in combined for kw in ['urgent', 'important', 'asap', 'immediately', 'critical', 'deadline']):
        score += 3

    # 요청/액션 필요
    if any(kw in combined for kw in ['please', 'need', 'require', 'must', 'action required']):
        score += 1

    # 자동 발송 메일 (낮은 중요도)
    if any(kw in combined for kw in ['automated', 'do not reply', 'no-reply', 'unsubscribe']):
        score -= 2

    return max(1, min(10, score))


def needs_reply(text: str) -> bool:
    """답변 필요 여부 판단"""
    text_lower = text.lower()

    # 질문 패턴
    if '?' in text:
        return True

    # 요청 패턴
    if any(kw in text_lower for kw in ['please let me know', 'can you', 'could you', 'would you', 'get back to me']):
        return True

    # 자동 발송은 답변 불필요
    if any(kw in text_lower for kw in ['do not reply', 'no-reply', 'automated']):
        return False

    return False


def process_enron_dataset(max_samples: int = 10000) -> List[Dict]:
    """
    Enron 데이터셋 다운로드 및 처리

    Args:
        max_samples: 최대 샘플 수 (메모리 관리)

    Returns:
        처리된 이메일 리스트
    """
    print(f"📥 Enron 이메일 데이터셋 다운로드 중... (최대 {max_samples}개)")

    # corbt/enron-emails 데이터셋 우선 사용 (더 안정적)
    try:
        dataset = load_dataset(
            "corbt/enron-emails",
            split=f"train[:{max_samples}]"
        )
        print(f"✅ {len(dataset)}개 이메일 로드 완료 (corbt/enron-emails)")
    except Exception as e:
        print(f"❌ 데이터셋 로드 실패: {e}")
        return []

    processed_emails = []

    print("🔄 이메일 전처리 중...")
    for i, item in enumerate(dataset):
        try:
            # corbt/enron-emails 형식: body, subject 필드 사용
            text = item.get('body', item.get('text', item.get('content', '')))
            subject = item.get('subject', '') or ''

            # 텍스트 정제
            cleaned_text = clean_email_text(text)

            # 너무 짧거나 긴 이메일 제외
            if len(cleaned_text) < 50 or len(cleaned_text) > 5000:
                continue

            # 메타데이터 추출/생성
            email_data = {
                "id": f"enron_{i:06d}",
                "text": cleaned_text,
                "subject": subject if subject else cleaned_text[:50] + "...",
                "email_type": classify_email_type(cleaned_text, subject),
                "importance_score": estimate_importance(cleaned_text, subject),
                "needs_reply": needs_reply(cleaned_text),
                "sentiment": "neutral",  # 기본값
                "source": "enron"
            }

            processed_emails.append(email_data)

            if (i + 1) % 1000 == 0:
                print(f"  처리 중: {i + 1}/{len(dataset)}")

        except Exception as e:
            continue

    print(f"✅ 전처리 완료: {len(processed_emails)}개 이메일")

    return processed_emails


def save_processed_data(emails: List[Dict], filename: str = "enron_processed.json"):
    """처리된 데이터 저장"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    output_path = DATA_DIR / filename

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "created_at": datetime.now().isoformat(),
            "total_count": len(emails),
            "emails": emails
        }, f, ensure_ascii=False, indent=2)

    print(f"💾 저장 완료: {output_path}")
    print(f"   - 총 {len(emails)}개 이메일")

    # 유형별 통계
    type_counts = {}
    for email in emails:
        t = email['email_type']
        type_counts[t] = type_counts.get(t, 0) + 1

    print("   - 유형별 분포:")
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"     {t}: {count}개 ({count/len(emails)*100:.1f}%)")


def create_email_type_samples(emails: List[Dict], samples_per_type: int = 50):
    """
    이메일 유형별 대표 샘플 추출 (RAG 검색용)
    """
    type_samples = {}

    for email in emails:
        email_type = email['email_type']
        if email_type not in type_samples:
            type_samples[email_type] = []

        if len(type_samples[email_type]) < samples_per_type:
            type_samples[email_type].append(email)

    # 저장
    samples_path = DATA_DIR / "email_type_samples.json"
    with open(samples_path, 'w', encoding='utf-8') as f:
        json.dump(type_samples, f, ensure_ascii=False, indent=2)

    print(f"💾 유형별 샘플 저장: {samples_path}")
    for t, samples in type_samples.items():
        print(f"   - {t}: {len(samples)}개")

    return type_samples


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("📧 Enron Email Dataset 다운로드 및 전처리")
    print("=" * 60)

    # 1. 데이터셋 다운로드 및 처리
    emails = process_enron_dataset(max_samples=10000)

    if not emails:
        print("❌ 데이터셋 처리 실패")
        return

    # 2. 전체 데이터 저장
    save_processed_data(emails)

    # 3. 유형별 샘플 추출
    create_email_type_samples(emails)

    print("\n" + "=" * 60)
    print("✅ 완료! 다음 단계: ChromaDB에 벡터 저장")
    print("   python -m src.rag.build_vectordb")
    print("=" * 60)


if __name__ == "__main__":
    main()
