"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ShellLayout from "@/components/shell-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { BackendCapabilities, HealthResponse } from "@/lib/api-types";
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

const SIZES = ["1024x1024", "1024x1536", "1536x1024"] as const;

type CheckState = "pending" | "pass" | "fail" | "skip";

interface GalleryItem {
  id: string;
  prompt: string;
  size: string;
  b64: string;
  at: string;
}

function CheckRow({
  label,
  state,
  detail,
}: {
  label: string;
  state: CheckState;
  detail?: string;
}) {
  const Icon =
    state === "pass"
      ? CheckCircle2
      : state === "fail"
        ? XCircle
        : state === "pending"
          ? Loader2
          : Circle;
  const color =
    state === "pass"
      ? "text-emerald-600"
      : state === "fail"
        ? "text-destructive"
        : "text-muted-foreground";
  return (
    <div className="flex items-start gap-2 border-b border-border py-2 text-sm last:border-0">
      <Icon
        className={`mt-0.5 h-4 w-4 shrink-0 ${color} ${state === "pending" ? "animate-spin" : ""}`}
      />
      <div className="min-w-0 flex-1">
        <div className="font-medium">{label}</div>
        {detail && (
          <div className="truncate text-xs text-muted-foreground">{detail}</div>
        )}
      </div>
    </div>
  );
}

export default function ShowcasePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [caps, setCaps] = useState<BackendCapabilities | null>(null);
  const [loadError, setLoadError] = useState("");
  const [prompt, setPrompt] = useState(
    "a minimalist gateway icon, flat vector, teal accent on dark background",
  );
  const [size, setSize] = useState<string>("1024x1024");
  const [loading, setLoading] = useState(false);
  const [imageError, setImageError] = useState("");
  const [gallery, setGallery] = useState<GalleryItem[]>([]);
  const [imageTestState, setImageTestState] = useState<CheckState>("skip");

  const refresh = useCallback(async () => {
    setLoadError("");
    try {
      const [h, c] = await Promise.all([api.health(), api.capabilities()]);
      setHealth(h);
      setCaps(c);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "加载失败");
      setHealth(null);
      setCaps(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const f = caps?.features;
  const checks = useMemo(
    () => [
      {
        label: "Gateway 健康",
        state: (health?.ok ? "pass" : health === null && loadError ? "fail" : "pending") as CheckState,
        detail: health?.ok ? "runtime=rust" : loadError || "等待响应",
      },
      {
        label: "数据面 upstream",
        state: (caps?.data_plane === "upstream" ? "pass" : caps ? "fail" : "pending") as CheckState,
        detail: caps?.data_plane ? `DATA_PLANE=${caps.data_plane}` : "—",
      },
      {
        label: "流式对话",
        state: (f?.stream_chat || f?.chat_stream ? "pass" : caps ? "fail" : "pending") as CheckState,
        detail: f?.stream_chat ? "stream_chat=true" : "chat_stream",
      },
      {
        label: "Estuary 下载",
        state: (f?.estuary_download ? "pass" : caps ? "fail" : "pending") as CheckState,
        detail: f?.estuary_download ? "upstream 生图拉取" : "未启用",
      },
      {
        label: "生图开关",
        state: (f?.image_generations ? "pass" : caps ? "fail" : "pending") as CheckState,
        detail: f?.image_generations ? "IMAGE_ENABLED=1" : "需开启 IMAGE_ENABLED",
      },
      {
        label: "静态 UI",
        state: (f?.static_ui || health?.static_ui ? "pass" : "skip") as CheckState,
        detail: f?.static_ui ? "GATEWAY_STATIC_DIR 已挂载" : "可选",
      },
      {
        label: "生图实测",
        state: imageTestState,
        detail:
          imageTestState === "pass"
            ? `已生成 ${gallery.length} 张`
            : imageTestState === "fail"
              ? imageError || "失败"
              : "点击下方「验收生图」",
      },
    ],
    [health, caps, f, loadError, imageTestState, gallery.length, imageError],
  );

  const passedCount = checks.filter((c) => c.state === "pass").length;
  const requiredCount = checks.filter((c) => c.label !== "静态 UI").length;

  async function runImageAcceptance() {
    if (!f?.image_generations || loading) return;
    const text = prompt.trim();
    if (!text) return;
    setLoading(true);
    setImageError("");
    setImageTestState("pending");
    try {
      const res = await api.image(text, size);
      const img = res.data?.[0]?.b64_json;
      if (!img) throw new Error("响应无 b64_json");
      const item: GalleryItem = {
        id: `${Date.now()}`,
        prompt: text,
        size,
        b64: img,
        at: new Date().toLocaleString(),
      };
      setGallery((prev) => [item, ...prev]);
      setImageTestState("pass");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "生图失败";
      setImageError(msg);
      setImageTestState("fail");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ShellLayout title="独立部署验收">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">验收看板</h2>
            <p className="text-sm text-muted-foreground">
              独立 upstream 栈 · 默认端口 8014 · 不触碰生产 :8012
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-accent/15 px-3 py-1 text-sm font-medium text-accent">
              {passedCount}/{requiredCount} 项通过
            </span>
            <Button variant="outline" size="sm" onClick={() => void refresh()}>
              刷新状态
            </Button>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>验收清单</CardTitle>
              <CardDescription>
                对应 docs/32-independent-deploy.md 本地/独立机检查项
              </CardDescription>
            </CardHeader>
            <CardContent>
              {checks.map((c) => (
                <CheckRow key={c.label} label={c.label} state={c.state} detail={c.detail} />
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>运行时快照</CardTitle>
              <CardDescription>
                wave {caps?.wave ?? "—"} · helper{" "}
                {caps?.helper_ok ? "ok" : "n/a"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loadError && (
                <p className="mb-2 text-sm text-destructive">{loadError}</p>
              )}
              <pre className="max-h-72 overflow-auto rounded-md bg-muted/50 p-3 text-xs">
                {JSON.stringify({ health, capabilities: caps }, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>生图验收</CardTitle>
            <CardDescription>
              经 gateway → upstream 数据面（PoW/SSE/estuary）；成功后将显示在下方画廊
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!f?.image_generations && (
              <p className="text-sm text-amber-600">
                后端未开启生图。请设置 <code className="text-xs">IMAGE_ENABLED=1</code>{" "}
                后重启 gateway。
              </p>
            )}
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="showcase-prompt">提示词</Label>
                <Input
                  id="showcase-prompt"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={loading || !f?.image_generations}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="showcase-size">尺寸</Label>
                <select
                  id="showcase-size"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={size}
                  onChange={(e) => setSize(e.target.value)}
                  disabled={loading || !f?.image_generations}
                >
                  {SIZES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <Button
              onClick={() => void runImageAcceptance()}
              disabled={loading || !f?.image_generations}
            >
              {loading ? "生成中…" : "验收生图"}
            </Button>
            {imageError && (
              <p className="text-sm text-destructive">{imageError}</p>
            )}
          </CardContent>
        </Card>

        {gallery.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>生成画廊</CardTitle>
              <CardDescription>本次会话验收产出（{gallery.length} 张）</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {gallery.map((item) => (
                  <div
                    key={item.id}
                    className="overflow-hidden rounded-lg border border-border bg-muted/20"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={`data:image/png;base64,${item.b64}`}
                      alt={item.prompt}
                      className="aspect-square w-full object-cover"
                    />
                    <div className="space-y-1 p-3 text-xs">
                      <p className="line-clamp-2 font-medium">{item.prompt}</p>
                      <p className="text-muted-foreground">
                        {item.size} · {item.at}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </ShellLayout>
  );
}
