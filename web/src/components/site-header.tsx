"use client";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";

export function SiteHeader({ title }: { title: string }) {
  const { logout } = useAuth();
  const router = useRouter();

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background px-6">
      <h1 className="text-lg font-semibold">{title}</h1>
      <Button
        variant="outline"
        size="sm"
        onClick={async () => {
          await logout();
          router.push("/login");
        }}
      >
        退出
      </Button>
    </header>
  );
}
