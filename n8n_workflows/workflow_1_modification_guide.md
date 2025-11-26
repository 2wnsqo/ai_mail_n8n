# n8n 워크플로우 #1 수정 가이드: 메일 동기화 (Gemini 노드 제거)

## 현재 상태
워크플로우 #1 "메일 동기화"는 현재 다음 기능을 수행합니다:
1. 네이버 IMAP으로 오늘의 이메일 가져오기 ✅
2. Gemini AI로 이메일 요약하기 ❌ (제거 필요)

## 수정 목적
- **메일 동기화**와 **요약 생성**을 분리
- 메일 동기화는 순수하게 **이메일 가져오기 + DB 저장**만 수행
- 요약 생성은 별도 워크플로우 #3에서 처리

---

## 제거할 노드 목록

현재 워크플로우에서 **다음 노드들을 삭제**하세요:

### 1. Code (요약) 노드
- **역할**: 여러 이메일을 하나의 텍스트로 결합
- **위치**: Loop 이후, Gemini 노드 이전
- **삭제 이유**: 요약 기능은 워크플로우 #3으로 이동

### 2. Gemini 노드
- **역할**: 이메일 요약 생성
- **모델**: gemini-2.0-flash-exp
- **삭제 이유**: 요약 기능은 워크플로우 #3으로 이동

### 3. Edit Fields 노드
- **역할**: Gemini 응답을 정리하여 DB에 저장할 형식으로 변환
- **위치**: Gemini 노드 이후
- **삭제 이유**: daily_summaries 삽입 기능 제거

### 4. Insert (daily_summaries) 노드
- **역할**: daily_summaries 테이블에 요약 저장
- **삭제 이유**: 요약 기능은 워크플로우 #3으로 이동

---

## 최종 워크플로우 구조

수정 후 워크플로우 #1은 다음과 같이 단순화됩니다:

```
┌──────────────┐
│   Webhook    │ ← POST /webhook-test/mail
└──────┬───────┘
       │
       ▼
┌──────────────────────────┐
│ GetEmailsList_email      │
│ (IMAP Email)             │
│ - Host: imap.naver.com   │
│ - Port: 993              │
│ - Filter: SINCE (오늘)   │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ Loop Over Items          │
│ - 각 이메일 반복 처리    │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ Code (HTML 정리)         │
│ - HTML → Plain Text      │
│ - 불필요한 태그 제거     │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ Insert (email 테이블)    │
│ - PostgreSQL             │
│ - 중복 체크 (original_uid)│
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ Respond to Webhook       │
│ - 동기화 완료 응답       │
└──────────────────────────┘
```

---

## 수정 단계별 가이드

### Step 1: n8n UI 접속
```bash
http://localhost:5678
```

### Step 2: 워크플로우 #1 열기
- 왼쪽 메뉴에서 "Workflows" 클릭
- "메일 동기화" 워크플로우 선택

### Step 3: 노드 삭제
다음 순서로 노드를 클릭 → 삭제:
1. **Insert (daily_summaries)** 노드 클릭 → Delete 키
2. **Edit Fields** 노드 클릭 → Delete 키
3. **Gemini** 노드 클릭 → Delete 키
4. **Code (요약)** 노드 클릭 → Delete 키

### Step 4: 노드 연결 확인
삭제 후 연결이 끊어졌을 수 있으므로 다음을 확인:

**Loop Over Items** → **Code (HTML 정리)** → **Insert (email)** → **Respond to Webhook**

연결이 끊어진 경우:
1. Loop Over Items의 출력 점 클릭
2. Code (HTML 정리)의 입력 점으로 드래그하여 연결

### Step 5: Respond to Webhook 수정
**Respond to Webhook** 노드를 다음과 같이 수정:

기존 응답 데이터를 삭제하고 새로운 응답으로 교체:

```json
{
  "success": true,
  "message": "메일 동기화 완료",
  "new_emails": "{{ $('Loop Over Items').itemCount }}",
  "sync_date": "{{ $now.format('YYYY-MM-DD') }}"
}
```

**설정 방법**:
1. Respond to Webhook 노드 클릭
2. "Response Body" 섹션에서 기존 내용 삭제
3. 위 JSON 붙여넣기

### Step 6: 워크플로우 저장 및 활성화
1. 우측 상단 **Save** 버튼 클릭
2. 우측 상단 **Active** 토글을 ON으로 설정

---

## 수정 전후 비교

### 수정 전 (현재)
```
Webhook → IMAP → Loop → Code(HTML정리) → Insert(email)
                    ↓
                 Code(요약) → Gemini → Edit → Insert(daily_summaries)
```

### 수정 후 (목표)
```
Webhook → IMAP → Loop → Code(HTML정리) → Insert(email) → Response
```

**제거된 기능**: Gemini 요약, daily_summaries 저장
**새로운 위치**: 워크플로우 #3 "일일 요약 생성"

---

## 테스트 방법

### 1. 워크플로우 수동 실행
n8n UI에서:
1. 워크플로우 #1 선택
2. 우측 상단 "Execute Workflow" 버튼 클릭

### 2. Backend API로 테스트
```bash
curl -X POST http://localhost:8000/sync-emails
```

### 3. 예상 응답
```json
{
  "success": true,
  "message": "메일 동기화 완료",
  "new_emails": 3,
  "total_emails": 15,
  "sync_date": "2025-11-15"
}
```

### 4. PostgreSQL 확인
```bash
docker exec -it mail_postgres psql -U mail_user -d mail_db
```

```sql
-- 오늘 동기화된 이메일 확인
SELECT id, subject, sender_name, received_at
FROM email
WHERE DATE(received_at) = CURRENT_DATE
ORDER BY received_at DESC;

-- daily_summaries 테이블은 비어있어야 함 (아직 요약 생성 안 함)
SELECT * FROM daily_summaries WHERE summary_date = CURRENT_DATE;
```

---

## 문제 해결

### 문제 1: 노드 삭제 후 연결이 끊어짐
**해결**: Loop Over Items와 Code (HTML 정리)를 수동으로 연결

### 문제 2: Webhook 404 에러
**해결**:
1. 워크플로우가 Active 상태인지 확인
2. Webhook 경로가 `/webhook-test/mail`인지 확인

### 문제 3: IMAP 인증 실패
**해결**:
1. n8n Credentials에서 네이버 이메일 설정 확인
2. 네이버 계정에서 IMAP 사용 설정 확인

---

## 다음 단계

워크플로우 #1 수정 완료 후:

1. **워크플로우 #3 생성**: 일일 요약 생성
   - 설계서: `workflow_3_daily_summary.md` 참고
   - Webhook: `/webhook-test/summary`

2. **워크플로우 #4 생성**: 이메일 분석
   - 설계서: `workflow_4_email_analysis.md` 참고
   - Webhook: `/webhook-test/analyze`

3. **워크플로우 #5 생성**: 답변 생성
   - 설계서: `workflow_5_reply_generation.md` 참고
   - Webhook: `/webhook-test/generate-reply`

4. **시스템 테스트**:
   - Frontend에서 "메일 동기화" 버튼 클릭
   - Frontend에서 "일일 요약" 버튼 클릭
   - 개별 이메일 "분석하기" 클릭
   - 답변 생성 및 발송 테스트
