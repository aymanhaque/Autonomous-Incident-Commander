import { useState } from "react";

function lineClass(line: string): string {
  const t = line.trimStart();
  if (t.startsWith("#")) return "tf-comment";
  if (t.startsWith("resource") || t.startsWith("data")) return "tf-keyword";
  return "";
}

export function PlanPanel({ plan }: { plan: string }) {
  const [open, setOpen] = useState(false);
  const lines = plan.split("\n");
  return (
    <div className={`plan ${open ? "plan--open" : ""}`}>
      <button className="plan-head" onClick={() => setOpen((o) => !o)}>
        <span className="plan-prompt">$</span>
        <span className="plan-title">terraform plan</span>
        <span className="plan-meta">{lines.length} lines</span>
        <span className="plan-chevron">{open ? "COLLAPSE" : "INSPECT"}</span>
      </button>
      {open && (
        <pre className="plan-body">
          {lines.map((l, i) => (
            <div className="plan-line" key={i}>
              <span className="plan-ln">{String(i + 1).padStart(2, "0")}</span>
              <code className={lineClass(l)}>{l || " "}</code>
            </div>
          ))}
        </pre>
      )}
    </div>
  );
}
