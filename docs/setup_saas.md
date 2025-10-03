# SaaS Deployment Guide

This document describes how to deploy the **Log Management System** in SaaS.
In this setup:

- **Backend API** is deployed on **Render**
- **Frontend UI** is deployed on **Vercel**
- **Database** is hosted on **Neon (PostgreSQL)**
- **Prisma** is used as ORM for schema migrations

---

## 1. Prerequisites

- GitHub repository containing:

  - `/backend/`
  - `/frontend/`
  - `prisma/schema.prisma`

- Accounts on:

  - [Render](https://render.com/) (for backend)
  - [Vercel](https://vercel.com/) (for frontend)
  - [Neon](https://neon.tech/) (for Postgres database)

---

## 2. Database Setup (Neon)

1. Create a **new project** in [Neon](https://console.neon.tech/).

2. Copy the **connection string** (Postgres URI), e.g.:

   ```
   postgres://user:password@ep-mydatabase.neon.tech:5432/logdb?sslmode=require
   ```

3. Update your `.env` file in `/backend/.env`:

   ```env
   DATABASE_URL="postgres://user:password@ep-mydatabase.neon.tech:5432/logdb?sslmode=require"
   ```

4. Run Prisma migrations locally:

   ```bash
   cd backend
   npx prisma migrate deploy
   ```

---

## 3. Backend Deployment (Render)

1. Go to [Render Dashboard](https://dashboard.render.com/).
2. Create a **New Web Service** → Connect your GitHub repo → Select `/backend`.
3. Configure:

   - **Environment**: Node.js
   - **Build Command**:

     ```bash
     npm install && npx prisma generate && npm run build
     ```

   - **Start Command**:

     ```bash
     npm run start
     ```

   - **Environment Variables** (copy from `.env`):

     ```
     DATABASE_URL=<your Neon Postgres URL>
     JWT_SECRET=<your_secret>
     ```

4. Deploy. After successful build, you’ll get a public URL, e.g.:

   ```
   https://log-backend.onrender.com
   ```

---

## 4. Frontend Deployment (Vercel)

1. Go to [Vercel Dashboard](https://vercel.com/).
2. Import your GitHub repo → Select `/frontend`.
3. Configure environment variables:

   ```
   NEXT_PUBLIC_API_URL=https://log-backend.onrender.com
   ```

4. Deploy. After successful build, you’ll get a public URL, e.g.:

   ```
   https://log-frontend.vercel.app
   ```

---

## 5. Connecting Frontend and Backend

- The **frontend** uses `VITE_API_URL` to call the backend APIs.
- Ensure CORS is enabled in backend (allow `https://log-frontend.vercel.app`).
- Test by visiting the frontend URL and logging in.

---

## 6. TLS/HTTPS

- Both Render and Vercel automatically provide free **HTTPS certificates**.
- Neon requires SSL mode for connections, which is already included in `DATABASE_URL`.

---

## 7. Multi-Tenant Support

- Tenants are separated via a `tenant` parameter in API requests.
- Example API call:

  ```bash
  curl -X POST https://log-backend.onrender.com/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-Tenant: demoA" \
  -d '{
    "source":"api",
    "event_type":"login_failed",
    "user":"alice",
    "ip":"203.0.113.7",
    "@timestamp":"2025-08-20T07:20:00Z"
  }'
  ```

---

## 8. Retention Policy

- Logs older than **7 days** are automatically deleted using a daily cron job (`cleanOldLogs` function in backend).
- Render cron job example:

- No separate script or background worker is needed; the function runs inside the backend process.

- Implementation uses node-cron to schedule the task once a week (e.g., every Monday at 05:00 AM UTC):

- Backend server must always be running (e.g., Render Web Service).

-Cleanup can be tested manually with

    ```bash
    "log:cleanup": "ts-node src/scripts/logCleanUp.ts",
    npm run log:cleanup
    ```

---

## 9. Demo URL for Reviewers

- **Frontend (UI)** → [https://log-frontend.vercel.app](https://log-frontend.vercel.app)
- **Backend (API)** → [https://log-backend.onrender.com](https://log-backend.onrender.com)
- **Database** → Hosted on Neon (not public)

---

## 10. Quick Test

1. Go to the frontend URL.

2. Log in as **Admin** user.

3. Send a test log event:

   ```bash
   curl -X POST https://log-backend.onrender.com/api/ingest \
   -H "Content-Type: application/json" \
   -d '{"tenant":"demoA","source":"api","event_type":"test_event","user":"alice","ip":"1.2.3.4","@timestamp":"2025-10-03T10:00:00Z"}'
   ```

4. Refresh dashboard → You should see the new log.
