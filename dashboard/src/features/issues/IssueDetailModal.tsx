import { AlertTriangle, Calendar, GitMerge, MapPin, User, X } from "lucide-react";
import { useState } from "react";
import type { IssueDTO, IssueStatus } from "@/types";
import { getCategoryConfig } from "./categoryConfig";
import { StatusBadge } from "./IssueList";
import {
  formatDate,
  getDescription,
  getDisplayLocation,
  getDisplayStatus,
  getMergedReports,
  getOriginalLocation,
  getPhotoUrl,
  getPrimaryReport,
  getTicketNo,
  getTitle,
  isUrgent,
  maskPhone,
} from "./issueView";
import TaskBoard from "@/features/tasks/TaskBoard";

const STATUSES: IssueStatus[] = ["open", "in_progress", "resolved"];

interface IssueDetailModalProps {
  issue: IssueDTO;
  onClose: () => void;
  onStatusChange: (issueId: number, status: IssueStatus) => void;
  onAssigned: (issueId: number, updatedIssue: IssueDTO) => void;
}

export default function IssueDetailModal({ issue, onClose, onStatusChange, onAssigned }: IssueDetailModalProps) {
  const [photoLoadFailed, setPhotoLoadFailed] = useState(false);
  const cat = getCategoryConfig(issue.category);
  const photo = getPhotoUrl(issue);
  const urgent = isUrgent(issue.severity);
  const merged = getMergedReports(issue);
  const primary = getPrimaryReport(issue);

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white border border-slate-200 rounded-xl w-full max-w-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        <div className="relative h-48 bg-slate-100 flex-shrink-0">
          {photo && !photoLoadFailed ? (
            <img
              src={photo}
              alt={getTitle(issue)}
              onError={() => setPhotoLoadFailed(true)}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className={`w-full h-full flex items-center justify-center ${cat.bg}`}>
              <span className={cat.color}>{cat.icon}</span>
            </div>
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent" />
          <button
            onClick={onClose}
            className="absolute top-3 right-3 bg-white/80 hover:bg-white border border-slate-200 rounded-lg p-1.5 text-slate-500 hover:text-slate-800 transition-colors"
          >
            <X size={15} />
          </button>
          {urgent && (
            <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-red-500 text-white text-xs font-semibold px-2.5 py-1 rounded-md">
              <AlertTriangle size={11} /> URGENT
            </div>
          )}
        </div>

        <div className="p-5 overflow-y-auto">
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded border ${cat.bg} ${cat.color}`}>
                {cat.icon} {issue.category}
              </span>
              <StatusBadge status={issue.status} />
              {merged.length > 0 && (
                <div className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-purple-600 bg-purple-50 border border-purple-200 px-1.5 py-0.5 rounded">
                  <GitMerge size={10} /> {merged.length + 1} reports
                </div>
              )}
              <span className="text-xs font-mono text-slate-400 ml-auto">{getTicketNo(issue.id)}</span>
            </div>
            <h2 className="text-lg font-semibold text-slate-900 leading-tight">{getTitle(issue)}</h2>
          </div>

          <p className="text-sm text-slate-600 leading-relaxed mb-5">{getDescription(issue)}</p>

          {merged.length > 0 && (
            <div className="mb-5 bg-purple-50 border border-purple-200 rounded-xl p-3">
              <p className="text-xs font-semibold text-purple-700 flex items-center gap-1.5 mb-2">
                <GitMerge size={12} /> Merged citizen reports
              </p>
              <div className="flex flex-col gap-1.5">
                {primary && (
                  <div className="flex items-center gap-2 text-xs text-slate-600">
                    <User size={11} className="text-slate-400" />
                    <span className="font-medium">{maskPhone(primary.phone_number)}</span>
                    <span className="text-slate-300">·</span>
                    <span className="text-slate-400 font-mono">{formatDate(primary.created_at)}</span>
                    <span className="text-[10px] bg-blue-100 border border-blue-200 text-blue-600 px-1.5 py-0.5 rounded ml-auto">
                      Primary
                    </span>
                  </div>
                )}
                {merged.map((r) => (
                  <div key={r.id} className="flex items-center gap-2 text-xs text-slate-600">
                    <User size={11} className="text-slate-400" />
                    <span>{maskPhone(r.phone_number)}</span>
                    <span className="text-slate-300">·</span>
                    <span className="text-slate-400 font-mono">{formatDate(r.created_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2.5 mb-5">
            {[
              { icon: <MapPin size={12} />, label: "District", value: getDisplayLocation(issue) },
              {
                icon: <User size={12} />,
                label: "Primary reporter",
                value: primary ? maskPhone(primary.phone_number) : "Unknown",
              },
              {
                icon: <Calendar size={12} />,
                label: "Submitted",
                value: formatDate(primary?.created_at ?? issue.created_at),
              },
              {
                icon: <MapPin size={12} />,
                label: "Coordinates",
                value: `${issue.latitude.toFixed(4)}, ${issue.longitude.toFixed(4)}`,
              },
            ].map(({ icon, label, value }) => (
              <div key={label} className="bg-slate-50 rounded-lg p-3 border border-slate-100">
                <div className="flex items-center gap-1.5 text-slate-400 text-[10px] mb-1 uppercase tracking-wide">
                  {icon} {label}
                </div>
                <p className="text-sm text-slate-800 font-medium">{value}</p>
              </div>
            ))}
          </div>

          {getOriginalLocation(issue) &&
            getOriginalLocation(issue) !== getDisplayLocation(issue) && (
              <p className="text-xs text-slate-400 mb-5">
                Citizen location text: {getOriginalLocation(issue)}
              </p>
            )}

          <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-slate-100">
            <div>
              <p className="text-[10px] text-slate-400 uppercase tracking-widest mb-1.5">Status</p>
              <div className="flex gap-2">
                {STATUSES.map((s) => (
                  <button
                    key={s}
                    onClick={() => onStatusChange(issue.id, s)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                      issue.status === s
                        ? "bg-blue-600 border-blue-600 text-white"
                        : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {getDisplayStatus(s)}
                  </button>
                ))}
              </div>
            </div>
            <div className="ml-auto">
              <p className="text-[10px] text-slate-400 uppercase tracking-widest mb-1.5">Field Assignment</p>
              <TaskBoard issue={issue} onAssigned={onAssigned} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
