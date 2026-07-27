"use client";

import { useEffect, useState } from "react";
import ShellLayout from "@/components/shell-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { BackendCapabilities } from "@/lib/api-types";

export default function ImagePage() {
  const [caps, setCaps] = useState<BackendCapabilities | null>(null);

  useEffect(() => {
    api.capabilities().then(setCaps).catch(() => setCaps(null));
  }, []);

  const enabled = caps?.features?.image_generations;

  return (
    <ShellLayout title="生图">
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>图像生成</CardTitle>
          <CardDescription>
            本阶段暂不接入生图执行路径，后续由后端管线统一对接。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="rounded-lg border border-dashed border-border bg-muted/40 p-6 text-center">
            <p className="font-medium text-foreground">
              {enabled ? "后端已标记可用" : "功能暂未开放"}
            </p>
            <p className="mt-2 text-muted-foreground">
              Phase B 已补齐 edits / estuary / fixtures 契约；运行时生图将在
              `IMAGE_ENABLED=1` 且后端接入后启用。
            </p>
          </div>
          {caps?.deferred && (
            <div>
              <p className="mb-2 font-medium">延后项</p>
              <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                {caps.deferred.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    </ShellLayout>
  );
}
