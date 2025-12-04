# 🚀 고급 AI 메일 비서 시스템 (D 버전)

## 📌 개요

LangGraph 기반 멀티 에이전트 시스템으로 업그레이드된 AI 메일 비서입니다.

**핵심 특징:**
- ✅ 멀티 에이전트 (Supervisor, Classifier, Analyzer, Reply, Feedback)
- ✅ 조건부 분기 (이메일 유형별 다른 처리)
- ✅ 병렬 처리 (3가지 톤 동시 생성)
- ✅ RAG (과거 이메일 검색 및 학습)
- ✅ 재시도 로직 (API 실패 시 3회 재시도)
- ✅ **Human-in-the-Loop (모든 답변은 사용자 승인 필수)**
- ✅ 피드백 학습 (사용자 수정사항 자동 학습)

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    SupervisorAgent (조율)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. ClassifierAgent                                             │
│     └─> 빠른 분류 (채용/마케팅/공지/개인/기타)                  │
│         └─> 재시도 3회 (tenacity)                              │
│                                                                 │
│  2. AdvancedAnalyzerAgent (조건부)                              │
│     ├─> 마케팅 이메일 → 스킵                                    │
│     ├─> 중요도 < 5 → 스킵                                       │
│     └─> 나머지 → 심층 분석 + RAG                                │
│         ├─> 유사 이메일 검색 (TF-IDF)                           │
│         ├─> 과거 답변 패턴 참고                                  │
│         └─> Gemini 심층 분석                                     │
│                                                                 │
│  3. AdvancedReplyAgent                                          │
│     └─> 병렬 답변 생성 (ThreadPoolExecutor)                     │
│         ├─> Formal (격식)                                       │
│         ├─> Casual (친근함)                                     │
│         └─> Brief (간결함)                                      │
│         └─> reply_suggestions 테이블 저장                       │
│                                                                 │
│  4. FeedbackAgent                                               │
│     └─> 사용자 피드백 학습                                       │
│         ├─> 수정 비율 계산                                       │
│         ├─> user_feedback 테이블 저장                           │
│         └─> reply_patterns 업데이트                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 새로운 데이터베이스 스키마

### 1. email 테이블 (확장)
```sql
ALTER TABLE email ADD COLUMN processing_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE email ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE email ADD COLUMN last_error TEXT;
```

### 2. reply_suggestions (새로 추가)
```sql
CREATE TABLE reply_suggestions (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES email(id),
    formal_draft TEXT,
    casual_draft TEXT,
    brief_draft TEXT,
    confidence_scores JSONB,
    status VARCHAR(50) DEFAULT 'pending',  -- pending/approved/rejected
    selected_tone VARCHAR(50)
);
```

### 3. user_feedback (새로 추가)
```sql
CREATE TABLE user_feedback (
    id SERIAL PRIMARY KEY,
    suggestion_id INTEGER REFERENCES reply_suggestions(id),
    email_id INTEGER REFERENCES email(id),
    original_draft TEXT,
    modified_draft TEXT,
    feedback_type VARCHAR(50),  -- accepted/modified/rejected
    modification_ratio FLOAT
);
```

### 4. reply_patterns (학습)
```sql
CREATE TABLE reply_patterns (
    id SERIAL PRIMARY KEY,
    email_type VARCHAR(50),
    reply_template TEXT,
    preferred_tone VARCHAR(50),
    usage_count INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 0.0
);
```

### 5. agent_execution_logs (디버깅)
```sql
CREATE TABLE agent_execution_logs (
    id SERIAL PRIMARY KEY,
    email_id INTEGER,
    agent_name VARCHAR(100),
    node_name VARCHAR(100),
    duration_ms INTEGER,
    status VARCHAR(50),
    error_message TEXT
);
```

---

## 🔄 전체 데이터 흐름 (사용자 시나리오)

### Step 1: 이메일 수신 → 분석

```
[사용자] "분석하기" 클릭
    ↓
POST /v2/analyze/123
    ↓
[SupervisorAgent] task="analyze" 실행
    ↓
┌─────────────────────────────────────┐
│ Node 1: ClassifierAgent             │
│ ─────────────────────────────────   │
│ • Gemini 빠른 분류                  │
│ • 재시도 3회 (tenacity)             │
│ • 결과: 채용, 중요도 8              │
└──────────┬──────────────────────────┘
           │
    조건부 분기: should_deep_analyze?
           │
    ┌──────┴──────┐
    │ 중요도 >= 5? │ → YES
    └──────┬──────┘
           ↓
┌─────────────────────────────────────┐
│ Node 2: AdvancedAnalyzerAgent       │
│ ─────────────────────────────────   │
│ • RAG: 유사 이메일 3개 검색         │
│ • 과거 답변 패턴 참고                │
│ • Gemini 심층 분석 (컨텍스트 포함) │
│ • 결과: needs_reply=True            │
└──────────┬──────────────────────────┘
           │
           ↓
    DB UPDATE email
    SET processing_status='analyzed',
        email_type='채용',
        importance_score=8,
        needs_reply=TRUE
```

**API 응답:**
```json
{
  "success": true,
  "email_id": 123,
  "analysis": {
    "email_type": "채용",
    "importance_score": 8,
    "needs_reply": true,
    "sentiment": "positive",
    "key_points": ["면접 일정", "준비물", "장소"]
  },
  "processing_status": "analyzed"
}
```

---

### Step 2: 답변 생성 (병렬)

```
[사용자] "답변 생성하기" 클릭
    ↓
POST /v2/generate-reply/123
    ↓
[SupervisorAgent] task="generate_reply" 실행
    ↓
┌─────────────────────────────────────┐
│ Node: AdvancedReplyAgent            │
│ ─────────────────────────────────   │
│ • RAG: 발신자에게 보낸 과거 답변 2개│
│ • ThreadPoolExecutor 병렬 생성      │
│                                     │
│   ┌─────────┐ ┌─────────┐ ┌──────┐│
│   │ Formal  │ │ Casual  │ │Brief ││
│   │ (3초)   │ │ (3초)   │ │(3초) ││
│   └────┬────┘ └────┬────┘ └───┬──┘│
│        └───────────┴──────────┘   │
│                 ↓                  │
│   reply_suggestions 테이블 저장    │
└─────────────┬───────────────────────┘
              │
              ↓
      suggestion_id: 456
```

**API 응답:**
```json
{
  "success": true,
  "email_id": 123,
  "suggestion_id": 456,
  "drafts": [
    {
      "tone": "formal",
      "content": "안녕하세요.\n면접 일정 안내 감사드립니다...",
      "confidence_score": 0.9
    },
    {
      "tone": "casual",
      "content": "안녕하세요!\n면접 일정 확인했습니다...",
      "confidence_score": 0.85
    },
    {
      "tone": "brief",
      "content": "확인했습니다. 해당 일정 참석 가능합니다.",
      "confidence_score": 0.8
    }
  ],
  "status": "pending_approval",
  "message": "답변이 생성되었습니다. 승인 후 발송할 수 있습니다."
}
```

---

### Step 3: 사용자 승인 및 발송 (Human-in-the-Loop)

```
[사용자] 답변 선택/수정 → "승인 및 발송" 클릭
    ↓
POST /v2/approve-reply/456
{
  "selected_tone": "formal",
  "modified_text": "안녕하세요.\n면접 일정 안내 감사합니다.\n..."  // 사용자 수정
}
    ↓
[Backend]
    1. reply_suggestions 조회
    2. n8n Webhook 호출 (메일 발송)
    3. sent_emails 저장
    4. email 테이블 업데이트 (is_replied_to=TRUE)
    5. reply_suggestions 상태 업데이트 (status='approved')
    ↓
[FeedbackAgent] 피드백 학습
    • 수정 비율 계산: 15%
    • user_feedback 저장
    • reply_patterns 업데이트 (success_rate 증가)
```

**API 응답:**
```json
{
  "success": true,
  "message": "답변이 발송되었습니다",
  "sent_id": 789,
  "feedback_learned": true
}
```

---

## 📡 새로운 API 엔드포인트 (v2)

### 1. 고급 분석
```bash
POST /v2/analyze/{email_id}

# 기존 /analyze/{email_id}와 차이:
# - Supervisor 조율
# - 조건부 분기 (마케팅은 스킵)
# - RAG 통합
# - 재시도 로직
```

### 2. 고급 답변 생성
```bash
POST /v2/generate-reply/{email_id}

# 기존 /generate-reply/{email_id}와 차이:
# - 병렬 생성 (3초 → 1초)
# - RAG 참고 (과거 답변 패턴)
# - reply_suggestions 테이블에 저장
# - **자동 발송 X, 승인 필요**
```

### 3. 답변 제안 조회
```bash
GET /v2/suggestions/{suggestion_id}

# 응답:
{
  "id": 456,
  "email_id": 123,
  "formal_draft": "...",
  "casual_draft": "...",
  "brief_draft": "...",
  "status": "pending"
}
```

### 4. 승인 및 발송
```bash
POST /v2/approve-reply/{suggestion_id}
{
  "selected_tone": "formal",
  "modified_text": "..."  // optional
}

# Human-in-the-Loop 핵심!
```

### 5. 에이전트 로그 조회
```bash
GET /v2/agent-logs/{email_id}

# 디버깅용: 어느 에이전트가 얼마나 걸렸는지
```

---

## 🔑 핵심 개선사항

### 기존 (Simple) vs 새로운 (Advanced)

| 항목 | Simple (기존) | Advanced (D 버전) |
|------|---------------|-------------------|
| **에이전트** | 단일 | 멀티 (Supervisor + 4개) |
| **그래프 구조** | 순차 실행 | 조건부 분기 + 병렬 |
| **RAG** | ❌ | ✅ (TF-IDF 유사도 검색) |
| **재시도** | ❌ | ✅ (tenacity, 3회) |
| **병렬 처리** | ❌ | ✅ (ThreadPoolExecutor) |
| **사용자 승인** | ❌ (자동 발송) | ✅ (필수 승인) |
| **피드백 학습** | ❌ | ✅ (자동 학습) |
| **로깅** | 기본 print | DB 저장 (agent_execution_logs) |

---

## 🧪 테스트 시나리오

### 1. PostgreSQL 초기화
```bash
docker exec -it mail_postgres psql -U admin -d mail < backend/init.sql
```

### 2. 이메일 분석 (v2)
```bash
curl -X POST http://localhost:8000/v2/analyze/123
```

**결과 확인:**
```sql
SELECT processing_status, email_type, importance_score
FROM email WHERE id = 123;

SELECT * FROM agent_execution_logs WHERE email_id = 123;
```

### 3. 답변 생성 (v2)
```bash
curl -X POST http://localhost:8000/v2/generate-reply/123
```

**결과 확인:**
```sql
SELECT * FROM reply_suggestions WHERE email_id = 123;
```

### 4. 승인 및 발송
```bash
curl -X POST http://localhost:8000/v2/approve-reply/456 \
  -H "Content-Type: application/json" \
  -d '{
    "selected_tone": "formal",
    "modified_text": "사용자 수정 답변..."
  }'
```

**결과 확인:**
```sql
SELECT * FROM sent_emails WHERE original_email_id = 123;
SELECT * FROM user_feedback WHERE email_id = 123;
SELECT * FROM reply_patterns;
```

---

## 🎯 LangGraph의 진짜 활용

### 왜 이제 LangGraph가 필요한가?

**Simple 버전 (불필요):**
```python
# 단순 순차 실행
analyze → save → END
```

**Advanced 버전 (필수):**
```python
# 복잡한 워크플로우
START
  → classify
  → [조건부 분기]
      ├─> 마케팅 → END
      ├─> 낮은 중요도 → END
      └─> 심층 분석 → RAG → finalize → END

# 병렬 처리
generate_formal ┐
generate_casual ├─> merge → save
generate_brief  ┘

# 재시도
try → fail → retry (3회) → fallback
```

---

## 📈 성능 개선

| 작업 | Simple | Advanced | 개선 |
|------|--------|----------|------|
| 이메일 분석 | 5초 | 3-7초 (조건부) | 마케팅 스킵 시 1초 |
| 답변 생성 | 9초 (순차) | 3초 (병렬) | **3배 빠름** |
| 재시도 | 실패 시 중단 | 3회 재시도 | **안정성 향상** |

---

## 🚀 실행 방법

### 1. Docker 실행
```bash
docker-compose up -d
```

### 2. PostgreSQL 초기화
```bash
docker exec -it mail_postgres psql -U admin -d mail -f /path/to/init.sql
```

### 3. API 테스트
```bash
# 건강 체크
curl http://localhost:8000/health

# Swagger UI
http://localhost:8000/docs
```

---

## 📚 Frontend 업데이트 필요

현재 Frontend는 v1 API (`/analyze`, `/generate-reply`)를 사용합니다.

**업데이트 필요 사항:**
1. `api.js`: v2 엔드포인트 추가
2. `ReplyGenerator.js`: 승인 버튼 추가
3. 새로운 컴포넌트: `ApprovalModal.js`

---

## 🎓 학습 포인트

이 D 버전을 통해 배울 수 있는 것:

1. **LangGraph 실전 활용**
   - 조건부 분기 (`add_conditional_edges`)
   - 병렬 처리 (ThreadPoolExecutor)
   - 상태 관리 (TypedDict)

2. **RAG 시스템**
   - TF-IDF 벡터 유사도
   - 과거 데이터 참고

3. **프로덕션 패턴**
   - Human-in-the-Loop
   - 재시도 로직 (tenacity)
   - 피드백 학습
   - 에이전트 로깅

4. **멀티 에이전트**
   - Supervisor 패턴
   - 역할 분담 (Classifier, Analyzer, Reply, Feedback)

---

## 🔮 향후 개선 방향

- [ ] ElasticSearch 통합 (TF-IDF → 벡터 검색)
- [ ] LangSmith 추가 (에이전트 시각화)
- [ ] WebSocket (실시간 진행 상황)
- [ ] A/B 테스트 (답변 품질 비교)
- [ ] 멀티모달 (이미지 첨부 분석)

---

## 📞 문의

프로젝트 관련 질문: [GitHub Issues]
