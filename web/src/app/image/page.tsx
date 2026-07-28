"use client";

import { useEffect, useState } from "react";
import ShellLayout from "@/components/shell-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { BackendCapabilities } from "@/lib/api-types";

const SIZES = ["1024x1024", "1024x1536", "1536x1024"] as const;

export default function ImagePage() {
  const [caps, setCaps] = useState<BackendCapabilities | null>(null);
  const [prompt, setPrompt] = useState("a serene lake at sunset, watercolor style");
  const [size, setSize] = useState<string>("1024x1024");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [b64, setB64] = useState<string | null>(null);

  useEffect(() => {
    api.capabilities().then(setCaps).catch(() => setCaps(null));
  }, []);

  const enabled = caps?.features?.image_generations;

  async function generate() {
    const text = prompt.trim();
    if (!text || loading || !enabled) return;
    setLoading(true);
    setError("");
    setB64(null);
    try {
      const res = await api.image(text, size);
      const img = res.data?.[0]?.b64_json;
      if (!img) throw new Error("响应无图像数据");
      setB64(img);
    } catch (e) {
      setError(e instanceof Error ? e.message : "生图失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ShellLayout title="生图">
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>图像生成</CardTitle>
          <CardDescription>
            {enabled
              ? caps?.data_plane === "upstream"
                ? "经 gateway → upstream Rust 数据面（PoW/SSE/estuary）"
                : "经 gateway → helper 桥接（需有效 pin 账号 token）"
              : "后端未开启 IMAGE_ENABLED=1"}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!enabled && (
            <p className="text-sm text-amber-600">
              请使用 <code className="text-xs">LOCAL_MODE=full bash scripts/local_bringup_wsl.sh</code> 启动。
            </p>
          )}
          <div className="space-y-2">
            <Label htmlFor="prompt">提示词</Label>
            <Input
              id="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={loading || !enabled}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="size">尺寸</Label>
            <select
              id="size"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={size}
              onChange={(e) => setSize(e.target.value)}
              disabled={loading || !enabled}
            >
              {SIZES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <Button onClick={generate} disabled={loading || !enabled}>
            {loading ? "生成中…" : "生成"}
          </Button>
          {error && <p className="text-sm text-destructive">{error}</p>}
          {b64 && (
            <div className="overflow-hidden rounded-lg border border-border">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`data:image/png;base64,${b64}`}
                alt="generated"
                className="mx-auto max-h-[480px] w-auto"
              />
            </div>
          )}
        </CardContent>
      </Card>
    </ShellLayout>
  );
}
