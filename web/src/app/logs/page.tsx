"use client";

import ShellLayout from "@/components/shell-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LogsPage() {
  return (
    <ShellLayout title="日志" roles={["admin"]}>
        <Card>
          <CardHeader>
            <CardTitle>Runlogs 元数据（占位）</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            读取 data/runlogs 脱敏元数据；不含 secret。
          </CardContent>
        </Card>
    </ShellLayout>
  );
}
