"use client";

import { AppSidebar } from "@/components/app-sidebar";
import { AuthGuard } from "@/components/auth-guard";
import { SiteHeader } from "@/components/site-header";
import type { Role } from "@/lib/api-types";

export default function ShellLayout({
  children,
  title = "控制台",
  roles,
}: {
  children: React.ReactNode;
  title?: string;
  roles?: Role[];
}) {
  return (
    <AuthGuard roles={roles}>
      <div className="flex min-h-screen bg-background">
        <AppSidebar />
        <div className="flex min-h-screen flex-1 flex-col">
          <SiteHeader title={title} />
          <main className="flex-1 overflow-auto p-6">{children}</main>
        </div>
      </div>
    </AuthGuard>
  );
}
