import React, { useState, useEffect } from 'react';
import { getEmails, getUnanalyzedEmails, analyzeEmail, analyzeAllUnanalyzed } from '../services/api';
import '../styles/App.css';

const EmailList = ({ onSelectEmail }) => {
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all, analyzed, unanalyzed
  const [analyzing, setAnalyzing] = useState(null);
  const [analyzingAll, setAnalyzingAll] = useState(false);

  useEffect(() => {
    fetchEmails();
  }, [filter]);

  const fetchEmails = async () => {
    try {
      setLoading(true);
      let data;

      if (filter === 'unanalyzed') {
        // 미분석 이메일만 조회
        data = await getUnanalyzedEmails(50);
      } else {
        // 전체 또는 분석됨 이메일 조회
        const analyzedOnly = filter === 'analyzed';
        data = await getEmails(50, 0, analyzedOnly);
      }

      setEmails(data);
    } catch (error) {
      console.error('Failed to fetch emails:', error);
      alert('이메일 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (emailId, e) => {
    e.stopPropagation();
    try {
      setAnalyzing(emailId);
      await analyzeEmail(emailId);
      alert('이메일 분석이 완료되었습니다!');
      fetchEmails(); // 목록 새로고침
    } catch (error) {
      console.error('Failed to analyze email:', error);
      const errorMsg = error.response?.data?.detail || error.message || '알 수 없는 오류';
      alert(`이메일 분석에 실패했습니다.\n\n${errorMsg}`);
    } finally {
      setAnalyzing(null);
    }
  };

  const handleAnalyzeAll = async () => {
    if (!window.confirm('모든 미분석 이메일을 분석하시겠습니까? 시간이 다소 걸릴 수 있습니다.')) {
      return;
    }

    try {
      setAnalyzingAll(true);
      const result = await analyzeAllUnanalyzed();
      alert(`${result.analyzed_count || 0}개의 이메일 분석이 완료되었습니다!`);
      fetchEmails(); // 목록 새로고침
    } catch (error) {
      console.error('Failed to analyze all emails:', error);
      alert('전체 분석에 실패했습니다.');
    } finally {
      setAnalyzingAll(false);
    }
  };

  const getImportanceBadge = (score) => {
    if (score >= 8) return <span className="badge badge-high">높음</span>;
    if (score >= 5) return <span className="badge badge-medium">보통</span>;
    return <span className="badge badge-low">낮음</span>;
  };

  const getTypeBadge = (type) => {
    const colors = {
      '채용': 'blue',
      '마케팅': 'purple',
      '공지': 'orange',
      '개인': 'green',
      '기타': 'gray'
    };
    return <span className={`badge badge-${colors[type] || 'gray'}`}>{type}</span>;
  };

  if (loading) {
    return <div className="loading">이메일 목록을 불러오는 중...</div>;
  }

  return (
    <div className="email-list-container">
      <div className="email-list-header">
        <h2>이메일 목록 ({emails.length})</h2>
        <div className="email-list-actions">
          <div className="filter-buttons">
            <button
              className={filter === 'all' ? 'active' : ''}
              onClick={() => setFilter('all')}
            >
              전체
            </button>
            <button
              className={filter === 'analyzed' ? 'active' : ''}
              onClick={() => setFilter('analyzed')}
            >
              분석됨
            </button>
            <button
              className={filter === 'unanalyzed' ? 'active' : ''}
              onClick={() => setFilter('unanalyzed')}
            >
              미분석
            </button>
          </div>
          <button
            className="btn-analyze-all"
            onClick={handleAnalyzeAll}
            disabled={analyzingAll || loading}
          >
            {analyzingAll ? '분석 중...' : '🔍 전체 분석'}
          </button>
        </div>
      </div>

      <div className="email-list">
        {emails.length === 0 ? (
          <div className="empty-state">이메일이 없습니다.</div>
        ) : (
          emails.map((email) => (
            <div
              key={email.id}
              className={`email-item ${email.is_replied_to ? 'replied' : ''}`}
              onClick={() => onSelectEmail(email)}
            >
              <div className="email-item-header">
                <div className="email-sender">
                  <strong>{email.sender_name || email.sender_address}</strong>
                  {email.is_replied_to && <span className="replied-badge">답변완료</span>}
                </div>
                <div className="email-date">
                  {new Date(email.received_at).toLocaleDateString('ko-KR')}
                </div>
              </div>

              <div className="email-subject">{email.subject}</div>

              <div className="email-item-footer">
                <div className="email-badges">
                  {email.email_type && getTypeBadge(email.email_type)}
                  {email.importance_score !== null && getImportanceBadge(email.importance_score)}
                  {email.needs_reply && <span className="badge badge-reply">답변필요</span>}
                </div>

                {!email.email_type && (
                  <button
                    className="btn-analyze"
                    onClick={(e) => handleAnalyze(email.id, e)}
                    disabled={analyzing === email.id}
                  >
                    {analyzing === email.id ? '분석중...' : '분석하기'}
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default EmailList;
