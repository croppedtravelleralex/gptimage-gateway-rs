"use client";

import ShellLayout from "@/components/shell-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const LOG_HINTS = [
  "data/runlogs/rust-gateway.log",
  "data/runlogs/helper.log",
  "data/runlogs/rust-gateway.pid",
  "data/runlogs/helper.pid",
];

export default function LogsPage() {
  return (
    <ShellLayout title="日志" roles={["admin"]}>
      <Card>
        <CardHeader>
          <CardTitle>本地运行日志</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            网关与 helper 由 <code className="text-xs">scripts/local_bringup_wsl.sh</code>{" "}
            写入以下路径（WSL 内可直接 tail）：
          </p>
          <ul className="list-disc space-y-1 pl-5 font-mono text-xs text-foreground">
            {LOG_HINTS.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
          <p>生产 runlog 脱敏校验：<code className="text-xs">python scripts/check_runlog_desense.py</code></p>
        </CardContent>
      </Card>
    </ShellLayout>
  );
}
