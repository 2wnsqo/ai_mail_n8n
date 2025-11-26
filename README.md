# AI 메일 비서 (AI Email Assistant)

LangGraph + Gemini + n8n 기반 AI 메일 자동화 시스템

## 프로젝트 개요

네이버 메일을 자동으로 동기화하고, AI로 분석하여 답변을 생성하는 시스템입니다.

### 주요 기능

- **이메일 자동 동기화** (n8n IMAP)
- **AI 이메일 분석** (LangGraph + Gemini)
  - 이메일 유형 분류 (채용/마케팅/공지/개인/기타)
  - 중요도 점수 (0-10)
  - 답변 필요 여부 판단
  - 감정 분석
- **AI 답변 생성** (3가지 톤: 격식/친근함/간결함)
- **답변 자동 발송** (n8n SMTP)
- **React 대시보드**

---

## 기술 스택

### Backend
- **FastAPI** - Python 웹 프레임워크
- **LangGraph** - AI 에이전트 오케스트레이션
- **Gemini API** - Google AI (이메일 분석 및 답변 생성)
- **PostgreSQL** - 데이터베이스

### Frontend
- **React** - UI 프레임워크
- **Axios** - HTTP 클라이언트

### Workflow
- **n8n** - 이메일 동기화 및 발송 워크플로우

### Infrastructure
- **Docker Compose** - 전체 서비스 통합

---

## 프로젝트 구조

```
my_n8n/
├── backend/                    # FastAPI + LangGraph
│   ├── src/
│   │   ├── main.py            # FastAPI 서버
│   │   ├── config.py          # 환경변수 설정
│   │   ├── models/
│   │   │   └── schemas.py     # Pydantic 모델
│   │   ├── services/
│   │   │   ├── db_service.py      # PostgreSQL
│   │   │   └── gemini_service.py  # Gemini API
│   │   └── agents/
│   │       ├── email_analyzer.py      # LangGraph 이메일 분석
│   │       └── reply_generator.py     # LangGraph 답변 생성
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                  # React 대시보드
│   ├── src/
│   │   ├── App.js
│   │   ├── components/
│   │   │   ├── Dashboard.js
│   │   │   ├── EmailList.js
│   │   │   ├── EmailDetail.js
│   │   │   └── ReplyGenerator.js
│   │   ├── services/
│   │   │   └── api.js         # API 클라이언트
│   │   └── styles/
│   │       └── App.css
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml         # 전체 서비스 통합
├── .env                       # 환경변수 (Git 제외)
├── .env.example               # 환경변수 템플릿
├── .gitignore
└── README.md
```

---

## 설치 및 실행

### 1. 사전 준비

#### 필수 요구사항
- Docker & Docker Compose
- Git

#### API 키 발급
1. **Gemini API 키**: https://ai.google.dev/
2. **네이버 앱 비밀번호**: https://nid.naver.com/user2/help/myInfoV2?m=viewSecurity

---

### 2. 프로젝트 클론

```bash
git clone <repository-url>
cd my_n8n
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
N8N_PASS=your_password

# 네이버 IMAP/SMTP 정보
MY_NAVER_EMAIL=your_email@naver.com
MY_NAVER_APP_PASSWORD=your_naver_app_password
MY_NAVER_NAME=your_name

# Gemini API 키
MY_GEMINI_API_KEY=your_gemini_api_key

# PostgreSQL DB 접속 정보
MY_POSTGRES_HOST=host.docker.internal
MY_POSTGRES_USER=admin
MY_POSTGRES_PASSWORD=your_db_password
MY_POSTGRES_DB=mail
MY_POSTGRES_PORT=5432
```

---

### 4. Docker Compose로 전체 시스템 실행

```bash
docker-compose up -d
```

**실행되는 서비스:**
- PostgreSQL: `localhost:5432`
- n8n: `http://localhost:5678`
- Backend API: `http://localhost:8000`
- Frontend: `http://localhost:3000`

---

### 5. PostgreSQL 테이블 생성

PostgreSQL 컨테이너에 접속:

```bash
docker exec -it mail_postgres psql -U admin -d mail
```

테이블 생성 SQL 실행:

```sql
-- 이메일 테이블
CREATE TABLE IF NOT EXISTS email (
    id SERIAL PRIMARY KEY,
    received_at TIMESTAMP,
    sender_name VARCHAR(255),
    sender_address VARCHAR(255),
    subject TEXT,
    body_text TEXT,
    original_uid VARCHAR(255) UNIQUE,
    is_replied_to BOOLEAN DEFAULT FALSE,

    -- AI 분석 필드
    email_type VARCHAR(50),
    importance_score INTEGER,
    needs_reply BOOLEAN,
    sentiment VARCHAR(50),
    ai_analysis JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 일일 요약 테이블
CREATE TABLE IF NOT EXISTS daily_summaries (
    id SERIAL PRIMARY KEY,
    summary_date DATE UNIQUE NOT NULL,
    summary_content TEXT NOT NULL,
    email_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 발송 이메일 테이블
CREATE TABLE IF NOT EXISTS sent_emails (
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

### 6. n8n 워크플로우 설정

1. n8n 접속: `http://localhost:5678`
2. 로그인 (`.env`에 설정한 `N8N_USER`, `N8N_PASS`)
3. 워크플로우 2개 가져오기 (Import):
   - **워크플로우 1**: 메일 동기화 및 요약
   - **워크플로우 2**: 답변 메일 발송

---

## 사용법

### 1. React 대시보드 접속

브라우저에서 `http://localhost:3000` 접속

### 2. 이메일 목록 확인

- 전체 / 분석됨 / 미분석 필터링 가능
- 각 이메일의 유형, 중요도, 답변 필요 여부 확인

### 3. 이메일 분석

- 미분석 이메일에서 **"분석하기"** 버튼 클릭
- AI가 자동으로 이메일 유형, 중요도, 답변 필요 여부 판단

### 4. 답변 생성

1. 분석된 이메일 클릭
2. **"답변 생성하기"** 버튼 클릭
3. 3가지 톤(격식/친근함/간결함) 중 선택
4. 답변 내용 수정 가능
5. **"답변 발송"** 버튼으로 네이버 메일 발송

---

## API 문서

Backend API는 `http://localhost:8000/docs`에서 Swagger UI로 확인 가능

### 주요 엔드포인트

#### 이메일 조회
- `GET /emails` - 이메일 목록
- `GET /emails/{email_id}` - 이메일 상세
- `GET /emails/unanalyzed` - 미분석 이메일

#### 이메일 분석
- `POST /analyze/{email_id}` - 특정 이메일 분석
- `POST /analyze-all` - 전체 미분석 이메일 분석

#### 답변 생성
- `POST /generate-reply/{email_id}` - 답변 생성

#### 답변 발송
- `POST /send-reply` - 답변 발송 (n8n Webhook 호출)

#### 일일 요약
- `GET /summary/today` - 오늘의 이메일 요약

---

## 개발 환경

### Backend 로컬 실행

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

### Frontend 로컬 실행

```bash
cd frontend
npm install
npm start
```

---

## 트러블슈팅

### PostgreSQL 연결 실패
- `.env`의 `MY_POSTGRES_HOST` 확인
- Docker 네트워크 확인: `docker network ls`

### Gemini API 오류
- API 키 확인: `.env`의 `MY_GEMINI_API_KEY`
- API 할당량 확인: https://ai.google.dev/

### n8n Webhook 오류
- n8n 워크플로우가 활성화되어 있는지 확인
- Webhook URL 확인: `backend/src/main.py:send_reply`

---

## 향후 계획

- [ ] ElasticSearch + RAG 통합
- [ ] 피드백 학습 시스템
- [ ] 이메일 첨부파일 처리
- [ ] 다중 이메일 계정 지원
- [ ] 모바일 대시보드

---

## 라이선스

MIT License

---

## 기여

Pull Request 환영합니다!

---

## 문의

프로젝트 관련 문의: [GitHub Issues]
