import React, { useState, useEffect } from 'react';
import { getStatsOverview, getFeedbackStats } from '../services/api';
import '../styles/App.css';

const StatsPanel = ({ onClose }) => {
  const [stats, setStats] = useState(null);
  const [feedbackStats, setFeedbackStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const [overviewData, feedbackData] = await Promise.all([
        getStatsOverview(),
        getFeedbackStats(),
      ]);
      setStats(overviewData);
      setFeedbackStats(feedbackData);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const getTypeColor = (type) => {
    const colors = {
      '채용': '#3b82f6',
      '마케팅': '#8b5cf6',
      '공지': '#f59e0b',
      '개인': '#10b981',
      '기타': '#6b7280',
    };
    return colors[type] || '#6b7280';
  };

  const getImportanceColor = (level) => {
    const colors = {
      low: '#10b981',
      medium: '#f59e0b',
      high: '#ef4444',
      urgent: '#dc2626',
    };
    return colors[level] || '#6b7280';
  };

  if (loading) {
    return (
      <div className="stats-panel">
        <div className="stats-header">
          <h2>📊 통계 대시보드</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>
        <div className="loading">통계를 불러오는 중...</div>
      </div>
    );
  }

  return (
    <div className="stats-panel">
      <div className="stats-header">
        <h2>📊 통계 대시보드</h2>
        <button className="btn-close" onClick={onClose}>✕</button>
      </div>

      <div className="stats-tabs">
        <button
          className={activeTab === 'overview' ? 'active' : ''}
          onClick={() => setActiveTab('overview')}
        >
          개요
        </button>
        <button
          className={activeTab === 'distribution' ? 'active' : ''}
          onClick={() => setActiveTab('distribution')}
        >
          분포
        </button>
        <button
          className={activeTab === 'feedback' ? 'active' : ''}
          onClick={() => setActiveTab('feedback')}
        >
          학습 현황
        </button>
      </div>

      <div className="stats-content">
        {activeTab === 'overview' && stats && (
          <div className="stats-overview">
            <div className="stats-cards">
              <div className="stat-card">
                <div className="stat-icon">📧</div>
                <div className="stat-info">
                  <span className="stat-value">{stats.email_stats.total}</span>
                  <span className="stat-label">전체 이메일</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">🔍</div>
                <div className="stat-info">
                  <span className="stat-value">{stats.email_stats.analyzed}</span>
                  <span className="stat-label">분석 완료</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">✅</div>
                <div className="stat-info">
                  <span className="stat-value">{stats.email_stats.replied}</span>
                  <span className="stat-label">답변 완료</span>
                </div>
              </div>
              <div className="stat-card highlight">
                <div className="stat-icon">⏳</div>
                <div className="stat-info">
                  <span className="stat-value">{stats.email_stats.pending_reply}</span>
                  <span className="stat-label">답변 대기</span>
                </div>
              </div>
            </div>

            <div className="daily-chart">
              <h3>최근 7일 이메일 수신</h3>
              <div className="chart-bars">
                {stats.daily_emails.map((day) => {
                  const maxCount = Math.max(...stats.daily_emails.map((d) => d.count), 1);
                  const height = (day.count / maxCount) * 100;
                  return (
                    <div key={day.date} className="chart-bar-item">
                      <div
                        className="chart-bar"
                        style={{ height: `${height}%` }}
                        title={`${day.count}개`}
                      >
                        <span className="bar-value">{day.count}</span>
                      </div>
                      <span className="bar-label">
                        {new Date(day.date).toLocaleDateString('ko-KR', {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'distribution' && stats && (
          <div className="stats-distribution">
            <div className="distribution-section">
              <h3>📁 유형별 분포</h3>
              <div className="distribution-bars">
                {Object.entries(stats.type_distribution).map(([type, count]) => {
                  const total = Object.values(stats.type_distribution).reduce((a, b) => a + b, 0);
                  const percent = total > 0 ? ((count / total) * 100).toFixed(1) : 0;
                  return (
                    <div key={type} className="distribution-item">
                      <div className="distribution-label">
                        <span className="type-badge" style={{ backgroundColor: getTypeColor(type) }}>
                          {type}
                        </span>
                        <span className="count">{count}개 ({percent}%)</span>
                      </div>
                      <div className="distribution-bar-bg">
                        <div
                          className="distribution-bar-fill"
                          style={{
                            width: `${percent}%`,
                            backgroundColor: getTypeColor(type),
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="distribution-section">
              <h3>⚡ 중요도별 분포</h3>
              <div className="distribution-bars">
                {Object.entries(stats.importance_distribution).map(([level, count]) => {
                  const total = Object.values(stats.importance_distribution).reduce((a, b) => a + b, 0);
                  const percent = total > 0 ? ((count / total) * 100).toFixed(1) : 0;
                  const labels = { low: '낮음', medium: '보통', high: '높음', urgent: '긴급' };
                  return (
                    <div key={level} className="distribution-item">
                      <div className="distribution-label">
                        <span
                          className="importance-badge"
                          style={{ backgroundColor: getImportanceColor(level) }}
                        >
                          {labels[level] || level}
                        </span>
                        <span className="count">{count}개 ({percent}%)</span>
                      </div>
                      <div className="distribution-bar-bg">
                        <div
                          className="distribution-bar-fill"
                          style={{
                            width: `${percent}%`,
                            backgroundColor: getImportanceColor(level),
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="distribution-section">
              <h3>😊 감정별 분포</h3>
              <div className="sentiment-grid">
                {Object.entries(stats.sentiment_distribution).map(([sentiment, count]) => {
                  const icons = { positive: '😊', neutral: '😐', negative: '😞' };
                  const labels = { positive: '긍정', neutral: '중립', negative: '부정' };
                  return (
                    <div key={sentiment} className="sentiment-card">
                      <span className="sentiment-icon">{icons[sentiment] || '❓'}</span>
                      <span className="sentiment-label">{labels[sentiment] || sentiment}</span>
                      <span className="sentiment-count">{count}개</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'feedback' && (
          <div className="stats-feedback">
            {feedbackStats && feedbackStats.total_feedback > 0 ? (
              <>
                <div className="feedback-summary">
                  <h3>🧠 AI 학습 현황</h3>
                  <p>
                    사용자 피드백으로부터 <strong>{feedbackStats.total_feedback}개</strong>의
                    답변 패턴을 학습했습니다.
                  </p>
                </div>

                <div className="feedback-cards">
                  <div className="feedback-card">
                    <span className="feedback-value">{feedbackStats.accepted_count}</span>
                    <span className="feedback-label">✅ 그대로 승인</span>
                  </div>
                  <div className="feedback-card">
                    <span className="feedback-value">{feedbackStats.modified_count}</span>
                    <span className="feedback-label">✏️ 수정 후 발송</span>
                  </div>
                  <div className="feedback-card">
                    <span className="feedback-value">{feedbackStats.modification_rate}%</span>
                    <span className="feedback-label">📊 수정률</span>
                  </div>
                </div>

                {feedbackStats.by_tone && Object.keys(feedbackStats.by_tone).length > 0 && (
                  <div className="feedback-section">
                    <h4>톤별 학습 데이터</h4>
                    <div className="tone-stats">
                      {Object.entries(feedbackStats.by_tone).map(([tone, count]) => {
                        const labels = { formal: '격식체', casual: '친근체', brief: '간결체' };
                        return (
                          <div key={tone} className="tone-stat-item">
                            <span className="tone-label">{labels[tone] || tone}</span>
                            <span className="tone-count">{count}개</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="feedback-info">
                  <p>💡 학습된 데이터가 많을수록 AI가 사용자 스타일에 맞는 답변을 생성합니다.</p>
                </div>
              </>
            ) : (
              <div className="empty-feedback">
                <span className="empty-icon">🎓</span>
                <h3>아직 학습 데이터가 없습니다</h3>
                <p>
                  이메일에 답변을 발송하면 AI가 사용자의 답변 스타일을 학습합니다.
                  <br />
                  답변을 수정하거나 그대로 승인하면 해당 패턴이 저장됩니다.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default StatsPanel;
