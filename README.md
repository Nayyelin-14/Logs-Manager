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

## 🏗️ System Architecture

### Frontend-Backend Communication Flow

The LMS uses a modern client-server architecture with the following communication pattern:

1. **Frontend (React + Vite)**

   - Makes HTTP/HTTPS requests to the backend API
   - Uses **React Query** for data fetching, caching, and synchronization
   - Stores JWT tokens in memory/localStorage for authentication
   - Manages global state with **Zustand** (user data, filters, settings)
   - Implements optimistic updates for better UX

2. **API Communication**

   - **REST API** endpoints for all operations
   - **JSON** format for request/response payloads
   - **JWT tokens** in Authorization headers (`Bearer <token>`)
   - **CORS** enabled for cross-origin requests
   - **Rate limiting** to prevent abuse

3. **Backend (Express.js)**

   - Validates incoming requests (JWT verification, input validation)
   - Processes business logic through services layer
   - Queries Redis cache first, falls back to PostgreSQL
   - Returns standardized JSON responses
   - Emits events to queue system for async operations

4. **Data Flow Example** (User Login):
   ```
   Frontend                    Backend                    Database
   --------                    -------                    --------
   Login Form → POST /api/auth/login → Validate credentials → PostgreSQL
                                     ← Generate JWT tokens ←
   Store tokens ← Return tokens & user data
   Update Zustand ←
   Redirect to Dashboard
   ```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         React Frontend (Vite + TypeScript)           │  │
│  │  • Shadcn UI + Tailwind CSS                          │  │
│  │  • React Query for data management                   │  │
│  │  • Zustand for state management                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↕️ HTTPS/REST API
                    (JSON payloads + JWT tokens)
┌─────────────────────────────────────────────────────────────┐
│                       API GATEWAY                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Express.js Backend (TypeScript)              │  │
│  │  • JWT Authentication                                │  │
│  │  • Rate Limiting & Security                          │  │
│  │  • Input Validation                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↕️
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
┌──────────────────┐                  ┌──────────────────┐
│  INGESTION       │                  │  PROCESSING      │
│  • HTTP API      │                  │  • Normalization │
│  • Syslog        │                  │  • Alert Engine  │
│  • Network       │    ────────→     │  • Analytics     │
│  • CrowdStrike   │                  │  • Aggregation   │
│  • Agents        │                  │                  │
└──────────────────┘                  └──────────────────┘
                                              ↓
                    ┌─────────────────────────┴──────────────┐
                    ↓                                        ↓
          ┌──────────────────┐                    ┌──────────────────┐
          │  REDIS CACHE     │                    │  POSTGRESQL DB   │
          │  • Logs          │                    │  • Users         │
          │  • Alerts        │    ←─ Sync ─→      │  • Alert Rules   │
          │  • Rules         │                    │  • Metadata      │
          │  • Sessions      │                    │                  │
          └──────────────────┘                    └──────────────────┘
                    ↓
          ┌──────────────────┐
          │  QUEUE & WORKER  │
          │  • Email Queue   │
          │  • Retry Logic   │
          │  • OTP Delivery  │
          └──────────────────┘
                    ↓
          ┌──────────────────┐
          │  SMTP SERVICE    │
          │  • Notifications │
          │  • Alerts        │
          └──────────────────┘
```

---

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
Frontend → API Call → Backend → Validate → Store in DB  → Response → UI Update
```

**Pattern 3: Real-time Alerts**

```
Log Ingestion → Alert Engine → Match Rules → Queue Email →
Worker Sends → Frontend Polls → Updates Dashboard
```

### Environment Configuration

**Frontend (.env)**

```env
VITE_API_URL=http://localhost:3000/api  # Backend API base URL
```

**Backend (.env)**

```env
FRONTEND_URL=http://localhost:5173      # Frontend URL for CORS
```

These environment variables ensure the frontend knows where to send requests and the backend knows which origin to allow.

---

## 🔄 How the System Works: End-to-End Flow

### 1. Log Ingestion → Normalization → Alert Detection → Email Notification

#### Step 1: Log Ingestion

```
External Sources               Backend API
─────────────────             ─────────────
HTTP Request    ──────────>   POST /api/ingest
Syslog Server   ──────────>   Syslog Listener
Network Feed    ──────────>   Network Parser
CrowdStrike API ──────────>   Third-party Integration
Custom Agent    ──────────>   Agent Endpoint
```

**What happens:**

- Logs arrive from various sources in different formats (JSON, syslog, CSV, etc.)
- Backend receives raw log data
- Initial validation checks (authentication, rate limiting)

#### Step 2: Log Normalization

```javascript
// Raw log from different sources
Input 1: { "level": "ERROR", "msg": "Failed login", "ts": "2025-10-04T10:30:00Z" }
Input 2: <134>Oct 4 10:30:00 server: Failed login attempt
Input 3: 2025-10-04 10:30:00 | ERROR | Failed login

// After normalization - Unified schema
Output: {
  id: "log_123456",
  timestamp: "2025-10-04T10:30:00Z",
  level: "ERROR",
  message: "Failed login",
  source: "auth-service",
  userId: "user_789",
  metadata: { ip: "192.168.1.1", attempt: 3 }
}
```

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
     │           • Indexed by: timestamp, level, source
     │
     └─────────> PostgreSQL (Durable metadata storage)
                 • Stores log metadata
                 • User associations
                 • Audit trail
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
│     • Source matches?            │
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
  name: Failed Login Alert,
  tenant: demoA,
  description: Trigger alert if a user fails login with severity >= 3,
  conditions: [
    {
      type: event_type,
      value: LoginFailed
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
│                                  │
│                                  │
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
     │     • Subject: "[CRITICAL] Payment Service Alert"
     │     • Body: HTML template with log details
     │
     ├─ 4. Send via Nodemailer + Gmail
     │     • Connect to Gmail SMTP
     │     • Authenticate with credentials
     │     • Send email
     │
     ├─ 5. Update job status
     │     • Success: Mark complete
     │     • Failure: Retry (up to 3 times)
     │
     └─ 6. Log delivery status
```

**What happens:**

- Background worker picks job from queue
- Generates formatted email using template
- Sends email via Nodemailer
- Handles failures with retry logic (exponential backoff)
- Updates alert status in database

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
     ├─ Alert list with filters
     └─ Real-time updates (polling)
```

### Complete End-to-End Example

**Scenario:** Payment service generates 5 error logs within 2 minutes

```
Time: 10:00:00 - Log 1 ingested → Normalized → Stored → Rule checked (no match yet)
Time: 10:00:30 - Log 2 ingested → Normalized → Stored → Rule checked (no match yet)
Time: 10:01:00 - Log 3 ingested → Normalized → Stored → Rule checked (no match yet)
Time: 10:01:30 - Log 4 ingested → Normalized → Stored → Rule checked (no match yet)
Time: 10:02:00 - Log 5 ingested → Normalized → Stored → Rule checked ✅ MATCH!
                  │
                  └─> Alert created → Queued → Worker processes → Email sent

Time: 10:02:05 - Admin receives email: "5 payment errors in 2 minutes"
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
- **Docker** & **Docker Compose** (optional)
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

### Using Docker (Recommended)

```bash
# From project root
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

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
├── docker-compose.yml         # Docker services configuration
├── .gitignore
└── README.md                  # This file
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

### Frontend Tests

```bash
cd frontend

# Run tests (when configured)
npm test
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

### Docker Deployment

```bash
# Build and start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f

# Scale services
docker-compose up -d --scale worker=3
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

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👥 Authors

- **Your Name** - _Initial work_ - [YourGithub](https://github.com/yourusername)

---

## 🙏 Acknowledgments

- Shadcn UI for the excellent component library
- The React and Node.js communities
- All contributors who have helped this project

---

## 📞 Support

For support, email support@lms.com or open an issue in the GitHub repository.

---

## 🗺️ Roadmap

- [ ] Implement WebSocket for real-time log streaming
- [ ] Add more log source integrations
- [ ] Implement log parsing with regex patterns
- [ ] Add export functionality (CSV, JSON, PDF)
- [ ] Implement log archiving to S3/Azure Blob
- [ ] Add advanced analytics with ML-based anomaly detection
- [ ] Mobile app development
- [ ] Kubernetes deployment configurations

---

**Made with ❤️ by the LMS Team**


