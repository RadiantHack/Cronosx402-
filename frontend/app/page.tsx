"use client";

import { usePrivy } from "@privy-io/react-auth";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const { ready, authenticated, login } = usePrivy();
  const router = useRouter();

  const handleLogin = () => {
    login();
  };

  // Redirect authenticated users to /chat
  useEffect(() => {
    if (ready && authenticated) {
      router.push("/chat");
    }
  }, [ready, authenticated, router]);

  // Show loading while checking authentication status
  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-violet-50 via-purple-50 to-blue-50 font-sans">
        <div className="text-center">
          <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-violet-200 border-t-violet-600"></div>
          <div className="text-lg font-medium text-gray-700">
            Loading...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-violet-50 via-purple-50 to-blue-50 font-sans">
      <main className="flex w-full max-w-2xl flex-col items-center gap-8 py-32 px-16">
        <div className="flex flex-col items-center gap-6 text-center">
          {/* Logo/Icon */}
          <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-lg shadow-violet-500/30">
            <svg className="h-10 w-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          
          <h1 className="max-w-md text-5xl font-bold leading-tight tracking-tight bg-gradient-to-r from-violet-600 via-purple-600 to-blue-600 bg-clip-text text-transparent">
            Cronos x402
          </h1>
          <p className="max-w-md text-xl leading-8 text-gray-600">
            AI-Powered DeFi Gateway
          </p>
          <p className="max-w-lg text-base text-gray-500">
            Connect your wallet to access intelligent DeFi agents for trading, lending, bridging, and more
          </p>
          
          <div className="flex w-full flex-col gap-3 md:w-[400px] mt-4">
            <button
              onClick={handleLogin}
              className="group relative flex h-14 w-full items-center justify-center gap-3 overflow-hidden rounded-2xl bg-gradient-to-r from-violet-600 to-purple-600 px-8 text-white shadow-lg shadow-violet-500/30 transition-all duration-300 hover:shadow-xl hover:shadow-violet-500/40 hover:scale-105"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-violet-700 to-purple-700 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
              <svg
                className="relative h-6 w-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"
                />
              </svg>
              <span className="relative text-base font-semibold">Connect Wallet</span>
            </button>
            
            {/* Feature Pills */}
            <div className="flex flex-wrap justify-center gap-2 mt-4">
              <span className="rounded-full bg-white px-4 py-2 text-sm font-medium text-violet-700 shadow-sm border border-violet-100">
                🤖 AI Agents
              </span>
              <span className="rounded-full bg-white px-4 py-2 text-sm font-medium text-purple-700 shadow-sm border border-purple-100">
                ⚡ Instant Execution
              </span>
              <span className="rounded-full bg-white px-4 py-2 text-sm font-medium text-blue-700 shadow-sm border border-blue-100">
                🔐 Secure
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
