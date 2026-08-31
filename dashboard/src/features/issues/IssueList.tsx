import { AlertTriangle, CheckCircle2, Clock, Eye, GitMerge, MapPin, RefreshCw, Search } from "lucide-react";
import { useState } from "react";
import type { IssueDTO, IssueStatus } from "@/types";
import { getCategoryConfig } from "./categoryConfig";
import {
  getDescription,
  getDisplayLocation,
  getDisplayStatus,
  getMergedReports,
  getPhotoUrl,
  getTicketNo,
  getTitle,
  isUrgent,
  timeAgo,
} from "./issueView";
import TaskBoard from "@/features/tasks/TaskBoard";

export function StatusBadge({ status }: { status: IssueStatus }) {
  const label = getDisplayStatus(status);
  const map = {
    Open: "bg-slate-100 text-slate-500 border-slate-200",
    "In Progress": "bg-blue-50 text-blue-600 border-blue-200",
    Resolved: "bg-emerald-50 text-emerald-600 border-emerald-200",
  } as const;
  const icons = {
    Open: <Clock size={10} />,
    "In Progress": <RefreshCw size={10} />,
    Resolved: <CheckCircle2 size={10} />,
  } as const;
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wide ${map[label]}`}
    >
      {icons[label]} {label}
    </span>
  );
}

function MergedBadge({ count }: { count: number }) {
  return (
    <div className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-purple-600 bg-purple-50 border border-purple-200 px-1.5 py-0.5 rounded">
      <GitMerge size={10} /> {count + 1} reports
    </div>
  );
}

function PhotoOrFallback({ issue }: { issue: IssueDTO }) {
  const [loadFailed, setLoadFailed] = useState(false);
  const photo = getPhotoUrl(issue);
  const cat = getCategoryConfig(issue.category);
  if (photo && !loadFailed) {
    return (
      <img
        src={photo}
        alt={getTitle(issue)}
        onError={() => setLoadFailed(true)}
        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
      />
    );
  }
  return (
    <div className={`w-full h-full flex items-center justify-center ${cat.bg}`}>
      <span className={cat.color}>{cat.icon}</span>
    </div>
  );
}

interface IssueCardProps {
  issue: IssueDTO;
  view: "grid" | "list";
  onView: (issue: IssueDTO) => void;
  onAssigned: (issueId: number, updatedIssue: IssueDTO) => void;
}

function IssueCard({ issue, view, onView, onAssigned }: IssueCardProps) {
  const cat = getCategoryConfig(issue.category);
  const urgent = isUrgent(issue.severity);
  const merged = getMergedReports(issue).length;
  const primaryCreatedAt = issue.reports[0]?.created_at ?? issue.created_at;

  if (view === "list") {
    return (
      <div className="group flex items-center gap-3 bg-white border border-slate-200 hover:border-slate-300 hover:shadow-sm rounded-xl p-3 transition-all">
        <div
          className="relative w-14 h-14 flex-shrink-0 rounded-lg overflow-hidden bg-slate-100 cursor-pointer"
          onClick={() => onView(issue)}
        >
          <PhotoOrFallback issue={issue} />
          {urgent && <div className="absolute top-0.5 right-0.5 w-2 h-2 bg-red-500 rounded-full ring-1 ring-white" />}
        </div>
        <div className={`w-0.5 h-9 rounded-full flex-shrink-0 ${cat.dot}`} />

        <div className="flex-1 min-w-0 cursor-pointer" onClick={() => onView(issue)}>
          <p className="text-sm font-medium text-slate-800 truncate leading-tight">{getTitle(issue)}</p>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            <span className={`text-[11px] ${cat.color} flex items-center gap-1`}>
              {cat.icon} {issue.category}
            </span>
            <span className="text-slate-300">·</span>
            <span className="text-[11px] text-slate-400">{getDisplayLocation(issue)}</span>
            {merged > 0 && <MergedBadge count={merged} />}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {urgent && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded">
              <AlertTriangle size={9} /> Urgent
            </span>
          )}
          <StatusBadge status={issue.status} />
          <TaskBoard issue={issue} onAssigned={onAssigned} />
          <span className="hidden md:block text-[10px] font-mono text-slate-400 w-14 text-right">
            {timeAgo(primaryCreatedAt)}
          </span>
          <Eye
            size={14}
            className="text-slate-400 group-hover:text-blue-500 transition-colors cursor-pointer"
            onClick={() => onView(issue)}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="group bg-white border border-slate-200 hover:border-slate-300 hover:shadow-md rounded-xl overflow-hidden transition-all flex flex-col">
      <div className="relative h-36 bg-slate-100 flex-shrink-0 cursor-pointer" onClick={() => onView(issue)}>
        <PhotoOrFallback issue={issue} />
        <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent" />
        {urgent && (
          <div className="absolute top-2 left-2 flex items-center gap-1 bg-red-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded">
            <AlertTriangle size={9} /> Urgent
          </div>
        )}
        {merged > 0 && (
          <div className="absolute top-2 right-2">
            <MergedBadge count={merged} />
          </div>
        )}
        <div className="absolute bottom-2 right-2">
          <StatusBadge status={issue.status} />
        </div>
      </div>

      <div className="p-3 flex flex-col flex-1">
        <div className="flex items-center gap-1.5 mb-2 flex-wrap">
          <span
            className={`inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded border ${cat.bg} ${cat.color}`}
          >
            {cat.icon} {cat.label}
          </span>
          <span className="text-[10px] font-mono text-slate-400 ml-auto">{getTicketNo(issue.id)}</span>
        </div>

        <h3
          className="text-sm font-semibold text-slate-800 leading-snug mb-1 line-clamp-2 cursor-pointer hover:text-blue-600 transition-colors"
          onClick={() => onView(issue)}
        >
          {getTitle(issue)}
        </h3>
        <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed flex-1">{getDescription(issue)}</p>

        <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-slate-100 gap-2">
          <span className="text-[10px] text-slate-400 flex items-center gap-1 truncate">
            <MapPin size={9} /> {getDisplayLocation(issue)}
          </span>
          <TaskBoard issue={issue} onAssigned={onAssigned} />
        </div>
      </div>
    </div>
  );
}

interface IssueListProps {
  issues: IssueDTO[];
  view: "grid" | "list";
  onView: (issue: IssueDTO) => void;
  onAssigned: (issueId: number, updatedIssue: IssueDTO) => void;
}

export default function IssueList({ issues, view, onView, onAssigned }: IssueListProps) {
  if (issues.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="w-12 h-12 rounded-2xl bg-slate-100 border border-slate-200 flex items-center justify-center mb-4">
          <Search size={20} className="text-slate-400" />
        </div>
        <p className="text-slate-700 font-medium mb-1">No issues found</p>
        <p className="text-sm text-slate-400">Adjust filters or search query</p>
      </div>
    );
  }

  if (view === "list") {
    return (
      <div className="flex flex-col gap-2">
        {issues.map((issue) => (
          <IssueCard key={issue.id} issue={issue} view="list" onView={onView} onAssigned={onAssigned} />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      {issues.map((issue) => (
        <IssueCard key={issue.id} issue={issue} view="grid" onView={onView} onAssigned={onAssigned} />
      ))}
    </div>
  );
}
