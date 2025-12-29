"use client";

import { CopilotChat } from "@copilotkit/react-ui";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Sidebar } from "../components/sidebar";
import { RightSidebar } from "../components/right-sidebar";

export default function ChatPage() {
  const { ready, authenticated } = usePrivy();
  const { wallets } = useWallets();
  const router = useRouter();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  
  // Get connected wallet address
  const connectedWalletAddress = wallets[0]?.address || null;

  // Redirect to home if not authenticated
  useEffect(() => {
    if (ready && !authenticated) {
      router.push("/");
    }
  }, [ready, authenticated, router]);

  // Show loading while checking authentication status
  if (!ready) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-zinc-50 font-sans dark:bg-black">
        <div className="text-center">
          <div className="text-lg text-zinc-600 dark:text-zinc-400">
            Loading...
          </div>
        </div>
      </div>
    );
  }

  // Redirect if not authenticated (handled by useEffect, but show nothing while redirecting)
  if (!authenticated) {
    return null;
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-zinc-50 dark:bg-black">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />

      <div className="flex flex-1 flex-col overflow-hidden border-x border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        {/* Mobile Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900 md:hidden">
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="rounded-md p-2 text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            <svg
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
          <span className="font-semibold text-zinc-900 dark:text-zinc-100">
            Cronos x402
          </span>
          <button
            onClick={() => setIsRightSidebarOpen(true)}
            className="rounded-md p-2 text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            <svg
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
              />
            </svg>
          </button>
        </div>

        <div className="flex-shrink-0 border-b border-zinc-200 bg-white px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900 hidden md:block">
          <h1 className="text-xl font-semibold text-zinc-950 dark:text-zinc-50">
            Agent Workspace
          </h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Orchestrate agents and execute strategies
          </p>
        </div>
        <div className="flex flex-1 flex-col overflow-hidden rounded-b-lg border-b border-zinc-200 dark:border-zinc-800">
          <CopilotChat
            className="h-full"
            instructions={`You are a Web3 and cryptocurrency assistant. Help users with blockchain operations, balance checks, token swaps, and market analysis. Always be helpful and provide clear, actionable information.${
              connectedWalletAddress
                ? `\n\nIMPORTANT: The user has a connected wallet address: ${connectedWalletAddress}. When the user says "my balance", "fetch my balance", "check my balance", or similar phrases referring to their own wallet, automatically use this address: ${connectedWalletAddress}. Only use a different address if the user explicitly provides a specific wallet address in their message.`
                : ""
            }`}
            labels={{
              title: "Cronos Assistant",
              initial: "Hi! 👋 How can I assist you today?",
            }}
          />
        </div>
      </div>

      <RightSidebar
        isOpen={isRightSidebarOpen}
        onClose={() => setIsRightSidebarOpen(false)}
      />
    </div>
  );
}
