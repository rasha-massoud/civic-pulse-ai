import { useState } from "react";
import { ChevronDown, Send, CheckCircle2, Lightbulb } from "lucide-react";
import type { IssueDTO } from "@/types";
import {
  DEPARTMENTS,
  DEPT_CONFIG,
  getRecommendedDepartment,
  type Department,
} from "@/features/issues/categoryConfig";
import { getLatestTask } from "@/features/issues/issueView";
import { createTask } from "@/api/tasks";

interface TaskBoardProps {
  issue: IssueDTO;
  onAssigned: (issueId: number, updatedIssue: IssueDTO) => void;
}

// Field crews have no accounts in this MVP (see backend Task model), so
// "assignment" is just a Task.assigned_to string. We reuse the Figma
// export's three department names as the assignable values.
export default function TaskBoard({ issue, onAssigned }: TaskBoardProps) {
  const [open, setOpen] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recommended = getRecommendedDepartment(issue.category);
  const latestTask = getLatestTask(issue);
  const assignedTo = latestTask?.assigned_to as Department | undefined;

  async function handleAssign(dept: Department) {
    setAssigning(true);
    setError(null);
    try {
      const task = await createTask(issue.id, dept);
      onAssigned(issue.id, { ...issue, tasks: [...issue.tasks, task] });
      setOpen(false);
    } catch {
      setError("Couldn't save, please try again.");
    } finally {
      setAssigning(false);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        disabled={assigning}
        className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-all disabled:opacity-60 ${
          assignedTo
            ? "bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100"
            : "bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100"
        }`}
      >
        <Send size={11} />
        {assignedTo ? DEPT_CONFIG[assignedTo].short : "Assign crew"}
        <ChevronDown size={11} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div
          className="absolute bottom-full mb-1.5 left-0 z-50 bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden min-w-[240px]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="px-3 py-2 border-b border-slate-100 bg-slate-50">
            <p className="text-[10px] text-slate-400 uppercase tracking-widest">Recommended</p>
            <p className="text-xs font-medium text-blue-600 flex items-center gap-1 mt-0.5">
              <Lightbulb size={11} /> {recommended}
            </p>
          </div>
          {DEPARTMENTS.map((dept) => (
            <button
              key={dept}
              onClick={() => handleAssign(dept)}
              disabled={assigning}
              className={`w-full text-left px-3 py-2.5 text-xs transition-colors flex items-center justify-between gap-2 disabled:opacity-60 ${
                assignedTo === dept ? "bg-emerald-50 text-emerald-700" : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              <span>{dept}</span>
              <div className="flex items-center gap-1 flex-shrink-0">
                {dept === recommended && (
                  <span className="text-[9px] bg-blue-100 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded uppercase tracking-wide">
                    Rec.
                  </span>
                )}
                {assignedTo === dept && <CheckCircle2 size={12} className="text-emerald-500" />}
              </div>
            </button>
          ))}
          {error && (
            <div className="px-3 py-2 text-[11px] text-red-600 bg-red-50 border-t border-red-100">{error}</div>
          )}
        </div>
      )}
    </div>
  );
}
