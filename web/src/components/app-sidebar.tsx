"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ImageIcon,
  LayoutDashboard,
  LayoutGrid,
  MessageSquare,
  Settings,
  Users,
  Gauge,
  ScrollText,
  Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

const adminLinks: Array<{
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  badge?: string;
}> = [
  { href: "/dashboard", label: "概览", icon: LayoutDashboard },
  { href: "/accounts", label: "号池", icon: Users },
  { href: "/quota", label: "额度", icon: Gauge },
  { href: "/settings", label: "用户", icon: Settings },
  { href: "/ops", label: "运维", icon: Wrench },
  { href: "/logs", label: "日志", icon: ScrollText },
];

const memberLinks: Array<{
  href: string;
  label: string;
  icon: typeof MessageSquare;
  badge?: string;
}> = [
  { href: "/showcase", label: "验收看板", icon: LayoutGrid },
  { href: "/chat", label: "对话", icon: MessageSquare },
  { href: "/image", label: "生图", icon: ImageIcon },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const links = isAdmin ? [...adminLinks, ...memberLinks] : memberLinks;

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-border bg-sidebar text-sidebar-foreground">
      <div className="flex h-14 items-center border-b border-border px-4">
        <span className="text-sm font-semibold tracking-tight">Gateway RS</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {links.map(({ href, label, icon: Icon, badge }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              pathname === href &&
                "bg-sidebar-primary text-sidebar-primary-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            <span className="flex-1">{label}</span>
            {badge && (
              <span className="rounded bg-accent/20 px-1.5 py-0.5 text-[10px] text-accent-foreground">
                {badge}
              </span>
            )}
          </Link>
        ))}
      </nav>
      <div className="border-t border-border p-3 text-xs text-muted-foreground">
        {user?.username} · {user?.role}
      </div>
    </aside>
  );
}
