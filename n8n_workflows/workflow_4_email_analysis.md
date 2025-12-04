# n8n 워크플로우 #4: 이메일 분석

## 개요
특정 이메일을 Gemini AI로 분석하여 유형, 중요도, 답변 필요 여부, 감정 등을 판단하고 email 테이블에 저장합니다.

## Webhook 정보
- **URL**: `http://n8n:5678/webhook-test/analyze`
- **Method**: POST
- **Payload**:
```json
{
  "email_id": 123
}
```

## 워크플로우 구조

```
┌─────────────┐
│   Webhook   │ ← POST /webhook-test/analyze
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
         ┌────────────────────────┐
         │ Code: 분석 프롬프트 생성│
         │ - 이메일 내용 포맷팅    │
         │ - 분석 요청 프롬프트    │
         └──────┬─────────────────┘
                │
                ▼
         ┌──────────────────────┐
         │ Google Gemini        │
         │ Model: gemini-       │
         │ 2.0-flash-exp        │
         │ 이메일 분석 수행      │
         └──────┬───────────────┘
                │
                ▼
         ┌────────────────────────┐
         │ Code: JSON 파싱         │
         │ - Gemini 응답 파싱      │
         │ - 구조화된 데이터 생성  │
         └──────┬─────────────────┘
                │
                ▼
         ┌──────────────────────────┐
         │ PostgreSQL: 분석 결과 저장│
         │ UPDATE email            │
         │ SET analysis_result =   │
         │ jsonb                   │
         └──────┬───────────────────┘
                │
                ▼
         ┌──────────────────┐
         │ Return Response  │
         │ - 분석 결과       │
         └──────────────────┘
```

## 노드 상세 설명

### 1. Webhook Trigger
- **Type**: Webhook
- **Path**: `/webhook-test/analyze`
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
  body_html,
  received_at
FROM email
WHERE id = {{ $json.email_id }}
LIMIT 1;
```

### 3. IF - 이메일 존재 여부
- **Type**: IF
- **Condition**: `{{ $json.rowCount > 0 }}`
- **True**: 다음 노드로 진행
- **False**: 404 에러 응답

### 4. Code - 분석 프롬프트 생성
- **Type**: Code (JavaScript)
- **Input**: PostgreSQL 결과
- **Output**: Gemini 프롬프트

```javascript
const email = $input.first().json;

const prompt = `다음 이메일을 분석해주세요.

### 이메일 정보:
- 보낸 사람: ${email.sender_name || email.sender_address}
- 제목: ${email.subject || "(제목 없음)"}
- 본문:
${email.body_text || "(본문 없음)"}

### 분석 요청 사항:
1. **이메일 유형** (email_type): 채용, 마케팅, 공지, 개인, 기타 중 선택
2. **중요도** (importance_score): 0~10 점수로 평가
3. **답변 필요 여부** (needs_reply): true 또는 false
4. **감정 분석** (sentiment): positive, neutral, negative 중 선택
5. **핵심 내용** (key_points): 3~5개의 핵심 포인트 배열
6. **추천 행동** (recommended_action): 사용자가 취해야 할 행동

### 응답 형식 (JSON):
{
  "email_type": "채용|마케팅|공지|개인|기타",
  "importance_score": 7,
  "needs_reply": true,
  "sentiment": "positive|neutral|negative",
  "key_points": ["포인트1", "포인트2", "포인트3"],
  "recommended_action": "추천 행동 설명"
}

**JSON만 출력하고 다른 텍스트는 포함하지 마세요.**`;

return [{
  json: {
    prompt: prompt,
    email_id: email.id
  }
}];
```

### 5. Google Gemini - 이메일 분석
- **Type**: Google Gemini
- **Model**: `gemini-2.0-flash-exp`
- **Prompt**: `{{ $json.prompt }}`
- **Temperature**: 0.3 (일관성 있는 분석)
- **Max Output Tokens**: 1024

### 6. Code - JSON 파싱
- **Type**: Code (JavaScript)
- **Input**: Gemini 응답
- **Output**: 파싱된 분석 결과

```javascript
const geminiResponse = $input.first().json.text;
const emailId = $('Code').item.json.email_id;

// SQL 쿼리용 작은따옴표 이스케이프 함수
function escapeForSQL(text) {
  if (typeof text === 'string') {
    return text.replace(/'/g, "''");  // ' -> ''
  }
  return text;
}

// 배열 내 문자열 이스케이프
function escapeArray(arr) {
  if (Array.isArray(arr)) {
    return arr.map(item => typeof item === 'string' ? escapeForSQL(item) : item);
  }
  return arr;
}

try {
  // Gemini 응답에서 JSON 추출 (마크다운 코드 블록 제거)
  let jsonText = geminiResponse.trim();
  if (jsonText.startsWith('```json')) {
    jsonText = jsonText.replace(/```json\n?/g, '').replace(/```\n?/g, '');
  } else if (jsonText.startsWith('```')) {
    jsonText = jsonText.replace(/```\n?/g, '');
  }

  const analysis = JSON.parse(jsonText);

  // 기본값 설정 + SQL 이스케이프 적용
  const result = {
    email_type: escapeForSQL(analysis.email_type || "기타"),
    importance_score: Math.min(10, Math.max(0, analysis.importance_score || 5)),
    needs_reply: analysis.needs_reply === true,
    sentiment: escapeForSQL(analysis.sentiment || "neutral"),
    key_points: escapeArray(Array.isArray(analysis.key_points) ? analysis.key_points : []),
    recommended_action: escapeForSQL(analysis.recommended_action || "검토 필요")
  };

  return [{
    json: {
      email_id: emailId,
      analysis: result
    }
  }];

} catch (error) {
  // JSON 파싱 실패 시 기본값 반환
  return [{
    json: {
      email_id: emailId,
      analysis: {
        email_type: "기타",
        importance_score: 5,
        needs_reply: false,
        sentiment: "neutral",
        key_points: ["분석 실패"],
        recommended_action: "수동 검토 필요",
        parse_error: escapeForSQL(error.message)
      }
    }
  }];
}
```

### 7. PostgreSQL - 분석 결과 저장
- **Type**: PostgreSQL
- **Operation**: Execute Query
- **Query**:
```sql
UPDATE email
SET
  analysis_result = '{{ JSON.stringify($json.analysis) }}'::jsonb,
  analyzed_at = NOW()
WHERE id = {{ $json.email_id }};
```

### 8. Response
- **Type**: Respond to Webhook
- **Response Data**:
```json
{
  "success": true,
  "email_id": "{{ $json.email_id }}",
  "analysis": "{{ $json.analysis }}"
}
```

## 환경 변수 필요
- `GEMINI_API_KEY`: Gemini API 키
- PostgreSQL 연결 정보

## 테스트 방법

### curl 예시
```bash
curl -X POST http://localhost:5678/webhook-test/analyze \
  -H "Content-Type: application/json" \
  -d '{"email_id": 123}'
```

### 예상 응답
```json
{
  "success": true,
  "email_id": 123,
  "analysis": {
    "email_type": "채용",
    "importance_score": 8,
    "needs_reply": true,
    "sentiment": "positive",
    "key_points": [
      "면접 일정 조율",
      "2025년 11월 20일 오후 2시",
      "Zoom 링크 제공됨"
    ],
    "recommended_action": "면접 일정 확인 후 답장"
  }
}
```

## 에러 처리
- 이메일 없음: `{"error": "Email not found", "email_id": 123}`
- Gemini API 오류: n8n 자동 재시도 (최대 3회)
- JSON 파싱 실패: 기본값으로 저장 + parse_error 필드 추가
