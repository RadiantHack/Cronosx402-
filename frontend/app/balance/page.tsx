"use client";

import { useEffect, useState } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { Sidebar } from "../components/sidebar";
import { RightSidebar } from "../components/right-sidebar";

interface TokenBalance {
  symbol: string;
  name: string;
  value: string;
  decimals: number;
  contract: string;
  is_native: boolean;
}

interface BalanceData {
  address: string;
  balances: TokenBalance[];
  success: boolean;
  error?: string;
}

export default function BalancePage() {
  const { ready, authenticated, user, login } = usePrivy();
  const { wallets } = useWallets();
  
  const [balanceData, setBalanceData] = useState<BalanceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);

  const walletAddress = wallets[0]?.address || "";

  // Auto-fetch balance when wallet is connected
  useEffect(() => {
    if (ready && authenticated && walletAddress) {
      fetchBalance();
    }
  }, [ready, authenticated, walletAddress]);

  const fetchBalance = async () => {
    if (!walletAddress) {
      setError("No wallet connected");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Call the structured JSON endpoint on the backend
      const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:8000";
      const response = await fetch(`${baseUrl}/api/balance/json`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          address: walletAddress,
          network: "cronos",
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      if (data.success) {
        setBalanceData(data);
      } else {
        setError(data.error || "Failed to fetch balance");
      }
    } catch (err) {
      console.error("Error fetching balance:", err);
      setError(err instanceof Error ? err.message : "Failed to connect to balance service");
    } finally {
      setLoading(false);
    }
  };

  const formatBalance = (value: string, decimals: number): string => {
    try {
      const valueInt = parseInt(value);
      const balance = valueInt / Math.pow(10, decimals);
      return balance.toFixed(6).replace(/\.?0+$/, "");
    } catch {
      return "0";
    }
  };

  // Show loading while checking authentication
  if (!ready) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gradient-to-br from-violet-50 via-purple-50 to-blue-50">
        <div className="text-center">
          <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-violet-200 border-t-violet-600"></div>
          <div className="text-lg font-medium text-gray-700">Loading...</div>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!authenticated) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gradient-to-br from-violet-50 via-purple-50 to-blue-50">
        <div className="text-center">
          <h2 className="mb-4 text-2xl font-bold text-gray-900">
            Please connect your wallet
          </h2>
          <button
            onClick={login}
            className="rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 px-6 py-3 font-semibold text-white shadow-lg hover:shadow-xl transition-all"
          >
            Connect Wallet
          </button>
        </div>
      </div>
    );
  }

  // Calculate total value (placeholder - would need price data)
  const nativeBalance = balanceData?.balances?.find((b) => b.is_native);
  const tokenBalances = balanceData?.balances?.filter((b) => !b.is_native) || [];

  return (
    <div className="flex h-screen w-full overflow-hidden bg-gradient-to-br from-violet-50/30 via-purple-50/30 to-blue-50/30">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />

      <div className="flex flex-1 flex-col overflow-hidden border-x border-violet-100 bg-white/80 backdrop-blur-sm">
        {/* Mobile Header */}
        <div className="flex items-center justify-between border-b border-violet-100 bg-white/90 backdrop-blur-md px-4 py-3 shadow-sm md:hidden">
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="rounded-lg p-2 text-gray-600 hover:bg-violet-50 transition-colors"
          >
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
              <svg className="h-4 w-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="font-bold text-gray-900">Portfolio</span>
          </div>
          <button
            onClick={() => setIsRightSidebarOpen(true)}
            className="rounded-lg p-2 text-gray-600 hover:bg-violet-50 transition-colors"
          >
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </button>
        </div>

        {/* Desktop Header */}
        <div className="flex-shrink-0 border-b border-violet-100 bg-gradient-to-r from-white via-violet-50/30 to-purple-50/30 px-6 py-5 shadow-sm hidden md:block">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-md shadow-violet-500/30">
              <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-violet-600 to-purple-600 bg-clip-text text-transparent">
                Portfolio Overview
              </h1>
            </div>
          </div>
          <p className="text-sm text-gray-600 ml-[52px]">
            View your token balances and holdings on Cronos
          </p>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Loading State */}
            {loading && (
              <div className="text-center py-12">
                <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-violet-200 border-t-violet-600"></div>
                <div className="text-lg font-medium text-gray-700">Fetching your balances...</div>
              </div>
            )}

            {/* Error State */}
            {error && !loading && (
              <div className="rounded-xl border border-red-200 bg-gradient-to-br from-red-50 to-rose-50 p-6 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-100">
                    <svg className="h-6 w-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-bold text-red-900">Error Loading Balance</h3>
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                </div>
                <button
                  onClick={fetchBalance}
                  className="mt-4 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 px-4 py-2 text-sm font-semibold text-white hover:from-red-700 hover:to-rose-700 transition-all"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Balance Cards */}
            {!loading && !error && balanceData && (
              <>
                {/* Native CRO Balance Card */}
                {nativeBalance && (
                  <div className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-500 via-purple-600 to-blue-600 p-8 shadow-xl text-white">
                    <div className="flex items-center justify-between mb-6">
                      <div>
                        <p className="text-sm font-medium text-violet-100">Native Balance</p>
                        <h2 className="text-4xl font-bold mt-2">
                          {formatBalance(nativeBalance.value, nativeBalance.decimals)} CRO
                        </h2>
                      </div>
                      <div className="h-16 w-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
                        <span className="text-3xl">💎</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-violet-100">
                      <span className="font-mono">{walletAddress.slice(0, 6)}...{walletAddress.slice(-4)}</span>
                    </div>
                  </div>
                )}

                {/* Token Holdings */}
                {tokenBalances.length > 0 && (
                  <div>
                    <h3 className="text-xl font-bold text-gray-900 mb-4">Token Holdings</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {tokenBalances.map((token, index) => (
                        <div
                          key={index}
                          className="group rounded-xl border border-violet-200 bg-white p-6 shadow-sm hover:shadow-lg transition-all hover:scale-105"
                        >
                          <div className="flex items-center justify-between mb-4">
                            <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-violet-100 to-purple-100 flex items-center justify-center text-2xl">
                              🪙
                            </div>
                            <div className="text-right">
                              <p className="text-xs font-semibold text-gray-500">{token.symbol}</p>
                            </div>
                          </div>
                          <h4 className="font-bold text-gray-900 mb-1">{token.name}</h4>
                          <p className="text-2xl font-bold text-violet-600">
                            {formatBalance(token.value, token.decimals)}
                          </p>
                          <p className="text-xs text-gray-500 mt-2 font-mono truncate">
                            {token.contract.slice(0, 8)}...{token.contract.slice(-6)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* No Tokens Message */}
                {tokenBalances.length === 0 && nativeBalance && (
                  <div className="rounded-xl border border-violet-200 bg-white p-8 text-center shadow-sm">
                    <div className="mb-4 inline-block h-16 w-16 rounded-2xl bg-gradient-to-br from-violet-100 to-purple-100 flex items-center justify-center">
                      <span className="text-3xl">📭</span>
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">No Token Holdings</h3>
                    <p className="text-sm text-gray-600">
                      You currently have no ERC-20 tokens in your wallet
                    </p>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <RightSidebar isOpen={isRightSidebarOpen} onClose={() => setIsRightSidebarOpen(false)} />
    </div>
  );
}
