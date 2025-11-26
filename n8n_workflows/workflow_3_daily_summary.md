# n8n 워크플로우 #3: 일일 요약 생성

## 개요
오늘 수신된 모든 이메일을 Gemini AI로 요약하여 daily_summaries 테이블에 저장합니다.

## Webhook 정보
- **URL**: `http://n8n:5678/webhook-test/summary`
- **Method**: POST
- **Payload**:
```json
{
  "summary_date": "2025-11-15",
  "trigger_source": "manual_request"
}
```

## 워크플로우 구조

```
┌─────────────┐
│   Webhook   │ ← POST /webhook-test/summary
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│ PostgreSQL: 오늘 이메일 조회 │
│ SELECT subject, sender_name,│
│ sender_address, body_text   │
│ FROM email                  │
│ WHERE DATE(received_at)     │
│   = CURRENT_DATE            │
└──────┬──────────────────────┘
       │
       ▼
┌──────────────────────┐
│ IF: 이메일 존재 여부  │
└──────┬───────────────┘
       │
       ├─ [이메일 0개] → Return {"success": false, "message": "오늘 수신된 이메일이 없습니다."}
       │
       └─ [이메일 있음] ▼
         ┌────────────────────────┐
         │ Code: 텍스트 결합       │
         │ - 각 이메일을 포맷팅    │
         │ - 하나의 프롬프트 생성  │
         └──────┬─────────────────┘
                │
                ▼
         ┌──────────────────┐
         │ Google Gemini    │
         │ Model: gemini-   │
         │ 2.0-flash-exp    │
         │ 한국어 요약 생성  │
         └──────┬───────────┘
                │
                ▼
         ┌──────────────────────────┐
         │ PostgreSQL: 요약 저장     │
         │ INSERT INTO              │
         │ daily_summaries          │
         │ ON CONFLICT UPDATE       │
         └──────┬───────────────────┘
                │
                ▼
         ┌──────────────────┐
         │ Return Response  │
         │ - success: true  │
         │ - email_count    │
         │ - summary        │
         └──────────────────┘
```

## 노드 상세 설명

### 1. Webhook Trigger
- **Type**: Webhook
- **Path**: `/webhook-test/summary`
- **Method**: POST
- **Response Mode**: Wait for response

### 2. PostgreSQL - 오늘 이메일 조회
- **Type**: PostgreSQL
- **Operation**: Execute Query
- **Query**:
```sql
SELECT
  subject,
  sender_name,
  sender_address,
  body_text,
  received_at
FROM email
WHERE DATE(received_at) = CURRENT_DATE
ORDER BY received_at DESC;
```

### 3. IF - 이메일 존재 여부
- **Type**: IF
- **Condition**: `{{ $json.rowCount > 0 }}`
- **True**: 다음 노드로 진행
- **False**: 에러 응답 Return

### 4. Code - 텍스트 결합
- **Type**: Code (JavaScript)
- **Input**: PostgreSQL 결과
- **Output**: Gemini 프롬프트

```javascript
const emails = $input.all();

if (!emails || emails.length === 0) {
  return [{
    json: {
      success: false,
      message: "오늘 수신된 이메일이 없습니다.",
      email_count: 0
    }
  }];
}

let combinedText = "다음은 오늘 수신된 이메일 전체 내용입니다. 각 이메일의 핵심 내용을 명확하게 한국어로 요약해 주세요:\n\n";

for (const email of emails) {
  const sender = email.json.sender_name || email.json.sender_address;
  const subject = email.json.subject || "(제목 없음)";
  const body = email.json.body_text || "";

  combinedText += "=====================================\n";
  combinedText += `보낸 사람: ${sender}\n`;
  combinedText += `제목: ${subject}\n`;
  combinedText += "-------------------------------------\n";
  combinedText += `${body.substring(0, 500)}\n\n`;
}

return [{
  json: {
    prompt: combinedText,
    email_count: emails.length
  }
}];
```

### 5. Google Gemini - 요약 생성
- **Type**: Google Gemini
- **Model**: `gemini-2.0-flash-exp`
- **Prompt**: `{{ $json.prompt }}`
- **Temperature**: 0.7
- **Max Output Tokens**: 2048

### 6. PostgreSQL - 요약 저장
- **Type**: PostgreSQL
- **Operation**: Execute Query
- **Query**:
```sql
INSERT INTO daily_summaries (summary_date, summary_content, email_count)
VALUES (
  CURRENT_DATE,
  '{{ $json.text }}',
  {{ $('Code').item.json.email_count }}
)
ON CONFLICT (summary_date)
DO UPDATE SET
  summary_content = EXCLUDED.summary_content,
  email_count = EXCLUDED.email_count,
  updated_at = NOW();
```

### 7. Response
- **Type**: Respond to Webhook
- **Response Data**:
```json
{
  "success": true,
  "message": "일일 요약 생성 완료",
  "email_count": "{{ $('Code').item.json.email_count }}",
  "summary": "{{ $json.text }}",
  "summary_date": "{{ $now.format('YYYY-MM-DD') }}"
}
```

## 환경 변수 필요
- `GEMINI_API_KEY`: Gemini API 키
- PostgreSQL 연결 정보 (credential 등록 필요)

## 테스트 방법

### curl 예시
```bash
curl -X POST http://localhost:5678/webhook-test/summary \
  -H "Content-Type: application/json" \
  -d '{"summary_date": "2025-11-15", "trigger_source": "manual_request"}'
```

### 예상 응답
```json
{
  "success": true,
  "message": "일일 요약 생성 완료",
  "email_count": 5,
  "summary": "오늘 총 5개의 이메일이 수신되었습니다...",
  "summary_date": "2025-11-15"
}
```

## 에러 처리
- 이메일 0개: `{"success": false, "message": "오늘 수신된 이메일이 없습니다."}`
- Gemini API 오류: n8n 자동 재시도 (최대 3회)
- PostgreSQL 오류: 워크플로우 중단 및 에러 로그 기록
