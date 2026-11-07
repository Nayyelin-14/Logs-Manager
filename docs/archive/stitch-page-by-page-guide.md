# Stitch Guide: LogOps, One Route at a Time

Use this guide to generate the Log Manager frontend in Stitch **one page at a time**. Each prompt is for one route only. Do not ask Stitch to put every feature on one page.

## Shared design direction

Use this direction for every authenticated route:

- Use Plus Jakarta Sans throughout the interface. Use JetBrains Mono sparingly for event IDs, timestamps, IP addresses, and telemetry values.
- Keep the existing LogOps visual direction: dark charcoal and blue-gray surfaces, warm white text, muted gray secondary text, restrained orange accents, and teal, amber, red, and slate for status/severity.
- Keep one consistent application shell, sidebar, top navigation, spacing scale, buttons, tables, filters, drawers, dialogs, and feedback states.
- Make each route's content and composition specific to its job. Do not repeat the same four-card-plus-chart template on every page.
- Generate only the requested route. Do not put other pages or their content below it.
- Treat the existing application data and capabilities as the source of truth. Do not invent statistics, features, integrations, or actions. Show loading, empty, error, and success states where appropriate.

## Important route distinction

There are two different overview pages:

- **Security Overview — `/dashboard`** is the SOC analyst's operational view of event activity, sources, rules, alerts, and investigation entry points.
- **Management Overview — `/`** is the administrator's tenant-scoped control-plane landing page with counts and links to management tasks.

Do not combine these pages.

---

## 1. Security Overview — `/dashboard`

### What the page does

This is the SOC analyst's landing page. It helps answer: what events came in, what detections fired, and where should I investigate next?

It uses backend data for:

- Event volume over time and total events in the selected window.
- Alert counts by severity and status, plus recent detection activity.
- Activity by event source, common event categories, and enabled versus paused rules.
- Recent security events and top IP indicators.

The time range supports Today, Last 3 days, and Last 7 days. Admins can select a tenant; other users see data within their permitted workspace.

### Stitch prompt

> Design the Security Overview page for a real Security Operations application. This is one route in a multi-page product, not a dashboard containing every feature. Its purpose is to help an analyst understand incoming security events and decide what to investigate.
>
> Create a clear hierarchy: a compact page heading with workspace/tenant context and time-range controls; a prominent event-volume timeline; a distinct alert severity and status summary; recent detection activity; source activity and enabled/paused rule summaries; then a recent events table and top IP indicators.
>
> Use asymmetric proportions to emphasize the event timeline and recent events. Avoid four identical metric cards and avoid putting every section inside the same card pattern. Make useful metrics and table rows clear entry points to their corresponding pages.
>
> Only show values supplied by the application. Do not invent throughput, source health, protocol types, attack attribution, MTTA/MTTR, or other statistics. Include loading, empty, error, and retry states.
>
> Apply the shared LogOps design direction: Plus Jakarta Sans throughout, JetBrains Mono only for technical identifiers and numeric telemetry, dark charcoal/blue-gray layered surfaces, restrained orange, teal, amber, red, and slate status colors, compact readable typography, and the existing sidebar/top navigation. Generate only the Security Overview route. Do not place Analytics, Logs, Alerts, Rules, or Users content below it.

---

## 2. Management Overview — `/`

### What the page does

This is an administrator's control-plane landing page, separate from Security Overview. It shows tenant-scoped counts for events, users, alerts, and rules, then links to Logs, Alerts, Rules, and Users. Administrators can select a tenant, and the selection should carry through to those pages.

### Stitch prompt

> Design a separate Management Overview page for administrators. Its job is to summarize the selected tenant's users, security events, alerts, and detection rules, then provide clear links to manage those records.
>
> Include an authorized tenant selector, a compact presentation of the real record counts, and a control-plane section linking to Users, Logs, Alert Rules, and Alert Triage. The alert queue summary should link to Alerts. Preserve the selected tenant when navigating to those pages.
>
> Keep this visually distinct from the SOC Security Overview: emphasize administration and navigation, not event timelines or analytics. Do not add tenant creation, system settings, or other actions unless the application provides them. Use the shared LogOps navigation, typography, and palette. Generate only this route.

---

## 3. Security Analytics — `/analytics`

### What the page does

Analytics explores real event and alert aggregates: event/alert trends, severity distribution, source mix, event categories, activity by weekday and three-hour interval, and tenant activity where the user is authorized. It shares the time-range and tenant scope controls.

The sample Stitch design contains unsupported example metrics such as compression, dropped packets, protocol breakdowns, MITRE counts, storage use, and ingestion-node health. Do not include those unless the backend later provides them.

### Stitch prompt

> Design a dedicated Security Analytics page for exploring historical patterns, not a second overview dashboard. Use the selected time range and authorized tenant scope.
>
> Organize the page around real event and alert trends, event severity distribution, event volume by source, leading event categories, and a weekday-by-three-hour activity heatmap. Show tenant comparisons only for users authorized to view multiple tenants.
>
> Give the main time-series chart the largest area, with smaller but legible comparison and distribution views around it. Include meaningful legends, axes, tooltips, and empty states. Do not include fabricated incident metrics, protocol breakdowns, MITRE tactic counts, ingestion throughput, storage consumption, or source health.
>
> Use the shared LogOps shell, Plus Jakarta Sans typography, and dark visual system. Keep Analytics as its own route and do not stack other pages beneath it.

---

## 4. Monitoring Logs — `/logs`

### What the page does

This is the searchable security event stream. Users can search by user, IP, source, or event type; filter by date and severity; inspect event fields; load more results; and submit an event through the supported ingestion form. Admin tenant scope is supported.

### Stitch prompt

> Design a Security Event Stream page focused on investigation. Provide a compact heading and a dense, readable event table with timestamp, severity, source, event type, and relevant identity/network fields. Include search, date and severity filters, active-filter clearing, pagination or load-more, and an event detail view.
>
> Include the existing create-log workflow as a real ingestion form. Do not imply unsupported ingestion protocols or integrations. Filters must be visible and clearly associated with the results. Preserve tenant scope for authorized administrators.
>
> Keep the table as the page's visual focus. Use restrained severity colors and monospace treatment only where it improves scanning. Include loading, error, and empty states. This is a separate Monitoring route, not a dashboard with unrelated charts.

---

## 5. Alert Triage — `/alerts`

### What the page does

This is the persisted detection queue. Users can search alerts, filter by status and severity, open alert details, and load more results. Details include rule information, context, related event IDs, tenant, and trigger time. Admins can resolve open alerts; show that action only when the user is authorized.

### Stitch prompt

> Design an Alert Triage page for reviewing persisted detections. Include a compact queue summary and a filterable alert table with severity, detection title, rule, status, and triggered time. Show tenant only when the user is permitted to view cross-tenant data.
>
> Selecting an alert opens a detail drawer containing its rule information, description/context, related event IDs, tenant, and trigger time. Provide a Resolve action only for authorized administrators on open alerts. Do not add acknowledge, assign, bulk resolve, or other unsupported actions.
>
> Include search, status and severity filters, load-more behavior, loading/error/empty states, and clear feedback after resolving an alert. Make this a focused triage workspace, distinct from Analytics and Logs.

---

## 6. Alert Rules — `/rules`

### What the page does

This is detection logic management. It supports searching and date filtering rules, creating and editing rules, enabling/disabling them, and deleting with confirmation. Create and edit forms persist through the backend.

### Stitch prompt

> Design a Detection Rules management page for administrators. The table should make rule name, description, enabled/disabled state, and creation information easy to scan.
>
> Provide search and date filtering, create and edit forms with clear validation, an enable/disable control, and a destructive delete action with confirmation. Creating or editing a rule must be represented as a persisted operation with loading, success, and error states; never show success before the save succeeds.
>
> Do not invent rule fields or evaluation capabilities. Keep rule management separate from alert triage. Use the shared navigation and design system, with status color used sparingly.

---

## 7. Workspace Users — `/users`

### What the page does

This is workspace account administration. It supports searching and filtering users by role, status, and date; creating users; and deleting users. The current table displays an Edit button without a working handler. Do not present editing as a functional action unless that implementation is added. Tenant visibility must follow authorization.

### Stitch prompt

> Design a Workspace Users administration page. Show each user's identity, email, tenant, role, account status, and creation date in a compact, readable table. Include search, role/status/date filters, clear-filters behavior, pagination/load-more, and a create-user form.
>
> Include delete with an explicit confirmation step. Do not present Edit, role changes, status changes, invitations, or other actions as functional unless the application supports them. Show tenant information and tenant filtering only according to the current user's permissions.
>
> Provide loading, error, empty, and mutation feedback states. Keep this page focused on access administration rather than adding general settings.

---

## 8. Authentication — `/login`, `/register`

### What the flow does

Authentication routes include login/logout and registration steps for registration, OTP verification, and password confirmation. Protected pages require an authenticated session and should respect user permissions.

### Stitch prompt

> Design the authentication routes as a cohesive, focused flow: Login, Registration, OTP verification, and Confirm Password. Keep the LogOps typography and color language, but use a simpler layout without the authenticated application sidebar.
>
> Forms need visible labels, validation messages, loading and API error states, and clear next-step guidance. Do not invent social login, password reset, or account recovery actions unless they exist in the product. Each primary action should advance its corresponding authentication step.

---

## Suggested Stitch sequence

1. Generate the shared authenticated shell and navigation.
2. Generate Security Overview.
3. Generate Analytics.
4. Generate Monitoring Logs.
5. Generate Alert Triage.
6. Generate Alert Rules.
7. Generate Workspace Users.
8. Generate the separate Management Overview.
9. Generate the authentication flow.

For each step, tell Stitch to generate **only that route**, keep the shared shell consistent, and avoid inventing any backend data or actions.
