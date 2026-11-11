import type { Approval, Decision, PendingList } from "./types";
import { MOCK_APPROVALS } from "./mocks";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8090";
const MOCK = import.meta.env.VITE_MOCK === "1";
const OPERATOR = import.meta.env.VITE_OPERATOR_ID ?? "ui:operator@aic";
const TOKEN = import.meta.env.VITE_API_TOKEN ?? "";

let mockState: Approval[] = MOCK ? MOCK_APPROVALS.map((a) => ({ ...a })) : [];

export const operatorId = OPERATOR;
export const isMock = MOCK;

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", "X-Actor": OPERATOR };
  if (TOKEN) h["Authorization"] = `Bearer ${TOKEN}`;
  return h;
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export async function fetchPending(): Promise<Approval[]> {
  if (MOCK) {
    await delay(260);
    return mockState.filter((a) => a.status === "pending");
  }
  const res = await fetch(`${BASE}/approvals/pending`);
  if (!res.ok) throw new Error(`pending ${res.status}`);
  const data: PendingList = await res.json();
  return data.items;
}

export async function fetchRecent(): Promise<Approval[]> {
  if (MOCK) {
    await delay(260);
    return mockState
      .filter((a) => a.status !== "pending")
      .sort((a, b) => (b.decided_at ?? "").localeCompare(a.decided_at ?? ""));
  }
  const res = await fetch(`${BASE}/approvals/recent`);
  if (!res.ok) throw new Error(`recent ${res.status}`);
  const data: PendingList = await res.json();
  return data.items;
}

export async function decide(id: string, decision: Decision, note?: string): Promise<void> {
  if (MOCK) {
    await delay(400);
    mockState = mockState.map((a) =>
      a.approval_id === id
        ? {
            ...a,
            status: decision === "approve" ? "approved" : "denied",
            decided_by: OPERATOR,
            decided_at: new Date().toISOString(),
            decision_channel: "web",
            decision_note: note ?? null,
          }
        : a
    );
    return;
  }
  const res = await fetch(`${BASE}/approvals/${id}/decide`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ decision, decision_channel: "web", decision_note: note ?? null }),
  });
  if (!res.ok) throw new Error(`decide ${res.status}`);
}

export async function ping(): Promise<boolean> {
  if (MOCK) return true;
  try {
    const res = await fetch(`${BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
