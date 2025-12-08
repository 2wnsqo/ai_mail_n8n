# n8n RAG 연동 설정 가이드

## 개요

이 가이드는 n8n 워크플로우에서 RAG(Retrieval-Augmented Generation)를 활용하여 이메일 분석 품질을 향상시키는 방법을 설명합니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG 적용 흐름                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Backend  │───▶│ RAG      │───▶│ n8n      │              │
│  │ API      │    │ Service  │    │ Workflow │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│       │               │               │                     │
│       │               ▼               ▼                     │
│       │         ┌──────────┐    ┌──────────┐              │
│       │         │ ChromaDB │    │ Gemini   │              │
│       │         │ VectorDB │    │ LLM      │              │
│       │         └──────────┘    └──────────┘              │
│       │               │               │                     │
│       │               └───────┬───────┘                     │
│       │                       │                             │
│       └───────────────────────▼                             │
│                         ┌──────────┐                        │
│                         │ 분석 결과 │                        │
│                         └──────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 방법 1: 기존 워크플로우 수정 (권장)

### Step 1: n8n UI 접속

1. 브라우저에서 `http://localhost:5678` 접속
2. 이메일 분석 워크플로우 선택 (또는 새로 생성)

### Step 2: Code 노드 수정

**기존 프롬프트 생성 노드**를 찾아서 다음과 같이 수정:

```javascript
// Webhook에서 받은 데이터 추출
const input = $input.first().json;
const body = input.body || input;

const email_id = body.email_id;
const subject = body.subject || '';
const sender_name = body.sender_name || '';
const sender_address = body.sender_address || '';
const body_text = body.body_text || '';
const rag_prompt = body.rag_prompt || null;  // ★ RAG 프롬프트 추가

// RAG 프롬프트가 있으면 사용, 없으면 기본 프롬프트 생성
let prompt;

if (rag_prompt) {
    // ★ RAG 강화 프롬프트 사용 (백엔드에서 생성됨)
    prompt = rag_prompt;
    console.log('[RAG] RAG 강화 프롬프트 사용');
} else {
    // 기본 프롬프트
    prompt = `다음 이메일을 분석해주세요.

## 이메일 정보
- 제목: ${subject}
- 발신자: ${sender_name} <${sender_address}>
- 본문:
${body_text.substring(0, 1500)}

## 분석 요청
위 이메일을 분석하여 다음 JSON 형식으로 응답해주세요:
{
    "email_type": "채용|마케팅|공지|개인|기타 중 하나",
    "importance_score": 1-10 사이의 정수,
    "needs_reply": true 또는 false,
    "sentiment": "positive|negative|neutral 중 하나",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", ...]
}`;
}

return [{
    json: {
        email_id: email_id,
        prompt: prompt,
        used_rag: rag_prompt !== null
    }
}];
```

### Step 3: 워크플로우 활성화

1. 워크플로우 저장
2. "Active" 토글 켜기

---

## 방법 2: 새 워크플로우 Import

### Step 1: JSON 파일 Import

1. n8n UI에서 좌측 메뉴 → "Workflows"
2. 우상단 "..." → "Import from File"
3. `workflow_analyze_with_rag.json` 파일 선택

### Step 2: Credentials 연결

1. Import된 워크플로우 열기
2. "Gemini - Analyze Email" 노드 클릭
3. Credentials에서 기존 "Google Gemini(PaLM) Api account" 선택

### Step 3: 활성화

1. 저장 후 Active 토글 켜기

---

## 방법 3: 백엔드에서 자동 처리 (코드 수정 완료)

**이미 구현됨!** `n8n_tools.py`에서 자동으로 RAG 프롬프트를 생성하여 n8n에 전달합니다.

### 작동 방식

```python
# backend/src/tools/n8n_tools.py

def analyze_email(self, email_id: int, email_data: Dict = None, use_rag: bool = True):
    # RAG 강화 프롬프트 자동 생성
    rag_prompt = None
    if use_rag:
        rag_prompt = self._get_rag_enhanced_prompt(email_data)

    # n8n webhook에 rag_prompt 포함하여 전달
    payload = {
        "email_id": email_id,
        "subject": email_data.get('subject', ''),
        "body_text": email_data.get('body_text', ''),
        "rag_prompt": rag_prompt  # ★ RAG 프롬프트
    }

    response = requests.post(url, json=payload)
```

---

## RAG 프롬프트 예시

### RAG가 적용된 프롬프트 (실제 예시)

```
다음 이메일을 분석해주세요.

## 이메일 정보
- 제목: [ABC회사] 서류 전형 합격 및 면접 안내
- 발신자: 김채용 <recruit@abc.com>
- 본문:
안녕하세요. ABC회사 채용담당자 김채용입니다...

## 참조 정보 (RAG)
다음은 유사한 이메일의 분류 예시입니다:

예시 1:
- 제목: Interview invitation from XYZ Corp
- 유형: 채용
- 중요도: 9

예시 2:
- 제목: Your application status update
- 유형: 채용
- 중요도: 8

위 예시를 참고하여 분류해주세요.

유사 이메일의 중요도 예시:
- [high] 중요도 9/10: Interview invitation...
- [high] 중요도 8/10: Application status...

(참고: 유사 이메일들의 평균 중요도는 8.5점입니다)

## 분석 요청
위 이메일을 분석하여 다음 JSON 형식으로 응답해주세요:
{
    "email_type": "채용|마케팅|공지|개인|기타 중 하나",
    "importance_score": 1-10 사이의 정수,
    "needs_reply": true 또는 false,
    "sentiment": "positive|negative|neutral 중 하나",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", ...]
}
```

---

## 테스트 방법

### curl로 RAG 적용 테스트

```bash
# 1. RAG 상태 확인
curl http://localhost:8000/rag/status

# 2. RAG 프롬프트 생성 테스트
curl -X POST http://localhost:8000/rag/enhance-prompt \
  -H "Content-Type: application/json" \
  -d '{"email_id": 1}'

# 3. 이메일 분석 (RAG 적용)
curl -X POST http://localhost:8000/analyze/1
```

### Python으로 테스트

```python
from src.tools.n8n_tools import n8n_tools

# RAG 적용 분석
result = n8n_tools.analyze_email(email_id=1, use_rag=True)
print(result)

# RAG 미적용 분석 (비교용)
result_no_rag = n8n_tools.analyze_email(email_id=1, use_rag=False)
print(result_no_rag)
```

---

## 트러블슈팅

### RAG가 적용되지 않는 경우

1. **RAG 서비스 상태 확인**
   ```bash
   curl http://localhost:8000/rag/status
   ```
   - `status: "ready"` 확인
   - Collections에 데이터가 있는지 확인

2. **Vector DB 빌드**
   ```bash
   docker exec mail_backend python -m src.rag.build_vectordb
   ```

3. **로그 확인**
   ```bash
   docker logs mail_backend 2>&1 | grep RAG
   ```

### n8n에서 rag_prompt가 인식되지 않는 경우

1. Code 노드에서 `body.rag_prompt` 접근 확인
2. Webhook이 JSON body를 정상 수신하는지 확인
3. 워크플로우 재활성화

---

## 파일 위치

| 파일 | 설명 |
|------|------|
| `backend/src/tools/n8n_tools.py` | n8n 연동 (RAG 프롬프트 자동 생성) |
| `backend/src/rag/rag_service.py` | RAG 서비스 코어 |
| `n8n_workflows/workflow_analyze_with_rag.json` | RAG 지원 워크플로우 |
| `backend/src/rag/vectordb/` | ChromaDB 벡터 저장소 |

---

*Generated: 2025-12-08*
