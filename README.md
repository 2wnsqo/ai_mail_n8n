# AI 메일 비서 (AI Email Assistant)

LangGraph + Gemini 2.5 Flash + n8n 기반 하이브리드 AI 메일 자동화 시스템

## 프로젝트 개요

네이버 메일을 자동으로 동기화하고, AI로 분석하여 답변을 생성하는 통합 시스템입니다.

### 주요 기능

- **이메일 자동 동기화** (n8n IMAP)
- **AI 이메일 분석** (Gemini 2.5 Flash)
  - 이메일 유형 분류 (채용/마케팅/공지/개인/기타)
  - 중요도 점수 (0-10)
  - 답변 필요 여부 판단
  - 감정 분석 (positive/neutral/negative)
  - 핵심 내용 요약
- **AI 답변 생성** (3가지 톤)
  - 격식체 (Formal)
  - 친근함 (Casual)
  - 간결함 (Brief)
- **답변 자동 발송** (n8n SMTP)
- **일일 요약** (오늘 받은 이메일 통계 및 요약)
- **React 대시보드**
  - 이메일 목록 필터링
  - 전체 분석 버튼
  - 요약 보기 모달
  - 답변 생성 및 편집

---

## 기술 스택

### Backend
- **FastAPI** - Python 웹 프레임워크
- **LangGraph** - AI 에이전트 오케스트레이션 (Supervisor pattern)
- **Gemini 2.5 Flash** - Google AI (이메일 분석 및 답변 생성)
- **PostgreSQL** - 관계형 데이터베이스
- **psycopg2** - PostgreSQL 어댑터

### Frontend
- **React** - UI 프레임워크
- **Axios** - HTTP 클라이언트 (timeout: 90초)

### Workflow Automation
- **n8n** - 이메일 동기화, 분석, 답변 생성 워크플로우

### Infrastructure
- **Docker Compose** - 멀티 컨테이너 통합 배포

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                          │
│                   (localhost:3000)                          │
└────────────────┬────────────────────────────────────────────┘
                 │ REST API
                 ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI Backend                               │
│              (localhost:8000)                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LangGraph Supervisor (email_processor.py)           │  │
│  │  - analyze_agent: 이메일 분석                        │  │
│  │  - reply_agent: 답변 생성                            │  │
│  │  - summary_agent: 일일 요약                          │  │
│  └──────────────────────────────────────────────────────┘  │
└────────┬───────────────────────┬────────────────────────────┘
         │ Gemini API            │ PostgreSQL
         ▼                       ▼
┌─────────────────┐    ┌─────────────────────────────────────┐
│  Gemini 2.5     │    │      PostgreSQL                     │
│     Flash       │    │    (localhost:5432)                 │
└─────────────────┘    │  - email                            │
                       │  - reply_drafts                     │
                       │  - daily_summaries                  │
                       │  - sent_emails                      │
                       └─────────────────────────────────────┘
         ▲
         │ Webhook
         │
┌─────────────────────────────────────────────────────────────┐
│                    n8n Workflows                            │
│                  (localhost:5678)                           │
│  - Email Sync (IMAP)                                        │
│  - Reply Generation (3 tones)                               │
│  - Email Sending (SMTP)                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 프로젝트 구조

```
ai_mail_n8n/
├── backend/                    # FastAPI + LangGraph
│   ├── src/
│   │   ├── main.py             # FastAPI 서버 (Gemini 직접 호출)
│   │   ├── config.py           # 환경변수 설정
│   │   ├── models/
│   │   │   └── schemas.py      # Pydantic 모델
│   │   ├── services/
│   │   │   ├── db_service.py       # PostgreSQL 연결
│   │   │   ├── gemini_service.py   # Gemini API (Legacy)
│   │   │   └── rag_service.py      # RAG (향후 확장)
│   │   ├── agents/
│   │   │   └── email_processor.py  # LangGraph Supervisor
│   │   └── tools/
│   │       └── n8n_tools.py        # n8n Webhook 호출
│   ├── init.sql                # DB 초기화 스크립트
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                   # React 대시보드
│   ├── src/
│   │   ├── App.js
│   │   ├── components/
│   │   │   ├── Dashboard.js        # 메인 대시보드
│   │   │   ├── EmailList.js        # 이메일 목록 (필터링)
│   │   │   ├── EmailDetail.js      # 이메일 상세
│   │   │   └── ReplyGenerator.js   # 답변 생성 (3 tones)
│   │   ├── services/
│   │   │   └── api.js              # API 클라이언트 (timeout 90s)
│   │   └── styles/
│   │       └── App.css
│   ├── package.json
│   └── Dockerfile
│
├── n8n_workflows/              # n8n 워크플로우 정의
│   ├── naver_mail.json         # 통합 워크플로우 (동기화/분석/답변/발송)
│   └── README.md               # 워크플로우 가이드
│
├── architecture/               # 시스템 아키텍처 문서
│   ├── FINAL_GUIDE.md
│   └── langgraph_n8n_hybrid.md
│
├── docker-compose.yml          # 전체 서비스 통합
├── .env.example                # 환경변수 템플릿
├── .gitignore
├── ADVANCED_SYSTEM.md
└── README.md
```

---

## 데이터베이스 스키마

### 1. email (이메일 테이블)
```sql
CREATE TABLE email (
    id SERIAL PRIMARY KEY,
    received_at TIMESTAMP,
    sender_name VARCHAR(255),
    sender_address VARCHAR(255),
    subject TEXT,
    body_text TEXT,
    original_uid VARCHAR(255) UNIQUE,
    is_replied_to BOOLEAN DEFAULT FALSE,

    -- AI 분석 필드
    email_type VARCHAR(50),              -- 채용/마케팅/공지/개인/기타
    importance_score INTEGER,            -- 0-10
    needs_reply BOOLEAN,
    sentiment VARCHAR(50),               -- positive/neutral/negative
    ai_analysis JSONB,                   -- 핵심 내용 등
    processing_status VARCHAR(50),       -- pending/analyzed/reply_generated

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. reply_drafts (답변 초안 테이블)
```sql
CREATE TABLE reply_drafts (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES email(id) ON DELETE CASCADE,
    tone VARCHAR(50) NOT NULL,           -- formal/casual/brief
    reply_text TEXT NOT NULL,
    confidence_score FLOAT,
    status VARCHAR(50) DEFAULT 'generated',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(email_id, tone)               -- 이메일당 톤별 1개
);
```

### 3. daily_summaries (일일 요약 테이블)
```sql
CREATE TABLE daily_summaries (
    id SERIAL PRIMARY KEY,
    summary_date DATE UNIQUE NOT NULL,
    summary_content TEXT NOT NULL,
    email_count INTEGER DEFAULT 0,
    reply_needed_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. sent_emails (발송 이메일 테이블)
```sql
CREATE TABLE sent_emails (
    id SERIAL PRIMARY KEY,
    original_email_id INTEGER REFERENCES email(id),
    to_email VARCHAR(255) NOT NULL,
    to_name VARCHAR(255),
    subject TEXT NOT NULL,
    reply_body TEXT NOT NULL,
    sender_name VARCHAR(255),
    sender_email VARCHAR(255),
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'sent',
    error_message TEXT
);
```

---

## 설치 및 실행

### 1. 사전 준비

#### 필수 요구사항
- **Docker Desktop** 설치 및 실행
- **Git** 설치

#### API 키 발급
1. **Gemini API 키**: https://ai.google.dev/
   - Google AI Studio에서 무료 API 키 발급
   - Gemini 2.5 Flash 사용

2. **네이버 앱 비밀번호**: https://nid.naver.com/user2/help/myInfoV2?m=viewSecurity
   - IMAP/SMTP 접근용 앱 비밀번호 생성

---

### 2. 프로젝트 클론

```bash
git clone https://github.com/2wnsqo/ai_mail_n8n.git
cd ai_mail_n8n
```

---

### 3. 환경변수 설정

`.env.example`을 복사하여 `.env` 파일 생성:

```bash
cp .env.example .env
```

`.env` 파일을 편집하여 실제 값 입력:

```env
# n8n 로그인 정보
N8N_USER=admin
N8N_PASS=your_secure_password

# 네이버 IMAP/SMTP 정보
MY_NAVER_EMAIL=your_email@naver.com
MY_NAVER_APP_PASSWORD=your_naver_app_password
MY_NAVER_NAME=홍길동

# Gemini API 키
MY_GEMINI_API_KEY=your_gemini_api_key

# PostgreSQL DB 접속 정보
MY_POSTGRES_HOST=postgres
MY_POSTGRES_USER=admin
MY_POSTGRES_PASSWORD=your_secure_db_password
MY_POSTGRES_DB=mail
MY_POSTGRES_PORT=5432
```

---

### 4. Docker Compose로 전체 시스템 실행

```bash
docker-compose up -d
```

**실행되는 서비스:**
- **PostgreSQL**: `localhost:5432` (자동으로 테이블 생성됨)
- **n8n**: `http://localhost:5678`
- **Backend API**: `http://localhost:8000`
- **Frontend**: `http://localhost:3000`

**컨테이너 상태 확인:**
```bash
docker-compose ps
```

**로그 확인:**
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

---

### 5. n8n 워크플로우 설정

1. **n8n 접속**: `http://localhost:5678`
2. **로그인**: `.env`에 설정한 `N8N_USER`, `N8N_PASS` 사용
3. **워크플로우 가져오기 (Import)**:
   - `n8n_workflows/naver_mail.json` 파일을 n8n에 Import
   - 워크플로우 이름: "Naver Mail Automation"

4. **IMAP Credentials 설정**:
   - IMAP Email 노드 클릭
   - Credentials 생성:
     - User: `.env`의 `MY_NAVER_EMAIL`
     - Password: `.env`의 `MY_NAVER_APP_PASSWORD`
     - Host: `imap.naver.com`
     - Port: `993`
     - SSL/TLS: Enable

5. **워크플로우 활성화**:
   - 워크플로우 우측 상단 토글 ON

---

## 사용법

### 1. 웹 대시보드 접속

브라우저에서 `http://localhost:3000` 접속

---

### 2. 이메일 동기화

- n8n이 자동으로 5분마다 네이버 메일 동기화
- 또는 Backend API 호출: `POST http://localhost:8000/sync-emails`

---

### 3. 이메일 목록 확인

**필터 옵션:**
- 전체 이메일
- 분석됨 (AI 분석 완료)
- 미분석

**표시 정보:**
- 발신자, 제목, 날짜
- 이메일 유형 (채용/마케팅/공지/개인/기타)
- 중요도 점수 (⭐ 1~10)
- 답변 필요 여부 (✉️)

---

### 4. 이메일 분석

#### 개별 분석:
1. 미분석 이메일 클릭
2. **"분석하기"** 버튼 클릭
3. AI가 자동 분석 (약 5~10초)

#### 전체 분석:
1. 상단 **"🔍 전체 분석"** 버튼 클릭
2. 모든 미분석 이메일을 일괄 분석

**분석 결과:**
- 이메일 유형
- 중요도 점수 (0-10)
- 답변 필요 여부
- 감정 분석 (positive/neutral/negative)
- 핵심 내용 요약

---

### 5. 일일 요약 확인

1. 상단 **"📊 요약 보기"** 버튼 클릭
2. 모달에서 확인:
   - 총 이메일 수
   - 답변 필요 이메일 수
   - AI 요약 내용
   - 핵심 포인트
   - 유형별 분포 (채용/마케팅/공지/개인/기타)

---

### 6. 답변 생성 및 발송

1. 분석된 이메일 클릭
2. **"답변 생성하기"** 버튼 클릭 (약 30~50초 소요)
3. **3가지 톤 중 선택**:
   - 🎩 격식체 (Formal): 공식적인 비즈니스 이메일
   - 😊 친근함 (Casual): 친밀한 톤의 답변
   - ⚡ 간결함 (Brief): 짧고 명확한 답변
4. 답변 내용 직접 수정 가능
5. **"답변 발송"** 버튼으로 네이버 메일 발송

---

## API 문서

Backend API는 `http://localhost:8000/docs`에서 Swagger UI로 확인 가능

### 주요 엔드포인트

#### 📧 이메일 관리
- `POST /sync-emails` - 네이버 메일 동기화 (n8n 호출)
- `GET /emails` - 이메일 목록 조회
  - `?limit=50` - 페이지당 개수
  - `?offset=0` - 오프셋
  - `?analyzed_only=false` - 분석됨만 필터
- `GET /emails/{email_id}` - 이메일 상세 조회
- `GET /emails/unanalyzed` - 미분석 이메일 목록

#### 🤖 AI 분석
- `POST /analyze/{email_id}` - 특정 이메일 분석 (Gemini 직접 호출)
- `POST /analyze-all` - 전체 미분석 이메일 분석

#### ✍️ 답변 생성
- `POST /generate-reply/{email_id}` - 답변 생성 (n8n 워크플로우 호출)
  - `?preferred_tone=formal` - 선호 톤 (formal/casual/brief)
  - **응답 시간**: 약 30~50초
  - **Timeout**: Backend 90초, Frontend 90초

#### 📮 답변 발송
- `POST /send-reply` - 답변 발송 (n8n SMTP 워크플로우 호출)
  ```json
  {
    "email_id": 1,
    "reply_text": "답변 내용",
    "to_email": "recipient@example.com",
    "to_name": "수신자"
  }
  ```

#### 📊 일일 요약
- `GET /summary/today` - 오늘의 이메일 요약 조회
- `POST /summary/generate` - 일일 요약 생성

#### 🏥 헬스체크
- `GET /health` - 서버 상태 확인

---

## 개발 환경

### Backend 로컬 실행 (개발 모드)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 환경변수 설정 (윈도우)
set MY_POSTGRES_HOST=localhost
set MY_GEMINI_API_KEY=your_key
# ... 기타 환경변수

uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend 로컬 실행 (개발 모드)

```bash
cd frontend
npm install
npm start
```

**Frontend 개발 시 주의사항:**
- `src/services/api.js`의 timeout이 90초로 설정됨
- Backend API가 `http://localhost:8000`에서 실행 중이어야 함

---

## 트러블슈팅

### 1. PostgreSQL 연결 실패

**증상**: Backend에서 DB 연결 오류

**해결책**:
```bash
# .env 파일 확인
cat .env | grep POSTGRES

# PostgreSQL 컨테이너 상태 확인
docker-compose ps postgres

# PostgreSQL 로그 확인
docker-compose logs postgres

# 컨테이너 재시작
docker-compose restart postgres backend
```

---

### 2. Gemini API 오류

**증상**: `429 Too Many Requests` 또는 `401 Unauthorized`

**해결책**:
- API 키 확인: `.env`의 `MY_GEMINI_API_KEY`
- API 할당량 확인: https://ai.google.dev/
- Gemini 2.5 Flash 모델 사용 확인
- Rate limit: 1분에 최대 15회 요청

---

### 3. n8n Webhook 오류

**증상**: 답변 생성 시 timeout 또는 500 에러

**해결책**:
```bash
# n8n 워크플로우 활성화 확인
# http://localhost:5678 접속 후 워크플로우 토글 ON 확인

# n8n 로그 확인
docker-compose logs n8n

# Backend에서 n8n 연결 확인
curl http://localhost:5678/webhook/generate-reply -X POST \
  -H "Content-Type: application/json" \
  -d '{"email_id": 1, "preferred_tone": "formal"}'
```

**Timeout 설정**:
- Backend → n8n: 90초
- Frontend → Backend: 90초
- n8n 워크플로우: 약 30~50초 소요

---

### 4. Frontend 화면이 안 나옴

**증상**: `localhost:3000`에서 빈 화면 또는 로딩만 표시

**해결책**:
```bash
# Frontend 컨테이너 로그 확인
docker-compose logs frontend

# Frontend 컨테이너 재시작
docker-compose restart frontend

# 브라우저 캐시 삭제 후 하드 리프레시
# Windows: Ctrl + Shift + R
# Mac: Cmd + Shift + R
```

---

### 5. 이메일 동기화가 안됨

**증상**: n8n에서 메일을 가져오지 못함

**해결책**:
1. n8n IMAP Credentials 재설정:
   - Host: `imap.naver.com`
   - Port: `993`
   - User: 네이버 이메일
   - Password: **앱 비밀번호** (일반 비밀번호 아님!)
   - SSL/TLS: Enable

2. 네이버 앱 비밀번호 재생성:
   - https://nid.naver.com/user2/help/myInfoV2?m=viewSecurity

3. n8n 워크플로우 수동 실행:
   - "Execute Workflow" 버튼 클릭하여 테스트

---

### 6. 답변 생성 시 undefined 오류

**증상**: Frontend에서 `Cannot read properties of undefined`

**해결책**:
```bash
# Frontend 컨테이너 재시작 (최신 코드 반영)
docker-compose restart frontend

# 브라우저 캐시 완전 삭제
# 개발자 도구 (F12) → Application → Clear site data

# 또는 시크릿 모드에서 테스트
```

---

## 성능 최적화

### Backend 최적화
- Gemini API 직접 호출로 분석 속도 향상 (5~10초)
- n8n 워크플로우는 답변 생성에만 사용 (30~50초)
- PostgreSQL 연결 풀링 활용

### Frontend 최적화
- Axios timeout 90초 설정 (긴 워크플로우 대응)
- React 상태 관리 최적화
- 에러 핸들링 강화

### n8n 워크플로우 최적화
- Loop Over Items 사용으로 메모리 효율 개선
- SQL Injection 방지 (Single quote escaping)
- Webhook 응답 형식 표준화

---

## 보안

### 환경변수 관리
- ⚠️ **절대 `.env` 파일을 Git에 커밋하지 마세요!**
- `.env.example`을 참고하여 로컬에서 `.env` 생성
- API 키 및 비밀번호는 안전하게 보관

### Docker Volumes
- `postgres_data/` - DB 데이터 (Git 제외)
- `n8n_data/` - n8n credentials 포함 (Git 제외)

### 네트워크 보안
- Docker 내부 네트워크 사용
- 외부 포트는 최소화 (3000, 5678, 8000만 노출)

---

## 향후 계획

- [ ] ElasticSearch + RAG 통합 (이메일 검색 고도화)
- [ ] 피드백 학습 시스템 (답변 품질 개선)
- [ ] 이메일 첨부파일 처리 (PDF, 이미지 분석)
- [ ] 다중 이메일 계정 지원
- [ ] 모바일 대시보드 (React Native)
- [ ] 실시간 알림 (WebSocket)
- [ ] 답변 템플릿 관리
- [ ] A/B 테스트 (답변 톤별 효과 분석)

---

## 기술적 특징

### 하이브리드 아키텍처
- **Backend (FastAPI + Gemini)**: 빠른 분석 (5~10초)
- **n8n 워크플로우**: 복잡한 작업 (답변 생성 30~50초)
- 장점: 각 작업에 최적화된 도구 활용

### LangGraph Supervisor Pattern
- Supervisor가 여러 Agent 조율
- analyze_agent, reply_agent, summary_agent
- 확장 가능한 구조

### 정규화된 DB 스키마
- `reply_drafts` 테이블로 톤별 답변 관리
- `UNIQUE(email_id, tone)` 제약 조건
- Upsert 패턴으로 중복 방지

---

## 라이선스

MIT License

---

## 기여

Pull Request 및 Issue 제출을 환영합니다!

**기여 가이드**:
1. Fork this repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 문의

프로젝트 관련 문의: [GitHub Issues](https://github.com/2wnsqo/ai_mail_n8n/issues)

---

## Credits

🤖 **Powered by**:
- [Google Gemini 2.5 Flash](https://ai.google.dev/)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [n8n](https://n8n.io/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/)

💻 **Developed with**:
- [Claude Code](https://claude.com/claude-code)
- Co-Authored-By: Claude <noreply@anthropic.com>

---

**⭐ 이 프로젝트가 도움이 되었다면 Star를 눌러주세요!**
