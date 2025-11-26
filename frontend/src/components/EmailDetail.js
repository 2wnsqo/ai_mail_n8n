import React from 'react';
import '../styles/App.css';

const EmailDetail = ({ email, onClose, onGenerateReply }) => {
  if (!email) return null;

  const getImportanceColor = (score) => {
    if (score >= 8) return '#ff4444';
    if (score >= 5) return '#ff9944';
    return '#44ff44';
  };

  return (
    <div className="email-detail-container">
      <div className="email-detail-header">
        <h2>이메일 상세</h2>
        <button className="btn-close" onClick={onClose}>
          ✕
        </button>
      </div>

      <div className="email-detail-content">
        {/* 기본 정보 */}
        <div className="email-info-section">
          <div className="email-info-row">
            <span className="label">발신자:</span>
            <span className="value">
              {email.sender_name || '이름 없음'} ({email.sender_address})
            </span>
          </div>

          <div className="email-info-row">
            <span className="label">제목:</span>
            <span className="value">{email.subject}</span>
          </div>

          <div className="email-info-row">
            <span className="label">수신 시간:</span>
            <span className="value">
              {new Date(email.received_at).toLocaleString('ko-KR')}
            </span>
          </div>

          {email.is_replied_to && (
            <div className="email-info-row">
              <span className="label">상태:</span>
              <span className="value replied-status">답변 완료</span>
            </div>
          )}
        </div>

        {/* AI 분석 결과 */}
        {email.email_type && (
          <div className="email-analysis-section">
            <h3>AI 분석 결과</h3>

            <div className="analysis-grid">
              <div className="analysis-item">
                <span className="analysis-label">유형:</span>
                <span className="analysis-value badge">{email.email_type}</span>
              </div>

              <div className="analysis-item">
                <span className="analysis-label">중요도:</span>
                <div className="importance-bar">
                  <div
                    className="importance-fill"
                    style={{
                      width: `${email.importance_score * 10}%`,
                      backgroundColor: getImportanceColor(email.importance_score),
                    }}
                  />
                  <span className="importance-score">{email.importance_score}/10</span>
                </div>
              </div>

              <div className="analysis-item">
                <span className="analysis-label">답변 필요:</span>
                <span className={`analysis-value ${email.needs_reply ? 'needs-reply' : ''}`}>
                  {email.needs_reply ? '예' : '아니오'}
                </span>
              </div>

              {email.sentiment && (
                <div className="analysis-item">
                  <span className="analysis-label">감정:</span>
                  <span className="analysis-value">
                    {email.sentiment === 'positive' && '긍정적'}
                    {email.sentiment === 'neutral' && '중립적'}
                    {email.sentiment === 'negative' && '부정적'}
                  </span>
                </div>
              )}
            </div>

            {email.ai_analysis?.key_points && (
              <div className="key-points">
                <h4>핵심 내용:</h4>
                <ul>
                  {email.ai_analysis.key_points.map((point, idx) => (
                    <li key={idx}>{point}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* 본문 */}
        <div className="email-body-section">
          <h3>본문</h3>
          <div className="email-body">
            {email.body_text}
          </div>
        </div>

        {/* 답변 생성 버튼 */}
        {email.email_type && !email.is_replied_to && (
          <div className="email-actions">
            <button
              className="btn-primary btn-generate-reply"
              onClick={() => onGenerateReply(email)}
            >
              답변 생성하기
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default EmailDetail;
