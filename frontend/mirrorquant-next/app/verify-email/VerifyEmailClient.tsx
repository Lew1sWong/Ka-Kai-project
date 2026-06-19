"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type VerificationState = "loading" | "success" | "error";

type VerifyEmailClientProps = {
  token: string | null;
};

export default function VerifyEmailClient({ token }: VerifyEmailClientProps) {
  const router = useRouter();
  const [status, setStatus] = useState<VerificationState>("loading");
  const [message, setMessage] = useState("Verifying your email...");

  useEffect(() => {
    let redirectTimeout: ReturnType<typeof setTimeout> | null = null;

    async function verifyEmail() {
      if (!token) {
        setStatus("error");
        setMessage("Verification link is missing a token.");
        return;
      }

      try {
        const response = await fetch(`/api/auth/verify-email?token=${encodeURIComponent(token)}`, {
          credentials: "include",
        });
        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(payload.detail || "Verification failed.");
        }

        setStatus("success");
        setMessage("Email verified. Redirecting you to the MirrorQuant workspace...");
        redirectTimeout = setTimeout(() => {
          router.replace("/workspace");
        }, 1200);
      } catch (error) {
        setStatus("error");
        setMessage(error instanceof Error ? error.message : "Verification failed.");
      }
    }

    verifyEmail();

    return () => {
      if (redirectTimeout) {
        clearTimeout(redirectTimeout);
      }
    };
  }, [router, token]);

  return (
    <main className="page auth-shell">
      <section className="panel auth-card">
        <p className="app-eyebrow">Email Verification</p>
        <h1 className="auth-title">
          {status === "loading" ? "Verifying your email..." : status === "success" ? "Email verified" : "Verification failed"}
        </h1>
        <p className={status === "success" ? "auth-success" : "panel-kicker"}>{message}</p>
        <div className="auth-actions">
          <Link href="/workspace" className="secondary-button">
            Open Workspace
          </Link>
          <Link href="/" className="secondary-button">
            Back To Landing
          </Link>
        </div>
      </section>
    </main>
  );
}
