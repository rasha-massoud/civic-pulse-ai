import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import type { IssueDTO } from "@/types";
import { getPinColor, getTitle, isUrgent } from "./issueView";

const BEIRUT_CENTER: [number, number] = [33.8938, 35.5018];

function makePin(color: string, size = 14) {
  return L.divIcon({
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};border:2.5px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.35);"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    className: "",
  });
}

interface IssueMapProps {
  issues: IssueDTO[];
  onView: (issue: IssueDTO) => void;
}

export default function IssueMap({ issues, onView }: IssueMapProps) {
  const center: [number, number] =
    issues.length > 0
      ? [
          issues.reduce((sum, i) => sum + i.latitude, 0) / issues.length,
          issues.reduce((sum, i) => sum + i.longitude, 0) / issues.length,
        ]
      : BEIRUT_CENTER;

  return (
    <div className="relative rounded-xl overflow-hidden border border-slate-200 shadow-sm" style={{ height: 520 }}>
      <MapContainer center={center} zoom={13} style={{ height: "100%", width: "100%" }} zoomControl={false}>
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com">CARTO</a>'
        />
        {issues.map((issue) => {
          const color = getPinColor(issue);
          const size = isUrgent(issue.severity) ? 18 : 14;
          return (
            <Marker key={issue.id} position={[issue.latitude, issue.longitude]} icon={makePin(color, size)}>
              <Popup closeButton={false}>
                <div
                  style={{
                    background: "#fff",
                    border: "1px solid #e2e8f0",
                    borderRadius: 10,
                    padding: "10px 12px",
                    minWidth: 220,
                    maxWidth: 260,
                    fontFamily: "Inter, system-ui, sans-serif",
                    color: "#0f172a",
                    boxShadow: "0 4px 16px rgba(0,0,0,0.1)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
                    <span
                      style={{
                        fontSize: 10,
                        color: "#64748b",
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        fontWeight: 600,
                      }}
                    >
                      {issue.category}
                    </span>
                    {isUrgent(issue.severity) && (
                      <span
                        style={{
                          marginLeft: "auto",
                          fontSize: 9,
                          background: "#fef2f2",
                          color: "#dc2626",
                          border: "1px solid #fecaca",
                          padding: "1px 5px",
                          borderRadius: 4,
                          fontWeight: 700,
                          textTransform: "uppercase",
                        }}
                      >
                        Urgent
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.4, marginBottom: 6, color: "#0f172a" }}>
                    {getTitle(issue)}
                  </p>
                  <p style={{ fontSize: 11, color: "#64748b", marginBottom: 8 }}>{issue.district}</p>
                  <button
                    onClick={() => onView(issue)}
                    style={{
                      width: "100%",
                      background: "#eff6ff",
                      border: "1px solid #bfdbfe",
                      color: "#1d4ed8",
                      borderRadius: 7,
                      padding: "5px 0",
                      fontSize: 11,
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    View Details
                  </button>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      <div className="absolute bottom-3 left-3 z-[400] bg-white/95 backdrop-blur border border-slate-200 rounded-xl px-3 py-2.5 flex flex-col gap-1.5 shadow-sm">
        <p className="text-[9px] text-slate-400 uppercase tracking-widest font-semibold mb-0.5">Pin Legend</p>
        {[
          { color: "#EF4444", label: "Urgent" },
          { color: "#3B82F6", label: "In Progress" },
          { color: "#9CA3AF", label: "Open" },
          { color: "#10B981", label: "Resolved" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full border-[1.5px] border-white flex-shrink-0 shadow-sm"
              style={{ background: color }}
            />
            <span className="text-[11px] text-slate-600">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
