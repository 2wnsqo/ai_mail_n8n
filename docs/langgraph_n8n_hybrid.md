# LangGraph + n8n 하이브리드 아키텍처

## 📐 아키텍처 개요

### 역할 분담

#### n8n의 역할: 기본 작업 에이전트 (Tools)
- **FetchEmailAgent**: IMAP으로 메일 가져오기
- **SummarizeEmailAgent**: Gemini로 메일 요약
- **GenerateReplyAgent**: Gemini로 3가지 톤 답변 생성
- **SendEmailAgent**: SMTP로 메일 발송

#### LangGraph의 역할: Supervisor & Orchestration
- **워크플로우 결정**: 어떤 순서로 작업할지 판단
- **조건부 실행**: 이메일 중요도에 따라 다른 처리
- **재시도 로직**: 실패 시 자동 재시도
- **복잡한 의사결정**: Gemini를 사용한 상황 판단
- **상태 관리**: 전체 처리 과정 추적

---

## 🏗️ 시스템 구조

```
┌──────────────┐
│   Frontend   │
└──────┬───────┘
       │ HTTP API
       ▼
┌─────────────────────────────┐
│   Backend (FastAPI)         │
│                             │
│  ┌───────────────────────┐  │
│  │  LangGraph Supervisor │  │
│  │  - EmailProcessor     │  │
│  │  - ReplyHandler       │  │
│  │  - DailySummarizer    │  │
│  └───────┬───────────────┘  │
│          │                  │
│  ┌───────▼───────────────┐  │
│  │  n8n Tool Wrappers    │  │
│  │  - fetch_emails()     │  │
│  │  - summarize_email()  │  │
│  │  - generate_reply()   │  │
│  │  - send_email()       │  │
│  └───────┬───────────────┘  │
└──────────┼──────────────────┘
           │ Webhook 호출
           ▼
    ┌──────────────┐
    │     n8n      │
    │              │
    │  Workflow #1 │ ← FetchEmailAgent
    │  Workflow #2 │ ← SendEmailAgent
    │  Workflow #3 │ ← SummarizeEmailAgent
    │  Workflow #4 │ ← GenerateReplyAgent
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  PostgreSQL  │
    └──────────────┘
```

---

## 📊 워크플로우 예시

### 예시 1: 새 이메일 처리

```python
# 사용자: "새 이메일 확인해줘"

LangGraph Supervisor:

  State: { task: "process_new_emails" }

  Step 1: fetch_emails_node()
    → Tool: n8n FetchEmailAgent
    → Result: 5개 새 이메일

  Step 2: classify_emails_node()
    → LangGraph 자체 로직 (Gemini 사용)
    → Result:
      - 이메일 1: 채용 (중요도 9) → 답변 필요
      - 이메일 2: 마케팅 (중요도 2) → 무시
      - 이메일 3: 공지 (중요도 5) → 보관
      - 이메일 4: 개인 (중요도 8) → 답변 필요
      - 이메일 5: 기타 (중요도 3) → 무시

  Step 3: decide_next_action()
    → 조건: 중요도 >= 7 이면 답변 생성
    → 이메일 1, 4 선택

  Step 4: generate_replies_node()
    → Tool: n8n GenerateReplyAgent (이메일 1)
    → Tool: n8n GenerateReplyAgent (이메일 4)
    → Result: 각각 3가지 톤 답변

  Step 5: wait_for_approval()
    → 사용자에게 답변 보여주고 승인 대기

  Step 6: send_approved_replies()
    → Tool: n8n SendEmailAgent
    → 승인된 답변만 발송
```

### 예시 2: 일일 요약

```python
# 사용자: "오늘의 이메일 요약해줘"

LangGraph Supervisor:

  State: { task: "daily_summary" }

  Step 1: fetch_today_emails_node()
    → PostgreSQL에서 오늘 이메일 조회
    → Result: 15개 이메일

  Step 2: summarize_emails_node()
    → Tool: n8n SummarizeEmailAgent
    → Result: "오늘 총 15개 이메일 수신. 채용 관련 3건, 마케팅 10건..."

  Step 3: save_and_return()
    → PostgreSQL에 요약 저장
    → 사용자에게 요약 반환
```

---

## 🛠️ n8n 워크플로우 (단순화)

### Workflow #1: FetchEmailAgent
```
Webhook → IMAP → Loop → Code(HTML정리) → Insert(email) → Response
```
- **Input**: `{ "since_date": "2025-11-15" }`
- **Output**: `{ "new_emails": 5, "email_ids": [1, 2, 3, 4, 5] }`

### Workflow #2: SendEmailAgent
```
Webhook → Code(준비) → SMTP → Insert(sent_emails) → Response
```
- **Input**: `{ "to_email": "...", "subject": "...", "body": "..." }`
- **Output**: `{ "success": true, "sent_id": 123 }`

### Workflow #3: SummarizeEmailAgent
```
Webhook → PostgreSQL(조회) → Code(결합) → Gemini → Response
```
- **Input**: `{ "email_ids": [1, 2, 3] }`
- **Output**: `{ "summary": "오늘 총 3개 이메일..." }`

### Workflow #4: GenerateReplyAgent
```
Webhook → PostgreSQL(조회) → Code(프롬프트) → Gemini(3개) → Code(결합) → Response
```
- **Input**: `{ "email_id": 123, "tone": "formal" }`
- **Output**: `{ "formal": "...", "casual": "...", "brief": "..." }`

---

## 🧩 LangGraph 구조

### State 정의
```python
from typing import TypedDict, List, Literal

class EmailProcessingState(TypedDict):
    # 작업 컨텍스트
    task: Literal["process_new_emails", "daily_summary", "reply_to_email"]

    # 이메일 데이터
    email_ids: List[int]
    emails: List[dict]

    # 분석 결과
    classifications: List[dict]
    important_emails: List[int]

    # 답변 데이터
    reply_drafts: dict
    approved_replies: List[dict]

    # 상태 추적
    current_step: str
    errors: List[str]
```

### Node 정의

#### 1. fetch_emails_node
```python
def fetch_emails_node(state: EmailProcessingState):
    """n8n FetchEmailAgent 호출"""
    result = n8n_tool.fetch_emails(since_date=today)

    return {
        "email_ids": result["email_ids"],
        "current_step": "fetched"
    }
```

#### 2. classify_emails_node
```python
def classify_emails_node(state: EmailProcessingState):
    """LangGraph 자체 로직 - Gemini로 분류"""
    emails = db.get_emails(state["email_ids"])

    classifications = []
    for email in emails:
        analysis = gemini_classifier.analyze(email)
        classifications.append(analysis)

    # 중요도 높은 이메일 필터링
    important = [
        email["id"]
        for email, analysis in zip(emails, classifications)
        if analysis["importance_score"] >= 7
    ]

    return {
        "classifications": classifications,
        "important_emails": important,
        "current_step": "classified"
    }
```

#### 3. generate_replies_node
```python
def generate_replies_node(state: EmailProcessingState):
    """n8n GenerateReplyAgent 호출"""
    reply_drafts = {}

    for email_id in state["important_emails"]:
        result = n8n_tool.generate_reply(email_id=email_id)
        reply_drafts[email_id] = result

    return {
        "reply_drafts": reply_drafts,
        "current_step": "replies_generated"
    }
```

#### 4. send_replies_node
```python
def send_replies_node(state: EmailProcessingState):
    """n8n SendEmailAgent 호출"""
    for reply in state["approved_replies"]:
        n8n_tool.send_email(
            to_email=reply["to_email"],
            subject=reply["subject"],
            body=reply["body"]
        )

    return {
        "current_step": "sent"
    }
```

#### 5. summarize_emails_node
```python
def summarize_emails_node(state: EmailProcessingState):
    """n8n SummarizeEmailAgent 호출"""
    result = n8n_tool.summarize_emails(
        email_ids=state["email_ids"]
    )

    return {
        "summary": result["summary"],
        "current_step": "summarized"
    }
```

### Conditional Edge
```python
def should_generate_replies(state: EmailProcessingState):
    """답변 생성 여부 결정"""
    if len(state["important_emails"]) > 0:
        return "generate_replies"
    else:
        return "end"
```

### Graph 구성
```python
from langgraph.graph import StateGraph

workflow = StateGraph(EmailProcessingState)

# 노드 추가
workflow.add_node("fetch_emails", fetch_emails_node)
workflow.add_node("classify_emails", classify_emails_node)
workflow.add_node("generate_replies", generate_replies_node)
workflow.add_node("send_replies", send_replies_node)

# 엣지 추가
workflow.set_entry_point("fetch_emails")
workflow.add_edge("fetch_emails", "classify_emails")
workflow.add_conditional_edges(
    "classify_emails",
    should_generate_replies,
    {
        "generate_replies": "generate_replies",
        "end": END
    }
)
workflow.add_edge("generate_replies", "send_replies")
workflow.add_edge("send_replies", END)

app = workflow.compile()
```

---

## 🔧 n8n Tool Wrapper

```python
# backend/src/tools/n8n_tools.py

import requests
from typing import List, Dict

class N8nToolWrapper:
    """n8n 워크플로우를 LangGraph Tools로 래핑"""

    def __init__(self, base_url: str = "http://n8n:5678"):
        self.base_url = base_url

    def fetch_emails(self, since_date: str) -> Dict:
        """워크플로우 #1: 메일 가져오기"""
        url = f"{self.base_url}/webhook-test/fetch-emails"
        payload = {"since_date": since_date}

        response = requests.post(url, json=payload, timeout=60)
        return response.json()

    def summarize_emails(self, email_ids: List[int]) -> Dict:
        """워크플로우 #3: 메일 요약"""
        url = f"{self.base_url}/webhook-test/summarize"
        payload = {"email_ids": email_ids}

        response = requests.post(url, json=payload, timeout=120)
        return response.json()

    def generate_reply(self, email_id: int, tone: str = "formal") -> Dict:
        """워크플로우 #4: 답변 생성"""
        url = f"{self.base_url}/webhook-test/generate-reply"
        payload = {"email_id": email_id, "tone": tone}

        response = requests.post(url, json=payload, timeout=60)
        return response.json()

    def send_email(self, to_email: str, subject: str, body: str) -> Dict:
        """워크플로우 #2: 메일 발송"""
        url = f"{self.base_url}/webhook-test/send-email"
        payload = {
            "to_email": to_email,
            "subject": subject,
            "body": body
        }

        response = requests.post(url, json=payload, timeout=30)
        return response.json()

# 전역 인스턴스
n8n_tool = N8nToolWrapper()
```

---

## 📈 장점

### LangGraph의 장점
- **복잡한 워크플로우**: 조건부 분기, 루프, 재시도 로직
- **상태 관리**: 전체 처리 과정 추적 가능
- **유연성**: Python 코드로 자유로운 로직 구현
- **AI 의사결정**: Gemini를 사용한 intelligent routing

### n8n의 장점
- **시각적 관리**: 기본 작업들을 GUI로 관리
- **재사용성**: 독립적인 에이전트로 어디서든 호출 가능
- **안정성**: 검증된 IMAP/SMTP/Gemini 노드 사용
- **디버깅**: n8n UI에서 실행 로그 확인

---

## 🎯 다음 단계

1. **n8n 워크플로우 4개 단순화**
   - Workflow #1: FetchEmailAgent
   - Workflow #2: SendEmailAgent
   - Workflow #3: SummarizeEmailAgent
   - Workflow #4: GenerateReplyAgent

2. **N8nToolWrapper 클래스 구현**
   - n8n webhook 호출 래퍼

3. **LangGraph Supervisor 구현**
   - EmailProcessingState 정의
   - Node 함수들 구현
   - Graph 구성

4. **Backend API 복원**
   - LangGraph를 사용하는 엔드포인트 추가
   - Frontend 연동
