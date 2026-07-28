"use client";

import { useEffect, useState } from "react";
import ShellLayout from "@/components/shell-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { BackendCapabilities, HealthResponse } from "@/lib/api-types";

function FeatureRow({ name, on }: { name: string; on?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-border py-2 text-sm last:border-0">
      <span>{name}</span>
      <span className={on ? "text-accent" : "text-muted-foreground"}>
        {on ? "可用" : "延后"}
      </span>
    </div>
  );
}

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [caps, setCaps] = useState<BackendCapabilities | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.health(), api.capabilities()])
      .then(([h, c]) => {
        setHealth(h);
        setCaps(c);
      })
      .catch((e) => setError(e.message));
  }, []);

  const f = caps?.features;

  return (
    <ShellLayout title="概览" roles={["admin"]}>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Gateway 健康</CardTitle>
          </CardHeader>
          <CardContent>
            {error && <p className="text-sm text-destructive">{error}</p>}
            {health && (
              <pre className="max-h-64 overflow-auto text-xs">
                {JSON.stringify(health, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>后端能力</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-xs text-muted-foreground">
              wave: {caps?.wave || "—"} · data_plane: {caps?.data_plane || "—"} · helper:{" "}
              {caps?.helper_ok ? "ok" : "n/a"}
            </p>
            <FeatureRow name="鉴权" on={f?.auth} />
            <FeatureRow name="对话" on={f?.chat} />
            <FeatureRow name="流式 SSE" on={f?.chat_stream || f?.stream_chat} />
            <FeatureRow name="生图" on={f?.image_generations} />
            <FeatureRow name="图生图 edits" on={f?.image_edits} />
            <FeatureRow name="estuary 下载" on={f?.estuary_download} />
          </CardContent>
        </Card>
      </div>
    </ShellLayout>
  );
}
