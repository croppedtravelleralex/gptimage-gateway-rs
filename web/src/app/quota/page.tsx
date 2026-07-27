"use client";

import { useState } from "react";
import ShellLayout from "@/components/shell-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { QuotaResponse } from "@/lib/api-types";

export default function QuotaPage() {
  const [data, setData] = useState<QuotaResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setData(await api.quota());
    } catch (e) {
      setError(e instanceof Error ? e.message : "刷新失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ShellLayout title="额度" roles={["admin"]}>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Quota Refresh</CardTitle>
            <Button onClick={refresh} disabled={loading} size="sm">
              {loading ? "刷新中…" : "刷新"}
            </Button>
          </CardHeader>
          <CardContent>
            {error && <p className="text-sm text-destructive">{error}</p>}
            {data && (
              <pre className="text-xs">{JSON.stringify(data, null, 2)}</pre>
            )}
          </CardContent>
        </Card>
    </ShellLayout>
  );
}
