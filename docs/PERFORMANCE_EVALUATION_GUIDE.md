# AI 메일 비서 성능 측정 가이드

## 목차
1. [개요](#1-개요)
2. [측정 대상](#2-측정-대상)
3. [평가 기준 상세](#3-평가-기준-상세)
4. [측정 방법론](#4-측정-방법론)
5. [실행 절차](#5-실행-절차)
6. [시각화 및 리포트](#6-시각화-및-리포트)
7. [API 사용 예시](#7-api-사용-예시)
8. [부록](#8-부록)

---

## 1. 개요

### 1.1 목적
이 문서는 AI 메일 비서 시스템의 **성능을 객관적으로 측정**하고, **개선 효과를 정량화**하기 위한 가이드입니다.

### 1.2 성능 측정이 필요한 이유
- 현재 시스템의 품질 수준 파악 (Baseline)
- 프롬프트/모델 변경 시 효과 검증
- 지속적인 품질 모니터링
- A/B 테스트를 통한 최적화

### 1.3 핵심 원칙
```
┌─────────────────────────────────────────────────────────┐
│  측정할 수 없으면 개선할 수 없다                          │
│  "If you can't measure it, you can't improve it"        │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 측정 대상

### 2.1 3가지 핵심 기능

| 기능 | 설명 | n8n 워크플로우 |
|------|------|---------------|
| **이메일 분석** | 이메일 유형, 중요도, 감정 분류 | `/webhook/analyze` |
| **답변 생성** | 3가지 톤으로 답변 초안 생성 | `/webhook/generate-reply` |
| **일일 요약** | 하루 이메일 종합 요약 | `/webhook/summary` |

### 2.2 데이터 흐름

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  이메일   │ ──▶ │  n8n     │ ──▶ │  Gemini  │ ──▶ │  결과    │
│  (입력)   │     │ Webhook  │     │  AI 처리  │     │  (출력)  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                        │
                                        ▼
                               ┌──────────────┐
                               │  성능 평가    │
                               │  시스템      │
                               └──────────────┘
```

---

## 3. 평가 기준 상세

### 3.1 이메일 분석 평가 (100점 만점)

| 항목 | 배점 | 평가 기준 | 측정 방식 |
|------|------|----------|----------|
| **email_type** | 25점 | 5가지 분류 정확도 | 정답과 일치 여부 |
| **importance_score** | 25점 | 중요도 점수 적절성 | 정답 ±2 이내 |
| **needs_reply** | 25점 | 답변 필요 여부 판단 | True/False 일치 |
| **sentiment** | 25점 | 감정 분석 정확도 | 3가지 분류 일치 |

#### email_type 분류 체계
```
채용     : 면접, 채용, 지원, 합격/불합격 관련
마케팅   : 광고, 프로모션, 할인, 이벤트 안내
공지     : 공식 안내, 정책 변경, 시스템 공지
개인     : 개인적 문의, 안부, 1:1 커뮤니케이션
기타     : 위 분류에 해당하지 않는 경우
```

#### importance_score 가이드
```
9-10점 : 즉시 대응 필요 (면접 일정, 긴급 요청)
7-8점  : 중요함 (업무 관련, 답변 필요한 문의)
4-6점  : 보통 (일반 공지, 정보성 이메일)
1-3점  : 낮음 (스팸성, 광고, 뉴스레터)
```

#### 점수 계산 예시
```python
# 예시: AI 분석 결과 vs Ground Truth
ai_result = {
    "email_type": "채용",        # 정답: "채용" ✓ → 25점
    "importance_score": 8,       # 정답: 9 (차이 1) ✓ → 25점
    "needs_reply": True,         # 정답: True ✓ → 25점
    "sentiment": "positive"      # 정답: "neutral" ✗ → 0점
}
# 총점: 75/100점
```

---

### 3.2 답변 생성 평가 (100점 만점)

| 항목 | 배점 | 평가 기준 | 세부 설명 |
|------|------|----------|----------|
| **문맥 이해도** | 25점 | 원본 이메일 내용 반영 | 핵심 요청/질문 파악 |
| **톤 일관성** | 25점 | 요청된 톤 유지 | formal/casual/brief |
| **응답 적절성** | 25점 | 답변으로서의 적합성 | 질문에 답변, 요청 처리 |
| **한국어 자연스러움** | 25점 | 문법/어휘/경어체 | 자연스러운 한국어 |

#### 톤별 특성
```
┌─────────┬────────────────────────────────────────────┐
│  톤     │  특성                                      │
├─────────┼────────────────────────────────────────────┤
│ formal  │ 격식체, 비즈니스 어투, "~합니다", "~드림"   │
│ casual  │ 친근함, 이모티콘 가능, "~해요", "~입니다~"  │
│ brief   │ 핵심만, 간결함, 불필요한 인사 최소화       │
└─────────┴────────────────────────────────────────────┘
```

#### 평가 프롬프트 (LLM-as-Judge용)
```
다음 기준으로 각 항목을 0-25점으로 평가하세요:

1. 문맥 이해도: 원본 이메일의 핵심 내용을 정확히 파악했는가?
2. 톤 일관성: 요청된 톤(formal/casual/brief)을 유지했는가?
3. 응답 적절성: 이메일에 대한 답변으로 적절한가?
4. 한국어 자연스러움: 문법과 어휘 사용이 자연스러운가?
```

---

### 3.3 일일 요약 평가 (100점 만점)

| 항목 | 배점 | 평가 기준 |
|------|------|----------|
| **정보 완전성** | 30점 | 핵심 내용 누락 없음 |
| **간결성** | 20점 | 불필요한 정보 제거 |
| **정확성** | 30점 | 사실 왜곡 없음 |
| **가독성** | 20점 | 구조화, 읽기 쉬움 |

---

## 4. 측정 방법론

### 4.1 Human Evaluation (인간 평가)

#### 개요
사람이 직접 AI 출력물을 평가하는 방식입니다.

#### 장점
- ✅ 가장 신뢰성 높은 평가
- ✅ 미묘한 뉘앙스와 맥락 파악 가능
- ✅ 실제 사용자 관점 반영

#### 단점
- ❌ 시간과 비용 소요
- ❌ 평가자 간 일관성 문제
- ❌ 대량 평가 어려움

#### 사용 시점
- Ground Truth (정답 데이터) 생성
- 최종 품질 검증
- 사용자 만족도 조사

#### 실행 방법
```
1. 평가할 이메일 샘플 선정 (10-20개)
2. 각 이메일에 대해 AI 결과 확인
3. 평가 기준표에 따라 점수 부여
4. 평가자 2인 이상 교차 검증 (선택)
5. 최종 점수 산출
```

---

### 4.2 LLM-as-Judge (LLM 평가자)

#### 개요
GPT-4, Claude 등 다른 LLM을 평가자로 사용합니다.

#### 장점
- ✅ 대량 평가 가능
- ✅ 일관된 기준 적용
- ✅ 빠른 평가 속도

#### 단점
- ❌ API 비용 발생
- ❌ LLM 자체의 편향 가능성
- ❌ 복잡한 맥락 이해 한계

#### 사용 시점
- 답변 생성 품질 평가
- 요약 품질 평가
- A/B 테스트 자동화

#### 평가 프롬프트 예시
```python
evaluation_prompt = """
다음 이메일에 대한 AI 생성 답변을 평가해주세요.

## 원본 이메일
{original_email}

## AI 생성 답변
{ai_reply}

## 평가 기준 (각 0-25점)
1. 문맥 이해도
2. 톤 일관성
3. 응답 적절성
4. 한국어 자연스러움

JSON 형식으로 점수와 평가 이유를 제공하세요.
"""
```

#### 비용 예측
```
GPT-4 기준:
- 입력: ~500 토큰/평가
- 출력: ~200 토큰/평가
- 비용: ~$0.02/평가
- 100개 평가 시: ~$2
```

---

### 4.3 자동화 메트릭

#### 4.3.1 분류 정확도 (Classification Accuracy)

```python
# email_type, sentiment, needs_reply 평가
accuracy = (정답 개수 / 전체 개수) * 100

예시:
- 10개 이메일 중 8개 email_type 정답
- 정확도 = 80%
```

#### 4.3.2 회귀 오차 (Regression Error)

```python
# importance_score 평가
MAE = Σ|AI점수 - 정답점수| / n

예시:
- AI: [8, 7, 5], 정답: [9, 7, 6]
- MAE = (|8-9| + |7-7| + |5-6|) / 3 = 0.67
```

#### 4.3.3 텍스트 유사도 (선택적)

```python
# BLEU Score - 답변/요약 평가
from nltk.translate.bleu_score import sentence_bleu

reference = "정답 답변 텍스트".split()
candidate = "AI 생성 답변".split()
score = sentence_bleu([reference], candidate)
```

---

## 5. 실행 절차

### 5.1 전체 워크플로우

```
┌─────────────────────────────────────────────────────────────┐
│                    성능 측정 워크플로우                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1          Step 2          Step 3          Step 4    │
│  ┌─────┐        ┌─────┐        ┌─────┐        ┌─────┐     │
│  │Ground│   ──▶  │Base │   ──▶  │개선  │   ──▶  │재측정│     │
│  │Truth │        │line │        │적용  │        │비교  │     │
│  └─────┘        └─────┘        └─────┘        └─────┘     │
│                                                             │
│  정답 데이터      현재 성능       프롬프트        개선 효과    │
│  생성            측정            업데이트        검증         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### 5.2 Step 1: Ground Truth 생성

#### 목적
AI 결과를 비교할 **정답 데이터**를 만듭니다.

#### 샘플 선정 기준
```
- 총 10-20개 이메일 선정
- 각 email_type별 최소 2개 이상 포함
- body_text가 정상인 이메일만 선정
- 다양한 발신자/주제 포함
```

#### Ground Truth 템플릿

```json
{
  "email_id": 1,
  "subject": "면접 일정 안내",
  "ground_truth": {
    "email_type": "채용",
    "importance_score": 9,
    "needs_reply": true,
    "sentiment": "positive",
    "key_points": ["면접 일정", "준비물 안내"]
  },
  "annotated_by": "평가자명",
  "annotated_at": "2024-12-04"
}
```

#### DB 저장
```sql
INSERT INTO ground_truth
(email_id, email_type, importance_score, needs_reply, sentiment, annotated_by)
VALUES (1, '채용', 9, true, 'positive', '평가자명');
```

---

### 5.3 Step 2: Baseline 측정

#### 목적
현재 시스템의 성능을 측정하여 **기준점**을 설정합니다.

#### 실행 방법

```bash
# 1. 이메일 분석 실행
curl -X POST http://localhost:8000/analyze/{email_id}

# 2. 답변 생성 실행
curl -X POST http://localhost:8000/generate-reply/{email_id}
```

#### 결과 기록

```python
from src.evaluation import evaluator

# AI 결과 vs Ground Truth 비교
evaluation = evaluator.evaluate_analysis(
    email_id=1,
    ai_result={
        "email_type": "채용",
        "importance_score": 8,
        "needs_reply": True,
        "sentiment": "positive"
    },
    ground_truth={
        "email_type": "채용",
        "importance_score": 9,
        "needs_reply": True,
        "sentiment": "positive"
    }
)

print(f"Total Score: {evaluation.total_score}/100")
```

#### Baseline 저장
```sql
INSERT INTO performance_evaluations
(evaluation_type, email_id, version_tag, total_score, prompt_version)
VALUES ('analysis', 1, 'baseline', 75.0, 'v1');
```

---

### 5.4 Step 3: 프롬프트 개선 적용

#### 개선된 프롬프트 위치
```
backend/src/prompts/improved_prompts.py
```

#### 주요 개선 사항

| 개선 항목 | 설명 |
|----------|------|
| Few-shot 예시 | 각 유형별 2-3개 예시 추가 |
| Chain-of-Thought | 단계별 분석 유도 |
| 출력 형식 명확화 | JSON 스키마 명시 |
| 컨텍스트 보강 | 발신자 도메인 분석 추가 |

#### n8n에 적용하기
1. n8n UI 접속 (http://localhost:5678)
2. 분석 워크플로우 열기
3. Code 노드의 프롬프트를 `improved_prompts.py`의 `ANALYSIS_PROMPT_V2`로 교체
4. 워크플로우 저장 및 활성화

---

### 5.5 Step 4: 재측정 및 비교

#### 동일 샘플로 재평가
```python
# 개선 후 결과 평가
evaluation_v2 = evaluator.evaluate_analysis(
    email_id=1,
    ai_result=improved_ai_result,
    ground_truth=ground_truth
)
```

#### 비교 리포트 생성
```python
report = evaluator.generate_comparison_report(
    before_stats=baseline_stats,
    after_stats=improved_stats,
    evaluation_type="analysis"
)
print(report)
```

---

## 6. 시각화 및 리포트

### 6.1 비교 리포트 예시

```
╔══════════════════════════════════════════════════════════════╗
║            ANALYSIS 성능 개선 비교 리포트                     ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  📊 전체 점수 비교                                            ║
║  ┌────────────┬────────────┬────────────┬────────────┐       ║
║  │   항목     │   Before   │   After    │   개선율   │       ║
║  ├────────────┼────────────┼────────────┼────────────┤       ║
║  │ 평균 점수  │   65.0점   │   85.0점   │  +30.8%   │       ║
║  └────────────┴────────────┴────────────┴────────────┘       ║
║                                                              ║
║  📈 항목별 상세                                               ║
║  email_type        ████████████████████░░░░░  20.0 (+5.0)   ║
║  importance        ██████████████████░░░░░░░  18.0 (+3.0)   ║
║  needs_reply       █████████████████████████  25.0 (+5.0)   ║
║  sentiment         ██████████████████████░░░  22.0 (+7.0)   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

### 6.2 시각화 차트 (추후 구현)

```
점수 분포 히스토그램
───────────────────
0-20   │██
20-40  │████
40-60  │████████
60-80  │████████████████
80-100 │██████████████████████
```

---

## 7. API 사용 예시

### 7.1 성능 평가 실행

```python
from src.evaluation import evaluator, create_ground_truth_template
from src.services.db_service import db

# 1. 평가할 이메일 조회
emails = db.get_emails(limit=10)

# 2. Ground Truth 템플릿 생성
templates = create_ground_truth_template(emails)
print(templates)  # 이 템플릿에 정답 입력

# 3. 분석 평가 실행
for email in emails:
    ai_result = {
        "email_type": email.get('email_type'),
        "importance_score": email.get('importance_score'),
        "needs_reply": email.get('needs_reply'),
        "sentiment": email.get('sentiment')
    }

    ground_truth = get_ground_truth(email['id'])  # DB에서 조회

    evaluation = evaluator.evaluate_analysis(
        email_id=email['id'],
        ai_result=ai_result,
        ground_truth=ground_truth
    )
    print(f"Email {email['id']}: {evaluation.total_score}점")

# 4. 통계 확인
stats = evaluator.get_analysis_statistics()
print(stats)

# 5. 결과 내보내기
evaluator.export_results("evaluation_results.json")
```

### 7.2 답변 평가 (LLM-as-Judge)

```python
# 1. 평가 프롬프트 생성
prompt = evaluator.create_reply_evaluation_prompt(
    original_email={
        "sender_name": "김채용",
        "sender_address": "hr@company.com",
        "subject": "면접 일정 안내",
        "body_text": "면접 일시: 12월 5일 오후 2시..."
    },
    generated_reply="안녕하세요. 면접 일정 확인했습니다...",
    target_tone="formal"
)

# 2. GPT-4/Claude에 평가 요청 (별도 API 호출 필요)
llm_response = call_evaluation_llm(prompt)

# 3. 결과 파싱
evaluation = evaluator.parse_reply_evaluation(
    email_id=1,
    llm_response=llm_response
)
print(f"답변 품질: {evaluation.total_score}점")
```

---

## 8. 부록

### 8.1 평가 체크리스트

```
□ Ground Truth 데이터 준비 완료
□ Baseline 측정 완료
□ 프롬프트 개선 적용 완료
□ 재측정 완료
□ 비교 리포트 생성 완료
□ 결과 문서화 완료
```

### 8.2 문제 해결 가이드

| 문제 | 원인 | 해결 방법 |
|------|------|----------|
| 분석 결과가 저장 안 됨 | DB 컬럼 누락 | 마이그레이션 실행 |
| 답변 품질이 낮음 | 프롬프트 부족 | Few-shot 예시 추가 |
| 평가 점수 일관성 없음 | 평가 기준 모호 | 기준 명확화 |

### 8.3 참고 자료

- [LLM Evaluation Best Practices](https://www.anthropic.com/research)
- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [n8n Documentation](https://docs.n8n.io/)

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0 | 2024-12-04 | 최초 작성 |

---

*이 문서는 AI 메일 비서 프로젝트의 성능 측정 가이드입니다.*
