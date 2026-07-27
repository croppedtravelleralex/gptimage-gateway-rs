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

  async function load(refresh = false) {
    setLoading(true);
    setError("");
    try {
      setData(refresh ? await api.quotaRefresh() : await api.quota());
    } catch (e) {
      setError(e instanceof Error ? e.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ShellLayout title="额度" roles={["admin"]}>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Quota</CardTitle>
          <div className="flex gap-2">
            <Button onClick={() => load(false)} disabled={loading} size="sm" variant="outline">
              查询
            </Button>
            <Button onClick={() => load(true)} disabled={loading} size="sm">
              {loading ? "刷新中…" : "强制刷新"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {error && <p className="text-sm text-destructive">{error}</p>}
          {data && (
            <pre className="text-xs">{JSON.stringify(data, null, 2)}</pre>
          )}
          {!data && !error && (
            <p className="text-sm text-muted-foreground">点击查询获取 pin 账号配额。</p>
          )}
        </CardContent>
      </Card>
    </ShellLayout>
  );
}
