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
          className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm xl:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar Container */}
      <div
        className={`fixed inset-y-0 right-0 z-50 flex w-80 flex-col border-l border-violet-100 bg-white shadow-lg transition-transform duration-300 xl:static xl:flex xl:translate-x-0 xl:shadow-none ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Logout Button - Top */}
        <div className="flex items-center justify-between border-b border-violet-100 bg-gradient-to-r from-white to-violet-50/30 p-4">
          <button
            onClick={handleLogout}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-red-50 to-rose-50 px-4 py-2.5 text-sm font-semibold text-red-600 transition-all hover:from-red-100 hover:to-rose-100 hover:shadow-md border border-red-100"
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
            className="ml-2 rounded-lg p-1.5 text-gray-500 hover:bg-violet-50 transition-colors xl:hidden"
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
        <div className="border-b border-violet-100 p-6 bg-gradient-to-b from-transparent to-violet-50/20">
          <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-gray-500">
            Connected Wallet
          </h2>
          {wallet ? (
            <div className="rounded-xl border border-violet-200 bg-gradient-to-br from-white to-violet-50/30 p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs font-semibold text-gray-600">
                  Active Connection
                </p>
                <div className="flex h-2 w-2 items-center justify-center">
                  <span className="absolute h-3 w-3 animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative h-2 w-2 rounded-full bg-emerald-500 shadow-sm"></span>
                </div>
              </div>
              <div className="mb-3">
                <p className="font-mono text-base font-bold text-gray-900">
                  {wallet.address.slice(0, 6)}...
                  {wallet.address.slice(-4)}
                </p>
                <p className="mt-1.5 text-xs font-medium text-violet-600 bg-violet-100 px-2 py-1 rounded-md inline-block">
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
            <div className="rounded-xl border border-violet-200 bg-gradient-to-br from-white to-violet-50/30 p-4 shadow-sm">
              <p className="mb-3 text-sm font-medium text-gray-600">
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
        <div className="border-b border-violet-100 p-6">
          <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-gray-500">
            Quick Actions
          </h2>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setShowDepositModal(true)}
              className="group flex flex-col items-center gap-2 rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-green-50 p-4 transition-all hover:shadow-lg hover:scale-105 hover:from-emerald-100 hover:to-green-100"
            >
              <div className="rounded-xl bg-white p-2 shadow-sm group-hover:shadow-md transition-shadow">
                <svg
                  className="h-6 w-6 text-emerald-600"
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
              </div>
              <span className="text-sm font-bold text-emerald-700">
                Deposit
              </span>
            </button>
            <button
              onClick={() => setShowWithdrawModal(true)}
              className="group flex flex-col items-center gap-2 rounded-xl border border-orange-200 bg-gradient-to-br from-orange-50 to-amber-50 p-4 transition-all hover:shadow-lg hover:scale-105 hover:from-orange-100 hover:to-amber-100"
            >
              <div className="rounded-xl bg-white p-2 shadow-sm group-hover:shadow-md transition-shadow">
                <svg
                  className="h-6 w-6 text-orange-600"
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
              </div>
              <span className="text-sm font-bold text-orange-700">
                Withdraw
              </span>
            </button>
          </div>

          {/* Simple modals - you can enhance these */}
          {showDepositModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
              <div className="w-96 rounded-2xl bg-white p-6 shadow-2xl border border-violet-100">
                <h3 className="mb-4 text-xl font-bold text-gray-900 flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center">
                    <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  </div>
                  Deposit Funds
                </h3>
                <p className="mb-4 text-sm text-gray-600">
                  Send funds to your wallet address:
                </p>
                <div className="mb-6 rounded-xl bg-gradient-to-br from-violet-50 to-purple-50 p-4 border border-violet-200">
                  <p className="break-all font-mono text-sm font-bold text-gray-900">
                    {wallet?.address || "Please connect a wallet first"}
                  </p>
                </div>
                <button
                  onClick={() => setShowDepositModal(false)}
                  className="w-full rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 px-4 py-3 text-sm font-semibold text-white shadow-lg hover:shadow-xl hover:from-violet-700 hover:to-purple-700 transition-all"
                >
                  Close
                </button>
              </div>
            </div>
          )}

          {showWithdrawModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
              <div className="w-96 rounded-2xl bg-white p-6 shadow-2xl border border-violet-100">
                <h3 className="mb-4 text-xl font-bold text-gray-900 flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center">
                    <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                    </svg>
                  </div>
                  Withdraw Funds
                </h3>
                <p className="mb-6 text-sm text-gray-600">
                  Use the chat to initiate a withdrawal with the Bridge Agent.
                </p>
                <button
                  onClick={() => setShowWithdrawModal(false)}
                  className="w-full rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 px-4 py-3 text-sm font-semibold text-white shadow-lg hover:shadow-xl hover:from-violet-700 hover:to-purple-700 transition-all"
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Recent Transactions Section (compact list) */}
        <div className="flex-1 overflow-y-auto p-6 bg-gradient-to-b from-transparent via-violet-50/10 to-violet-50/20">
          <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-gray-500">
            Recent Activity
          </h2>
          <div className="space-y-2">
            {recentTransactions.map((tx) => (
              <div key={tx.id} className="group flex items-center gap-3 rounded-xl px-3 py-3 transition-all hover:bg-white hover:shadow-md border border-transparent hover:border-violet-100">
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl shadow-sm ${
                    tx.color === "purple"
                      ? "bg-gradient-to-br from-purple-100 to-violet-100 text-purple-600"
                      : tx.color === "blue"
                      ? "bg-gradient-to-br from-blue-100 to-sky-100 text-blue-600"
                      : tx.color === "green"
                      ? "bg-gradient-to-br from-emerald-100 to-green-100 text-emerald-600"
                      : "bg-gradient-to-br from-yellow-100 to-amber-100 text-amber-600"
                  }`}
                >
                  <span className="text-lg">{tx.icon}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold truncate text-gray-900 group-hover:text-violet-700 transition-colors">
                    {tx.description}
                  </p>
                  <p className="mt-0.5 text-xs font-medium text-gray-500">
                    {tx.time}
                  </p>
                </div>
                <svg className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
