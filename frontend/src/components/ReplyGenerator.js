import React, { useState, useEffect } from 'react';
import { generateReply, sendReply, learnFromFeedback } from '../services/api';
import '../styles/App.css';

const ReplyGenerator = ({ email, onClose, onReplySent }) => {
  const [loading, setLoading] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [selectedDraft, setSelectedDraft] = useState(null);
  const [editedReply, setEditedReply] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (email) {
      handleGenerateReplies();
    }
  }, [email]);

  const handleGenerateReplies = async () => {
    setLoading(true);
    setDrafts([]); // 초기화
    setSelectedDraft(null);
    setEditedReply('');

    try {
      const response = await generateReply(email.id);

      console.log('Generate reply response:', response);

      // 응답 검증
      if (!response || typeof response !== 'object') {
        throw new Error('Invalid response format');
      }

      if (!response.reply_drafts || typeof response.reply_drafts !== 'object') {
        throw new Error('No reply_drafts in response');
      }

      // Backend 응답 형식: { success, email_id, reply_drafts: { formal: {...}, casual: {...}, brief: {...} } }
      // Frontend 형식으로 변환: [{ tone: 'formal', content: '...' }, ...]
      const draftsArray = [];

      Object.entries(response.reply_drafts).forEach(([toneKey, draftData]) => {
        if (draftData && typeof draftData === 'object') {
          draftsArray.push({
            tone: toneKey, // 'formal', 'casual', 'brief'
            content: draftData.reply_text || draftData.content || '',
            toneName: draftData.tone || getToneLabel(toneKey)
          });
        }
      });

      console.log('Drafts array:', draftsArray);

      if (draftsArray.length === 0) {
        throw new Error('No valid drafts generated');
      }

      setDrafts(draftsArray);

      // 첫 번째 답변을 기본 선택
      setSelectedDraft(draftsArray[0]);
      setEditedReply(draftsArray[0].content);

    } catch (error) {
      console.error('Failed to generate replies:', error);
      const errorMsg = error.response?.data?.detail || error.message || '알 수 없는 오류';
      alert(`답변 생성에 실패했습니다.\n\n${errorMsg}`);

      // 오류 발생 시에도 상태 초기화
      setDrafts([]);
      setSelectedDraft(null);
      setEditedReply('');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDraft = (draft) => {
    setSelectedDraft(draft);
    setEditedReply(draft.content);
  };

  const handleSendReply = async () => {
    if (!editedReply.trim()) {
      alert('답변 내용을 입력해주세요.');
      return;
    }

    if (!window.confirm('이 답변을 발송하시겠습니까?')) {
      return;
    }

    try {
      setSending(true);

      // 1. 답변 발송
      await sendReply(
        email.id,
        editedReply,
        email.sender_address,
        email.sender_name
      );

      // 2. 피드백 학습 (백그라운드에서 실행)
      if (selectedDraft) {
        try {
          await learnFromFeedback(
            email.id,
            selectedDraft.content,  // 원본 AI 답변
            editedReply,            // 최종 발송 답변 (수정됨 또는 원본)
            selectedDraft.tone      // 선택한 톤
          );
          console.log('피드백 학습 완료');
        } catch (feedbackError) {
          // 피드백 학습 실패해도 답변 발송은 성공으로 처리
          console.warn('피드백 학습 실패 (무시됨):', feedbackError);
        }
      }

      alert('답변이 성공적으로 발송되었습니다!');
      onReplySent();
      onClose();
    } catch (error) {
      console.error('Failed to send reply:', error);
      alert('답변 발송에 실패했습니다.');
    } finally {
      setSending(false);
    }
  };

  const getToneLabel = (tone) => {
    const labels = {
      formal: '격식 있는',
      casual: '친근한',
      brief: '간결한',
    };
    return labels[tone] || tone;
  };

  if (!email) return null;

  return (
    <div className="reply-generator-container">
      <div className="reply-generator-header">
        <h2>답변 생성</h2>
        <button className="btn-close" onClick={onClose}>
          ✕
        </button>
      </div>

      <div className="reply-generator-content">
        {/* 원본 이메일 요약 */}
        <div className="original-email-summary">
          <h3>원본 이메일</h3>
          <p>
            <strong>발신자:</strong> {email.sender_name || email.sender_address}
          </p>
          <p>
            <strong>제목:</strong> {email.subject}
          </p>
        </div>

        {loading ? (
          <div className="loading">답변을 생성하는 중입니다...</div>
        ) : (
          <>
            {/* 답변 톤 선택 */}
            {drafts && drafts.length > 0 && (
              <div className="tone-selector">
                <h3>답변 스타일 선택</h3>
                <div className="tone-buttons">
                  {drafts.map((draft, idx) => (
                    <button
                      key={idx}
                      className={`tone-button ${
                        selectedDraft?.tone === draft.tone ? 'active' : ''
                      }`}
                      onClick={() => handleSelectDraft(draft)}
                    >
                      {getToneLabel(draft.tone)}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* 답변 편집 */}
            {selectedDraft && (
              <div className="reply-editor">
                <h3>답변 내용 (수정 가능)</h3>
                <textarea
                  className="reply-textarea"
                  value={editedReply}
                  onChange={(e) => setEditedReply(e.target.value)}
                  rows={15}
                  placeholder="답변 내용을 입력하세요..."
                />

                <div className="reply-actions">
                  <button
                    className="btn-secondary"
                    onClick={handleGenerateReplies}
                    disabled={loading}
                  >
                    다시 생성
                  </button>

                  <button
                    className="btn-primary"
                    onClick={handleSendReply}
                    disabled={sending || !editedReply.trim()}
                  >
                    {sending ? '발송 중...' : '답변 발송'}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default ReplyGenerator;
