"use client";

import ShellLayout from "@/components/shell-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function OpsPage() {
  return (
    <ShellLayout title="运维" roles={["admin"]}>
        <Card>
          <CardHeader>
            <CardTitle>Phase D RCA（占位）</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            未来将接入 llm_ops / risk dashboard 只读视图。
          </CardContent>
        </Card>
    </ShellLayout>
  );
}
