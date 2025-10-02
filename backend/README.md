# Log Management Backend

Backend service that ingests logs from multiple sources, normalizes them into a centralized schema, evaluates alert rules, stores logs/alerts/rules/users in Redis + PostgreSQL for durable metadata, and sends alert notifications via a queued worker. Built with Express + TypeScript and intended to be run in containerized environments.

## Overview

This backend ingests logs from heterogeneous sources (HTTP, syslog, agents, third-party feeds), normalizes them into a central schema, persists fast-access data in Redis and durable metadata in PostgreSQL, evaluates alert rules in real-time, enqueues alert deliveries, and uses workers to send email notifications reliably. Logs are retained for 7 days and removed by a scheduled job.

### Key Features

- **Ingestion** Ingest logs from multiple sources (HTTP, Syslog, Network, Crowstrike , etc...) -**Normalization** Normalize logs into a central schema. -**Readis-cache** Store logs, alert rules, alerts, and users in Redis. -**QUEUE-Worker** Background workers for email notifications with retries. -**Cron-Job** Automatic log retention (7 days). -**Authorization** Support for Admin and User roles (RBAC). -**Data-Preparation** Analytics and pre-aggregation for fast queries.

## Architecture

![Architecutre for backend](./images/lms_backend.png)

- Ingestion: HTTP/Syslog endpoints

- Normalization: unify log formats into schema

- Storage: Redis for logs, alerts, users, rules

- Alert Engine: compares logs with active rules

- Queue & Worker: send alerts and OTP for account registeration via email with retries

- Cron-based retention: delete logs older than 7 days

- Admin and user roles (RBAC), dashboards and aggregated analytics

## Tech Stack

### Core

- **Runtime**: Node.js 18.x
- **Framework**: Express.js
- **Language**: TypeScript

### Database

- **Primary Database**: PostgreSQL 15
- **Cache**: Redis 7.0
- **ORM**: Prisma

### Authentication & Security

- JWT for authentication
- bcrypt for password hashing
- Helmet.js for security headers
- Rate limiting with express-rate-limit

### Testing

- Unit Tests: Jest

### DevOps & Tools

- Docker & Docker Compose

## Prerequisites

- Node.js >= 18.0.0 (or appropriate runtime)
- PostgreSQL >= 15.0
- Redis >= 7.0
- Docker & Docker Compose (optional)
- npm/yarn/pnpm

## Installation

## Manual Installation

```bash
# Clone the repository
git clone https://github.com/username/project-name.git
cd project-name

# Install dependencies
npm install
# Set up database

npx prisma migrate
# Seed database (optional)
npm run db:seed

# Start dev server
npm run server
```

# Environment Variables

```bash
NODE_ENV=development
PORT=desired_port

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp
DB_USER=postgres
DB_PASSWORD=password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Authentication
ACCESS_TOKEN_SECRET=your-access-secret
REFRESH_TOKEN_SECRET=your-refresh-secret

# External APIs
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-password
```

## 📂 Project Structure (Backend)

backend/
├── node_modules/ # Dependencies
├── prisma/ # Prisma schema & migrations
├── src/ # Source code
│ ├── **tests**/ # Unit & integration tests
│ │ └── user_login.test.ts
│ │
│ ├── actions/ # Action handlers (e.g., email, templates)
│ │ ├── emailAction.ts
│ │ └── templates/
│ │
│ ├── config/ # Configurations & clients
│ │ ├── errorcode.ts
│ │ ├── PrismaClient.ts
│ │ └── redisClient.ts
│ │
│ ├── controllers/ # Controllers (logic per domain)
│ │ ├── admin/
│ │ │ ├── alert.con.ts
│ │ │ ├── logs.con.ts
│ │ │ └── manage.con.ts
│ │ ├── auth/
│ │ │ ├── auth.con.ts
│ │ │ └── authChecks.ts
│ │ └── users/
│ │ └── users.con.ts
│ │
│ ├── generated/ # Auto-generated files (e.g., Prisma client)
│ │
│ ├── jobs/ # Background jobs & workers
│ │ ├── queues/
│ │ └── workers/
│ │
│ ├── middleware/ # Middleware (auth, validation, etc.)
│ │ ├── authorization.ts
│ │ └── isAuth.ts
│ │
│ ├── routes/ # API routes
│ │ ├── alert.route.ts
│ │ ├── auth.route.ts
│ │ ├── index.route.ts
│ │ ├── logs.route.ts
│ │ └── manage.route.ts
│ │
│ ├── services/ # Services (handle core logic & DB ops)
│ │ ├── alert.service.ts
│ │ ├── auth.service.ts
│ │ ├── logs.service.ts
│ │ └── users.service.ts
│ │
│ ├── types/ # TypeScript types/interfaces
│ │
│ ├── utils/ # Utility functions/helpers
│ │
│ ├── app.ts # Main Express app
│ ├── index.ts # App entry point
│ ├── testDb.ts # Test DB setup
│ └── testRedis.ts # Test Redis setup
│
├── .env # Environment variables
├── .env.example # Example environment configuration

📌 **Legend**

- **controllers/** → Handles incoming requests, calls services.
- **services/** → Contains reusable business logic, database queries.
- **routes/** → Defines API endpoints and routes.
- **middleware/** → Contains request middlewares (auth, validation).
- **jobs/** → Background tasks like email alerts, cron jobs.
- **config/** → Database clients, Redis, error handling configs.
- **actions/** → Specific business actions (like sending emails).
- **tests/** → Unit and integration test files.

## 🔑 API Endpoints

### 🛂 Authentication Endpoints

| Method | Endpoint                     | Description            |
| ------ | ---------------------------- | ---------------------- |
| POST   | `/api/auth/register`         | Register new user      |
| POST   | `/api/auth/login`            | Login user             |
| POST   | `/api/auth/verify-otp`       | Verify OTP             |
| POST   | `/api/auth/confirm-password` | Confirm password reset |
| POST   | `/api/auth/logout`           | Logout user            |
| GET    | `/api/auth/auth-check`       | Check authentication   |

---

### 📜 Log Management Endpoints

| Method | Endpoint                      | Description                             |
| ------ | ----------------------------- | --------------------------------------- |
| POST   | `/api/ingest`                 | Ingest new logs                         |
| GET    | `/api/get-logs`               | Get all logs                            |
| DELETE | `/api/delete-log/:logId`      | Delete log (**Admin**)                  |
| GET    | `/api/user-dashboard/:userId` | Get user dashboard data                 |
| GET    | `/api/dashboard`              | Get overall dashboard stats (**Admin**) |
| GET    | `/api/get-all-data`           | Get overall data count (**Admin**)      |

---

### 🚨 Alert Management Endpoints

| Method | Endpoint                | Description                    |
| ------ | ----------------------- | ------------------------------ |
| POST   | `/api/create-alertRule` | Create alert rule (**Admin**)  |
| GET    | `/api/get-rules`        | Get all alert rules(**Admin**) |
| DELETE | `/api/delete-rule/:id`  | Delete alert rule (**Admin**)  |

---

### 👤 User Management Endpoints (Admin Only)

| Method | Endpoint                   | Description     |
| ------ | -------------------------- | --------------- |
| POST   | `/api/create-user`         | Create new user |
| GET    | `/api/get-users`           | Get all users   |
| PUT    | `/api/update-user`         | Update user     |
| DELETE | `/api/delete-user/:userId` | Delete user     |

---

## Database CLI

```bash
# Create a new migration
npx prisma migrate dev --name add_new_feature

# Apply migrations to production
npx prisma migrate deploy

# Reset database (CAUTION: drops all data)
npx prisma migrate reset

# View migration status
npx prisma migrate status

# Generate Prisma Client after schema changes
npx prisma generate
```

## Available Scripts

| Command              | Description                      | Use Case                     |
| -------------------- | -------------------------------- | ---------------------------- |
| `npm start`          | Run compiled production build    | Production deployment        |
| `npm run build`      | Compile TypeScript to JavaScript | Before production deployment |
| `npm run server:dev` | Run dev server with hot-reload   | Local development            |
| `npm run work`       | Run email worker                 | Process email notifications  |
| `npm run cache`      | Run cache worker                 | Manage Redis cache           |
| `npm run server`     | Run all services in parallel     | Full local development       |
| `npm test`           | Run all tests                    | Testing                      |
