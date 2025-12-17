import React, { useState, useEffect } from 'react';
import { getReplyHistory } from '../services/api';
import '../styles/App.css';

const ReplyHistory = ({ onClose, onSelectEmail }) => {
  const [replies, setReplies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [selectedReply, setSelectedReply] = useState(null);
  const limit = 10;

  useEffect(() => {
    fetchReplies();
  }, [page]);

  const fetchReplies = async () => {
    try {
      setLoading(true);
      const data = await getReplyHistory(limit, page * limit);
      setReplies(data.replies);
      setTotal(data.total);
    } catch (error) {
      console.error('Failed to fetch reply history:', error);
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(total / limit);

  const getTypeBadgeColor = (type) => {
    const colors = {
      '채용': 'blue',
      '마케팅': 'purple',
      '공지': 'orange',
      '개인': 'green',
      '기타': 'gray',
    };
    return colors[type] || 'gray';
  };

  return (
    <div className="reply-history-panel">
      <div className="reply-history-header">
        <h2>📬 답변 히스토리</h2>
        <button className="btn-close" onClick={onClose}>✕</button>
      </div>

      <div className="reply-history-content">
        {loading ? (
          <div className="loading">답변 히스토리를 불러오는 중...</div>
        ) : replies.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">📭</span>
            <p>아직 발송된 답변이 없습니다.</p>
          </div>
        ) : (
          <>
            <div className="reply-list">
              {replies.map((reply) => (
                <div
                  key={reply.id}
                  className={`reply-item ${selectedReply?.id === reply.id ? 'selected' : ''}`}
                  onClick={() => setSelectedReply(reply)}
                >
                  <div className="reply-item-header">
                    <div className="reply-recipient">
                      <strong>{reply.to_name || reply.to_email}</strong>
                      {reply.was_modified && (
                        <span className="modified-badge">✏️ 수정됨</span>
                      )}
                    </div>
                    <div className="reply-date">
                      {new Date(reply.sent_at).toLocaleDateString('ko-KR', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </div>
                  </div>
                  <div className="reply-subject">{reply.subject}</div>
                  <div className="reply-preview">{reply.reply_body}</div>
                  <div className="reply-item-footer">
                    {reply.email_type && (
                      <span className={`badge badge-${getTypeBadgeColor(reply.email_type)}`}>
                        {reply.email_type}
                      </span>
                    )}
                    {reply.importance_score && (
                      <span className="importance-indicator">
                        중요도: {reply.importance_score}/10
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  ← 이전
                </button>
                <span className="page-info">
                  {page + 1} / {totalPages} 페이지
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                >
                  다음 →
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {selectedReply && (
        <div className="reply-detail-modal">
          <div className="reply-detail-content">
            <div className="reply-detail-header">
              <h3>답변 상세</h3>
              <button className="btn-close" onClick={() => setSelectedReply(null)}>
                ✕
              </button>
            </div>
            <div className="reply-detail-body">
              <div className="detail-row">
                <span className="label">받는 사람:</span>
                <span className="value">
                  {selectedReply.to_name} &lt;{selectedReply.to_email}&gt;
                </span>
              </div>
              <div className="detail-row">
                <span className="label">제목:</span>
                <span className="value">{selectedReply.subject}</span>
              </div>
              <div className="detail-row">
                <span className="label">발송 시간:</span>
                <span className="value">
                  {new Date(selectedReply.sent_at).toLocaleString('ko-KR')}
                </span>
              </div>
              <div className="detail-row">
                <span className="label">상태:</span>
                <span className="value">
                  {selectedReply.was_modified ? '✏️ 수정 후 발송' : '✅ 원본 그대로 발송'}
                </span>
              </div>
              <div className="detail-section">
                <h4>답변 내용</h4>
                <div className="reply-full-text">{selectedReply.reply_body}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReplyHistory;
