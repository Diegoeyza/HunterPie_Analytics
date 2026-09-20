# API image: FastAPI + SQLite (DB lives on a mounted volume).
FROM python:3.12-slim AS api
WORKDIR /srv
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
ENV HUNTS_DB=/data/hunts.db PORT=8000
EXPOSE 8000
CMD ["python", "-m", "app.api"]

# Dashboard image: standalone Next.js build.
FROM node:20-slim AS dashboard
WORKDIR /srv/dashboard
COPY dashboard/package*.json ./
RUN npm ci
COPY dashboard ./
ENV NEXT_PUBLIC_API_URL=http://localhost:8000
RUN npm run build
EXPOSE 3000
CMD ["npm", "start", "--", "-p", "3000"]
