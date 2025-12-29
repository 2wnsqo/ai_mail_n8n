# AI 메일 비서 시스템 - n8n 중심 아키텍처

## 📋 개요

이 시스템은 **n8n을 핵심 워크플로우 엔진**으로 사용하여 이메일 자동화를 처리합니다.

### 아키텍처 철학
- **n8n**: 모든 비즈니스 로직 (IMAP, SMTP, Gemini AI, PostgreSQL 작업)
- **Backend (FastAPI)**: 얇은 API Gateway (n8n webhook 호출만)
- **Frontend (React)**: 사용자 인터페이스
- **PostgreSQL**: 데이터 저장소

---

## 🏗️ 시스템 구조

```
┌──────────────┐
│   Frontend   │ (React)
│  Port: 3000  │
└──────┬───────┘
       │ HTTP API
       ▼
┌──────────────┐
│   Backend    │ (FastAPI)
│  Port: 8000  │ - API Gateway 역할
└──────┬───────┘
       │ Webhook 호출
       ▼
┌──────────────┐
│     n8n      │ (Workflow Engine)
│  Port: 5678  │ - IMAP Email
│              │ - Google Gemini
│              │ - PostgreSQL
│              │ - SMTP
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  PostgreSQL  │
│  Port: 5432  │
└──────────────┘
```

---

## 📦 n8n 워크플로우 구성

### 현재 워크플로우

| # | 이름 | Webhook 경로 | 역할 | 상태 |
|---|------|------------|------|------|
| 1 | 메일 동기화 | `/webhook-test/mail` | 오늘의 이메일 가져오기 (IMAP → DB) | ✅ 수정 필요 |
| 2 | 답변 발송 | `/webhook-test/send-reply` | 이메일 발송 (SMTP) | ✅ 완료 |
| 3 | 일일 요약 생성 | `/webhook-test/summary` | 오늘 이메일 Gemini 요약 | 🔧 신규 생성 |
| 4 | 이메일 분석 | `/webhook-test/analyze` | 개별 이메일 Gemini 분석 | 🔧 신규 생성 |
| 5 | 답변 생성 | `/webhook-test/generate-reply` | 3가지 톤 답변 생성 | 🔧 신규 생성 |

---

## 🔄 사용자 플로우

### 1. 메일 동기화
```
사용자: "📧 메일 동기화" 버튼 클릭
  ↓
Frontend → Backend POST /sync-emails
  ↓
Backend → n8n POST /webhook-test/mail
  ↓
n8n: IMAP으로 네이버 메일 가져오기
  ↓
n8n: PostgreSQL email 테이블에 저장
  ↓
Response: {"success": true, "new_emails": 5}
```

### 2. 일일 요약 생성
```
사용자: "📝 일일 요약" 버튼 클릭
  ↓
Frontend → Backend POST /summary/generate
  ↓
Backend → n8n POST /webhook-test/summary
  ↓
n8n: PostgreSQL에서 오늘 이메일 조회
  ↓
n8n: Gemini로 요약 생성
  ↓
n8n: daily_summaries 테이블에 저장
  ↓
Response: {"success": true, "summary": "..."}
```

### 3. 개별 이메일 분석
```
사용자: 특정 이메일 선택 → "분석하기" 버튼 클릭
  ↓
Frontend → Backend POST /analyze/123
  ↓
Backend → n8n POST /webhook-test/analyze
  ↓
n8n: PostgreSQL에서 이메일 조회
  ↓
n8n: Gemini로 분석 (유형, 중요도, 감정, 답변필요 여부)
  ↓
n8n: email 테이블 analysis_result 컬럼 업데이트
  ↓
Response: {"email_type": "채용", "importance_score": 8, ...}
```

### 4. 답변 생성
```
사용자: "답변 생성" 버튼 클릭
  ↓
Frontend → Backend POST /generate-reply/123
  ↓
Backend → n8n POST /webhook-test/generate-reply
  ↓
n8n: PostgreSQL에서 이메일 조회
  ↓
n8n: Gemini로 3가지 톤 답변 생성 (격식/친근/간결)
  ↓
n8n: reply_suggestions 테이블에 저장
  ↓
Response: {"reply_drafts": {"formal": "...", "casual": "...", "brief": "..."}}
```

### 5. 답변 발송
```
사용자: 생성된 답변 중 하나 선택 → "발송하기" 버튼 클릭
  ↓
Frontend → Backend POST /send-reply
  ↓
Backend → n8n POST /webhook-test/send-reply
  ↓
n8n: SMTP로 네이버 메일 발송
  ↓
n8n: sent_emails 테이블에 기록
  ↓
Backend: email 테이블 is_replied = true 업데이트
  ↓
Response: {"success": true, "message": "Reply sent"}
```

---

## 🛠️ 구현 단계

### ✅ 완료된 작업
1. Backend 간소화 - Gemini 로직 제거, n8n webhook 호출로 변경
2. LangGraph 에이전트 파일 삭제 (더 이상 필요 없음)
3. Backend 재시작
4. n8n 워크플로우 설계서 작성 (3, 4, 5번)
5. 워크플로우 #1 수정 가이드 작성

### 🔧 진행 중인 작업
**사용자가 수행해야 할 작업**:

#### 1단계: 워크플로우 #1 수정
- **가이드**: `workflow_1_modification_guide.md`
- **작업**: Gemini 요약 노드 4개 삭제
- **결과**: 순수 메일 동기화 기능만 남김

#### 2단계: 워크플로우 #3 생성 (일일 요약)
- **가이드**: `workflow_3_daily_summary.md`
- **Webhook**: `/webhook-test/summary`
- **노드 구성**:
  1. Webhook Trigger
  2. PostgreSQL - 오늘 이메일 조회
  3. IF - 이메일 존재 여부
  4. Code - 텍스트 결합
  5. Google Gemini - 요약 생성
  6. PostgreSQL - daily_summaries 저장
  7. Response

#### 3단계: 워크플로우 #4 생성 (이메일 분석)
- **가이드**: `workflow_4_email_analysis.md`
- **Webhook**: `/webhook-test/analyze`
- **노드 구성**:
  1. Webhook Trigger
  2. PostgreSQL - 이메일 조회
  3. IF - 이메일 존재 여부
  4. Code - 분석 프롬프트 생성
  5. Google Gemini - 분석
  6. Code - JSON 파싱
  7. PostgreSQL - 분석 결과 저장
  8. Response

#### 4단계: 워크플로우 #5 생성 (답변 생성)
- **가이드**: `workflow_5_reply_generation.md`
- **Webhook**: `/webhook-test/generate-reply`
- **노드 구성**:
  1. Webhook Trigger
  2. PostgreSQL - 이메일 조회
  3. IF - 이메일 존재 여부
  4. Code - 프롬프트 생성
  5. Google Gemini (formal) - 격식체 답변
  6. Google Gemini (casual) - 친근한 답변
  7. Google Gemini (brief) - 간결한 답변
  8. Code - 답변 결합
  9. PostgreSQL - reply_suggestions 저장
  10. Response

---

## 🔐 필요한 Credentials (n8n)

### 1. PostgreSQL
- **Type**: PostgreSQL
- **Host**: `postgres`
- **Port**: `5432`
- **Database**: `mail_db`
- **User**: `mail_user`
- **Password**: `.env` 파일 참조

### 2. Google Gemini
- **Type**: Google Gemini API
- **API Key**: `.env` 파일의 `GEMINI_API_KEY`
- **Model**: `gemini-2.0-flash-exp`

### 3. IMAP (네이버)
- **Type**: IMAP
- **Host**: `imap.naver.com`
- **Port**: `993`
- **Email**: `your_email@naver.com`
- **Password**: `.env` 파일 참조
- **Security**: SSL/TLS

### 4. SMTP (네이버)
- **Type**: SMTP
- **Host**: `smtp.naver.com`
- **Port**: `465`
- **Email**: `your_email@naver.com`
- **Password**: `.env` 파일 참조
- **Security**: SSL/TLS

---

## 📊 PostgreSQL 테이블 구조

### 주요 테이블

| 테이블 | 용도 | 주요 컬럼 |
|--------|------|----------|
| `email` | 수신 이메일 저장 | id, subject, sender_name, body_text, analysis_result, is_replied |
| `daily_summaries` | 일일 요약 | summary_date, summary_content, email_count |
| `reply_suggestions` | 답변 제안 | email_id, reply_drafts (jsonb), preferred_tone |
| `sent_emails` | 발송 기록 | original_email_id, to_email, reply_body, status |
| `reply_patterns` | 답변 패턴 (RAG용) | pattern_name, template_text, usage_count |
| `similar_emails` | 유사 이메일 매칭 | email_id, similar_email_id, similarity_score |
| `user_feedback` | 사용자 피드백 | suggestion_id, feedback_type, rating |
| `agent_execution_logs` | 실행 로그 | agent_name, email_id, execution_time |
| `notification_queue` | 알림 큐 | notification_type, recipient_email, is_sent |

---

## 🧪 테스트 체크리스트

### 1. 워크플로우 개별 테스트

#### 워크플로우 #1: 메일 동기화
```bash
curl -X POST http://localhost:5678/webhook-test/mail \
  -H "Content-Type: application/json" \
  -d '{"sync_date": "2025-11-15", "trigger_source": "manual_sync"}'
```

#### 워크플로우 #2: 답변 발송
```bash
curl -X POST http://localhost:5678/webhook-test/send-reply \
  -H "Content-Type: application/json" \
  -d '{
    "to_email": "test@example.com",
    "to_name": "홍길동",
    "subject": "Re: 테스트",
    "reply_body": "안녕하세요...",
    "sender_name": "AI 비서",
    "sender_email": "your_email@naver.com"
  }'
```

#### 워크플로우 #3: 일일 요약
```bash
curl -X POST http://localhost:5678/webhook-test/summary \
  -H "Content-Type: application/json" \
  -d '{"summary_date": "2025-11-15"}'
```

#### 워크플로우 #4: 이메일 분석
```bash
curl -X POST http://localhost:5678/webhook-test/analyze \
  -H "Content-Type: application/json" \
  -d '{"email_id": 123}'
```

#### 워크플로우 #5: 답변 생성
```bash
curl -X POST http://localhost:5678/webhook-test/generate-reply \
  -H "Content-Type: application/json" \
  -d '{"email_id": 123, "preferred_tone": "formal"}'
```

### 2. Backend API 테스트

```bash
# 헬스 체크
curl http://localhost:8000/health

# 메일 동기화
curl -X POST http://localhost:8000/sync-emails

# 일일 요약 생성
curl -X POST http://localhost:8000/summary/generate

# 이메일 분석
curl -X POST http://localhost:8000/analyze/123

# 답변 생성
curl -X POST http://localhost:8000/generate-reply/123?preferred_tone=formal

# 이메일 목록 조회
curl http://localhost:8000/emails?limit=10
```

### 3. Frontend 테스트
1. http://localhost:3000 접속
2. "📧 메일 동기화" 버튼 클릭 → 이메일 목록 표시
3. "📝 일일 요약" 버튼 클릭 → 요약 생성 확인
4. 이메일 선택 → 상세 내용 확인
5. "분석하기" 버튼 클릭 → 분석 결과 확인
6. "답변 생성" 버튼 클릭 → 3가지 답변 옵션 표시
7. 답변 선택 → "발송하기" 버튼 클릭 → 이메일 발송

---

## 📈 시스템 모니터링

### n8n 실행 로그 확인
```bash
docker logs -f mail_n8n
```

### Backend 로그 확인
```bash
docker logs -f mail_backend
```

### PostgreSQL 데이터 확인
```bash
docker exec -it mail_postgres psql -U mail_user -d mail_db
```

```sql
-- 최근 이메일 조회
SELECT id, subject, sender_name, received_at
FROM email
ORDER BY received_at DESC
LIMIT 10;

-- 오늘의 요약 조회
SELECT * FROM daily_summaries
WHERE summary_date = CURRENT_DATE;

-- 답변 제안 조회
SELECT id, email_id, preferred_tone, created_at
FROM reply_suggestions
ORDER BY created_at DESC
LIMIT 5;

-- 발송 이력 조회
SELECT id, to_email, subject, status, sent_at
FROM sent_emails
ORDER BY sent_at DESC
LIMIT 5;
```

---

## 🐛 문제 해결

### n8n Webhook 404 에러
**원인**: 워크플로우가 비활성화 상태
**해결**:
1. n8n UI 접속 (http://localhost:5678)
2. 해당 워크플로우 선택
3. 우측 상단 "Active" 토글 ON

### Gemini API 오류
**원인**: API Key 만료 또는 할당량 초과
**해결**:
1. `.env` 파일에서 `GEMINI_API_KEY` 확인
2. Google AI Studio에서 할당량 확인
3. n8n Credentials에서 API Key 재등록

### PostgreSQL 연결 실패
**원인**: 컨테이너 실행 안 됨
**해결**:
```bash
docker ps | grep postgres
docker restart mail_postgres
```

### IMAP/SMTP 인증 실패
**원인**: 네이버 계정 보안 설정
**해결**:
1. 네이버 메일 설정 → POP3/IMAP 설정 활성화
2. 2단계 인증 사용 시 앱 비밀번호 생성
3. n8n Credentials에서 비밀번호 업데이트

---

## 📚 참고 문서

- `workflow_1_modification_guide.md` - 워크플로우 #1 수정 방법
- `workflow_3_daily_summary.md` - 워크플로우 #3 생성 가이드
- `workflow_4_email_analysis.md` - 워크플로우 #4 생성 가이드
- `workflow_5_reply_generation.md` - 워크플로우 #5 생성 가이드
- `../backend/init.sql` - PostgreSQL 스키마 정의
- `../.env` - 환경 변수 (비밀번호, API Key)

---

## 🚀 다음 단계

1. **워크플로우 #1 수정** (`workflow_1_modification_guide.md` 참조)
2. **워크플로우 #3, #4, #5 생성** (각 가이드 참조)
3. **전체 시스템 테스트** (위 체크리스트 활용)
4. **프로덕션 배포 준비**:
   - 환경 변수 보안 강화
   - n8n 워크플로우 백업
   - PostgreSQL 백업 스케줄 설정
   - 모니터링 및 알림 설정
