"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Shield, Mail, ArrowRight, Loader2, Sparkles, AlertCircle } from "lucide-react";
import { createClient } from "@/lib/supabase/client";

function LoginForm() {
  const searchParams = useSearchParams();
  const [emailMode, setEmailMode] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const supabase = createClient();

  useEffect(() => {
    const errorParam = searchParams.get("error");
    if (errorParam) {
      setMessage("Authentication session was not completed. Please sign in using the Demo Account or Email.");
    }
  }, [searchParams]);

  // 1-Click Instant Demo Login (Zero typing required)
  const handleDemoLogin = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email: "user_a_nirbhar@test.com",
        password: "NirbharSecurePass2026!",
      });
      if (error) {
        setMessage(error.message);
      } else {
        window.location.href = "/";
      }
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Demo sign in failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setLoading(true);
    setMessage(null);
    try {
      // In Supabase Cloud, Google OAuth requires Google Client ID & Secret configured in the project dashboard.
      // Proactively warn if unconfigured so user is not redirected to a raw 400 error page.
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
          skipBrowserRedirect: true,
        },
      });

      if (error) {
        setMessage(
          "Google OAuth is not enabled in this Supabase instance. Please use the '1-Click Demo Sign In' button above or sign in with Email."
        );
      } else if (data?.url) {
        window.location.href = data.url;
      }
    } catch {
      setMessage(
        "Google OAuth is not enabled in this Supabase instance. Please use the '1-Click Demo Sign In' button above or sign in with Email."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleFillDemoCreds = () => {
    setEmail("user_a_nirbhar@test.com");
    setPassword("NirbharSecurePass2026!");
    setMessage(null);
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    setMessage(null);
    try {
      if (password) {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) {
          setMessage(error.message);
        } else {
          window.location.href = "/";
        }
      } else {
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: {
            emailRedirectTo: `${window.location.origin}/auth/callback`,
          },
        });
        if (error) {
          setMessage(error.message);
        } else {
          setMessage("Check your email for the magic link!");
        }
      }
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-sm flex flex-col items-center text-center space-y-8">
      {/* Logo */}
      <div className="flex flex-col items-center space-y-3">
        <div className="w-12 h-12 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-md">
          <Shield className="w-6 h-6 stroke-[2.5]" />
        </div>
        <div>
          <span className="text-base font-semibold tracking-tight text-slate-900 block">
            Nirbhar AI
          </span>
          <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400 block">
            Trust & Authorization Layer
          </span>
        </div>
      </div>

      {/* Buttons / Minimal Auth */}
      <div className="w-full space-y-3">
        {!emailMode ? (
          <>
            {/* Primary Action: 1-Click Demo Login */}
            <button
              type="button"
              onClick={handleDemoLogin}
              disabled={loading}
              className="w-full h-11 px-4 flex items-center justify-between bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-xs font-semibold rounded-lg shadow-sm transition-all cursor-pointer disabled:opacity-50"
            >
              <div className="flex items-center gap-2.5">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 text-indigo-200" />}
                <span>1-Click Demo Sign In</span>
              </div>
              <span className="text-[10px] font-mono bg-indigo-500/50 px-2 py-0.5 rounded text-indigo-100">
                Recommended
              </span>
            </button>

            <div className="relative flex py-1 items-center">
              <div className="grow border-t border-slate-200" />
              <span className="shrink mx-3 text-[11px] text-slate-400 font-mono">or other options</span>
              <div className="grow border-t border-slate-200" />
            </div>

            {/* Button 2: Email */}
            <button
              type="button"
              onClick={() => setEmailMode(true)}
              className="w-full h-10 px-4 flex items-center justify-center gap-2.5 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 shadow-2xs hover:border-slate-300 transition-all cursor-pointer"
            >
              <Mail className="w-4 h-4 shrink-0 text-slate-500" />
              <span>Continue with Email &amp; Password</span>
            </button>

            {/* Button 3: Google */}
            <button
              type="button"
              onClick={handleGoogleLogin}
              disabled={loading}
              className="w-full h-10 px-4 flex items-center justify-center gap-2.5 bg-white hover:bg-slate-50 text-slate-600 text-xs font-medium rounded-lg border border-slate-200 shadow-2xs hover:border-slate-300 transition-all cursor-pointer opacity-80 hover:opacity-100"
            >
              <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              <span>Continue with Google</span>
            </button>
          </>
        ) : (
          <form onSubmit={handleEmailSubmit} className="space-y-3">
            <div>
              <label htmlFor="login-email" className="sr-only">
                Email address
              </label>
              <input
                id="login-email"
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                className="w-full h-11 px-3 text-xs bg-white border border-slate-200 rounded-lg text-slate-900 placeholder:text-slate-400 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:border-indigo-600 shadow-2xs"
              />
            </div>
            <div>
              <label htmlFor="login-password" className="sr-only">
                Password
              </label>
              <input
                id="login-password"
                type="password"
                placeholder="Password (optional for magic link)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full h-11 px-3 text-xs bg-white border border-slate-200 rounded-lg text-slate-900 placeholder:text-slate-400 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:border-indigo-600 shadow-2xs"
              />
            </div>

            <div className="flex items-center justify-between text-[11px] pt-0.5">
              <button
                type="button"
                onClick={handleFillDemoCreds}
                className="text-indigo-600 hover:text-indigo-700 font-medium underline underline-offset-2 cursor-pointer"
              >
                Use Demo Credentials
              </button>
              <span className="text-slate-400 font-mono">user_a_nirbhar</span>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full h-11 px-4 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-all cursor-pointer disabled:opacity-50 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <span>{password ? "Sign In" : "Send Magic Link"}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
            <button
              type="button"
              onClick={() => {
                setEmailMode(false);
                setMessage(null);
              }}
              className="text-xs text-slate-500 hover:text-slate-700 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 rounded p-1"
            >
              Back to options
            </button>
          </form>
        )}

        {message && (
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-800 text-left flex items-start gap-2 animate-in fade-in duration-200">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <span className="leading-relaxed">{message}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen w-screen flex flex-col items-center justify-center bg-slate-50 p-6 selection:bg-indigo-100 selection:text-indigo-800">
      <Suspense fallback={<div className="text-xs text-slate-400">Loading...</div>}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
