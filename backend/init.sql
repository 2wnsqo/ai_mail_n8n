-- ===================================================
-- AI 메일 비서 - 고급 데이터베이스 스키마
-- ===================================================

-- 1. 기존 email 테이블 (확장)
CREATE TABLE IF NOT EXISTS email (
    id SERIAL PRIMARY KEY,
    received_at TIMESTAMP,
    sender_name VARCHAR(255),
    sender_address VARCHAR(255),
    subject TEXT,
    body_text TEXT,
    original_uid VARCHAR(255) UNIQUE,
    is_replied_to BOOLEAN DEFAULT FALSE,

    -- AI 분석 결과
    email_type VARCHAR(50),           -- 채용/마케팅/공지/개인/기타
    importance_score INTEGER,         -- 0-10
    needs_reply BOOLEAN,
    sentiment VARCHAR(50),            -- positive/neutral/negative
    ai_analysis JSONB,                -- 전체 분석 결과

    -- 새로 추가: 처리 상태
    processing_status VARCHAR(50) DEFAULT 'pending', -- pending/analyzing/analyzed/replying/replied
    retry_count INTEGER DEFAULT 0,    -- 재시도 횟수
    last_error TEXT,                  -- 마지막 에러 메시지

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 추가 (검색 성능 향상)
CREATE INDEX IF NOT EXISTS idx_email_type ON email(email_type);
CREATE INDEX IF NOT EXISTS idx_email_importance ON email(importance_score);
CREATE INDEX IF NOT EXISTS idx_email_status ON email(processing_status);
CREATE INDEX IF NOT EXISTS idx_email_received ON email(received_at DESC);


-- 2. 일일 요약 테이블
CREATE TABLE IF NOT EXISTS daily_summaries (
    id SERIAL PRIMARY KEY,
    summary_date DATE UNIQUE NOT NULL,
    summary_content TEXT NOT NULL,
    email_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 3. 발송 이메일 테이블 (확장)
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
    error_message TEXT,

    -- 새로 추가: 사용자 승인 관련
    approved_by VARCHAR(255),         -- 승인한 사용자
    approved_at TIMESTAMP,            -- 승인 시간
    original_draft TEXT,              -- 원본 AI 생성 답변
    user_modifications TEXT           -- 사용자 수정 내용 (JSON)
);


-- 4. 답변 제안 테이블 (새로 추가)
-- 사용자 승인 전 AI가 생성한 답변 임시 저장
CREATE TABLE IF NOT EXISTS reply_suggestions (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES email(id),

    -- 3가지 톤의 답변
    formal_draft TEXT,
    casual_draft TEXT,
    brief_draft TEXT,

    -- 메타데이터
    confidence_scores JSONB,          -- {"formal": 0.9, "casual": 0.85, "brief": 0.8}
    generation_metadata JSONB,        -- 생성 관련 정보

    -- 상태
    status VARCHAR(50) DEFAULT 'pending',  -- pending/approved/rejected
    selected_tone VARCHAR(50),        -- 사용자가 선택한 톤

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '7 days')
);

CREATE INDEX IF NOT EXISTS idx_suggestions_email ON reply_suggestions(email_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_status ON reply_suggestions(status);


-- 5. 유사 이메일 매핑 테이블 (RAG용)
-- 이메일 간 유사도 저장
CREATE TABLE IF NOT EXISTS similar_emails (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES email(id),
    similar_email_id INTEGER REFERENCES email(id),
    similarity_score FLOAT,           -- 0.0 ~ 1.0
    similarity_method VARCHAR(50),    -- 'keyword', 'semantic', 'sender'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(email_id, similar_email_id)
);

CREATE INDEX IF NOT EXISTS idx_similar_email ON similar_emails(email_id);
CREATE INDEX IF NOT EXISTS idx_similar_score ON similar_emails(similarity_score DESC);


-- 6. 답변 패턴 학습 테이블 (피드백 학습)
CREATE TABLE IF NOT EXISTS reply_patterns (
    id SERIAL PRIMARY KEY,

    -- 입력 패턴
    email_type VARCHAR(50),
    sender_category VARCHAR(100),     -- 회사/개인/학교 등
    subject_keywords TEXT[],          -- 제목 키워드 배열
    body_keywords TEXT[],             -- 본문 키워드 배열

    -- 출력 패턴 (학습된 답변 템플릿)
    reply_template TEXT,              -- "안녕하세요. {sender_name}님..."
    preferred_tone VARCHAR(50),       -- formal/casual/brief
    common_phrases TEXT[],            -- 자주 쓰는 문구들

    -- 통계
    usage_count INTEGER DEFAULT 0,   -- 사용 횟수
    success_rate FLOAT DEFAULT 0.0,  -- 승인율
    avg_modification_rate FLOAT DEFAULT 0.0, -- 평균 수정 비율

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patterns_type ON reply_patterns(email_type);
CREATE INDEX IF NOT EXISTS idx_patterns_success ON reply_patterns(success_rate DESC);


-- 7. 사용자 피드백 테이블
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    suggestion_id INTEGER REFERENCES reply_suggestions(id),
    email_id INTEGER REFERENCES email(id),

    -- 피드백 내용
    original_draft TEXT,              -- AI 생성 원본
    modified_draft TEXT,              -- 사용자 수정본
    feedback_type VARCHAR(50),        -- accepted/modified/rejected

    -- 수정 분석 (자동 계산)
    modification_ratio FLOAT,         -- 수정 비율 (0.0 ~ 1.0)
    added_phrases TEXT[],             -- 추가된 문구
    removed_phrases TEXT[],           -- 삭제된 문구
    tone_changed BOOLEAN DEFAULT FALSE,

    -- 사용자 명시적 피드백
    user_rating INTEGER,              -- 1-5 별점
    user_comment TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_email ON user_feedback(email_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON user_feedback(feedback_type);


-- 8. 에이전트 실행 로그 (디버깅용)
CREATE TABLE IF NOT EXISTS agent_execution_logs (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES email(id),
    agent_name VARCHAR(100),          -- SupervisorAgent, ClassifierAgent 등
    node_name VARCHAR(100),           -- 그래프 내 노드 이름

    -- 실행 정보
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,

    -- 상태
    status VARCHAR(50),               -- success/failed/timeout
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- 입출력
    input_state JSONB,
    output_state JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_email ON agent_execution_logs(email_id);
CREATE INDEX IF NOT EXISTS idx_logs_agent ON agent_execution_logs(agent_name);
CREATE INDEX IF NOT EXISTS idx_logs_status ON agent_execution_logs(status);


-- 9. 알림/액션 큐 테이블
-- 중요한 이메일이나 에러 발생 시 알림 전송
CREATE TABLE IF NOT EXISTS notification_queue (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES email(id),

    notification_type VARCHAR(50),    -- urgent_email/error/approval_needed
    priority INTEGER DEFAULT 0,       -- 0-10 (10이 가장 높음)

    message TEXT,
    metadata JSONB,

    status VARCHAR(50) DEFAULT 'pending',  -- pending/sent/failed
    sent_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notif_status ON notification_queue(status);
CREATE INDEX IF NOT EXISTS idx_notif_priority ON notification_queue(priority DESC);


-- ===================================================
-- 트리거: updated_at 자동 갱신
-- ===================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_email_updated_at BEFORE UPDATE ON email
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_daily_summaries_updated_at BEFORE UPDATE ON daily_summaries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reply_patterns_updated_at BEFORE UPDATE ON reply_patterns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ===================================================
-- 초기 데이터: 답변 패턴 템플릿
-- ===================================================
INSERT INTO reply_patterns (email_type, sender_category, reply_template, preferred_tone, common_phrases)
VALUES
    ('채용', '회사', '안녕하세요.\n\n면접 일정 안내 감사드립니다.\n해당 일정에 참석 가능하며, 준비물도 빠짐없이 준비하겠습니다.\n\n감사합니다.',
     'formal',
     ARRAY['감사드립니다', '참석 가능합니다', '준비하겠습니다']),

    ('공지', '학교', '안녕하세요.\n\n공지 확인했습니다.\n\n감사합니다.',
     'formal',
     ARRAY['확인했습니다', '감사합니다']),

    ('개인', '개인', '안녕하세요!\n\n메일 잘 받았습니다.\n\n감사합니다~',
     'casual',
     ARRAY['잘 받았습니다', '감사합니다'])
ON CONFLICT DO NOTHING;
