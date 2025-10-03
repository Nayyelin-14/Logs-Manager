# Log Management System (LMS)

A high-performance, enterprise-grade **Log Management System** with real-time alerting, analytics, and role-based access control. Built with modern technologies for scalability, reliability, and exceptional user experience.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Node](https://img.shields.io/badge/node-%3E%3D18.0.0-brightgreen)
![React](https://img.shields.io/badge/react-19-blue)
![TypeScript](https://img.shields.io/badge/typescript-5.0-blue)

---

## 🎯 Overview

The LMS provides a comprehensive solution for ingesting, normalizing, storing, and analyzing logs from multiple sources. It features real-time alert evaluation, automated notifications, role-based access control, and powerful analytics dashboards.

### Key Capabilities

- **Multi-Source Log Ingestion**: HTTP, Syslog, Network feeds, CrowdStrike, and custom agents
- **Real-Time Alerting**: Rule-based evaluation with customizable thresholds
- **Advanced Analytics**: Interactive dashboards with filtering, search, and visualization
- **Role-Based Access Control**: Separate permissions for Admin and User roles
- **Automated Notifications**: Queue-based email delivery with retry mechanisms
- **Data Retention**: Automatic cleanup of logs older than 7 days
- **High Performance**: Redis caching with PostgreSQL persistence

---

### Architecture Diagram

## ![Architecutre Diagram](./architecture_diagram.png)

## 🔄 How Frontend and Backend Work Together

The LMS uses a **client-server architecture** where the React frontend and Express backend communicate seamlessly:

### Communication Flow

1. **User Interaction** → User performs an action (login, view logs, create alert)
2. **Frontend Request** → React Query makes HTTP request to backend API endpoint
3. **Authentication** → Backend validates JWT token from Authorization header
4. **Processing** → Backend processes request, queries database, applies business logic
5. **Response** → Backend returns JSON data to frontend
6. **UI Update** → React Query updates cache and React re-renders components

### Example: Viewing Logs

```
┌─────────────┐                                    ┌─────────────┐
│   Frontend  │                                    │   Backend   │
│   (React)   │                                    │  (Express)  │
└─────────────┘                                    └─────────────┘
      │                                                    │
      │  1. User clicks "View Logs"                       │
      │────────────────────────────────────────────────>  │
      │     GET /api/get-logs                             │
      │     Headers: Authorization: Bearer <JWT>          │
      │                                                    │
      │                          2. Validate JWT token    │
      │                          3. Check Redis cache     │
      │                          4. Query PostgreSQL      │
      │                          5. Apply filters/pagination
      │                                                    │
      │  <────────────────────────────────────────────────│
      │     Response: { logs: [...], total: 1250 }        │
      │                                                    │
      │  6. React Query caches data                       │
      │  7. UI updates with logs table                    │
      │                                                    │
```

### Key Integration Points

| Aspect                | Frontend                                    | Backend                                                   |
| --------------------- | ------------------------------------------- | --------------------------------------------------------- |
| **Authentication**    | Stores JWT tokens, includes in all requests | Validates tokens, manages sessions                        |
| **Data Fetching**     | React Query with automatic caching          | REST API endpoints with JSON responses                    |
| **State Management**  | Zustand for global state (user, filters)    | Redis + PostgreSQL for persistence                        |
| **Real-time Updates** | Polling/refetch with React Query            | Background workers + queue system                         |
| **Form Handling**     | React Hook Form + Zod validation            | Express validators + Zod schemas                          |
| **Error Handling**    | Toast notifications, error boundaries       | Standardized error responses with codes                   |
| **Security**          | HTTPS, token storage, input sanitization    | JWT verification, rate limiting, SQL injection protection |

### Data Flow Patterns

**Pattern 1: Simple CRUD Operations**

```
Frontend → API Call → Backend → Database → Response → UI Update
```

**Pattern 2: Complex Operations (e.g., Creating Alert Rule)**

```
Frontend → API Call → Backend → Validate → Store in DB → Response → UI Update
```

**Pattern 3: Real-time Alerts**

```
Log Ingestion → Check Alert Rule → Match Rules → Queue Email →
Worker Sends → Frontend Polls → Updates Dashboard
```

---

## 🔄 How the System Works: End-to-End Flow

### 1. Log Ingestion → Normalization → Alert Detection → Email Notification

#### Step 1: Log Ingestion

**Current Implementation:**

```
Frontend UI Form    ─────────>   POST /api/ingest (JSON)
```

Users can create logs through:

1. **Frontend Form** - Manual log entry through UI
2. **API Endpoint** - Programmatic submission via HTTP POST

**Example: Creating a log via Frontend Form**

```
Form submission → POST /api/ingest → Backend processes
```

```bash
curl -X POST http://localhost:3000/api/ingest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
  "tenant": "demoA",
  "source": "API",
  "eventType": "LoginFailed",
  "user": "alice",
  "ip": "203.0.113.7",
  "severity": 5,
  "action": "LOGIN",
  "timestamp": "2025-10-01T01:00:00Z"
}'
```

**Supported Log Sources** (All sent as JSON):

- Application logs (via API)
- Frontend manual entries
- Firewall logs (formatted as JSON)
- Network device logs (formatted as JSON)
- CrowdStrike alerts (formatted as JSON)
- AWS CloudTrail events (formatted as JSON)
- Microsoft 365 audit logs (formatted as JSON)
- Active Directory events (formatted as JSON)

**What happens:**

- User creates log via frontend form
- Backend receives JSON payload
- Validates authentication (JWT token)
- Validates JSON schema and required fields
- Rate limiting applied to prevent abuse

#### Step 2: Log Normalization

```javascript
// Raw log from a source
{
  tenant: "demoA",
  source: "API",
  eventType: "LoginFailed",
  user: "alice",
  ip: "203.0.113.7",
  severity: 5,
  action: "LOGIN",
  timestamp: "2025-10-01T01:00:00Z"
}
// After normalization -Example Unified schema
```

## ![alt text](schema.png)

**What happens:**

- Parser identifies log source type
- Extracts key fields (timestamp, level, message, source)
- Converts to standardized schema
- Enriches with metadata (IP, user info, geo-location)
- Validates normalized data

#### Step 3: Storage

```
Normalized Log
     │
     ├─────────> Redis Cache (Fast access, 7-day TTL)
     │           • Key: log:{id}
     │           • Indexed by: timestamp, severity level, source
     │
     └─────────> PostgreSQL (Durable metadata storage)
                 • Stores log metadata

```

**What happens:**

- Log stored in Redis for fast retrieval
- Metadata stored in PostgreSQL for durability
- Indexed for efficient querying
- Automatic expiration set (7 days)

#### Step 4: Alert Rule Evaluation

```
Normalized Log
     │
     ▼
┌─────────────────────────────────┐
│   Alert Engine (Real-time)      │
│                                  │
│  1. Fetch active alert rules    │
│     from Redis cache             │
│                                  │
│  2. Check each rule:             │
│     • Log level matches?         │
│     • Tenant matches?            │
│     • Keywords present?          │
│     • Threshold exceeded?        │
│                                  │
│  3. Rule matched? ──> Create Alert
│                                  │
└─────────────────────────────────┘
```

**Example Alert Rule:**

```javascript
{
  name: "Failed Login Alert",
  tenant: "demoA",
  description: "Trigger alert if a user fails login with severity >= 3",
  conditions: [
    {
      type: "event_type",
      value: "LoginFailed"
    }
  ]
}
```

**What happens:**

- System fetches all active alert rules
- Compares log against each rule's conditions
- If match found, creates alert object
- Stores alert in Redis + PostgreSQL
- Prepares for notification

#### Step 5: Queue Alert for Email

```
Alert Created
     │
     ▼
┌─────────────────────────────────┐
│   Bull/BullMQ Queue System      │
│                                  │
│  Job: {                          │
│    type: "SEND_ALERT_EMAIL",     │
│    data: {                       │
│      alertId: "alert_456",       │
│      recipients: [...],          │
│      priority: "HIGH",           │
│      logDetails: {...}           │
│    },                            │
│    attempts: 3,                  │
│    backoff: exponential          │
│  }                               │
└─────────────────────────────────┘
```

**What happens:**

- Alert job added to email queue
- Job includes alert details and recipients
- Queue ensures reliable delivery (with retries)
- Jobs processed in order of priority

#### Step 6: Email Worker Processes Job

```
Email Worker (Background Process)
     │
     ├─ 1. Pick job from queue
     │
     ├─ 2. Fetch alert details from Redis
     │
     ├─ 3. Generate email content
     │     • Subject: "[CRITICAL] Log in Error Alert"
     │     • Body: HTML template with log details
     │
     ├─ 4. Send via Nodemailer + Gmail
     │     • Connect to Gmail SMTP
     │     • Authenticate with credentials
     │     • Send email
     │
     ├─ 5. Update job status
           • Success: Mark complete
           • Failure: Retry (up to 3 times)

```

**What happens:**

- Background worker picks job from queue
- Generates formatted email using template
- Sends email via Nodemailer + Gmail
- Handles failures with retry logic (exponential backoff)
- Create a new alert in database

#### Step 7: User Views Alert in Dashboard

```
Frontend (React)
     │
     ├─ React Query: GET /api/get-alerts
     │
     ▼
Backend responds with alerts
     │
     ├─ Check Redis cache first
     ├─ Fallback to PostgreSQL if needed
     ├─ Return JSON: { alerts: [...] }
     │
     ▼
Frontend displays in UI
     │
     ├─ Alert badge with count
     ├─ Alert list
     └─ Real-time updates (polling)
```

### Complete End-to-End Example

**Scenario:** User failed to log in within 2 minutes

```
Time: 10:00:00 - Log 1 ingested → Normalized → Stored → Rule checked (no match yet)
Time: 10:00:30 - Log 2 ingested → Normalized → Stored → Rule checked (no match yet)
Time: 10:01:00 - Log 3 ingested → Normalized → Stored → Rule checked (no match yet)
Time: 10:01:30 - Log 4 ingested → Normalized → Stored → Rule checked (no match yet)
Time: 10:02:00 - Log 5 ingested → Normalized → Stored → Rule checked ✅ MATCH!
│
└─> Alert created → Queued → Worker processes → Email sent
Time: 10:02:05 - Admin receives email: "5 failed login attempts in 2 minutes"
Time: 10:02:10 - Admin logs in → Views alert dashboard → Investigates logs
```

### Background Jobs & Scheduled Tasks

**Cron Job: Log Cleanup (Runs daily at 2 AM)**

```
┌─────────────────────────────────┐
│   Log Cleanup Script            │
│                                  │
│  1. Calculate cutoff date        │
│     (current date - 7 days)      │
│                                  │
│  2. Query Redis for old logs     │
│                                  │
│  3. Delete from Redis            │
│     • SCAN for log:* keys        │
│     • Check timestamp            │
│     • DEL old entries            │
│                                  │
│  4. Clean PostgreSQL metadata    │
│                                  │
│  5. Log cleanup stats            │
└─────────────────────────────────┘
```

**What happens:**

- Scheduled task runs daily
- Identifies logs older than 7 days
- Removes from Redis and PostgreSQL
- Frees up storage space
- Maintains system performance

---

## ✨ Features

### Frontend Features

- **Authentication**: Login, registration, OTP verification, password recovery
- **Role-Based UI**: Dynamic interface based on Admin/User permissions
- **Analytics Dashboard**: Interactive charts with Recharts
- **Advanced Filtering**: Multi-parameter search and filtering
- **Real-Time Updates**: Live alert notifications
- **Responsive Design**: Mobile-first approach with Tailwind CSS
- **Dark/Light Mode**: Theme switching with persistence
- **Optimized Performance**: Lazy loading, code splitting, caching

### Backend Features

- **Multi-Source Ingestion**: Support for various log sources
- **Log Normalization**: Unified schema for all log types
- **Alert Rule Engine**: Configurable rules with real-time evaluation
- **Queue System**: Reliable background job processing
- **Automated Cleanup**: Scheduled log retention (7 days)
- **RBAC**: Fine-grained access control
- **API Rate Limiting**: Protection against abuse
- **Comprehensive Testing**: Unit and integration tests

---

## 🛠️ Tech Stack

### Frontend

| Technology      | Purpose                 |
| --------------- | ----------------------- |
| React 19        | UI framework            |
| TypeScript      | Type safety             |
| Vite            | Build tool & dev server |
| Tailwind CSS    | Styling                 |
| Shadcn UI       | Component library       |
| React Query     | Data fetching & caching |
| Zustand         | State management        |
| React Hook Form | Form handling           |
| Zod             | Schema validation       |
| Recharts        | Data visualization      |
| Lucide React    | Icons                   |

### Backend

| Technology    | Purpose               |
| ------------- | --------------------- |
| Node.js 18+   | Runtime               |
| Express.js    | Web framework         |
| TypeScript    | Type safety           |
| PostgreSQL 15 | Primary database      |
| Redis 7.0     | Cache & session store |
| Prisma        | ORM                   |
| JWT           | Authentication        |
| Bull/BullMQ   | Queue system          |
| Nodemailer    | Email delivery        |
| Jest          | Testing framework     |

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js** >= 18.0.0
- **PostgreSQL** >= 15.0
- **Redis** >= 7.0
- **npm** or **yarn** or **pnpm**
- **Git**

---

## 🚀 Getting Started

### Clone the Repository

```bash
git clone https://github.com/yourusername/lms-project.git
cd lms-project
```

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
npx prisma migrate dev

# Seed the database
npm run seed

# Start development server
npm run server:dev
```

### Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your backend API URL

# Start development server
npm run dev
```

## ⚙️ Environment Configuration

### Backend (.env)

```env
NODE_ENV=development
PORT=3000

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/lms_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=lms_db
DB_USER=postgres
DB_PASSWORD=password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Authentication
ACCESS_TOKEN_SECRET=your-super-secret-access-token
REFRESH_TOKEN_SECRET=your-super-secret-refresh-token
JWT_EXPIRES_IN=15m
REFRESH_TOKEN_EXPIRES_IN=7d

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@lms.com

# Application
LOG_RETENTION_DAYS=7
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100
```

### Frontend (.env)

```env
VITE_API_URL=http://localhost:3000/api
VITE_APP_NAME=Log Management System
VITE_APP_VERSION=1.0.0
```

---

## 📁 Project Structure

```
lms-project/
├── backend/                    # Backend application
│   ├── prisma/                # Database schema & migrations
│   ├── src/
│   │   ├── actions/          # Email actions & templates
│   │   ├── config/           # Configuration files
│   │   ├── controllers/      # Request handlers
│   │   ├── jobs/             # Background jobs & workers
│   │   ├── middleware/       # Express middleware
│   │   ├── routes/           # API routes
│   │   ├── scripts/          # Utility scripts
│   │   ├── services/         # Business logic
│   │   ├── tests/            # Test files
│   │   ├── types/            # TypeScript types
│   │   ├── utils/            # Helper functions
│   │   ├── app.ts            # Express app setup
│   │   └── index.ts          # Entry point
│   ├── .env.example          # Example environment file
│   └── package.json
│
├── frontend/                   # Frontend application
│   ├── public/               # Static assets
│   ├── src/
│   │   ├── api/              # API client functions
│   │   ├── AppComponents/    # Layout components
│   │   ├── assets/           # Images, fonts, styles
│   │   ├── components/       # Shadcn UI components
│   │   ├── data/             # Mock/sample data
│   │   ├── hooks/            # Custom React hooks
│   │   ├── lib/              # Utility libraries
│   │   ├── pages/            # Page components
│   │   ├── router/           # Route configurations
│   │   ├── Schemas/          # Zod validation schemas
│   │   ├── store/            # Zustand stores
│   │   ├── types/            # TypeScript types
│   │   ├── index.css         # Global styles
│   │   ├── main.tsx          # Entry point
│   │   └── routes.tsx        # Route definitions
│   ├── .env.example          # Example environment file
│   └── package.json
│
├── .gitignore
└── README.md
```

---

## 🔌 API Documentation

### Authentication Endpoints

| Method | Endpoint                     | Description       | Access        |
| ------ | ---------------------------- | ----------------- | ------------- |
| POST   | `/api/auth/register`         | Register new user | Public        |
| POST   | `/api/auth/login`            | User login        | Public        |
| POST   | `/api/auth/verify-otp`       | Verify OTP        | Public        |
| POST   | `/api/auth/confirm-password` | Reset password    | Public        |
| POST   | `/api/auth/logout`           | User logout       | Authenticated |
| GET    | `/api/auth/auth-check`       | Check auth status | Authenticated |

### Log Management Endpoints

| Method | Endpoint                      | Description         | Access        |
| ------ | ----------------------------- | ------------------- | ------------- |
| POST   | `/api/ingest`                 | Ingest new logs     | Authenticated |
| GET    | `/api/get-logs`               | Retrieve all logs   | Authenticated |
| DELETE | `/api/delete-log/:logId`      | Delete specific log | Admin         |
| GET    | `/api/user-dashboard/:userId` | User dashboard data | User/Admin    |
| GET    | `/api/dashboard`              | System dashboard    | Admin         |
| GET    | `/api/get-all-data`           | Overall statistics  | Admin         |

### Alert Management Endpoints

| Method | Endpoint                | Description       | Access |
| ------ | ----------------------- | ----------------- | ------ |
| POST   | `/api/create-alertRule` | Create alert rule | Admin  |
| GET    | `/api/get-rules`        | Get all rules     | Admin  |
| DELETE | `/api/delete-rule/:id`  | Delete rule       | Admin  |

### User Management Endpoints

| Method | Endpoint                   | Description     | Access |
| ------ | -------------------------- | --------------- | ------ |
| POST   | `/api/create-user`         | Create new user | Admin  |
| GET    | `/api/get-users`           | Get all users   | Admin  |
| PUT    | `/api/update-user`         | Update user     | Admin  |
| DELETE | `/api/delete-user/:userId` | Delete user     | Admin  |

---

## 🧪 Testing

### Backend Tests

```bash
cd backend

# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test -- user_login.test.ts
```

---

## 📦 Available Scripts

### Backend Scripts

```bash
npm start              # Run production build
npm run build          # Compile TypeScript
npm run server:dev     # Development server with hot-reload
npm run work           # Start email worker
npm run cache          # Start cache worker
npm run server         # Run all services
npm test               # Run tests
npm run log:cleanup    # Run log cleanup
npm run seed           # Seed database
```

### Frontend Scripts

```bash
npm run dev            # Development server
npm run build          # Production build
npm run preview        # Preview production build
npm run lint           # Run ESLint
```

---

## 🚢 Deployment

### Production Build

```bash
# Backend
cd backend
npm run build
npm start

# Frontend
cd frontend
npm run build
# Serve the dist/ folder with your web server
```

---

## 🔒 Security

- **Authentication**: JWT-based with refresh tokens
- **Password Hashing**: bcrypt with salt rounds
- **Security Headers**: Helmet.js middleware
- **Rate Limiting**: Prevents brute force attacks
- **Input Validation**: Zod schemas on all inputs
- **SQL Injection Protection**: Prisma ORM parameterized queries
- **XSS Protection**: React's built-in escaping
- **CORS**: Configured for specific origins

---

## 👥 Authors

-[Github](https://github.com/Nayyelin-14)

**Made with ❤️**
