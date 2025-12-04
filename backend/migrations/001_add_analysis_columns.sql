-- ===================================================
-- Migration 001: emails 테이블에 분석 컬럼 추가
-- ===================================================
-- 실행 전 백업 권장: pg_dump -h localhost -U user -d dbname > backup.sql

-- 1. 분석 관련 컬럼 추가
ALTER TABLE emails
ADD COLUMN IF NOT EXISTS email_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS importance_score INTEGER,
ADD COLUMN IF NOT EXISTS needs_reply BOOLEAN,
ADD COLUMN IF NOT EXISTS sentiment VARCHAR(50),
ADD COLUMN IF NOT EXISTS ai_analysis JSONB,
ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_error TEXT,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 2. 인덱스 추가 (검색 성능 향상)
CREATE INDEX IF NOT EXISTS idx_emails_type ON emails(email_type);
CREATE INDEX IF NOT EXISTS idx_emails_importance ON emails(importance_score);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(processing_status);
CREATE INDEX IF NOT EXISTS idx_emails_received ON emails(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_emails_needs_reply ON emails(needs_reply);

-- 3. 성능 평가 결과 테이블
CREATE TABLE IF NOT EXISTS performance_evaluations (
    id SERIAL PRIMARY KEY,
    evaluation_type VARCHAR(50) NOT NULL,  -- 'analysis', 'reply', 'summary'
    email_id INTEGER REFERENCES emails(id),
    version_tag VARCHAR(100),  -- 'baseline', 'v1_improved', 등

    -- 점수들
    total_score FLOAT,
    breakdown_scores JSONB,  -- 항목별 점수

    -- 메타데이터
    prompt_version VARCHAR(100),
    evaluation_notes TEXT,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_eval_type ON performance_evaluations(evaluation_type);
CREATE INDEX IF NOT EXISTS idx_eval_version ON performance_evaluations(version_tag);

-- 4. Ground Truth 테이블 (정답 데이터)
CREATE TABLE IF NOT EXISTS ground_truth (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES emails(id) UNIQUE,

    -- 분석 정답
    email_type VARCHAR(50),
    importance_score INTEGER,
    needs_reply BOOLEAN,
    sentiment VARCHAR(50),
    key_points TEXT[],

    -- 메타데이터
    annotated_by VARCHAR(100),  -- 평가자
    annotated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_gt_email ON ground_truth(email_id);

-- 5. updated_at 트리거 (emails 테이블용)
CREATE OR REPLACE FUNCTION update_emails_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_emails_updated_at ON emails;
CREATE TRIGGER trigger_emails_updated_at
    BEFORE UPDATE ON emails
    FOR EACH ROW
    EXECUTE FUNCTION update_emails_updated_at();

-- 6. 기존 데이터 처리 상태 초기화
UPDATE emails
SET processing_status = 'pending'
WHERE processing_status IS NULL;

-- 마이그레이션 완료 확인
SELECT
    'Migration 001 완료' as status,
    COUNT(*) as total_emails,
    COUNT(CASE WHEN email_type IS NOT NULL THEN 1 END) as analyzed_emails
FROM emails;
