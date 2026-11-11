# AIC Approval UI(Route A)

React + Vite + TypeScript dashboard for the Generic Approval API. Lists pending
approvals with risk badges and the proposed Terraform plan, and approves/denies them
through the same `POST /approvals/{id}/decide` endpoint that Route B uses.

## Dev

```
npm install
npm run dev          # http://localhost:5173
```

- Real API: set `VITE_API_BASE_URL` (default `http://localhost:8000`). The API must
  allow this origin via `CORS_ORIGINS`.
- Demo feed (no backend): set `VITE_MOCK=1` (e.g. in `.env.local`). Useful for design
  work and the live demo when the stack is not running.

## Build + deploy(Firebase Hosting)

```
npm run build        # type-checks, then outputs dist/
firebase deploy --only hosting
```

Env vars in `.env.example`: `VITE_API_BASE_URL`, `VITE_MOCK`, `VITE_OPERATOR_ID`.
