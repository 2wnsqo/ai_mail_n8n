import React, { useState } from 'react';
import EmailList from './EmailList';
import EmailDetail from './EmailDetail';
import ReplyGenerator from './ReplyGenerator';
import { syncEmails, generateDailySummary, getTodaySummary } from '../services/api';
import '../styles/App.css';

const Dashboard = () => {
  const [selectedEmail, setSelectedEmail] = useState(null);
  const [showReplyGenerator, setShowReplyGenerator] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  const [summarizing, setSummarizing] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [summaryData, setSummaryData] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  const handleSelectEmail = (email) => {
    setSelectedEmail(email);
    setShowReplyGenerator(false);
  };

  const handleGenerateReply = (email) => {
    setSelectedEmail(email);
    setShowReplyGenerator(true);
  };

  const handleCloseDetail = () => {
    setSelectedEmail(null);
    setShowReplyGenerator(false);
  };

  const handleCloseReplyGenerator = () => {
    setShowReplyGenerator(false);
  };

  const handleReplySent = () => {
    // 이메일 목록 새로고침
    setRefreshKey((prev) => prev + 1);
    setSelectedEmail(null);
    setShowReplyGenerator(false);
  };

  const handleSyncEmails = async () => {
    setSyncing(true);
    setSyncMessage('');

    try {
      const result = await syncEmails();

      if (result.success) {
        setSyncMessage(
          `✅ ${result.new_emails}개의 새 이메일이 동기화되었습니다. (전체: ${result.total_emails}개)`
        );
        // 이메일 목록 새로고침
        setRefreshKey((prev) => prev + 1);

        // 3초 후 메시지 제거
        setTimeout(() => setSyncMessage(''), 3000);
      }
    } catch (error) {
      setSyncMessage(`❌ 동기화 실패: ${error.response?.data?.detail || error.message}`);
      setTimeout(() => setSyncMessage(''), 5000);
    } finally {
      setSyncing(false);
    }
  };

  const handleGenerateSummary = async () => {
    setSummarizing(true);
    setSyncMessage('');

    try {
      const result = await generateDailySummary();

      if (result.success) {
        setSyncMessage(
          `✅ ${result.email_count}개 이메일의 일일 요약이 생성되었습니다.`
        );
        setTimeout(() => setSyncMessage(''), 3000);
      } else {
        setSyncMessage(result.message || '요약 생성 실패');
        setTimeout(() => setSyncMessage(''), 5000);
      }
    } catch (error) {
      setSyncMessage(`❌ 요약 생성 실패: ${error.response?.data?.detail || error.message}`);
      setTimeout(() => setSyncMessage(''), 5000);
    } finally {
      setSummarizing(false);
    }
  };

  const handleViewSummary = async () => {
    try {
      setLoadingSummary(true);
      setShowSummary(true);
      const data = await getTodaySummary();
      setSummaryData(data);
    } catch (error) {
      console.error('Failed to load summary:', error);
      alert('요약을 불러오는데 실패했습니다.');
      setShowSummary(false);
    } finally {
      setLoadingSummary(false);
    }
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-content">
          <div className="header-title">
            <h1>AI 메일 비서</h1>
            <p>LangGraph + Gemini 기반 이메일 자동화 시스템</p>
          </div>
          <div className="header-actions">
            <button
              className={`sync-button ${syncing ? 'syncing' : ''}`}
              onClick={handleSyncEmails}
              disabled={syncing || summarizing}
            >
              {syncing ? '동기화 중...' : '📧 메일 동기화'}
            </button>
            <button
              className={`sync-button summary-button ${summarizing ? 'syncing' : ''}`}
              onClick={handleGenerateSummary}
              disabled={syncing || summarizing}
            >
              {summarizing ? '요약 생성 중...' : '📝 일일 요약 생성'}
            </button>
            <button
              className="sync-button view-summary-button"
              onClick={handleViewSummary}
              disabled={syncing || summarizing}
            >
              📊 요약 보기
            </button>
            {syncMessage && (
              <div className="sync-message">{syncMessage}</div>
            )}
          </div>
        </div>
      </header>

      <div className="dashboard-content">
        <div className="dashboard-layout">
          {/* 왼쪽: 이메일 목록 */}
          <div className="dashboard-left">
            <EmailList key={refreshKey} onSelectEmail={handleSelectEmail} />
          </div>

          {/* 오른쪽: 이메일 상세 또는 답변 생성 */}
          <div className="dashboard-right">
            {showReplyGenerator ? (
              <ReplyGenerator
                email={selectedEmail}
                onClose={handleCloseReplyGenerator}
                onReplySent={handleReplySent}
              />
            ) : selectedEmail ? (
              <EmailDetail
                email={selectedEmail}
                onClose={handleCloseDetail}
                onGenerateReply={handleGenerateReply}
              />
            ) : (
              <div className="empty-detail">
                <p>이메일을 선택하세요</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 요약 모달 */}
      {showSummary && (
        <div className="modal-overlay" onClick={() => setShowSummary(false)}>
          <div className="modal-content summary-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📊 오늘의 이메일 요약</h2>
              <button className="btn-close" onClick={() => setShowSummary(false)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              {loadingSummary ? (
                <div className="loading">요약을 불러오는 중...</div>
              ) : summaryData ? (
                <div className="summary-content">
                  <div className="summary-stats">
                    <div className="stat-item">
                      <span className="stat-label">총 이메일:</span>
                      <span className="stat-value">{summaryData.total_count || 0}개</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-label">답변 필요:</span>
                      <span className="stat-value">{summaryData.needs_reply_count || 0}개</span>
                    </div>
                  </div>

                  {summaryData.summary && (
                    <div className="summary-text">
                      <h3>요약</h3>
                      <p>{summaryData.summary}</p>
                    </div>
                  )}

                  {summaryData.key_points && summaryData.key_points.length > 0 && (
                    <div className="summary-points">
                      <h3>주요 내용</h3>
                      <ul>
                        {summaryData.key_points.map((point, idx) => (
                          <li key={idx}>{point}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {summaryData.type_distribution && (
                    <div className="summary-distribution">
                      <h3>유형별 분포</h3>
                      <div className="type-bars">
                        {Object.entries(summaryData.type_distribution).map(([type, count]) => (
                          <div key={type} className="type-bar-item">
                            <span className="type-name">{type}</span>
                            <div className="type-bar">
                              <div
                                className="type-bar-fill"
                                style={{ width: `${(count / summaryData.total_count) * 100}%` }}
                              />
                              <span className="type-count">{count}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="empty-state">요약 데이터가 없습니다.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
