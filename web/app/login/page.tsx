"use client";

import { LockKeyhole, LoaderCircle, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!username || !password || busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail ?? "登录失败。");
      router.replace("/");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败。");
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-brand"><ShieldCheck size={24} /><span>售后工单工作台</span></div>
        <div className="login-heading">
          <span className="login-icon"><LockKeyhole size={24} /></span>
          <div><h1 id="login-title">登录工作台</h1><p>使用操作员或审批管理员账号继续。</p></div>
        </div>
        <form onSubmit={submit} className="login-form">
          <label htmlFor="username">用户名</label>
          <input id="username" name="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} disabled={busy} required />
          <label htmlFor="password">密码</label>
          <input id="password" name="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} disabled={busy} required />
          {error && <p className="login-error" role="alert">{error}</p>}
          <button className="primary-button login-submit" type="submit" disabled={busy || !username || !password} aria-busy={busy}>
            {busy ? <><LoaderCircle className="spin" size={18} />正在验证</> : "登录"}
          </button>
        </form>
        <p className="login-note">操作员可以处理工单；退款批准与驳回仅限审批管理员。</p>
      </section>
    </main>
  );
}
