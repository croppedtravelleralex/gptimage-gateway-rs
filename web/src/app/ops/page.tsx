"use client";

import { useCallback, useEffect, useState } from "react";
import ShellLayout from "@/components/shell-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { AdminStatusResponse, HealthResponse } from "@/lib/api-types";

export default function OpsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<AdminStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [h, s] = await Promise.all([api.health(), api.adminStatus()]);
      setHealth(h);
      setStatus(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <ShellLayout title="运维" roles={["admin"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">运行时状态</h2>
          <Button size="sm" onClick={refresh} disabled={loading}>
            {loading ? "刷新中…" : "刷新"}
          </Button>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">/health</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="max-h-80 overflow-auto text-xs">
                {health ? JSON.stringify(health, null, 2) : "—"}
              </pre>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">/api/admin/status</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="max-h-80 overflow-auto text-xs">
                {status ? JSON.stringify(status, null, 2) : "—"}
              </pre>
            </CardContent>
          </Card>
        </div>
      </div>
    </ShellLayout>
  );
}
