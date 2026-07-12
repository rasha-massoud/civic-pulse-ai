import { useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle, ChevronDown, ChevronUp, GitMerge, Lightbulb, Send, Zap } from "lucide-react";
import type { IssueDTO } from "@/types";
import { getMergedReports, isUrgent } from "@/features/issues/issueView";

interface Step {
  icon: ReactNode;
  priority: string;
  badge: string;
  border: string;
  text: string;
}

interface StepsPanelProps {
  issues: IssueDTO[];
}

export default function StepsPanel({ issues }: StepsPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  const urgentOpen = issues.filter((i) => isUrgent(i.severity) && i.status === "open");
  const electricalOpen = issues.filter((i) => i.category === "Electrical Hazard" && i.status !== "resolved");
  const unassigned = issues.filter((i) => i.tasks.length === 0 && i.status !== "resolved");
  const merged = issues.filter((i) => getMergedReports(i).length > 0 && i.status === "open");

  const steps = [
    urgentOpen.length > 0 && {
      icon: <AlertTriangle size={14} className="text-red-500" />,
      priority: "Critical",
      badge: "bg-red-50 text-red-600 border-red-200",
      border: "border-red-200 bg-red-50/50",
      text: `Dispatch field crews to ${urgentOpen.length} urgent open issue${urgentOpen.length > 1 ? "s" : ""} — these require immediate on-site response.`,
    },
    electricalOpen.length > 0 && {
      icon: <Zap size={14} className="text-yellow-500" />,
      priority: "High",
      badge: "bg-yellow-50 text-yellow-600 border-yellow-200",
      border: "border-yellow-200 bg-yellow-50/50",
      text: `Contact Ministry of Electricity for ${electricalOpen.length} active electrical hazard${electricalOpen.length > 1 ? "s" : ""}. Restrict public access near affected areas.`,
    },
    unassigned.length > 0 && {
      icon: <Send size={14} className="text-blue-500" />,
      priority: "Medium",
      badge: "bg-blue-50 text-blue-600 border-blue-200",
      border: "border-blue-200 bg-blue-50/50",
      text: `${unassigned.length} open issue${unassigned.length > 1 ? "s have" : " has"} no field crew assigned. Use "Assign crew" to route them.`,
    },
    merged.length > 0 && {
      icon: <GitMerge size={14} className="text-purple-500" />,
      priority: "Info",
      badge: "bg-purple-50 text-purple-600 border-purple-200",
      border: "border-purple-200 bg-purple-50/50",
      text: `${merged.length} merged issue${merged.length > 1 ? "s indicate" : " indicates"} recurring problems — consider infrastructure audits in those districts.`,
    },
    {
      icon: <CheckCircle size={14} className="text-emerald-500" />,
      priority: "Routine",
      badge: "bg-emerald-50 text-emerald-600 border-emerald-200",
      border: "border-emerald-200 bg-emerald-50/50",
      text: "Review and mark any field-verified completions as Resolved to keep citizen tracking accurate.",
    },
  ].filter(Boolean) as Step[];

  return (
    <div className="bg-white border border-slate-200 rounded-xl mb-5 overflow-hidden shadow-sm">
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
        onClick={() => setCollapsed((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-blue-100 border border-blue-200 flex items-center justify-center">
            <Lightbulb size={13} className="text-blue-600" />
          </div>
          <span className="text-sm font-semibold text-slate-800">Steps to Do Next</span>
          <span className="text-[11px] bg-blue-50 border border-blue-200 text-blue-600 px-2 py-0.5 rounded-full">
            {steps.length} action{steps.length !== 1 ? "s" : ""}
          </span>
        </div>
        {collapsed ? <ChevronDown size={15} className="text-slate-400" /> : <ChevronUp size={15} className="text-slate-400" />}
      </button>

      {!collapsed && (
        <div className="px-4 pb-4 grid sm:grid-cols-2 gap-2">
          {steps.map((step, i) => (
            <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${step.border}`}>
              <div className="mt-0.5 flex-shrink-0">{step.icon}</div>
              <div className="min-w-0">
                <span
                  className={`inline-block text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded border mb-1.5 ${step.badge}`}
                >
                  {step.priority}
                </span>
                <p className="text-xs text-slate-600 leading-relaxed">{step.text}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
