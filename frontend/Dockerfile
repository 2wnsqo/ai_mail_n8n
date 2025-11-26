FROM node:18-alpine

WORKDIR /app

# package.json 복사 및 의존성 설치
COPY package*.json ./
RUN npm install

# 소스 코드 복사
COPY . .

# 환경변수 설정
ENV REACT_APP_API_URL=http://localhost:8000

# 포트 노출
EXPOSE 3000

# 개발 서버 실행
CMD ["npm", "start"]
