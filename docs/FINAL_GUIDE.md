# LangGraph + n8n 하이브리드 시스템 최종 가이드

## 🎉 완료된 작업

### ✅ Backend 구현 완료
1. **n8n Tool Wrapper** (`src/tools/n8n_tools.py`)
   - n8n 워크플로우를 Python 함수로 래핑
   - `fetch_emails()`, `send_email()`, `summarize_emails()`, `generate_reply()`, `analyze_email()`

2. **LangGraph Supervisor Agent** (`src/agents/email_processor.py`)
   - 이메일 처리 워크플로우 orchestration
   - Gemini를 사용한 intelligent routing
   - 상태 관리 및 조건부 실행

3. **Backend API 업데이트** (`src/main.py`)
   - `POST /sync-emails`: LangGraph supervisor로 전체 워크플로우 실행
   - `POST /summary/generate`: LangGraph supervisor로 요약 생성

---

## 🏗️ 최종 시스템 아키텍처

```
사용자: "메일 동기화" 버튼 클릭
  ↓
Frontend → Backend API
  ↓
LangGraph Supervisor ┐
  ↓                  │ Orchestration
Step 1: n8n FetchEmailAgent 호출 ← IMAP (네이버)
  ↓
Step 2: Gemini로 이메일 분류
  - 이메일 유형: 채용/마케팅/공지/개인/기타
  - 중요도 점수: 0-10
  - 답변 필요 여부: true/false
  ↓
Step 3: 조건부 실행 (중요도 >= 7?)
  YES → n8n GenerateReplyAgent 호출 ← Gemini (3가지 톤 답변)
  NO  → 종료
  ↓
Response:
  {
    "new_emails": 5,
    "important_emails": 2,
    "reply_drafts_generated": 2,
    "classifications": [...]
  }
```

---

## 📋 사용자가 해야 할 작업

### 현재 상태
- ✅ Backend 코드 완료
- ✅ LangGraph 구현 완료
- ❌ n8n 워크플로우 아직 초기 상태 (수정 필요)

### 필요한 작업

#### 1단계: n8n 워크플로우 #1 수정 (FetchEmailAgent)
현재 워크플로우 #1 "메일 동기화"는 Gemini 요약까지 포함되어 있습니다.
**→ Gemini 요약 노드 제거** (순수 메일 가져오기만)

**가이드**: `n8n_workflows/workflow_1_modification_guide.md`

**최종 구조**:
```
Webhook → IMAP → Loop → Code(HTML정리) → Insert(email) → Response
```

**Webhook 경로**: `/webhook-test/mail`
**Response 형식**:
```json
{
  "success": true,
  "new_emails": 5,
  "email_ids": [1, 2, 3, 4, 5],
  "total_emails": 10
}
```

#### 2단계: n8n 워크플로우 #3 생성 (SummarizeEmailAgent)
**가이드**: `n8n_workflows/workflow_3_daily_summary.md`

**구조**:
```
Webhook → PostgreSQL(조회) → Code(결합) → Gemini → PostgreSQL(저장) → Response
```

**Webhook 경로**: `/webhook-test/summary`

#### 3단계: n8n 워크플로우 #4 생성 (AnalyzeEmailAgent) - 선택사항
**가이드**: `n8n_workflows/workflow_4_email_analysis.md`

**구조**:
```
Webhook → PostgreSQL(조회) → Code(프롬프트) → Gemini → Code(파싱) → PostgreSQL(저장) → Response
```

**Webhook 경로**: `/webhook-test/analyze`
**Note**: 현재 LangGraph가 Gemini를 직접 호출하므로 선택사항

#### 4단계: n8n 워크플로우 #5 생성 (GenerateReplyAgent)
**가이드**: `n8n_workflows/workflow_5_reply_generation.md`

**구조**:
```
Webhook → PostgreSQL(조회) → Code(프롬프트) → Gemini(3개 병렬) → Code(결합) → PostgreSQL(저장) → Response
```

**Webhook 경로**: `/webhook-test/generate-reply`

---

## 🔄 작동 방식

### 시나리오 1: 새 이메일 처리

```python
# Frontend: "메일 동기화" 버튼 클릭
POST /sync-emails

# Backend: LangGraph Supervisor 실행
email_processor.process_new_emails()

# LangGraph 내부 플로우:

1. fetch_emails_node()
   → n8n_tools.fetch_emails()
   → n8n Workflow #1 호출 (IMAP)
   → Result: [email_id: 1, 2, 3, 4, 5]

2. classify_emails_node()
   → Gemini 직접 호출 (LangGraph 자체 로직)
   → 각 이메일 분석:
     email_1: 채용 (중요도 9) ← 답변 필요
     email_2: 마케팅 (중요도 2)
     email_3: 공지 (중요도 5)
     email_4: 개인 (중요도 8) ← 답변 필요
     email_5: 기타 (중요도 3)

3. should_generate_replies()
   → important_emails: [1, 4]  (중요도 >= 7)
   → 조건: YES → generate_replies_node()

4. generate_replies_node()
   → n8n_tools.generate_reply(email_id=1)
   → n8n Workflow #5 호출 (Gemini 3개)
   → Result: {formal, casual, brief}

   → n8n_tools.generate_reply(email_id=4)
   → Result: {formal, casual, brief}

5. Return to Frontend:
   {
     "new_emails": 5,
     "important_emails": 2,
     "reply_drafts_generated": 2,
     "classifications": [...],
     "important_email_ids": [1, 4]
   }
```

### 시나리오 2: 일일 요약

```python
# Frontend: "일일 요약" 버튼 클릭
POST /summary/generate

# Backend: LangGraph Supervisor 실행
email_processor.generate_daily_summary()

# LangGraph 내부 플로우:

1. summarize_emails_node()
   → n8n_tools.summarize_emails()
   → n8n Workflow #3 호출
   → PostgreSQL에서 오늘 이메일 조회
   → Gemini로 요약 생성
   → daily_summaries 테이블에 저장

2. Return to Frontend:
   {
     "success": true,
     "summary": "오늘 총 5개 이메일 수신. 채용 1건...",
     "current_step": "summarized"
   }
```

---

## 🎯 핵심 개념

### LangGraph의 역할 (두뇌)
- **워크플로우 orchestration**: 어떤 순서로 작업할지 결정
- **Intelligent routing**: Gemini를 사용한 이메일 분류
- **조건부 실행**: 중요한 이메일만 답변 생성
- **상태 관리**: 전체 처리 과정 추적
- **재시도 로직**: 실패 시 자동 재시도

### n8n의 역할 (손발)
- **FetchEmailAgent**: IMAP으로 메일 가져오기
- **SendEmailAgent**: SMTP로 메일 발송
- **SummarizeEmailAgent**: Gemini로 메일 요약
- **GenerateReplyAgent**: Gemini로 3가지 톤 답변 생성
- **AnalyzeEmailAgent**: Gemini로 메일 분석 (선택사항)

---

## 🧪 테스트 방법

### 1. Backend 헬스 체크
```bash
curl http://localhost:8000/health
```

### 2. 메일 동기화 (LangGraph Supervisor)
```bash
curl -X POST http://localhost:8000/sync-emails
```

**예상 응답**:
```json
{
  "success": true,
  "message": "메일 동기화 및 자동 분석 완료",
  "new_emails": 5,
  "important_emails": 2,
  "reply_drafts_generated": 2,
  "classifications": [
    {
      "email_id": 1,
      "email_type": "채용",
      "importance_score": 9,
      "needs_reply": true,
      "sentiment": "positive",
      "key_points": ["면접 일정 조율", ...]
    }
  ],
  "important_email_ids": [1, 4]
}
```

### 3. 일일 요약 (LangGraph Supervisor)
```bash
curl -X POST http://localhost:8000/summary/generate
```

### 4. Frontend 테스트
1. http://localhost:3000 접속
2. "📧 메일 동기화" 클릭
   - 새 이메일 가져오기
   - 자동 분류
   - 중요한 이메일 답변 초안 생성
3. "📝 일일 요약" 클릭
   - 오늘 이메일 요약 생성

---

## 📊 장점 요약

### LangGraph + n8n 하이브리드의 강점

1. **최고의 유연성**
   - LangGraph: 복잡한 로직과 AI 의사결정
   - n8n: 시각적 관리와 검증된 통합

2. **유지보수 용이**
   - 기본 작업: n8n UI에서 수정
   - 워크플로우 로직: Python 코드로 관리

3. **확장성**
   - 새로운 n8n 에이전트 추가 쉬움
   - LangGraph 그래프 확장 가능

4. **디버깅**
   - n8n: 각 노드 실행 로그 확인
   - LangGraph: Python 로그로 상태 추적

---

## 📚 관련 문서

- **아키텍처**: `architecture/langgraph_n8n_hybrid.md`
- **워크플로우 수정 가이드**: `n8n_workflows/workflow_1_modification_guide.md`
- **워크플로우 생성 가이드**: `n8n_workflows/workflow_3_daily_summary.md`
- **전체 시스템 README**: `n8n_workflows/README.md`

---

## 🚀 다음 단계

1. **n8n UI 접속** (http://localhost:5678)
2. **워크플로우 #1 수정**: Gemini 노드 제거
3. **워크플로우 #3 생성**: 일일 요약 에이전트
4. **워크플로우 #5 생성**: 답변 생성 에이전트
5. **전체 시스템 테스트**: Frontend에서 테스트

---

## 💡 핵심 포인트

```
✨ LangGraph = 두뇌 (워크플로우 orchestration + AI 의사결정)
🔧 n8n = 손발 (IMAP/SMTP/Gemini 호출)
🎯 Backend = API Gateway (Frontend ↔ LangGraph 연결)
```

이제 **n8n 워크플로우만 수정하면 시스템 완성**입니다! 🎉
