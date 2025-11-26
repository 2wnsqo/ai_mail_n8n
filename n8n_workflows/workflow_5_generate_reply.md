# 워크플로우 #5: 답변 생성 (3가지 톤)

특정 이메일에 대해 **격식체, 친근함, 간결함** 3가지 톤으로 답변을 자동 생성합니다.

---

## 📋 노드 구성

```
Webhook (POST /generate-reply)
  ↓
PostgreSQL - 이메일 조회
  ↓
IF - 이메일 존재 여부
  ├─ TRUE → Code - 3가지 톤 프롬프트 생성
  │           ↓
  │         Google Gemini - 답변 생성
  │           ↓
  │         Code - 답변 결합
  │           ↓
  │         PostgreSQL - 답변 저장
  │           ↓
  │         Respond to Webhook (성공)
  │
  └─ FALSE → Respond - 이메일 없음
```

---

## 🛠️ 노드별 설정

### 1️⃣ Webhook
- **Type**: `Webhook`
- **HTTP Method**: `POST`
- **Path**: `generate-reply`
- **Response Mode**: `Using 'Respond to Webhook' Node`

---

### 2️⃣ PostgreSQL - 이메일 조회
- **Type**: `PostgreSQL`
- **Operation**: `Execute Query`
- **Credentials**: `PostgreSQL account`

**Query**:
```sql
SELECT id, subject, sender_name, sender_address, body_text, received_at
FROM email
WHERE id = {{ $json.body.email_id }};
```

---

### 3️⃣ IF - 이메일 존재 여부
- **Type**: `IF`
- **Conditions**:
  - **Value 1**: `{{ $input.all().length }}`
  - **Operation**: `Larger`
  - **Value 2**: `0`

---

### 4️⃣ Code - 3가지 톤 프롬프트 생성
- **Type**: `Code`
- **Mode**: `Run Once for All Items`

**Code**:
```javascript
const email = $input.first().json;

if (!email) {
  return [{
    json: {
      success: false,
      message: "이메일을 찾을 수 없습니다."
    }
  }];
}

const sender = email.sender_name || email.sender_address;
const subject = email.subject || "(제목 없음)";
const body = email.body_text || "";

// 3가지 톤에 대한 프롬프트 생성
const basePrompt = `다음 이메일에 대한 답변을 작성해주세요:

보낸 사람: ${sender}
제목: ${subject}
내용:
${body.substring(0, 1000)}

`;

return [
  {
    json: {
      tone_type: "formal",
      prompt: basePrompt + "격식 있고 전문적인 톤으로 답변을 작성해주세요. 존댓말을 사용하고 정중한 표현을 사용하세요.",
      email_id: email.id,
      original_subject: subject
    }
  },
  {
    json: {
      tone_type: "casual",
      prompt: basePrompt + "친근하고 편안한 톤으로 답변을 작성해주세요. 부담스럽지 않으면서도 예의 바른 표현을 사용하세요.",
      email_id: email.id,
      original_subject: subject
    }
  },
  {
    json: {
      tone_type: "brief",
      prompt: basePrompt + "간결하고 핵심적인 톤으로 답변을 작성해주세요. 요점만 명확하게 전달하세요.",
      email_id: email.id,
      original_subject: subject
    }
  }
];
```

**💡 중요**: 이 노드는 1개의 입력을 받아서 **3개의 아이템**을 출력합니다 (각 톤마다 1개씩).

---

### 5️⃣ Google Gemini - 답변 생성
- **Type**: `Google Gemini`
- **Credentials**: `Google Gemini account`
- **Model**: `gemini-2.0-flash-exp` (또는 `gemini-1.5-flash`)
- **Prompt**: `={{ $json.prompt }}`

**Options**:
- **Temperature**: `0.7`
- **Max Output Tokens**: `1024`

**Settings** (권장):
- **Retry On Fail**: `ON`
- **Max Tries**: `3`
- **Wait Between Tries**: `10000` (10초)

**💡 중요**: 이 노드는 **3개의 아이템을 받아서 각각 처리**합니다 (병렬 처리).

---

### 6️⃣ Code - 답변 결합
- **Type**: `Code`
- **Mode**: `Run Once for All Items`

**Code**:
```javascript
const items = $input.all();

if (!items || items.length === 0) {
  return [{
    json: {
      success: false,
      message: "답변 생성 실패"
    }
  }];
}

// 3가지 톤의 답변을 객체로 결합
const reply_drafts = {};
let email_id = null;
let original_subject = null;

for (const item of items) {
  const tone_type = item.json.tone_type;
  const reply_text = item.json.text || "";

  if (!email_id) {
    email_id = item.json.email_id;
    original_subject = item.json.original_subject;
  }

  let tone_name = "격식체";
  if (tone_type === "casual") tone_name = "친근함";
  if (tone_type === "brief") tone_name = "간결함";

  reply_drafts[tone_type] = {
    tone: tone_name,
    reply_text: reply_text
  };
}

return [{
  json: {
    success: true,
    email_id: email_id,
    original_subject: original_subject,
    reply_drafts: reply_drafts,
    preferred_tone: "formal"
  }
}];
```

**💡 중요**: 이 노드는 **3개의 아이템을 받아서 1개로 결합**합니다.

---

### 7️⃣ PostgreSQL - 답변 저장
- **Type**: `PostgreSQL`
- **Operation**: `Execute Query`
- **Credentials**: `PostgreSQL account`

**Query**:
```sql
INSERT INTO reply_suggestions (email_id, tone, reply_text)
VALUES
  ({{ $json.email_id }}, 'formal', '{{ $json.reply_drafts.formal.reply_text }}'),
  ({{ $json.email_id }}, 'casual', '{{ $json.reply_drafts.casual.reply_text }}'),
  ({{ $json.email_id }}, 'brief', '{{ $json.reply_drafts.brief.reply_text }}');
```

---

### 8️⃣ Respond to Webhook (성공)
- **Type**: `Respond to Webhook`
- **Respond With**: `JSON`
- **Response Body** (Expression 모드):

```javascript
={{ $('Code - 답변 결합').item.json }}
```

**💡 참고**: 이렇게 하면 전체 결과 객체를 그대로 반환합니다:
```json
{
  "success": true,
  "email_id": 6,
  "original_subject": "테스트 메일",
  "reply_drafts": {
    "formal": {
      "tone": "격식체",
      "reply_text": "안녕하세요..."
    },
    "casual": {
      "tone": "친근함",
      "reply_text": "안녕하세요~..."
    },
    "brief": {
      "tone": "간결함",
      "reply_text": "확인했습니다..."
    }
  },
  "preferred_tone": "formal"
}
```

---

### 9️⃣ Respond - 이메일 없음 (FALSE 브랜치)
- **Type**: `Respond to Webhook`
- **Respond With**: `JSON`
- **Response Body** (Expression 모드):

```javascript
={
  "success": false,
  "message": "이메일을 찾을 수 없습니다.",
  "email_id": {{ $('Webhook').item.json.body.email_id }}
}
```

---

## 🔗 노드 연결

1. **Webhook** → **PostgreSQL - 이메일 조회**
2. **PostgreSQL - 이메일 조회** → **IF - 이메일 존재 여부**
3. **IF - 이메일 존재 여부** (TRUE) → **Code - 3가지 톤 프롬프트 생성**
4. **IF - 이메일 존재 여부** (FALSE) → **Respond - 이메일 없음**
5. **Code - 3가지 톤 프롬프트 생성** → **Google Gemini - 답변 생성**
6. **Google Gemini - 답변 생성** → **Code - 답변 결합**
7. **Code - 답변 결합** → **PostgreSQL - 답변 저장**
8. **PostgreSQL - 답변 저장** → **Respond to Webhook**

---

## ✅ 생성 후 확인 사항

1. ✅ Webhook Response Mode가 **"Using 'Respond to Webhook' Node"**인지 확인
2. ✅ IF 노드 조건이 `{{ $input.all().length }}` > 0 인지 확인
3. ✅ Code 노드들이 **"Run Once for All Items"** 모드인지 확인
4. ✅ PostgreSQL Credentials가 올바른지 확인
5. ✅ Gemini Credentials가 올바른지 확인
6. ✅ Workflow를 **Active**로 설정
7. ✅ **Save** 버튼 클릭

---

## 🧪 테스트 방법

### 1️⃣ n8n 직접 호출 (워크플로우만 테스트)
```bash
curl -X POST http://localhost:5678/webhook/generate-reply \
  -H "Content-Type: application/json" \
  -d '{"email_id": 6}'
```

### 2️⃣ Backend API 호출 (LangGraph + n8n 통합 테스트)
```bash
# Backend에서 자동으로 중요한 이메일에 대해 답변 생성
curl -X POST http://localhost:8000/sync-emails
```

---

## 📊 예상 응답

### 성공 시:
```json
{
  "success": true,
  "email_id": 6,
  "original_subject": "[심스페이스] 동의 접수 완료 및 회원가입 절차 안내",
  "reply_drafts": {
    "formal": {
      "tone": "격식체",
      "reply_text": "안녕하세요. 심스페이스 회원가입 절차 안내 이메일 잘 받았습니다. 안내해주신 대로 회원가입을 진행하겠습니다. 감사합니다."
    },
    "casual": {
      "tone": "친근함",
      "reply_text": "안녕하세요~ 회원가입 안내 이메일 확인했습니다. 곧바로 가입 절차 진행해볼게요. 감사합니다!"
    },
    "brief": {
      "tone": "간결함",
      "reply_text": "확인했습니다. 회원가입 진행하겠습니다."
    }
  },
  "preferred_tone": "formal"
}
```

### 실패 시 (이메일 없음):
```json
{
  "success": false,
  "message": "이메일을 찾을 수 없습니다.",
  "email_id": 999
}
```

---

## ⚠️ 주의사항

1. **Gemini API 과부하**: 재시도 설정을 꼭 추가하세요
2. **응답 시간**: 3개의 Gemini 호출이 순차적으로 처리되므로 20-30초 소요될 수 있습니다
3. **PostgreSQL 문자열**: SQL INSERT에서 작은따옴표(') 이스케이프 처리가 필요할 수 있습니다 (답변에 작은따옴표가 포함될 경우)

---

## 🔧 문제 해결

### "Unused Respond to Webhook node found"
→ Webhook Response Mode를 **"Using 'Respond to Webhook' Node"**로 변경

### "Invalid JSON in Response Body"
→ Expression 모드로 변경하고 `={{ }}` 형식 사용

### Gemini "Service unavailable"
→ Settings 탭에서 **Retry On Fail** 활성화

### "relation reply_suggestions does not exist"
→ PostgreSQL에 `reply_suggestions` 테이블이 있는지 확인

---

## 🎯 다음 단계

워크플로우 생성 후:

1. **Backend URL 수정**: `n8n_tools.py`에서 URL을 `/webhook/generate-reply`로 수정
2. **Backend 재시작**: `docker-compose restart backend`
3. **전체 시스템 테스트**: 메일 동기화 → 분류 → 답변 생성 전체 플로우 테스트
