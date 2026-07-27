"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ShellLayout from "@/components/shell-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { User } from "@/lib/api-types";

export default function SettingsPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      const r = await api.listUsers();
      setUsers(r.users || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <ShellLayout title="用户管理" roles={["admin"]}>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>用户列表</CardTitle>
            <Button asChild size="sm" variant="outline">
              <Link href="/register">新建成员</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-2">用户名</th>
                  <th className="p-2">角色</th>
                  <th className="p-2">状态</th>
                  <th className="p-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b">
                    <td className="p-2">{u.username}</td>
                    <td className="p-2">{u.role}</td>
                    <td className="p-2">{u.disabled ? "禁用" : "正常"}</td>
                    <td className="p-2">
                      {u.role !== "admin" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={async () => {
                            await api.setUserDisabled(u.id, !u.disabled);
                            await load();
                          }}
                        >
                          {u.disabled ? "启用" : "禁用"}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
    </ShellLayout>
  );
}
