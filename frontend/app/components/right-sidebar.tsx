"use client";

import { usePrivy, useWallets } from "@privy-io/react-auth";
import { useState } from "react";

export function RightSidebar({
  isOpen,
  onClose,
}: {
  isOpen?: boolean;
  onClose?: () => void;
}) {
  const { logout, linkWallet } = usePrivy();
  const { wallets } = useWallets();
  const [showDepositModal, setShowDepositModal] = useState(false);
  const [showWithdrawModal, setShowWithdrawModal] = useState(false);

  const handleLogout = () => {
    logout();
  };

  // const handleConnectWallet = () => {
  //   linkWallet();
  // };

  const wallet = wallets[0];

  // Mock recent transactions - replace with actual data
  const recentTransactions = [
    {
      id: "1",
      type: "Bridge",
      description: "Bridged 100 USDC to Cronos",
      time: "2 mins ago",
      status: "completed",
      icon: "🌉",
      color: "purple",
    },
    {
      id: "2",
      type: "Trade",
      description: "Bought 500 CRO at $0.10",
      time: "15 mins ago",
      status: "completed",
      icon: "💱",
      color: "blue",
    },
    {
      id: "3",
      type: "Liquidity",
      description: "Added to CRO/USDC pool",
      time: "1 hour ago",
      status: "completed",
      icon: "💧",
      color: "green",
    },
    {
      id: "4",
      type: "Balance",
      description: "Checked ETH balance",
      time: "2 hours ago",
      status: "completed",
      icon: "💰",
      color: "yellow",
    },
  ];

  const getColorClasses = (color: string) => {
    const colors: Record<string, string> = {
      purple:
        "bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400",
      blue: "bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400",
      green:
        "bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400",
      yellow:
        "bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400",
    };
    return colors[color] || colors.blue;
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 xl:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar Container */}
      <div
        className={`fixed inset-y-0 right-0 z-50 flex w-80 flex-col border-l border-zinc-200 bg-zinc-50 transition-transform duration-300 dark:border-zinc-800 dark:bg-zinc-900 xl:static xl:flex xl:translate-x-0 ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Logout Button - Top */}
        <div className="flex items-center justify-between border-b border-zinc-200 p-4 dark:border-zinc-800">
          <button
            onClick={handleLogout}
            className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/30"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
            Logout
          </button>

          {/* Close button for mobile */}
          <button
            onClick={onClose}
            className="ml-2 rounded-md p-1 text-zinc-500 hover:bg-zinc-200 dark:text-zinc-400 dark:hover:bg-zinc-800 xl:hidden"
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

        {/* Wallet Section */}
        <div className="border-b border-zinc-200 p-6 dark:border-zinc-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
            Wallet
          </h2>
          {wallet ? (
            <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-800">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  Wallet Connected
                </p>
                <div className="flex h-2 w-2 items-center justify-center">
                  <span className="absolute h-2 w-2 animate-ping rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative h-2 w-2 rounded-full bg-green-500"></span>
                </div>
              </div>
              <div className="mb-3">
                <p className="font-mono text-sm font-medium text-zinc-950 dark:text-zinc-50">
                  {wallet.address.slice(0, 6)}...
                  {wallet.address.slice(-4)}
                </p>
                <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
                  {wallet.walletClientType || "Cronos"}
                </p>
              </div>
              {/* <button
                onClick={handleConnectWallet}
                className="mt-2 w-full rounded-md bg-purple-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600"
              >
                Connect Another Wallet
              </button> */}
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-800">
              <p className="mb-3 text-sm text-zinc-600 dark:text-zinc-400">
                No wallet connected
              </p>
              {/* <button
                onClick={handleConnectWallet}
                className="w-full rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600"
              >
                Connect Wallet
              </button> */}
            </div>
          )}
        </div>

        {/* Deposit/Withdraw Section */}
        <div className="border-b border-zinc-200 p-6 dark:border-zinc-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
            Quick Actions
          </h2>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setShowDepositModal(true)}
              className="flex flex-col items-center gap-2 rounded-lg border border-zinc-200 bg-white p-4 transition-all hover:border-green-300 hover:bg-green-50 dark:border-zinc-700 dark:bg-zinc-800 dark:hover:border-green-700 dark:hover:bg-green-900/20"
            >
              <svg
                className="h-6 w-6 text-green-600 dark:text-green-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                Deposit
              </span>
            </button>
            <button
              onClick={() => setShowWithdrawModal(true)}
              className="flex flex-col items-center gap-2 rounded-lg border border-zinc-200 bg-white p-4 transition-all hover:border-orange-300 hover:bg-orange-50 dark:border-zinc-700 dark:bg-zinc-800 dark:hover:border-orange-700 dark:hover:bg-orange-900/20"
            >
              <svg
                className="h-6 w-6 text-orange-600 dark:text-orange-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M20 12H4"
                />
              </svg>
              <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                Withdraw
              </span>
            </button>
          </div>

          {/* Simple modals - you can enhance these */}
          {showDepositModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
              <div className="w-96 rounded-lg bg-white p-6 dark:bg-zinc-800">
                <h3 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                  Deposit Funds
                </h3>
                <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">
                  Send funds to your wallet address:
                </p>
                <div className="mb-4 rounded-md bg-zinc-100 p-3 dark:bg-zinc-700">
                  <p className="break-all font-mono text-xs text-zinc-900 dark:text-zinc-100">
                    {wallet?.address || "Please connect a wallet first"}
                  </p>
                </div>
                <button
                  onClick={() => setShowDepositModal(false)}
                  className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
                >
                  Close
                </button>
              </div>
            </div>
          )}

          {showWithdrawModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
              <div className="w-96 rounded-lg bg-white p-6 dark:bg-zinc-800">
                <h3 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                  Withdraw Funds
                </h3>
                <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">
                  Use the chat to initiate a withdrawal with the Bridge Agent.
                </p>
                <button
                  onClick={() => setShowWithdrawModal(false)}
                  className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Recent Transactions Section (compact list) */}
        <div className="flex-1 overflow-y-auto p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
            Recent Activity
          </h2>
          <div className="space-y-2">
            {recentTransactions.map((tx) => (
              <div key={tx.id} className="flex items-center gap-3 px-2 py-1">
                <span
                  className={`inline-block h-3 w-3 shrink-0 rounded-full ${
                    tx.color === "purple"
                      ? "bg-purple-400"
                      : tx.color === "blue"
                      ? "bg-blue-400"
                      : tx.color === "green"
                      ? "bg-emerald-400"
                      : "bg-yellow-400"
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate text-zinc-900 dark:text-zinc-100">
                    {tx.description}
                  </p>
                  <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                    {tx.time}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
