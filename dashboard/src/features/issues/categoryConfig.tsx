import type { ReactNode } from "react";
import { Construction, Trash2, Droplets, Lightbulb, AlertOctagon, Zap, Layers } from "lucide-react";

export type Category =
  | "Pothole"
  | "Garbage Overflow"
  | "Water Leak"
  | "Broken Streetlight"
  | "Damaged Sidewalk"
  | "Electrical Hazard"
  | "Other";

export const CATEGORIES: Category[] = [
  "Pothole",
  "Garbage Overflow",
  "Water Leak",
  "Broken Streetlight",
  "Damaged Sidewalk",
  "Electrical Hazard",
  "Other",
];

interface CategoryConfig {
  icon: ReactNode;
  color: string;
  bg: string;
  dot: string;
  label: string;
}

export const CATEGORY_CONFIG: Record<Category, CategoryConfig> = {
  Pothole: {
    icon: <Construction size={13} />,
    color: "text-amber-600",
    bg: "bg-amber-50 border-amber-200",
    dot: "bg-amber-500",
    label: "Pothole",
  },
  "Garbage Overflow": {
    icon: <Trash2 size={13} />,
    color: "text-emerald-600",
    bg: "bg-emerald-50 border-emerald-200",
    dot: "bg-emerald-500",
    label: "Garbage",
  },
  "Water Leak": {
    icon: <Droplets size={13} />,
    color: "text-sky-600",
    bg: "bg-sky-50 border-sky-200",
    dot: "bg-sky-500",
    label: "Water Leak",
  },
  "Broken Streetlight": {
    icon: <Lightbulb size={13} />,
    color: "text-yellow-600",
    bg: "bg-yellow-50 border-yellow-200",
    dot: "bg-yellow-500",
    label: "Streetlight",
  },
  "Damaged Sidewalk": {
    icon: <AlertOctagon size={13} />,
    color: "text-orange-600",
    bg: "bg-orange-50 border-orange-200",
    dot: "bg-orange-500",
    label: "Sidewalk",
  },
  "Electrical Hazard": {
    icon: <Zap size={13} />,
    color: "text-red-600",
    bg: "bg-red-50 border-red-200",
    dot: "bg-red-500",
    label: "Electrical",
  },
  Other: {
    icon: <Layers size={13} />,
    color: "text-purple-600",
    bg: "bg-purple-50 border-purple-200",
    dot: "bg-purple-500",
    label: "Other",
  },
};

export function getCategoryConfig(category: string): CategoryConfig {
  return CATEGORY_CONFIG[category as Category] ?? CATEGORY_CONFIG.Other;
}

export type Department =
  | "Roads & Maintenance Department"
  | "Waste Management Department"
  | "Ministry of Electricity";

export const DEPARTMENTS: Department[] = [
  "Roads & Maintenance Department",
  "Waste Management Department",
  "Ministry of Electricity",
];

export const DEPT_CONFIG: Record<Department, { color: string; short: string }> = {
  "Roads & Maintenance Department": { color: "text-amber-600", short: "Roads & Maint." },
  "Waste Management Department": { color: "text-emerald-600", short: "Waste Mgmt." },
  "Ministry of Electricity": { color: "text-yellow-600", short: "Min. Electricity" },
};

export function getRecommendedDepartment(category: string): Department {
  switch (category) {
    case "Garbage Overflow":
      return "Waste Management Department";
    case "Electrical Hazard":
    case "Broken Streetlight":
      return "Ministry of Electricity";
    default:
      return "Roads & Maintenance Department";
  }
}
