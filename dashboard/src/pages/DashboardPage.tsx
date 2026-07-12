import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Bell,
  CheckCircle2,
  ClipboardList,
  Clock,
  Filter,
  LayoutGrid,
  List,
  LogOut,
  Map as MapIcon,
  RefreshCw,
  Search,
  User,
  X,
} from "lucide-react";
import type { IssueDTO, IssueStatus } from "@/types";
import { listIssues, updateIssueStatus } from "@/api/issues";
import { CATEGORIES, CATEGORY_CONFIG, type Category } from "@/features/issues/categoryConfig";
import { getDisplayStatus, getTicketNo, getTitle, isUrgent } from "@/features/issues/issueView";
import { useAuth } from "@/features/auth/AuthContext";
import IssueList from "@/features/issues/IssueList";
import IssueMap from "@/features/issues/IssueMap";
import IssueDetailModal from "@/features/issues/IssueDetailModal";
import StatCard from "@/components/StatCard";
import StepsPanel from "@/components/StepsPanel";

type MainView = "issues" | "map";
type ViewMode = "grid" | "list";

export default function DashboardPage() {
  const { logout } = useAuth();
  const [issues, setIssues] = useState<IssueDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [selectedCategory, setSelectedCategory] = useState<Category | "All">("All");
  const [selectedStatus, setSelectedStatus] = useState<IssueStatus | "All">("All");
  const [urgentOnly, setUrgentOnly] = useState(false);
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [mainView, setMainView] = useState<MainView>("issues");
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest">("newest");
  const [activeIssueId, setActiveIssueId] = useState<number | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listIssues()
      .then((data) => {
        if (!cancelled) setIssues(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load issues");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const list = issues.filter((issue) => {
      if (selectedCategory !== "All" && issue.category !== selectedCategory) return false;
      if (selectedStatus !== "All" && issue.status !== selectedStatus) return false;
      if (urgentOnly && !isUrgent(issue.severity)) return false;
      if (search) {
        const q = search.toLowerCase();
        const matches =
          getTitle(issue).toLowerCase().includes(q) ||
          issue.district.toLowerCase().includes(q) ||
          getTicketNo(issue.id).toLowerCase().includes(q);
        if (!matches) return false;
      }
      return true;
    });
    return [...list].sort((a, b) => {
      const ta = new Date(a.created_at).getTime();
      const tb = new Date(b.created_at).getTime();
      return sortOrder === "newest" ? tb - ta : ta - tb;
    });
  }, [issues, selectedCategory, selectedStatus, urgentOnly, search, sortOrder]);

  const stats = useMemo(
    () => ({
      total: issues.length,
      open: issues.filter((i) => i.status === "open").length,
      inProgress: issues.filter((i) => i.status === "in_progress").length,
      resolved: issues.filter((i) => i.status === "resolved").length,
      urgent: issues.filter((i) => isUrgent(i.severity)).length,
    }),
    [issues],
  );

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    CATEGORIES.forEach((c) => {
      counts[c] = issues.filter((i) => i.category === c).length;
    });
    return counts;
  }, [issues]);

  const activeIssue = issues.find((i) => i.id === activeIssueId) ?? null;

  function handleAssigned(issueId: number, updatedIssue: IssueDTO) {
    setIssues((prev) => prev.map((i) => (i.id === issueId ? updatedIssue : i)));
  }

  async function handleStatusChange(issueId: number, status: IssueStatus) {
    try {
      const updated = await updateIssueStatus(issueId, status);
      setIssues((prev) => prev.map((i) => (i.id === issueId ? updated : i)));
    } catch {
      setActionError("Couldn't save, please try again.");
    }
  }

  function handleView(issue: IssueDTO) {
    setActiveIssueId(issue.id);
  }

  return (
    <div className="h-screen flex bg-slate-50 overflow-hidden" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      {sidebarOpen && <div className="fixed inset-0 z-40 bg-black/30 lg:hidden" onClick={() => setSidebarOpen(false)} />}

      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 h-full z-50 w-56 bg-[#EEF2F7] border-r border-slate-200 flex flex-col transition-transform duration-300 lg:translate-x-0 lg:sticky lg:top-0 lg:h-screen lg:z-auto ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-slate-200">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
            <AlertCircle size={14} className="text-white" />
          </div>
          <div>
            <p
              className="text-sm font-bold text-slate-800 leading-tight tracking-wide"
              style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
            >
              CIVICPULSE
            </p>
            <p className="text-[10px] text-slate-400">Admin Console</p>
          </div>
        </div>

        <nav className="flex-1 px-2.5 py-3.5 overflow-y-auto">
          <p className="text-[9px] uppercase tracking-widest text-slate-400 px-2 mb-1.5 font-semibold">Views</p>
          {(
            [
              { key: "issues", label: "Issues", icon: <ClipboardList size={13} /> },
              { key: "map", label: "Map View", icon: <MapIcon size={13} /> },
            ] as const
          ).map(({ key, label, icon }) => (
            <button
              key={key}
              onClick={() => setMainView(key)}
              className={`w-full flex items-center gap-2 px-2 py-2 rounded-lg text-sm mb-0.5 transition-colors ${
                mainView === key ? "bg-blue-100 text-blue-700" : "text-slate-500 hover:bg-slate-200 hover:text-slate-800"
              }`}
            >
              {icon} {label}
            </button>
          ))}

          <div className="my-3 border-t border-slate-200" />

          <p className="text-[9px] uppercase tracking-widest text-slate-400 px-2 mb-1.5 font-semibold">Status</p>
          {(["All", "open", "in_progress", "resolved"] as (IssueStatus | "All")[]).map((s) => {
            const count = s === "All" ? stats.total : s === "open" ? stats.open : s === "in_progress" ? stats.inProgress : stats.resolved;
            const icons = {
              All: <LayoutGrid size={13} />,
              open: <Clock size={13} />,
              in_progress: <RefreshCw size={13} />,
              resolved: <CheckCircle2 size={13} />,
            };
            const active = selectedStatus === s && selectedCategory === "All" && !urgentOnly;
            const label = s === "All" ? "All Issues" : getDisplayStatus(s);
            return (
              <button
                key={s}
                onClick={() => {
                  setSelectedStatus(s);
                  setSelectedCategory("All");
                  setUrgentOnly(false);
                  setMainView("issues");
                }}
                className={`w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-xs mb-0.5 transition-colors ${
                  active ? "bg-blue-100 text-blue-700" : "text-slate-500 hover:bg-slate-200 hover:text-slate-800"
                }`}
              >
                <span className="flex items-center gap-2">
                  {icons[s]} {label}
                </span>
                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${active ? "bg-blue-200 text-blue-700" : "bg-slate-200 text-slate-500"}`}>
                  {count}
                </span>
              </button>
            );
          })}

          <button
            onClick={() => {
              setUrgentOnly(true);
              setSelectedStatus("All");
              setSelectedCategory("All");
              setMainView("issues");
            }}
            className={`w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-xs mb-3 mt-0.5 transition-colors ${
              urgentOnly ? "bg-red-100 text-red-700" : "text-slate-500 hover:bg-slate-200 hover:text-slate-800"
            }`}
          >
            <span className="flex items-center gap-2">
              <AlertTriangle size={13} /> Urgent Only
            </span>
            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${urgentOnly ? "bg-red-200 text-red-700" : "bg-slate-200 text-slate-500"}`}>
              {stats.urgent}
            </span>
          </button>

          <p className="text-[9px] uppercase tracking-widest text-slate-400 px-2 mb-1.5 font-semibold">Category</p>
          {CATEGORIES.map((cat) => {
            const cfg = CATEGORY_CONFIG[cat];
            const active = selectedCategory === cat;
            return (
              <button
                key={cat}
                onClick={() => {
                  setSelectedCategory(cat);
                  setSelectedStatus("All");
                  setUrgentOnly(false);
                  setMainView("issues");
                }}
                className={`w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-xs mb-0.5 transition-colors ${
                  active ? `${cfg.bg} ${cfg.color}` : "text-slate-500 hover:bg-slate-200 hover:text-slate-800"
                }`}
              >
                <span className="flex items-center gap-2">
                  {cfg.icon} {cat}
                </span>
                <span className="font-mono text-[10px]">{categoryCounts[cat]}</span>
              </button>
            );
          })}
        </nav>

        <div className="px-4 py-3.5 border-t border-slate-200">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-blue-100 border border-blue-200 flex items-center justify-center">
              <User size={12} className="text-blue-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-700">Admin User</p>
              <p className="text-[10px] text-slate-400">City Operations</p>
            </div>
            <button
              onClick={logout}
              title="Log out"
              className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition-colors"
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-sm border-b border-slate-200 flex items-center gap-2.5 px-4 py-2.5">
          <button className="lg:hidden text-slate-400 hover:text-slate-700" onClick={() => setSidebarOpen(true)}>
            <Filter size={17} />
          </button>

          <div className="flex-1 relative max-w-sm">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search title, district, ticket…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-blue-400 transition-colors"
            />
            {search && (
              <button onClick={() => setSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700">
                <X size={11} />
              </button>
            )}
          </div>

          <button
            onClick={() => setSortOrder((v) => (v === "newest" ? "oldest" : "newest"))}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 hover:bg-slate-100 transition-colors"
          >
            {sortOrder === "newest" ? <ArrowDown size={13} /> : <ArrowUp size={13} />}
            <span className="hidden sm:inline">{sortOrder === "newest" ? "Newest" : "Oldest"}</span>
            <ArrowUpDown size={11} className="text-slate-400" />
          </button>

          <div className="ml-auto flex items-center gap-2">
            <button className="relative p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors">
              <Bell size={15} />
              <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-red-500 rounded-full" />
            </button>
            {mainView === "issues" && (
              <div className="flex items-center gap-0.5 bg-slate-100 border border-slate-200 rounded-lg p-1">
                <button
                  onClick={() => setViewMode("grid")}
                  className={`p-1 rounded transition-colors ${viewMode === "grid" ? "bg-white shadow-sm text-blue-600" : "text-slate-400 hover:text-slate-700"}`}
                >
                  <LayoutGrid size={13} />
                </button>
                <button
                  onClick={() => setViewMode("list")}
                  className={`p-1 rounded transition-colors ${viewMode === "list" ? "bg-white shadow-sm text-blue-600" : "text-slate-400 hover:text-slate-700"}`}
                >
                  <List size={13} />
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="flex-1 p-4 md:p-5 overflow-y-auto">
          <div className="mb-5">
            <h1
              className="text-2xl font-bold text-slate-900"
              style={{ fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.02em" }}
            >
              {mainView === "map"
                ? "MAP VIEW"
                : selectedCategory !== "All"
                  ? selectedCategory.toUpperCase()
                  : urgentOnly
                    ? "URGENT ISSUES"
                    : selectedStatus !== "All"
                      ? `${getDisplayStatus(selectedStatus).toUpperCase()} ISSUES`
                      : "ALL ISSUES"}
            </h1>
            {mainView === "issues" && (
              <p className="text-xs text-slate-400">
                {filtered.length} issue{filtered.length !== 1 ? "s" : ""}
                {search ? ` matching "${search}"` : ""} · sorted {sortOrder === "newest" ? "newest first" : "oldest first"}
              </p>
            )}
          </div>

          {actionError && (
            <div className="flex items-center justify-between gap-2 mb-4 bg-red-50 border border-red-200 text-red-600 text-xs px-3 py-2 rounded-lg">
              <span>{actionError}</span>
              <button onClick={() => setActionError(null)}>
                <X size={12} />
              </button>
            </div>
          )}

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
            <StatCard label="Total Issues" value={stats.total} sub="All categories" accent="text-slate-800" />
            <StatCard label="Open" value={stats.open} sub="Awaiting action" accent="text-slate-500" />
            <StatCard label="In Progress" value={stats.inProgress} sub="Being addressed" accent="text-blue-600" />
            <StatCard
              label="Resolved"
              value={stats.resolved}
              sub={stats.total > 0 ? `${Math.round((stats.resolved / stats.total) * 100)}% resolution rate` : "No issues yet"}
              accent="text-emerald-600"
            />
          </div>

          <StepsPanel issues={issues} />

          {(urgentOnly || selectedCategory !== "All" || selectedStatus !== "All") && (
            <div className="flex items-center gap-2 mb-4 flex-wrap">
              {urgentOnly && (
                <span className="inline-flex items-center gap-1.5 bg-red-50 border border-red-200 text-red-600 text-xs px-2.5 py-1 rounded-full">
                  <AlertTriangle size={10} /> Urgent{" "}
                  <button onClick={() => setUrgentOnly(false)}>
                    <X size={10} />
                  </button>
                </span>
              )}
              {selectedCategory !== "All" && (
                <span
                  className={`inline-flex items-center gap-1.5 border text-xs px-2.5 py-1 rounded-full ${CATEGORY_CONFIG[selectedCategory].bg} ${CATEGORY_CONFIG[selectedCategory].color}`}
                >
                  {CATEGORY_CONFIG[selectedCategory].icon} {selectedCategory}
                  <button onClick={() => setSelectedCategory("All")}>
                    <X size={10} />
                  </button>
                </span>
              )}
              {selectedStatus !== "All" && (
                <span className="inline-flex items-center gap-1.5 bg-blue-50 border border-blue-200 text-blue-600 text-xs px-2.5 py-1 rounded-full">
                  {getDisplayStatus(selectedStatus)}{" "}
                  <button onClick={() => setSelectedStatus("All")}>
                    <X size={10} />
                  </button>
                </span>
              )}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-24 text-sm text-slate-400">Loading issues…</div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <p className="text-red-600 font-medium mb-1">Couldn't load issues</p>
              <p className="text-sm text-slate-400">{error}</p>
            </div>
          ) : mainView === "map" ? (
            <IssueMap issues={filtered} onView={handleView} />
          ) : (
            <IssueList issues={filtered} view={viewMode} onView={handleView} onAssigned={handleAssigned} />
          )}
        </main>
      </div>

      {activeIssue && (
        <IssueDetailModal
          issue={activeIssue}
          onClose={() => setActiveIssueId(null)}
          onStatusChange={handleStatusChange}
          onAssigned={handleAssigned}
        />
      )}
    </div>
  );
}
