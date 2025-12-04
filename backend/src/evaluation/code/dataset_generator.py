"""
테스트 데이터셋 생성기

일관된 성능 측정을 위한 고정 테스트 데이터셋을 생성합니다.
- 실제 DB 이메일에서 선별
- 합성 이메일 생성
- Ground Truth 포함
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

# 현재 파일 기준 data 폴더 경로
DATA_DIR = Path(__file__).parent.parent / "data"


class DatasetGenerator:
    """테스트 데이터셋 생성기"""

    def __init__(self):
        self.test_emails: List[Dict] = []
        self.ground_truth: List[Dict] = []

    def generate_synthetic_emails(self) -> List[Dict]:
        """
        합성 테스트 이메일 생성
        각 유형별로 다양한 케이스 포함
        """
        synthetic_emails = [
            # ========== 채용 관련 (5개) ==========
            {
                "id": "synthetic_001",
                "subject": "[ABC회사] 서류 전형 합격 및 면접 안내",
                "sender_name": "ABC회사 인사팀",
                "sender_address": "hr@abc-company.com",
                "body_text": """안녕하세요, 홍길동님.

ABC회사 백엔드 개발자 채용에 지원해 주셔서 감사합니다.

서류 전형 결과, 귀하께서 합격하셨음을 알려드립니다.
다음 단계인 1차 면접 일정을 아래와 같이 안내드립니다.

- 일시: 2024년 12월 10일 (화) 오후 2시
- 장소: ABC회사 본사 3층 회의실
- 준비물: 신분증, 포트폴리오

참석 가능 여부를 12월 6일까지 회신 부탁드립니다.

감사합니다.
ABC회사 인사팀 드림""",
                "received_at": "2024-12-04T09:00:00",
                "ground_truth": {
                    "email_type": "채용",
                    "importance_score": 9,
                    "needs_reply": True,
                    "sentiment": "positive",
                    "key_points": ["서류 합격", "면접 일정 12/10", "참석 여부 회신 필요"]
                }
            },
            {
                "id": "synthetic_002",
                "subject": "면접 결과 안내 - 불합격",
                "sender_name": "XYZ테크 채용담당",
                "sender_address": "recruit@xyztech.co.kr",
                "body_text": """안녕하세요.

XYZ테크 프론트엔드 개발자 채용에 지원해 주셔서 감사합니다.

안타깝게도 이번 채용에서는 귀하의 합류가 어렵게 되었습니다.
더 좋은 기회가 있으시길 바라며, 앞으로의 발전을 응원합니다.

감사합니다.""",
                "received_at": "2024-12-04T10:00:00",
                "ground_truth": {
                    "email_type": "채용",
                    "importance_score": 7,
                    "needs_reply": False,
                    "sentiment": "negative",
                    "key_points": ["불합격 통보"]
                }
            },
            {
                "id": "synthetic_003",
                "subject": "코딩테스트 안내",
                "sender_name": "스타트업A HR",
                "sender_address": "hr@startup-a.io",
                "body_text": """안녕하세요.

스타트업A 개발자 채용 프로세스의 일환으로 코딩테스트를 안내드립니다.

- 응시 기간: 12월 5일 ~ 12월 7일
- 소요 시간: 약 2시간
- 문제 수: 3문제 (알고리즘 2, SQL 1)
- 링크: https://test.example.com/abc123

기한 내 응시 부탁드립니다.

감사합니다.""",
                "received_at": "2024-12-04T11:00:00",
                "ground_truth": {
                    "email_type": "채용",
                    "importance_score": 8,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["코딩테스트 안내", "기한 12/5~12/7", "2시간 소요"]
                }
            },
            {
                "id": "synthetic_004",
                "subject": "연봉 협상 관련 문의",
                "sender_name": "DEF기업 인사",
                "sender_address": "hr@def-corp.com",
                "body_text": """안녕하세요, 홍길동님.

최종 면접 합격을 축하드립니다!

처우 협의를 위해 아래 내용을 확인 부탁드립니다.
- 희망 연봉
- 입사 가능일
- 현재 재직 여부

회신 부탁드립니다.

감사합니다.""",
                "received_at": "2024-12-04T14:00:00",
                "ground_truth": {
                    "email_type": "채용",
                    "importance_score": 10,
                    "needs_reply": True,
                    "sentiment": "positive",
                    "key_points": ["최종 합격", "연봉 협상", "입사일 문의"]
                }
            },
            {
                "id": "synthetic_005",
                "subject": "이력서 접수 확인",
                "sender_name": "채용플랫폼",
                "sender_address": "noreply@jobplatform.com",
                "body_text": """이력서가 정상적으로 접수되었습니다.

지원 정보:
- 회사: GHI컴퍼니
- 포지션: 데이터 엔지니어
- 접수일: 2024년 12월 4일

서류 검토 후 개별 연락드리겠습니다.

감사합니다.""",
                "received_at": "2024-12-04T15:00:00",
                "ground_truth": {
                    "email_type": "채용",
                    "importance_score": 5,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["이력서 접수 확인", "서류 검토 예정"]
                }
            },

            # ========== 마케팅 관련 (5개) ==========
            {
                "id": "synthetic_006",
                "subject": "[50% 할인] 블랙프라이데이 특별 프로모션!",
                "sender_name": "쇼핑몰A",
                "sender_address": "marketing@shoppingmall.com",
                "body_text": """🎉 블랙프라이데이 특별 할인!

전 상품 최대 50% 할인!
- 기간: 11월 24일 ~ 11월 27일
- 쿠폰코드: BLACKFRI2024

지금 바로 쇼핑하세요!

수신거부: unsubscribe@shoppingmall.com""",
                "received_at": "2024-11-24T08:00:00",
                "ground_truth": {
                    "email_type": "마케팅",
                    "importance_score": 2,
                    "needs_reply": False,
                    "sentiment": "positive",
                    "key_points": ["50% 할인", "블랙프라이데이", "쿠폰코드"]
                }
            },
            {
                "id": "synthetic_007",
                "subject": "새로운 기능 출시 안내 - RunPod",
                "sender_name": "RunPod Team",
                "sender_address": "team@runpod.io",
                "body_text": """RunPod의 새로운 기능을 소개합니다!

Load Balancer가 출시되었습니다.
- 실시간 스트리밍 지원
- 저지연 API 엔드포인트
- vLLM 최적화

자세한 내용은 문서를 확인하세요.

Unsubscribe | Manage Preferences""",
                "received_at": "2024-12-01T10:00:00",
                "ground_truth": {
                    "email_type": "마케팅",
                    "importance_score": 3,
                    "needs_reply": False,
                    "sentiment": "positive",
                    "key_points": ["새 기능 출시", "Load Balancer", "기술 업데이트"]
                }
            },
            {
                "id": "synthetic_008",
                "subject": "무료 웨비나 초대 - AI 트렌드 2025",
                "sender_name": "테크컨퍼런스",
                "sender_address": "events@techconf.co.kr",
                "body_text": """AI 트렌드 2025 웨비나에 초대합니다!

일시: 12월 15일 오후 7시
주제: 2025년 AI 산업 전망
연사: 김AI 교수 (서울대)

무료 등록: https://webinar.example.com

수신거부""",
                "received_at": "2024-12-03T09:00:00",
                "ground_truth": {
                    "email_type": "마케팅",
                    "importance_score": 4,
                    "needs_reply": False,
                    "sentiment": "positive",
                    "key_points": ["무료 웨비나", "AI 트렌드", "12월 15일"]
                }
            },
            {
                "id": "synthetic_009",
                "subject": "구독 갱신 안내",
                "sender_name": "SaaS서비스",
                "sender_address": "billing@saas-service.com",
                "body_text": """구독이 곧 만료됩니다.

현재 플랜: Pro ($29/월)
만료일: 2024년 12월 10일

지금 갱신하시면 20% 할인!
자동 갱신을 원하시면 결제 정보를 확인해주세요.

문의: support@saas-service.com""",
                "received_at": "2024-12-03T11:00:00",
                "ground_truth": {
                    "email_type": "마케팅",
                    "importance_score": 5,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["구독 만료 임박", "갱신 할인", "12월 10일 만료"]
                }
            },
            {
                "id": "synthetic_010",
                "subject": "뉴스레터 - 이번 주 테크 뉴스",
                "sender_name": "테크뉴스레터",
                "sender_address": "newsletter@technews.kr",
                "body_text": """이번 주 테크 뉴스 Top 5

1. OpenAI GPT-5 발표 임박
2. 애플 M4 칩 성능 공개
3. 테슬라 로보택시 시범 운행
4. 구글 Gemini 2.0 업데이트
5. 삼성 갤럭시 S25 유출

자세히 보기: https://technews.kr/weekly""",
                "received_at": "2024-12-04T07:00:00",
                "ground_truth": {
                    "email_type": "마케팅",
                    "importance_score": 2,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["주간 뉴스레터", "테크 뉴스"]
                }
            },

            # ========== 공지 관련 (5개) ==========
            {
                "id": "synthetic_011",
                "subject": "서울시 당현천 개장 안내",
                "sender_name": "서울시청",
                "sender_address": "info@seoul.go.kr",
                "body_text": """서울시 당현천 '당현마루·달빛브릿지' 개장 안내

개장일: 2024년 12월 5일
위치: 서대문구 당현천
시설: 산책로, 전망대, 야간 조명

많은 방문 부탁드립니다.

서울특별시""",
                "received_at": "2024-12-04T08:00:00",
                "ground_truth": {
                    "email_type": "공지",
                    "importance_score": 3,
                    "needs_reply": False,
                    "sentiment": "positive",
                    "key_points": ["시설 개장", "당현천", "12월 5일"]
                }
            },
            {
                "id": "synthetic_012",
                "subject": "시스템 점검 안내 (12/7 02:00-06:00)",
                "sender_name": "IT지원팀",
                "sender_address": "it-support@company.com",
                "body_text": """시스템 정기 점검 안내

일시: 12월 7일(토) 02:00 ~ 06:00
대상: 전사 시스템 (메일, ERP, 그룹웨어)
영향: 해당 시간 서비스 이용 불가

양해 부탁드립니다.

IT지원팀""",
                "received_at": "2024-12-04T16:00:00",
                "ground_truth": {
                    "email_type": "공지",
                    "importance_score": 6,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["시스템 점검", "12/7 새벽", "서비스 중단"]
                }
            },
            {
                "id": "synthetic_013",
                "subject": "개인정보 처리방침 변경 안내",
                "sender_name": "서비스운영팀",
                "sender_address": "privacy@service.com",
                "body_text": """개인정보 처리방침 변경 안내

시행일: 2024년 12월 15일

주요 변경사항:
1. 개인정보 보유기간 변경 (3년 → 5년)
2. 제3자 제공 항목 추가
3. 마케팅 동의 절차 간소화

자세한 내용: https://service.com/privacy

문의: privacy@service.com""",
                "received_at": "2024-12-01T10:00:00",
                "ground_truth": {
                    "email_type": "공지",
                    "importance_score": 4,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["개인정보 방침 변경", "12월 15일 시행"]
                }
            },
            {
                "id": "synthetic_014",
                "subject": "[긴급] 보안 업데이트 필수 적용 안내",
                "sender_name": "보안팀",
                "sender_address": "security@company.com",
                "body_text": """긴급 보안 업데이트 안내

중요한 보안 취약점이 발견되어 즉시 업데이트가 필요합니다.

대상: 전 직원 PC
방법: 제어판 > Windows Update 실행
기한: 12월 5일까지

미적용 시 네트워크 접속이 제한됩니다.

보안팀""",
                "received_at": "2024-12-04T09:00:00",
                "ground_truth": {
                    "email_type": "공지",
                    "importance_score": 8,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["긴급 보안 업데이트", "12/5까지", "필수 적용"]
                }
            },
            {
                "id": "synthetic_015",
                "subject": "연말 휴무 안내",
                "sender_name": "총무팀",
                "sender_address": "admin@company.com",
                "body_text": """2024년 연말 휴무 안내

휴무 기간: 12월 30일(월) ~ 1월 1일(수)
업무 재개: 1월 2일(목)

긴급 연락처: 010-1234-5678

즐거운 연말연시 보내세요!

총무팀""",
                "received_at": "2024-12-03T14:00:00",
                "ground_truth": {
                    "email_type": "공지",
                    "importance_score": 5,
                    "needs_reply": False,
                    "sentiment": "positive",
                    "key_points": ["연말 휴무", "12/30~1/1", "긴급 연락처"]
                }
            },

            # ========== 개인 관련 (5개) ==========
            {
                "id": "synthetic_016",
                "subject": "프로젝트 협업 요청",
                "sender_name": "김개발",
                "sender_address": "kim.dev@gmail.com",
                "body_text": """안녕하세요, 홍길동님.

오픈소스 프로젝트에서 활동하시는 것을 보고 연락드립니다.

현재 진행 중인 AI 챗봇 프로젝트에 참여 의향이 있으신지 문의드립니다.
- 기술 스택: Python, LangChain, FastAPI
- 예상 기간: 3개월
- 보상: 오픈소스 기여 + 소정의 사례비

관심 있으시면 회신 부탁드립니다.

감사합니다.
김개발 드림""",
                "received_at": "2024-12-04T11:00:00",
                "ground_truth": {
                    "email_type": "개인",
                    "importance_score": 7,
                    "needs_reply": True,
                    "sentiment": "positive",
                    "key_points": ["프로젝트 협업 제안", "AI 챗봇", "회신 요청"]
                }
            },
            {
                "id": "synthetic_017",
                "subject": "Re: 지난주 미팅 후속",
                "sender_name": "이매니저",
                "sender_address": "lee.manager@partner.com",
                "body_text": """안녕하세요.

지난주 미팅에서 논의한 내용 정리해서 보내드립니다.

1. API 연동 방식 확정
2. 일정: 1월 중 MVP 완료
3. 다음 미팅: 12월 12일

첨부 파일 확인 부탁드립니다.
의견 있으시면 말씀해주세요.

감사합니다.""",
                "received_at": "2024-12-04T13:00:00",
                "ground_truth": {
                    "email_type": "개인",
                    "importance_score": 7,
                    "needs_reply": True,
                    "sentiment": "neutral",
                    "key_points": ["미팅 후속", "일정 확인", "의견 요청"]
                }
            },
            {
                "id": "synthetic_018",
                "subject": "생일 축하해요!",
                "sender_name": "박친구",
                "sender_address": "park.friend@naver.com",
                "body_text": """생일 축하해~! 🎂🎉

올해도 건강하고 행복한 한 해 보내!
다음에 만나서 밥 한번 먹자ㅋㅋ

선물은 나중에 줄게~""",
                "received_at": "2024-12-04T00:01:00",
                "ground_truth": {
                    "email_type": "개인",
                    "importance_score": 4,
                    "needs_reply": True,
                    "sentiment": "positive",
                    "key_points": ["생일 축하", "친구"]
                }
            },
            {
                "id": "synthetic_019",
                "subject": "기술 질문 - LangGraph 관련",
                "sender_name": "최주니어",
                "sender_address": "choi.junior@company.com",
                "body_text": """안녕하세요, 선배님.

LangGraph 관련해서 질문이 있어서 메일 드립니다.

StateGraph에서 conditional_edges를 사용할 때
여러 조건을 처리하는 best practice가 궁금합니다.

혹시 시간 되시면 간단히 조언 부탁드려도 될까요?

감사합니다.
최주니어 드림""",
                "received_at": "2024-12-04T15:00:00",
                "ground_truth": {
                    "email_type": "개인",
                    "importance_score": 5,
                    "needs_reply": True,
                    "sentiment": "neutral",
                    "key_points": ["기술 질문", "LangGraph", "조언 요청"]
                }
            },
            {
                "id": "synthetic_020",
                "subject": "이번 주 스터디 불참 안내",
                "sender_name": "정스터디",
                "sender_address": "jung.study@gmail.com",
                "body_text": """안녕하세요.

이번 주 토요일 스터디에 개인 사정으로 불참합니다.
다음 주에는 꼭 참석하겠습니다.

발표 자료는 미리 공유드릴게요.

감사합니다.""",
                "received_at": "2024-12-04T17:00:00",
                "ground_truth": {
                    "email_type": "개인",
                    "importance_score": 3,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["스터디 불참", "자료 공유 예정"]
                }
            },

            # ========== 기타 (5개) ==========
            {
                "id": "synthetic_021",
                "subject": "택배 배송 완료 안내",
                "sender_name": "CJ대한통운",
                "sender_address": "noreply@cjlogistics.com",
                "body_text": """배송이 완료되었습니다.

운송장번호: 1234567890
배송완료: 2024-12-04 14:32
수령인: 홍길동
배송위치: 경비실

감사합니다.""",
                "received_at": "2024-12-04T14:35:00",
                "ground_truth": {
                    "email_type": "기타",
                    "importance_score": 3,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["배송 완료", "경비실 수령"]
                }
            },
            {
                "id": "synthetic_022",
                "subject": "카드 사용 내역 알림",
                "sender_name": "KB국민카드",
                "sender_address": "card@kbcard.com",
                "body_text": """KB국민카드 사용 알림

일시: 2024-12-04 12:30
가맹점: 스타벅스 강남점
금액: 6,500원
누적: 125,000원/500,000원

이용해 주셔서 감사합니다.""",
                "received_at": "2024-12-04T12:31:00",
                "ground_truth": {
                    "email_type": "기타",
                    "importance_score": 2,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["카드 사용 알림", "6,500원"]
                }
            },
            {
                "id": "synthetic_023",
                "subject": "GitHub - New pull request",
                "sender_name": "GitHub",
                "sender_address": "noreply@github.com",
                "body_text": """@contributor opened a new pull request in your-repo/project

#42 Add feature: email classification

Files changed: 5
Commits: 3

View pull request: https://github.com/your-repo/project/pull/42""",
                "received_at": "2024-12-04T16:00:00",
                "ground_truth": {
                    "email_type": "기타",
                    "importance_score": 6,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["GitHub PR", "코드 리뷰 필요"]
                }
            },
            {
                "id": "synthetic_024",
                "subject": "비밀번호 변경 완료",
                "sender_name": "네이버",
                "sender_address": "noreply@naver.com",
                "body_text": """비밀번호가 성공적으로 변경되었습니다.

변경 일시: 2024-12-04 10:15
변경 IP: 123.456.xxx.xxx

본인이 변경하지 않았다면 즉시 고객센터로 연락주세요.
고객센터: 1588-1234""",
                "received_at": "2024-12-04T10:15:00",
                "ground_truth": {
                    "email_type": "기타",
                    "importance_score": 4,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["비밀번호 변경 완료", "보안 알림"]
                }
            },
            {
                "id": "synthetic_025",
                "subject": "Slack 알림 요약",
                "sender_name": "Slack",
                "sender_address": "notification@slack.com",
                "body_text": """You have 15 unread messages

#general (5 messages)
#dev-team (8 messages)
#random (2 messages)

View in Slack: https://slack.com/messages""",
                "received_at": "2024-12-04T18:00:00",
                "ground_truth": {
                    "email_type": "기타",
                    "importance_score": 3,
                    "needs_reply": False,
                    "sentiment": "neutral",
                    "key_points": ["Slack 알림", "15개 메시지"]
                }
            },
        ]

        return synthetic_emails

    def save_test_dataset(self, filename: str = "test_dataset.json"):
        """테스트 데이터셋 저장"""
        emails = self.generate_synthetic_emails()

        dataset = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "description": "AI 메일 비서 성능 측정용 테스트 데이터셋",
            "statistics": {
                "total": len(emails),
                "by_type": {
                    "채용": 5,
                    "마케팅": 5,
                    "공지": 5,
                    "개인": 5,
                    "기타": 5
                }
            },
            "emails": emails
        }

        filepath = DATA_DIR / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

        print(f"테스트 데이터셋 저장 완료: {filepath}")
        return filepath

    def save_ground_truth(self, filename: str = "ground_truth.json"):
        """Ground Truth 별도 저장"""
        emails = self.generate_synthetic_emails()

        ground_truth_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "description": "성능 평가용 정답 데이터",
            "ground_truths": [
                {
                    "id": email["id"],
                    "subject": email["subject"],
                    **email["ground_truth"]
                }
                for email in emails
            ]
        }

        filepath = DATA_DIR / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(ground_truth_data, f, ensure_ascii=False, indent=2)

        print(f"Ground Truth 저장 완료: {filepath}")
        return filepath

    def load_test_dataset(self, filename: str = "test_dataset.json") -> Dict:
        """테스트 데이터셋 로드"""
        filepath = DATA_DIR / filename

        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_ground_truth(self, filename: str = "ground_truth.json") -> Dict:
        """Ground Truth 로드"""
        filepath = DATA_DIR / filename

        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


# 싱글톤 인스턴스
dataset_generator = DatasetGenerator()


if __name__ == "__main__":
    # 데이터셋 생성 테스트
    generator = DatasetGenerator()
    generator.save_test_dataset()
    generator.save_ground_truth()
    print("데이터셋 생성 완료!")
