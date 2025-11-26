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

export default api;
