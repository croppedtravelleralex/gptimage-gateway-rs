"use client";

import { useEffect, useState } from "react";
import ShellLayout from "@/components/shell-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

type ChatMsg = { role: "user" | "assistant"; content: string };

export default function ChatPage() {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stream, setStream] = useState(false);

  async function send() {
    const text = prompt.trim();
    if (!text || loading) return;
    setLoading(true);
    setError("");
    setPrompt("");
    const nextMessages: ChatMsg[] = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);

    try {
      const apiMessages = nextMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      if (stream) {
        const res = await api.chat(apiMessages, true);
        if (!(res instanceof Response) || !res.ok) {
          const data = await (res as Response).json().catch(() => ({}));
          throw new Error(data?.error?.message || "流式请求失败");
        }
        setMessages([
          ...nextMessages,
          { role: "assistant", content: "（流式响应已发送，UI 展示待完善）" },
        ]);
        return;
      }
      const data = await api.chat(apiMessages, false);
      if (data instanceof Response) throw new Error("unexpected response");
      const content =
        data?.choices?.[0]?.message?.content || JSON.stringify(data);
      setMessages([...nextMessages, { role: "assistant", content }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "对话失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ShellLayout title="对话">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <Card className="min-h-[420px]">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>文本对话</CardTitle>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={stream}
                onChange={(e) => setStream(e.target.checked)}
              />
              流式（实验）
            </label>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex max-h-[360px] flex-col gap-3 overflow-y-auto rounded-md border border-border p-3">
              {messages.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  发送一条消息开始对话。当前后端为简易文本桥接。
                </p>
              )}
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={
                    m.role === "user"
                      ? "ml-8 rounded-lg bg-primary/10 px-3 py-2 text-sm"
                      : "mr-8 rounded-lg bg-muted px-3 py-2 text-sm"
                  }
                >
                  <div className="mb-1 text-xs font-medium text-muted-foreground">
                    {m.role === "user" ? "你" : "助手"}
                  </div>
                  <div className="whitespace-pre-wrap">{m.content}</div>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                placeholder="输入消息…"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
                disabled={loading}
              />
              <Button onClick={send} disabled={loading}>
                {loading ? "…" : "发送"}
              </Button>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>
      </div>
    </ShellLayout>
  );
}
