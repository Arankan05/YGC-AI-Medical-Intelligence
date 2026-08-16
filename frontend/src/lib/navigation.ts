import {
  Activity,
  AlertTriangle,
  Beaker,
  FileText,
  LayoutDashboard,
  MapPin,
  MessageCircle,
  Pill,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  User,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

/** Figma: App Sidebar (node 12:2) — groups MEDICAL RECORDS and ASSISTANCE. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "MEDICAL RECORDS",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { label: "Documents", href: "/documents", icon: FileText },
      { label: "Timeline", href: "/timeline", icon: Activity },
      { label: "Medications", href: "/medications", icon: Pill },
      {
        label: "Medication Safety",
        href: "/medication-safety",
        icon: ShieldCheck,
      },
      { label: "Lab Results", href: "/lab-results", icon: Beaker },
      { label: "Allergies", href: "/allergies", icon: ShieldAlert },
      { label: "AI Findings", href: "/findings", icon: AlertTriangle },
      { label: "AI Analysis", href: "/analyses", icon: Sparkles },
    ],
  },
  {
    label: "ASSISTANCE",
    items: [
      { label: "Ask AI", href: "/ask-ai", icon: MessageCircle },
      { label: "Find Healthcare Provider", href: "/providers", icon: MapPin },
      { label: "Profile", href: "/profile", icon: User },
    ],
  },
];
