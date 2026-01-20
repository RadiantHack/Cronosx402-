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
    { href: "/balance", label: "Overview" },
    { href: "/chat", label: "New Chat" },
    { href: "/premium", label: "Premium Chat", premium: true },
    { href: "/transfer", label: "Transfer" },
    { href: "/swap", label: "Swap" },
    { href: "/bridge", label: "Bridge" },
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
    {
      name: "Bridge",
      description: "Cross-chain bridge",
      icon: "🌉",
      gradient:
        "bg-gradient-to-br from-blue-100 via-cyan-100 to-sky-100 text-blue-700",
    },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar Container */}
      <div
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-violet-100 bg-white shadow-lg transition-transform duration-300 md:static md:translate-x-0 md:shadow-none ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo */}
        <div className="flex items-center justify-between border-b border-violet-100 bg-gradient-to-r from-white to-violet-50/30 p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-md shadow-violet-500/30">
              <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900">
                Cronos x402
              </h1>
              <p className="text-xs text-gray-600">
                AI-Powered DeFi
              </p>
            </div>
          </div>
          {/* Close button for mobile */}
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-500 hover:bg-violet-50 transition-colors md:hidden"
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
        <div className="flex-1 overflow-y-auto p-4 bg-gradient-to-b from-transparent to-violet-50/20">
          <nav className="space-y-2">
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              const isPremium = item.premium || false;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => onClose?.()}
                  className={`flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-medium transition-all ${
                    isActive
                      ? "bg-gradient-to-r from-violet-500 to-purple-600 text-white shadow-md shadow-violet-500/30"
                      : "text-gray-700 hover:bg-violet-50 hover:text-violet-700"
                  }`}
                >
                  {isPremium ? (
                    <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 2L15 8.5L22 9.5L17 14.5L18 21.5L12 18L6 21.5L7 14.5L2 9.5L9 8.5L12 2Z" />
                    </svg>
                  ) : (
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  )}
                  {item.label}
                  {isPremium && (
                    <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-bold ${
                      isActive ? "bg-white/20" : "bg-yellow-100 text-yellow-700"
                    }`}>
                      PRO
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* Available Agents */}
          <div className="mt-8">
            <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-gray-500 px-2">
              AI AGENTS
            </h2>
            <div className="grid gap-3">
              {agents.map((agent) => (
                <button
                  key={agent.name}
                  className={`group flex w-full items-center gap-3 rounded-xl p-3.5 transition-all hover:shadow-lg hover:scale-105 ${agent.gradient} border border-white/50 shadow-sm`}
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/90 text-xl shadow-md backdrop-blur-sm">
                    <span aria-hidden>{agent.icon}</span>
                  </div>
                  <div className="text-left flex-1">
                    <p className="text-sm font-bold leading-tight">
                      {agent.name}
                    </p>
                    <p className="mt-1 text-xs opacity-90 font-medium">
                      {agent.description}
                    </p>
                  </div>
                  <svg className="h-5 w-5 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
