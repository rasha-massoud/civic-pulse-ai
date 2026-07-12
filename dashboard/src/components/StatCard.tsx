interface StatCardProps {
  label: string;
  value: number | string;
  sub: string;
  accent: string;
}

export default function StatCard({ label, value, sub, accent }: StatCardProps) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
      <p className="text-[10px] text-slate-400 uppercase tracking-widest mb-1">{label}</p>
      <p className={`text-3xl font-bold ${accent}`} style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
        {value}
      </p>
      <p className="text-[11px] text-slate-400 mt-1">{sub}</p>
    </div>
  );
}
