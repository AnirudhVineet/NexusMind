"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SignUpPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail ?? "Registration failed");
      }
      const signInRes = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });
      if (signInRes?.error) throw new Error("Auto sign-in failed");
      router.push("/");
      router.refresh();
    } catch (e: any) {
      setError(e.message ?? "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm bg-surface border border-border rounded-xl p-6 space-y-4"
      >
        <div>
          <h1 className="text-xl font-semibold">Create account</h1>
          <p className="text-muted-foreground text-sm mt-1">Start ingesting documents in seconds.</p>
        </div>
        <div className="space-y-2">
          <label className="text-sm">Email</label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm">Password</label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
          <p className="text-xs text-muted-foreground">At least 8 characters.</p>
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <Button type="submit" disabled={submitting} className="w-full">
          {submitting ? "Creating…" : "Create account"}
        </Button>
        <p className="text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/sign-in" className="text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
