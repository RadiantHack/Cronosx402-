"use client";

import { useState, useEffect } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { useRouter } from "next/navigation";
import { Sidebar } from "../components/sidebar";
import { RightSidebar } from "../components/right-sidebar";
import { transferCRO, type CronosNetwork } from "@/app/lib/transfer";

export default function TransferPage() {
  const { ready, authenticated, login } = usePrivy();
  const { wallets } = useWallets();
  const router = useRouter();

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  
  // Form state
  const [recipient, setRecipient] = useState("");
  const [amount, setAmount] = useState("");
  const [network, setNetwork] = useState<CronosNetwork>("mainnet");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);

  // Get Privy embedded wallet
  const privyWallet = wallets.find(w => {
    if (w.walletClientType === 'privy') return true;
    if (!w.walletClientType || (w as any).chainType === 'ethereum') {
      return w.walletClientType !== 'metamask' && 
             w.walletClientType !== 'coinbase_wallet' &&
             w.walletClientType !== 'wallet_connect' &&
             w.walletClientType !== 'phantom';
    }
    return false;
  });

  const walletAddress = privyWallet?.address || "";

  // Redirect to home if not authenticated
  useEffect(() => {
    if (ready && !authenticated) {
      router.push("/");
    }
  }, [ready, authenticated, router]);

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

  const handleTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!privyWallet) {
      setError("No Privy wallet connected. Please connect your Privy wallet.");
      return;
    }

    // Validation
    if (!recipient || !amount) {
      setError("Please fill in all fields");
      return;
    }

    if (!recipient.startsWith("0x") || recipient.length !== 42) {
      setError("Invalid recipient address. Must be a valid Ethereum address (0x...)");
      return;
    }

    const amountNum = parseFloat(amount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setError("Invalid amount. Must be a positive number.");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);
    setTxHash(null);

    try {
      const result = await transferCRO({
        wallet: privyWallet,
        recipient,
        amount,
        network,
      });

      setSuccess(`Transfer successful! Sent ${amount} ${network === 'testnet' ? 'TCRO' : 'CRO'} to ${recipient}`);
      setTxHash(result.hash);
      
      // Clear form
      setRecipient("");
      setAmount("");
    } catch (err: any) {
      console.error("Transfer error:", err);
      setError(err.message || "Transfer failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const explorerUrl = network === "mainnet" 
    ? `https://cronoscan.com/tx/${txHash}`
    : `https://testnet.cronoscan.com/tx/${txHash}`;

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
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center">
              <span className="text-lg">✈️</span>
            </div>
            <span className="font-bold text-gray-900">Transfer</span>
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
        <div className="flex-shrink-0 border-b border-violet-100 bg-gradient-to-r from-white via-emerald-50/30 to-green-50/30 px-6 py-5 shadow-sm hidden md:block">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center shadow-md shadow-emerald-500/30">
              <span className="text-2xl">✈️</span>
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-600 to-green-600 bg-clip-text text-transparent">
                Transfer CRO
              </h1>
            </div>
          </div>
          <p className="text-sm text-gray-600 ml-[52px]">
            Send native CRO tokens to any address on Cronos
          </p>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl mx-auto space-y-6">
            {/* Wallet Info Card */}
            <div className="rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-green-50 p-6 shadow-sm">
              <div className="flex items-center gap-3 mb-3">
                <div className="h-10 w-10 rounded-xl bg-white/80 flex items-center justify-center">
                  <svg className="h-5 w-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-xs font-semibold text-emerald-700">Your Wallet</p>
                  <p className="text-sm font-mono text-gray-700">{walletAddress ? `${walletAddress.slice(0, 10)}...${walletAddress.slice(-8)}` : 'Not connected'}</p>
                </div>
              </div>
            </div>

            {/* Transfer Form */}
            <form onSubmit={handleTransfer} className="rounded-2xl border border-violet-200 bg-white p-8 shadow-lg">
              <h2 className="text-xl font-bold text-gray-900 mb-6">Transfer Details</h2>
              
              {/* Network Selection */}
              <div className="mb-6">
                <label className="block text-sm font-semibold text-gray-700 mb-3">
                  Network
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setNetwork("mainnet")}
                    className={`p-4 rounded-xl border-2 transition-all ${
                      network === "mainnet"
                        ? "border-emerald-500 bg-emerald-50 text-emerald-900"
                        : "border-gray-200 bg-gray-50 text-gray-700 hover:border-emerald-300"
                    }`}
                  >
                    <div className="font-bold text-sm">Cronos Mainnet</div>
                    <div className="text-xs mt-1 opacity-75">Chain ID: 25</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setNetwork("testnet")}
                    className={`p-4 rounded-xl border-2 transition-all ${
                      network === "testnet"
                        ? "border-emerald-500 bg-emerald-50 text-emerald-900"
                        : "border-gray-200 bg-gray-50 text-gray-700 hover:border-emerald-300"
                    }`}
                  >
                    <div className="font-bold text-sm">Cronos Testnet</div>
                    <div className="text-xs mt-1 opacity-75">Chain ID: 338</div>
                  </button>
                </div>
              </div>

              {/* Recipient Address */}
              <div className="mb-6">
                <label htmlFor="recipient" className="block text-sm font-semibold text-gray-700 mb-2">
                  Recipient Address
                </label>
                <input
                  type="text"
                  id="recipient"
                  value={recipient}
                  onChange={(e) => setRecipient(e.target.value)}
                  placeholder="0x..."
                  className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all font-mono text-sm"
                  disabled={loading}
                />
              </div>

              {/* Amount */}
              <div className="mb-6">
                <label htmlFor="amount" className="block text-sm font-semibold text-gray-700 mb-2">
                  Amount ({network === 'testnet' ? 'TCRO' : 'CRO'})
                </label>
                <input
                  type="text"
                  id="amount"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.0"
                  className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all text-lg font-semibold"
                  disabled={loading}
                />
              </div>

              {/* Error Message */}
              {error && (
                <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4">
                  <div className="flex items-center gap-2">
                    <svg className="h-5 w-5 text-red-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-sm text-red-800">{error}</p>
                  </div>
                </div>
              )}

              {/* Success Message */}
              {success && (
                <div className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <div className="flex items-start gap-2">
                    <svg className="h-5 w-5 text-emerald-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <div className="flex-1">
                      <p className="text-sm text-emerald-800 mb-2">{success}</p>
                      {txHash && (
                        <a
                          href={explorerUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:text-emerald-800 underline"
                        >
                          View on Explorer
                          <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading || !privyWallet}
                className="w-full flex items-center justify-center gap-3 rounded-xl bg-gradient-to-r from-emerald-600 to-green-600 px-6 py-4 font-bold text-white shadow-lg shadow-emerald-500/30 hover:shadow-xl hover:scale-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
              >
                {loading ? (
                  <>
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                    <span>Processing Transfer...</span>
                  </>
                ) : (
                  <>
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                    <span>Send Transfer</span>
                  </>
                )}
              </button>
            </form>

            {/* Info Card */}
            <div className="rounded-xl border border-blue-200 bg-blue-50 p-6">
              <div className="flex items-start gap-3">
                <div className="h-8 w-8 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0">
                  <svg className="h-4 w-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-bold text-blue-900 mb-2">Transfer Information</h3>
                  <ul className="text-sm text-blue-800 space-y-1">
                    <li>• Transfers are irreversible - double-check the recipient address</li>
                    <li>• Gas fees will be deducted from your wallet balance</li>
                    <li>• Use testnet for testing with test tokens</li>
                    <li>• Transactions typically confirm in 5-10 seconds</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <RightSidebar isOpen={isRightSidebarOpen} onClose={() => setIsRightSidebarOpen(false)} />
    </div>
  );
}
