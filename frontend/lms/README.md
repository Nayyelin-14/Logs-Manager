# LMS Project

A React + TypeScript setup using Vite, with Tailwind CSS, Shadcn UI components, React Query, and other modern libraries for building a responsive Logs Management System (LMS).

---

## Features

-**User Access** : Login, registration, OTP verification, and password recovery -**Role-Based Access Control (RBAC)** : Separate permissions for Admin and User
-Admin: Full access to manage alert rules , alerts, logs, and user accounts
-User: only view alerts and create/delete logs, cannot perform administrative tasks -**Analytics Dashboard**: Browse logs, apply filters, search efficiently, and visualize data with interactive charts -**Alert Rule(Admin)**: Create, edit, delete, and monitor alerts -**UI Components** : Built with shadcn/ui and Tailwind for a modern, responsive, and consistent interface -**State Management** : Global state managed with Zustand for users, filters, and app settings -**Data Handling** : Efficient data fetching, caching, and syncing using React Router actions/loaders and TanStack Query

- **Form Validation** : Zod schemas integrated with React Hook Form for robust input validation
- **Developer Experience**: Modular, reusable, and scalable architecture for maintainable and high-performance code
- **Theming & Styling** : Dark/light mode support and customizable Tailwind themes -**Performance Optimizations** : Lazy loading, code splitting, and optimized rendering for faster UI

---

## Technologies & Libraries

-**React 19** : UI library for building components -**TypeScript** : Static type checking -**Vite** : Fast development server & build tool -**Tailwind CSS** : Utility-first CSS framework -**Radix UI** : Accessible component primitives -**React Query** : Data fetching and caching -**Zod** : Schema validation -**React Hook Form** : Form management -**Recharts** : Charts and data visualization -**Lucide React** : Icons library -**Lottie React** : Animations-**Zustand** : Lightweight state management

## Dev Tools

-**ESLint** : Code linting -**vite-tsconfig-paths** : Module path alias support -**React Query DevTools** : Debug React Query cache and queries

---

### Available Scripts

| Command           | Description                                         |
| ----------------- | --------------------------------------------------- |
| `npm run dev`     | Run the development server with Vite HMR            |
| `npm run build`   | Compile TypeScript and build production-ready files |
| `npm run preview` | Preview the production build                        |
| `npm run lint`    | Run ESLint to check for code style issues           |

## How to Run

### Clone the Repository

```bash
git clone <your-repo-url>
cd frontend
#install dependencies
npm install
## Environment Variables
#Create a .env file in the root folder and add your configuration:
VITE_API_URL=https://your-backend-api-url
#Run Development Server
npm run dev
#Build for Production
npm run build
```

## Folder Structure

```

frontend/
├─ node_modules/ # Node.js dependencies
├─ public/ # Public assets like index.html
├─ src/ # Main source code
│ ├─ api/ # API calls and request handling
│ ├─ AppComponents/ # Reusable app components / layout components
│ ├─ assets/ # Images, icons, fonts, CSS
│ ├─ components/ # ShadcnUI components
│ ├─ hooks/ # Custom React hooks
│ ├─ lib/ # Utility libraries / helper functions
│ ├─ data/ # Sample data
│ ├─ pages/ # Page-level components (views)
│ ├─ router/ # Route actions and loaders
│ ├─ Schemas/ # zod validation schemas
│ ├─ store/ # State management (Zustand)
│ ├─ types/ # TypeScript types and interfaces
│ ├─ index.css # Global styles
│ ├─ main.tsx # Entry point for the app
│ ├─ rotues.tsx # Routing configuration
│ └─ vite-env.d.ts # Vite TypeScript environment declarations
├─ .env # Environment variables
├─ .eslintrc.js # ESLint configuration
├─ .gitignore # Git ignore rules
├─ index.html # Main HTML template
├─ package.json # Project dependencies and scripts
├─ tsconfig.json # TypeScript configuration
├─ tsconfig.node.json # Node-specific TS config
└─ vite.config.ts # Vite configuration

```

---

```

```
