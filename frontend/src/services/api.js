import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 90000, // 90초로 증가 (n8n 워크플로우 응답 시간 고려)
  headers: {
    'Content-Type': 'application/json',
  },
});

// ========== 메일 동기화 API ==========

export const syncEmails = async () => {
  const response = await api.post('/sync-emails');
  return response.data;
};

// ========== 이메일 조회 API ==========

export const getEmails = async (limit = 50, offset = 0, analyzedOnly = false) => {
  const response = await api.get('/emails', {
    params: { limit, offset, analyzed_only: analyzedOnly },
  });
  return response.data;
};

export const getEmailById = async (emailId) => {
  const response = await api.get(`/emails/${emailId}`);
  return response.data;
};

export const getUnanalyzedEmails = async (limit = 10) => {
  const response = await api.get('/emails/unanalyzed', {
    params: { limit },
  });
  return response.data;
};

// ========== 이메일 분석 API ==========

export const analyzeEmail = async (emailId) => {
  const response = await api.post(`/analyze/${emailId}`);
  return response.data;
};

export const analyzeAllUnanalyzed = async () => {
  const response = await api.post('/analyze-all');
  return response.data;
};

// ========== 답변 생성 API ==========

export const generateReply = async (emailId, preferredTone = 'formal') => {
  const response = await api.post(`/generate-reply/${emailId}`, null, {
    params: { preferred_tone: preferredTone },
  });
  return response.data;
};

// ========== 답변 발송 API ==========

export const sendReply = async (emailId, replyText, toEmail, toName) => {
  const response = await api.post('/send-reply', {
    email_id: emailId,
    reply_text: replyText,
    to_email: toEmail,
    to_name: toName,
  });
  return response.data;
};

// ========== 일일 요약 API ==========

export const getTodaySummary = async () => {
  const response = await api.get('/summary/today');
  return response.data;
};

export const generateDailySummary = async () => {
  const response = await api.post('/summary/generate');
  return response.data;
};

// ========== 헬스 체크 ==========

export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

// ========== 통계 API ==========

export const getStatsOverview = async () => {
  const response = await api.get('/stats/overview');
  return response.data;
};

export const getReplyHistory = async (limit = 20, offset = 0) => {
  const response = await api.get('/stats/reply-history', {
    params: { limit, offset },
  });
  return response.data;
};

// ========== 피드백 API ==========

export const learnFromFeedback = async (emailId, originalDraft, finalReply, selectedTone = 'formal') => {
  const response = await api.post('/feedback/learn', null, {
    params: {
      email_id: emailId,
      original_draft: originalDraft,
      final_reply: finalReply,
      selected_tone: selectedTone,
    },
  });
  return response.data;
};

export const getFeedbackStats = async () => {
  const response = await api.get('/feedback/stats');
  return response.data;
};

// ========== 고급 필터링 API ==========

export const getEmailsFiltered = async (filters = {}) => {
  const params = {
    limit: filters.limit || 50,
    offset: filters.offset || 0,
    analyzed_only: filters.analyzedOnly || false,
  };

  const response = await api.get('/emails', { params });

  // 클라이언트 사이드 필터링 (서버에서 지원 안 하는 필터)
  let emails = response.data;

  if (filters.emailType && filters.emailType !== 'all') {
    emails = emails.filter((e) => e.email_type === filters.emailType);
  }

  if (filters.importance) {
    const [min, max] = filters.importance;
    emails = emails.filter(
      (e) => e.importance_score >= min && e.importance_score <= max
    );
  }

  if (filters.needsReply !== undefined) {
    emails = emails.filter((e) => e.needs_reply === filters.needsReply);
  }

  if (filters.dateRange) {
    const { start, end } = filters.dateRange;
    emails = emails.filter((e) => {
      const date = new Date(e.received_at);
      return date >= start && date <= end;
    });
  }

  return emails;
};

export default api;
