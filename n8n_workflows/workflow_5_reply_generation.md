# n8n 워크플로우 #5: 답변 생성

## 개요
특정 이메일에 대한 답변을 3가지 톤(격식, 친근함, 간결함)으로 생성하여 reply_suggestions 테이블에 저장합니다.

## Webhook 정보
- **URL**: `http://n8n:5678/webhook-test/generate-reply`
- **Method**: POST
- **Payload**:
```json
{
  "email_id": 123,
  "preferred_tone": "formal"
}
```

## 워크플로우 구조

```
┌─────────────┐
│   Webhook   │ ← POST /webhook-test/generate-reply
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│ PostgreSQL: 이메일 조회      │
│ SELECT * FROM email         │
│ WHERE id = {{ $json.email_id }}│
└──────┬──────────────────────┘
       │
       ▼
┌──────────────────────┐
│ IF: 이메일 존재 여부  │
└──────┬───────────────┘
       │
       ├─ [없음] → Return 404 Error
       │
       └─ [있음] ▼
         ┌────────────────────────────┐
         │ PostgreSQL: 유사 답변 패턴  │
         │ 조회 (선택사항)            │
         │ - reply_patterns 테이블    │
         └──────┬─────────────────────┘
                │
                ▼
         ┌────────────────────────┐
         │ Code: 답변 프롬프트 생성│
         │ - 3가지 톤 정의         │
         │ - 이메일 컨텍스트       │
         │ - 유사 패턴 참고        │
         └──────┬─────────────────┘
                │
                ▼
         ┌──────────────────────┐
         │ Google Gemini (톤1)  │
         │ formal: 격식체 답변   │
         └──────┬───────────────┘
                │
                ├────────────────────┐
                │                    │
                ▼                    ▼
         ┌──────────────┐    ┌──────────────┐
         │ Gemini (톤2) │    │ Gemini (톤3) │
         │ casual: 친근  │    │ brief: 간결  │
         └──────┬───────┘    └──────┬───────┘
                │                    │
                └────────┬───────────┘
                         │
                         ▼
                  ┌──────────────────────┐
                  │ Code: 답변 결합       │
                  │ - 3가지 톤 JSON 생성 │
                  └──────┬───────────────┘
                         │
                         ▼
                  ┌──────────────────────────┐
                  │ PostgreSQL: 답변 저장     │
                  │ INSERT INTO              │
                  │ reply_suggestions        │
                  └──────┬───────────────────┘
                         │
                         ▼
                  ┌──────────────────┐
                  │ Return Response  │
                  │ - suggestion_id  │
                  │ - 3가지 답변     │
                  └──────────────────┘
```

## 노드 상세 설명

### 1. Webhook Trigger
- **Type**: Webhook
- **Path**: `/webhook-test/generate-reply`
- **Method**: POST
- **Response Mode**: Wait for response

### 2. PostgreSQL - 이메일 조회
- **Type**: PostgreSQL
- **Operation**: Execute Query
- **Query**:
```sql
SELECT
  id,
  subject,
  sender_name,
  sender_address,
  body_text,
  analysis_result
FROM email
WHERE id = {{ $json.email_id }}
LIMIT 1;
```

### 3. IF - 이메일 존재 여부
- **Type**: IF
- **Condition**: `{{ $json.rowCount > 0 }}`
- **True**: 다음 노드로 진행
- **False**: 404 에러 응답

### 4. PostgreSQL - 유사 답변 패턴 조회 (선택사항)
- **Type**: PostgreSQL
- **Operation**: Execute Query
- **Query**:
```sql
SELECT pattern_name, template_text
FROM reply_patterns
WHERE is_active = true
ORDER BY usage_count DESC
LIMIT 3;
```

### 5. Code - 답변 프롬프트 생성
- **Type**: Code (JavaScript)
- **Input**: 이메일 + 답변 패턴
- **Output**: 3가지 톤별 프롬프트

```javascript
const email = $('PostgreSQL').first().json;
const preferredTone = $('Webhook').first().json.preferred_tone || 'formal';

const sender = email.sender_name || email.sender_address;
const subject = email.subject || "(제목 없음)";
const body = email.body_text || "";

// 기본 컨텍스트
const baseContext = `다음 이메일에 대한 답변을 작성해주세요.

### 원본 이메일:
- 보낸 사람: ${sender}
- 제목: ${subject}
- 본문:
${body}

### 답변 작성 가이드:
- 한국어로 작성
- 전문적이고 정중한 태도
- 구체적이고 명확한 표현
- 3~5문단 분량`;

// 톤별 프롬프트
const prompts = {
  formal: `${baseContext}

### 톤: 격식체 (formal)
- 존댓말 사용
- 공식적이고 정중한 표현
- 비즈니스 이메일 형식`,

  casual: `${baseContext}

### 톤: 친근함 (casual)
- 존댓말이지만 친근한 표현
- 부드럽고 따뜻한 어조
- 개인적인 소통 느낌`,

  brief: `${baseContext}

### 톤: 간결함 (brief)
- 핵심만 간단명료하게
- 1~2문단으로 짧게
- 요점 중심의 답변`
};

return [{
  json: {
    email_id: email.id,
    sender: sender,
    subject: subject,
    preferred_tone: preferredTone,
    prompt_formal: prompts.formal,
    prompt_casual: prompts.casual,
    prompt_brief: prompts.brief
  }
}];
```

### 6-8. Google Gemini (3개 병렬 실행)

**Gemini Node #1 - Formal**
- **Model**: `gemini-2.0-flash-exp`
- **Prompt**: `{{ $json.prompt_formal }}`
- **Temperature**: 0.5
- **Max Output Tokens**: 1024

**Gemini Node #2 - Casual**
- **Model**: `gemini-2.0-flash-exp`
- **Prompt**: `{{ $json.prompt_casual }}`
- **Temperature**: 0.7
- **Max Output Tokens**: 1024

**Gemini Node #3 - Brief**
- **Model**: `gemini-2.0-flash-exp`
- **Prompt**: `{{ $json.prompt_brief }}`
- **Temperature**: 0.4
- **Max Output Tokens**: 512

### 9. Code - 답변 결합
- **Type**: Code (JavaScript)
- **Input**: 3개 Gemini 응답
- **Output**: 구조화된 답변 데이터

```javascript
const code = $('Code').first().json;
const formalReply = $('Gemini Formal').first().json.text;
const casualReply = $('Gemini Casual').first().json.text;
const briefReply = $('Gemini Brief').first().json.text;

const replies = {
  formal: {
    tone: "격식체",
    reply_text: formalReply.trim()
  },
  casual: {
    tone: "친근함",
    reply_text: casualReply.trim()
  },
  brief: {
    tone: "간결함",
    reply_text: briefReply.trim()
  }
};

return [{
  json: {
    email_id: code.email_id,
    sender: code.sender,
    subject: code.subject,
    preferred_tone: code.preferred_tone,
    reply_drafts: replies
  }
}];
```

### 10. PostgreSQL - 답변 저장
- **Type**: PostgreSQL
- **Operation**: Execute Query
- **Query**:
```sql
INSERT INTO reply_suggestions
  (email_id, reply_drafts, preferred_tone, status)
VALUES
  (
    {{ $json.email_id }},
    '{{ JSON.stringify($json.reply_drafts) }}'::jsonb,
    '{{ $json.preferred_tone }}',
    'pending'
  )
RETURNING id;
```

### 11. Response
- **Type**: Respond to Webhook
- **Response Data**:
```json
{
  "success": true,
  "email_id": "{{ $json.email_id }}",
  "suggestion_id": "{{ $json.id }}",
  "sender": "{{ $json.sender }}",
  "subject": "{{ $json.subject }}",
  "reply_drafts": "{{ $json.reply_drafts }}",
  "preferred_tone": "{{ $json.preferred_tone }}"
}
```

## 환경 변수 필요
- `GEMINI_API_KEY`: Gemini API 키
- PostgreSQL 연결 정보

## 테스트 방법

### curl 예시
```bash
curl -X POST http://localhost:5678/webhook-test/generate-reply \
  -H "Content-Type: application/json" \
  -d '{"email_id": 123, "preferred_tone": "formal"}'
```

### 예상 응답
```json
{
  "success": true,
  "email_id": 123,
  "suggestion_id": 45,
  "sender": "홍길동",
  "subject": "면접 일정 안내",
  "reply_drafts": {
    "formal": {
      "tone": "격식체",
      "reply_text": "안녕하세요, 홍길동님.\n\n면접 일정 안내 메일 잘 받았습니다..."
    },
    "casual": {
      "tone": "친근함",
      "reply_text": "안녕하세요 홍길동님,\n\n면접 일정 메일 감사합니다..."
    },
    "brief": {
      "tone": "간결함",
      "reply_text": "안녕하세요.\n\n11월 20일 오후 2시 면접 참석 가능합니다..."
    }
  },
  "preferred_tone": "formal"
}
```

## 최적화 팁
1. **병렬 실행**: 3개 Gemini 노드를 병렬로 실행하여 속도 향상
2. **캐싱**: 동일 이메일에 대한 재요청 시 캐시 활용
3. **토큰 절약**: brief 톤은 Max Output Tokens를 512로 제한
4. **재시도**: Gemini API 오류 시 n8n 자동 재시도 활성화

## 에러 처리
- 이메일 없음: `{"error": "Email not found"}`
- Gemini API 오류: 최대 3회 재시도
- 하나의 톤만 실패: 나머지 2개는 정상 저장
