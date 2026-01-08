"use client";

import { usePrivy, useWallets } from "@privy-io/react-auth";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function Sidebar({
  isOpen,
  onClose,
}: {
  isOpen?: boolean;
  onClose?: () => void;
}) {
  const { user } = usePrivy();
  const { wallets } = useWallets();
  const pathname = usePathname();

  const walletAddress = wallets[0]?.address || "";

  const navItems = [
    { href: "/chat", label: "New Chat" },
  ];

  const agents = [
    {
      name: "Balance",
      description: "Check balances",
      icon: "💰",
      gradient:
        "bg-gradient-to-br from-yellow-100 via-amber-100 to-orange-100 text-orange-800",
    },
    {
      name: "Swap",
      description: "Swap tokens",
      icon: "🔁",
      gradient:
        "bg-gradient-to-br from-indigo-100 via-purple-100 to-pink-100 text-pink-700",
    },
    {
      name: "Transfer",
      description: "Send native CRO",
      icon: "✈️",
      gradient:
        "bg-gradient-to-br from-emerald-100 via-green-100 to-teal-100 text-emerald-700",
    },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar Container */}
      <div
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-zinc-200 bg-zinc-50 transition-transform duration-300 dark:border-zinc-800 dark:bg-zinc-900 md:static md:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo */}
        <div className="flex items-center justify-between border-b border-zinc-200 p-4 dark:border-zinc-800">
          <div>
            <h1 className="text-xl font-semibold text-zinc-950 dark:text-zinc-50">
              Cronos x402
            </h1>
            <p className="text-xs text-zinc-600 dark:text-zinc-400">
              AI-Powered DeFi Gateway
            </p>
          </div>
          {/* Close button for mobile */}
          <button
            onClick={onClose}
            className="rounded-md p-1 text-zinc-500 hover:bg-zinc-200 dark:text-zinc-400 dark:hover:bg-zinc-800 md:hidden"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <div className="flex-1 overflow-y-auto p-4">
          <nav className="space-y-2">
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => onClose?.()}
                  className={`block rounded-lg px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? "bg-purple-100 font-medium text-purple-900 dark:bg-purple-900/30 dark:text-purple-300"
                      : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* Available Agents */}
          <div className="mt-8">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              AVAILABLE AGENTS
            </h2>
            <div className="grid gap-3">
              {agents.map((agent) => (
                <button
                  key={agent.name}
                  className={`group flex w-full items-center gap-3 rounded-xl p-3 transition-shadow hover:shadow-md ${agent.gradient} border border-zinc-100 dark:border-zinc-800`}
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/70 text-lg shadow-sm">
                    <span aria-hidden>{agent.icon}</span>
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-semibold leading-4">
                      {agent.name}
                    </p>
                    <p className="mt-1 text-xs opacity-80">
                      {agent.description}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
