# LMS Project

A high-performance **Log Management System (LMS)** frontend application built with **React** and **TypeScript**, using **Vite** for lightning-fast development and build times. The interface leverages **Tailwind CSS** and **Shadcn UI** components to provide a fully responsive, accessible, and consistent design.

**React Query** enables efficient data fetching, caching, and state management, ensuring high performance throughout the app. The frontend delivers a comprehensive dashboard for:

- Log management and viewing
- Real-time alerts
- Alert rule configuration
- Analytics and reporting

It also includes robust authentication flows and a rich set of reusable UI components, all engineered for **clean code, scalability, and optimal performance**.

---

## Features

- **Authentication**: Login and logout for admin-provisioned accounts. Public registration, OTP verification, and password recovery are not implemented.
- **Role-Based Access Control (RBAC)**: Separate permissions for `ADMIN` and `VIEWER`
  - **ADMIN**: Full access to dashboard, logs, alerts, analytics, rules, users, and tenants
  - **VIEWER**: Read-only access to dashboard, logs, alerts, and analytics
- **Analytics Dashboard**: Browse logs, apply filters, search efficiently, and visualize data with interactive charts
- **Alert Rules (Admin)**: Create, edit, enable/disable, test, and delete rules
- **UI Components**: Built with shadcn/ui and Tailwind for a modern, responsive, and consistent interface
- **State Management**: Zustand for session and user state
- **Data Handling**: Efficient data fetching, caching, and syncing using React Router actions/loaders and TanStack Query
- **Form Validation**: Zod schemas integrated with React Hook Form for robust input validation
- **Performance Optimizations**: Lazy loading, code splitting, and optimized rendering for faster UI

---

## Technologies & Libraries

- **React 19**: UI library for building components
- **TypeScript**: Static type checking
- **Vite**: Fast development server & build tool
- **Tailwind CSS**: Utility-first CSS framework
- **Radix UI**: Accessible component primitives
- **React Query**: Data fetching and caching
- **Zod**: Schema validation
- **React Hook Form**: Form management
- **Recharts**: Charts and data visualization
- **Lucide React**: Icons library
- **Zustand**: Lightweight state management
- **React Router**: Routing, loaders, and actions

---

## Dev Tools

- **ESLint**: Code linting
- **vite-tsconfig-paths**: Module path alias support
- **React Query DevTools**: Debug React Query cache and queries

---

### Available Scripts

| Command           | Description                                         |
| ----------------- | --------------------------------------------------- |
| `npm run dev`     | Run the development server with Vite HMR            |
| `npm run build`   | Compile TypeScript and build production-ready files |
| `npm run preview` | Preview the production build                        |
| `npm run lint`    | Run ESLint to check for code style issues           |

## How to Run

For the complete application, use the root-level workflow:

```bash
make up
make seed
```

The UI is served at `http://localhost:8080`. See the root
[`README.md`](../../README.md) for prerequisites and shutdown commands.

For frontend-only development:

```bash
cd frontend/lms
npm install
echo 'VITE_API_URL=http://localhost:4500' > .env
npm run dev
```

Use `npm run lint`, `npx tsc -b`, and `npm run build` to run the frontend
checks. The root `make check-frontend` target runs the same commands.

## Folder Structure

```
frontend/lms/
├─ public/              # Static assets
├─ src/
│  ├─ api/              # API calls and request handling
│  ├─ AppComponents/    # Reusable app and layout components
│  ├─ assets/           # Images, icons, and styles
│  ├─ components/       # shadcn/ui components
│  ├─ hooks/            # Custom React hooks
│  ├─ lib/              # Utilities and constants
│  ├─ pages/            # Page-level views
│  ├─ router/           # Route actions and loaders
│  ├─ Schemas/          # Zod validation schemas
│  ├─ store/            # Zustand state
│  ├─ types/            # TypeScript types
│  ├─ main.tsx          # Entry point
│  └─ routes.tsx        # Route configuration
├─ index.html
├─ package.json
├─ playwright.config.ts
├─ vite.config.ts
└─ eslint.config.js
```
