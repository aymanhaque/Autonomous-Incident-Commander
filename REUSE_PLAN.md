# Phase 1 — Reuse Plan: AIC Approval Console

**Target location:** `orchestration/web-ui/` (already a blank Vite scaffold — we build here)  
**Reference only:** `hackutd25/frontend/` (do not modify)

---

## 1. Candidate Module Table

### Design System & Config

| Module | Source path | Verdict | Reason |
|--------|------------|---------|--------|
| CSS design tokens | `hackutd25/frontend/src/index.css` | **REUSE AS-IS** (copy) | Complete token system: semantic color scales, dark mode, 3 accent themes, typography — no project-specific content |
| Tailwind config | `hackutd25/frontend/tailwind.config.js` | **ADAPT** | Tailwind v3 `tailwind.config.js` format; web-ui uses Tailwind v4 — tokens must be re-expressed as a CSS `@theme {}` block inside `index.css` |

### Shared Primitives & Utilities

| Module | Source path | Verdict | Reason |
|--------|------------|---------|--------|
| `PrimaryButton` | `components/PrimaryButton.jsx` | **REUSE AS-IS** | `primary` / `ghost` / `danger` variants map exactly to Approve / secondary / Deny |
| `StatCard` | `components/StatCard.jsx` | **REUSE AS-IS** | Generic KPI tile; reused for risk score display and alert metadata |
| `Toast` + `useToast` | `components/Toast.jsx`, `hooks/useToast.js` | **REUSE AS-IS** | Standard feedback; no changes needed |
| `ThemeSwitch` + `useTheme` | `components/ThemeSwitch.jsx`, `hooks/useTheme.js` | **REUSE AS-IS** | Theme system is entirely generic (dark/light + 3 accents) |
| `useReducedMotion` | `hooks/useReducedMotion.js` | **REUSE AS-IS** | Accessibility helper; no changes |
| `ErrorBoundary` | `components/ErrorBoundary.jsx` | **REUSE AS-IS** | Generic React pattern |
| `StatusChip` | `components/StatusChip.jsx` | **ADAPT** | Generalize colour map from work-order statuses to approval statuses (`pending` / `approved` / `denied`) and risk levels (`low` / `medium` / `high`) |
| `apiCall` helper | `utils/api.js` | **ADAPT** | Remove auth header, add typed wrappers for all three approval endpoints; mock via fixtures until the API is live |

### Layout

| Module | Source path | Verdict | Reason |
|--------|------------|---------|--------|
| `SplitLayout` | `components/SplitLayout.jsx` | **REUSE AS-IS** | Resizable 2-pane shell is identical in concept: queue left, detail right |
| `TopBar` | `components/TopBar.jsx` | **ADAPT** | Strip DataPilot brand + search + work-order create; keep theme toggle and notification bell slot; rename to "AIC" |

### Plan / Step Components (core reuse)

| Module | Source path | Verdict | Reason |
|--------|------------|---------|--------|
| `Timeline` | `components/Timeline.jsx` | **ADAPT** | Step renderer maps directly to Terraform plan steps — swap `executor` for `resource_type`, add a read-only mode (no confirm/issue buttons), keep status dot + connector design |
| `LogsDrawer` + `LogItem` | `components/LogsDrawer.jsx`, `LogItem.jsx` | **ADAPT** | Reuse as the incident event timeline drawer; relabel log sources from `Agent/Technician` to `Prometheus/Agent/Executor` |
| `AgentReasoningFeed` | `components/AgentReasoningFeed.jsx` | **ADAPT** | Reuse as "Plan Generation Reasoning" stream below the detail panel; minimal change |

### List / Queue

| Module | Source path | Verdict | Reason |
|--------|------------|---------|--------|
| `WorkOrdersList` | `components/WorkOrdersList.jsx` | **ADAPT** | Same filter-tab + polling + list pattern; rename to `ApprovalQueue`, swap filter tabs to `all / pending / approved / denied` |
| `WorkOrderRow` | `components/WorkOrderRow.jsx` | **ADAPT** | Swap rack/severity fields for alert name + risk badge + timestamp; keep layout |
| `ApprovalRequests` | `components/ApprovalRequests.jsx` | **REFERENCE** | Already implements the approval queue concept (mocked); confirms the interaction model but is superseded by the API-backed version we build |

### Not Applicable (skip)

| Module | Source path | Verdict | Reason |
|--------|------------|---------|--------|
| `WorkOrderDetails` | `components/WorkOrderDetails.jsx` | **BUILD NEW** | HCL viewer + risk badge + approve/deny replaces the inventory/SLA/confirm-step pattern entirely |
| `IssueReportForm` | `components/IssueReportForm.jsx` | **BUILD NEW** | Denial reason modal is simpler (single text field) |
| `CreateWorkOrderModal` | `components/CreateWorkOrderModal.jsx` | **SKIP** | Alerts come from Prometheus only; no manual creation |
| `WorkOrderAssignment` | `components/WorkOrderAssignment.jsx` | **SKIP** | No human assignment in AIC flow |
| `EscalatedIssues` | `components/EscalatedIssues.jsx` | **SKIP** | Not part of the approval console |
| `InventoryBadge` / `LocationGuidance` / `PathfindingCard` | various | **SKIP** | Data-centre-specific; no equivalent concept |
| `ProcedureView` | `components/ProcedureView.jsx` | **SKIP** | Legacy and unused even in hackutd25 |
| `AuthContext` | `contexts/AuthContext.jsx` | **SKIP** | No auth for the console in Phase 2/3 |

---

## 2. Proposed App Structure

```
orchestration/web-ui/src/
├── main.tsx                     # BrowserRouter + ErrorBoundary
├── App.tsx                      # Route declarations
├── index.css                    # Tailwind v4 @theme + token values from hackutd25
│
├── api/
│   └── approvals.ts             # typed fetch wrappers (GET pending, POST, POST decide)
│                                # returns mock fixtures when VITE_MOCK_API=true
│
├── hooks/
│   ├── useTheme.ts              # ported from hackutd25
│   ├── useToast.ts              # ported from hackutd25
│   └── useReducedMotion.ts      # ported from hackutd25
│
├── components/
│   │
│   ├── primitives/              # design-system atoms
│   │   ├── PrimaryButton.tsx    # reused
│   │   ├── StatCard.tsx         # reused
│   │   ├── StatusChip.tsx       # adapted (adds risk variants)
│   │   ├── Toast.tsx            # reused
│   │   └── RiskBadge.tsx        # NEW — Low/Med/High pill with hard-stop treatment
│   │
│   ├── layout/
│   │   ├── TopBar.tsx           # adapted
│   │   ├── SplitLayout.tsx      # reused
│   │   └── ThemeSwitch.tsx      # reused
│   │
│   ├── queue/
│   │   ├── ApprovalQueue.tsx    # adapted from WorkOrdersList
│   │   └── ApprovalRow.tsx      # adapted from WorkOrderRow
│   │
│   ├── detail/
│   │   ├── ApprovalDetail.tsx   # NEW orchestrator (replaces WorkOrderDetails)
│   │   ├── HclViewer.tsx        # NEW — syntax-highlighted HCL block
│   │   ├── PlanTimeline.tsx     # adapted from Timeline (read-only)
│   │   ├── HighRiskBlock.tsx    # NEW — full-stop overlay for High risk
│   │   └── DenyReasonModal.tsx  # NEW — denial reason capture
│   │
│   ├── incident/
│   │   ├── IncidentTimeline.tsx # adapted from LogsDrawer
│   │   └── ReasoningFeed.tsx    # adapted from AgentReasoningFeed
│   │
│   └── ErrorBoundary.tsx        # reused
│
├── pages/
│   └── ConsolePage.tsx          # SplitLayout(ApprovalQueue | ApprovalDetail)
│
└── types/
    └── approval.ts              # Approval, AlertPayload, RiskLevel, Decision types
```

### Routes

| Path | Page | Notes |
|------|------|-------|
| `/` | redirect → `/approvals` | |
| `/approvals` | `ConsolePage` | main console, no selection |
| `/approvals/:id` | `ConsolePage` | deep-link; pre-selects row and opens detail |

---

## 3. Target Stack & New Dependencies

| Concern | Choice | Reason |
|---------|--------|--------|
| Framework | React 19 + TypeScript | Already in web-ui scaffold; hackutd25 had `@types/*` deps suggesting TypeScript was always intended |
| Build | Vite 8 + `@tailwindcss/vite` | Already in web-ui |
| Styling | Tailwind v4 | Already in web-ui; design tokens from hackutd25 re-expressed as `@theme {}` |
| Animation | `framer-motion` (v11+) | Same library as hackutd25; add to web-ui deps |
| Routing | `react-router-dom` v6 | Same version as hackutd25; add to web-ui deps |
| HCL highlighting | `shiki` | Lightweight, zero-runtime WASM highlighter; has HCL grammar; no CSS bundle overhead |
| Mock API | JSON fixture files + a thin switch in `api/approvals.ts` | `VITE_MOCK_API=true` serves fixtures; no external mock library needed |
| State | Local `useState` + React Context (toast, theme) | Matches hackutd25 pattern; complexity does not justify a store |

No new dependencies beyond `framer-motion`, `react-router-dom`, and `shiki`.

---

## 4. Data Model

```ts
// types/approval.ts
type RiskLevel = 'low' | 'medium' | 'high'
type ApprovalStatus = 'pending' | 'approved' | 'denied'
type Decision = 'approve' | 'deny'

interface AlertPayload {
  alertname: string        // e.g. "OOMKilled", "HTTP504", "NodePressure"
  namespace: string
  pod?: string
  node?: string
  severity: string
  startsAt: string         // ISO timestamp
  labels: Record<string, string>
  annotations: Record<string, string>
}

interface Approval {
  id: string
  status: ApprovalStatus
  risk_level: RiskLevel
  terraform_plan: string   // raw HCL
  alert: AlertPayload
  created_at: string
  decided_at?: string
  decided_by?: string
  deny_reason?: string
}
```

---

## 5. API Mock Strategy

The `orchestration/approval_api/` directory is empty (only `.gitkeep`). Until the real API is live:

- `src/api/approvals.ts` checks `import.meta.env.VITE_MOCK_API`
- If true, all calls return static fixture objects from `src/api/fixtures/`  
- Fixtures include one approval per risk level (Low / Medium / High) so every UI state can be tested
- The same function signatures are used, so switching to the real API is a one-line `.env` change

---

## 6. Open Questions & Assumptions

| # | Question / Assumption | Impact if wrong |
|---|----------------------|-----------------|
| 1 | **TypeScript over JSX.** hackutd25 is `.jsx` but web-ui scaffold is already `.tsx`. I'm proposing TypeScript throughout for type safety on the approval data model. | Low: easy to strip types if the team prefers JSX |
| 2 | **Tailwind v3 → v4 token migration.** hackutd25's `tailwind.config.js` semantic aliases must be re-expressed as `@theme { --color-* }` in `index.css`. The token values are identical; only the syntax changes. | Low: cosmetic migration, well-documented |
| 3 | **No authentication.** The console has no login screen. If the API requires a bearer token, `apiCall` gains a header but the UI has no login flow. | Medium: blocked if API requires auth before Phase 3 |
| 4 | **High-risk = full UI block** (not just a visual flag). I'm planning `HighRiskBlock.tsx` to render a locked overlay over the approve button with an explicit "This plan is blocked — contact your SRE lead" message. This assumes the project constraint ("hard stop") means the UI itself must prevent approval, not just warn. | Low: easy to soften to a warning banner if the team prefers |
| 5 | **`shiki` for HCL syntax highlighting.** If bundle size or WASM is a concern, `prism-react-renderer` is the fallback (no WASM, smaller bundle, HCL grammar available via community). | Low: swap is 1 component |
| 6 | **Polling, not WebSocket.** I'm proposing the same `setInterval` polling pattern from hackutd25 (every 5 s for the queue). If the API eventually supports SSE/WebSocket, the hook changes but component interfaces are identical. | Low |
| 7 | **`orchestration/web-ui/` is the right target.** This is already the declared web-UI location in the project (CLAUDE.md, docker-compose). Confirm this is where Phase 2 code should land, not a new `apps/console/`. | Medium: rename before Phase 2 if wrong |
