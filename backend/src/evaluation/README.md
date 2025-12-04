# AI 메일 비서 성능 평가 시스템

## 목차
1. [개요](#개요)
2. [테스트 데이터셋](#테스트-데이터셋)
3. [평가 지표](#평가-지표)
4. [테스트 방법](#테스트-방법)
5. [빠른 시작](#빠른-시작)
6. [폴더 구조](#폴더-구조)

---

## 개요

이 시스템은 AI 메일 비서의 성능을 객관적으로 측정하고 개선을 추적하기 위해 설계되었습니다.

**목적**:
- 이메일 분석 정확도 측정 (유형 분류, 중요도, 답변 필요 여부, 감정)
- 답변 생성 품질 평가
- RAG 적용 전/후 성능 비교

---

## 테스트 데이터셋

### 1. 데이터 생성 방식

테스트 데이터는 **합성(Synthetic) 데이터**로 생성됩니다.

```
dataset_generator.py
└── generate_synthetic_emails()
    ├── 실제 이메일 패턴을 분석하여 설계
    ├── 각 유형별로 대표적인 시나리오 포함
    └── Ground Truth(정답)를 함께 생성
```

**합성 데이터를 사용하는 이유**:
1. **일관성**: 동일한 데이터로 반복 측정 가능 (Phase 1 vs Phase 2 비교)
2. **정답 확보**: 미리 정의된 Ground Truth로 정확한 평가 가능
3. **다양성 보장**: 모든 유형과 시나리오를 균등하게 커버
4. **프라이버시**: 실제 개인 메일 데이터 사용 불필요

### 2. 데이터 구성 (총 25개)

| 유형 | 개수 | 시나리오 예시 |
|------|------|--------------|
| **채용** | 5개 | 면접 합격, 불합격, 코딩테스트, 연봉협상, 이력서 접수 |
| **마케팅** | 5개 | 프로모션, 기능 업데이트, 웨비나, 구독 갱신, 뉴스레터 |
| **공지** | 5개 | 시설 개장, 시스템 점검, 개인정보 변경, 보안 업데이트, 휴무 |
| **개인** | 5개 | 협업 요청, 미팅 후속, 생일 축하, 기술 질문, 불참 안내 |
| **기타** | 5개 | 택배, 카드 알림, GitHub PR, 비밀번호 변경, Slack 알림 |

### 3. 데이터 구조

```json
{
  "id": "synthetic_001",
  "subject": "[ABC회사] 서류 전형 합격 및 면접 안내",
  "sender_name": "ABC회사 인사팀",
  "sender_address": "hr@abc-company.com",
  "body_text": "안녕하세요...(이메일 본문)",
  "received_at": "2024-12-04T09:00:00",
  "ground_truth": {
    "email_type": "채용",
    "importance_score": 9,
    "needs_reply": true,
    "sentiment": "positive",
    "key_points": ["서류 합격", "면접 일정 12/10", "참석 여부 회신 필요"]
  }
}
```

### 4. Ground Truth 정의 기준

| 항목 | 정의 기준 |
|------|----------|
| **email_type** | 이메일의 주된 목적에 따라 5가지로 분류 |
| **importance_score** | 1-10점, 답변 시급성 + 비즈니스 영향도 고려 |
| **needs_reply** | 발신자가 명시적/암시적으로 응답을 기대하는지 |
| **sentiment** | 이메일 전체 톤 (positive/neutral/negative) |
| **key_points** | 이메일 핵심 내용 3개 이내 |

**importance_score 기준**:
```
10점: 매우 긴급 (합격 통보, 연봉 협상, 긴급 보안)
7-9점: 높음 (면접 안내, 프로젝트 협업, 미팅 후속)
4-6점: 중간 (코딩테스트, 기술 질문, 시스템 점검)
1-3점: 낮음 (마케팅, 뉴스레터, 카드 알림)
```

---

## 평가 지표

### 1. 이메일 분석 평가 (100점 만점)

| 지표 | 배점 | 채점 방식 | 선정 이유 |
|------|------|----------|----------|
| **email_type** | 25점 | 정확히 일치하면 25점, 불일치 0점 | 분류가 맞아야 후속 처리가 올바름 |
| **importance_score** | 25점 | ±2 이내 25점, ±3 15점, 그 외 0점 | 정확한 숫자보다 범위가 실용적 |
| **needs_reply** | 25점 | 정확히 일치하면 25점, 불일치 0점 | 답변 필요 여부는 핵심 의사결정 |
| **sentiment** | 25점 | 정확히 일치하면 25점, 불일치 0점 | 톤 파악이 답변 생성에 영향 |

**지표 선정 이유**:

1. **균등 배점 (각 25점)**
   - 4가지 요소 모두 실무에서 동등하게 중요
   - 특정 항목에 편향되지 않은 종합 평가

2. **importance_score 허용 오차 (±2)**
   - 중요도는 주관적 요소가 있음
   - 9점 vs 10점 차이보다 3점 vs 8점 차이가 더 중요
   - 실용적 관점에서 "근접하면 OK" 정책

3. **Binary 평가 (email_type, needs_reply, sentiment)**
   - 부분 점수는 모호함 유발
   - 명확한 성공/실패 기준이 개선에 도움

### 2. 답변 생성 평가 (LLM-as-Judge)

| 지표 | 배점 | 평가 기준 |
|------|------|----------|
| **문맥 이해도** | 25점 | 원본 이메일 핵심을 파악했는가 |
| **톤 일관성** | 25점 | 요청된 톤(격식/친근/간결)을 유지했는가 |
| **응답 적절성** | 25점 | 질문에 답변, 요청 처리 등이 적절한가 |
| **한국어 자연스러움** | 25점 | 문법, 어휘, 경어체 사용이 자연스러운가 |

### 3. 통계 지표

```
┌─────────────────────────────────────────┐
│             통계 지표 설명               │
├─────────────────────────────────────────┤
│ average_score : 전체 평균 점수          │
│ median_score  : 중앙값 (이상치 영향 배제)│
│ std_dev       : 표준편차 (일관성 측정)   │
│ min/max       : 최악/최고 케이스 파악    │
│ breakdown     : 항목별 상세 점수        │
└─────────────────────────────────────────┘
```

---

## 테스트 방법

### 1. 테스트 프로세스

```
┌─────────────────────────────────────────────────────────────────┐
│                      성능 측정 프로세스                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [1] 데이터 생성                                                │
│      └── run_evaluation.py --generate-data                     │
│          ├── test_dataset.json (25개 이메일)                    │
│          └── ground_truth.json (정답 데이터)                    │
│                           │                                     │
│                           ▼                                     │
│  [2] Phase 1 측정 (Baseline)                                   │
│      └── run_evaluation.py --phase phase1_baseline             │
│          ├── n8n /webhook/analyze 호출                         │
│          ├── AI 결과 vs Ground Truth 비교                      │
│          └── results/phase1_baseline.json 저장                 │
│                           │                                     │
│                           ▼                                     │
│  [3] RAG DB 구축 (개선 작업)                                    │
│      └── 과거 이메일 패턴, 피드백 학습                          │
│                           │                                     │
│                           ▼                                     │
│  [4] Phase 2 측정 (With RAG)                                   │
│      └── run_evaluation.py --phase phase2_with_rag             │
│                           │                                     │
│                           ▼                                     │
│  [5] 비교 리포트                                                │
│      └── run_evaluation.py --compare                           │
│          └── reports/phase_comparison.md                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2. 측정 흐름

```python
# 각 이메일에 대해:
for email in test_emails:
    # 1. n8n webhook으로 AI 분석 요청
    ai_result = requests.post("http://localhost:5678/webhook/analyze", {
        "email_id": email["id"],
        "subject": email["subject"],
        "body_text": email["body_text"],
        ...
    })

    # 2. Ground Truth와 비교
    ground_truth = load_ground_truth(email["id"])

    # 3. 점수 계산
    score = evaluate(ai_result, ground_truth)
    # email_type: 일치하면 25점
    # importance: ±2 이내면 25점
    # needs_reply: 일치하면 25점
    # sentiment: 일치하면 25점

    # 4. 결과 저장
    save_result(email_id, score, notes)
```

### 3. 실행 환경 요구사항

```
필수 조건:
├── Docker 컨테이너 실행 중
│   ├── mail_postgres (PostgreSQL)
│   ├── n8n (워크플로우 엔진)
│   └── backend (FastAPI)
├── n8n 워크플로우 활성화
│   └── /webhook/analyze 엔드포인트 동작
└── Python 환경
    └── requests, json 모듈
```

---

## 빠른 시작

### 1. 테스트 데이터 생성

```bash
cd backend/src/evaluation/code
python run_evaluation.py --generate-data
```

결과:
- `data/test_dataset.json` - 25개 합성 이메일
- `data/ground_truth.json` - 정답 데이터

### 2. Phase 1 (Baseline) 측정

```bash
python run_evaluation.py --phase phase1_baseline
```

결과:
- `results/phase1_baseline.json`
- `reports/phase1_baseline/analysis_report.md`

### 3. Phase 2 (RAG 적용 후) 측정

```bash
python run_evaluation.py --phase phase2_with_rag
```

### 4. Phase 비교

```bash
python run_evaluation.py --compare
```

결과:
- `reports/phase_comparison.md`

---

## 폴더 구조

```
evaluation/
├── code/                          # 평가 코드
│   ├── __init__.py
│   ├── performance_evaluator.py   # 성능 평가 클래스
│   ├── dataset_generator.py       # 테스트 데이터 생성기
│   └── run_evaluation.py          # 평가 실행 스크립트
├── data/                          # 테스트 데이터
│   ├── test_dataset.json          # 25개 합성 이메일 (고정)
│   └── ground_truth.json          # 정답 데이터
├── results/                       # 측정 결과 (JSON)
│   ├── phase1_baseline.json       # Phase 1 결과
│   └── phase2_with_rag.json       # Phase 2 결과
├── reports/                       # 리포트 (Markdown)
│   ├── phase1_baseline/
│   │   └── analysis_report.md
│   ├── phase2_with_rag/
│   │   └── analysis_report.md
│   └── phase_comparison.md        # Phase 비교 리포트
└── README.md                      # 이 파일
```

---

## 옵션 설명

| 옵션 | 설명 |
|------|------|
| `--phase` | 평가 Phase 선택 (phase1_baseline, phase2_with_rag) |
| `--limit N` | 평가할 이메일 수 제한 (테스트용) |
| `--analysis-only` | 이메일 분석만 평가 (답변 생성 제외) |
| `--compare` | Phase 1과 Phase 2 비교 리포트 생성 |
| `--generate-data` | 테스트 데이터만 생성 |

---

## 결과 해석 가이드

### 점수 범위 해석

| 점수 범위 | 평가 | 권장 조치 |
|----------|------|----------|
| 90-100 | 우수 | 현재 수준 유지 |
| 75-89 | 양호 | 약한 항목 개선 |
| 60-74 | 보통 | 프롬프트 튜닝 필요 |
| 60 미만 | 미흡 | 전면적 개선 필요 |

### 항목별 개선 방향

```
email_type 점수 낮음:
  → 프롬프트에 분류 예시 추가
  → Few-shot learning 적용

importance_score 점수 낮음:
  → 중요도 기준 명확화
  → 업무 맥락 정보 추가

needs_reply 점수 낮음:
  → 답변 필요 신호 키워드 정의
  → 질문/요청 패턴 학습

sentiment 점수 낮음:
  → 한국어 감정 표현 예시 추가
  → 비즈니스 맥락 고려
```

---

## 주의사항

1. **일관성**: 두 Phase 측정 시 반드시 동일한 테스트 데이터 사용
2. **n8n 필요**: 측정 전 n8n 워크플로우가 활성화되어 있어야 함
3. **시간**: 25개 이메일 분석에 약 5-10분 소요
4. **네트워크**: localhost:5678로 n8n에 접근 가능해야 함

---

## 문의

문제가 있으면 이슈를 등록해주세요.
