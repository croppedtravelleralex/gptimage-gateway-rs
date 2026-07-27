"use client";

import { useEffect, useState } from "react";
import ShellLayout from "@/components/shell-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<
    Array<{ email: string; proxy_host: string; has_token: boolean }>
  >([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .candidates()
      .then((r) => setAccounts(r.accounts || []))
      .catch((e) => setError(e.message));
  }, []);

  return (
    <ShellLayout title="号池" roles={["admin"]}>
        <Card>
          <CardHeader>
            <CardTitle>Candidates（只读）</CardTitle>
          </CardHeader>
          <CardContent>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="p-2">Email</th>
                    <th className="p-2">Proxy Host</th>
                    <th className="p-2">Token</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((a, i) => (
                    <tr key={i} className="border-b">
                      <td className="p-2">{a.email}</td>
                      <td className="p-2">{a.proxy_host}</td>
                      <td className="p-2">{a.has_token ? "yes" : "no"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
    </ShellLayout>
  );
}
