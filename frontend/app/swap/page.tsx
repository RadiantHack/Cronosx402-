"use client";

import { useState, useEffect } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { useRouter } from "next/navigation";
import { Sidebar } from "../components/sidebar";
import { RightSidebar } from "../components/right-sidebar";
import { createPublicClient, formatUnits, http, parseUnits } from "viem";
import {
  swapCRO,
  swapToken,
  routerAbi,
  VVS_ROUTER,
  WCRO,
  type CronosNetwork,
  type TokenInfo,
} from "../../app/lib/swap/swap";

// Common token list for Cronos
const CRONOS_TOKENS: Record<string, TokenInfo> = {
  CRO: {
    address: "0x0000000000000000000000000000000000000000",
    symbol: "CRO",
    decimals: 18,
    isNative: true,
  },
  USDC: {
    address: "0xc21223249CA28397B4B6541dfFaEcC539BfF0c59",
    symbol: "USDC",
    decimals: 6,
    isNative: false,
  },
  USDT: {
    address: "0x66e428c3f67a68878562e79A0234c1F83c208770",
    symbol: "USDT",
    decimals: 6,
    isNative: false,
  },
  WCRO: {
    address: "0x5C7F8A570d578ED84E63fdFA7b1eE72dEae1AE23",
    symbol: "WCRO",
    decimals: 18,
    isNative: false,
  },
  VVS: {
    address: "0x2D03bECE6747ADC00E1a131BBA1469C15fD11e03",
    symbol: "VVS",
    decimals: 18,
    isNative: false,
  },
};

// Testnet tokens
const CRONOS_TESTNET_TOKENS: Record<string, TokenInfo> = {
  TCRO: {
    address: "0x0000000000000000000000000000000000000000",
    symbol: "TCRO",
    decimals: 18,
    isNative: true,
  },
  USDC: {
    address: "0x7ef95a0FEE0Dd31b22626fA2e10Ee6A223F8a684",
    symbol: "USDC",
    decimals: 6,
    isNative: false,
  },
  WCRO: {
    address: "0x6a3173618859C7cd40fAF6921b5E9eB6A76f1fD4",
    symbol: "WCRO",
    decimals: 18,
    isNative: false,
  },
};

const CRONOS_MAINNET_RPC = "https://cronos-evm.publicnode.com";
const CRONOS_TESTNET_RPC = "https://cronos-testnet.publicnode.com";

const erc20BalanceOfAbi = [
  {
    type: "function",
    name: "balanceOf",
    stateMutability: "view",
    inputs: [{ name: "account", type: "address" }],
    outputs: [{ name: "", type: "uint256" }],
  },
] as const;

export default function SwapPage() {
  const { ready, authenticated, login } = usePrivy();
  const { wallets } = useWallets();
  const router = useRouter();

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  
  // Form state
  const [network, setNetwork] = useState<CronosNetwork>("mainnet");
  const [fromToken, setFromToken] = useState("CRO");
  const [toToken, setToToken] = useState("USDC");
  const [amount, setAmount] = useState("");
  const [slippage, setSlippage] = useState("0.5");
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [quoting, setQuoting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);
  const [quote, setQuote] = useState<{
    expectedOutput: string;
    minimumOutput: string;
  } | null>(null);
  const [balance, setBalance] = useState<string>("");
  const [balanceLoading, setBalanceLoading] = useState(false);

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

  // Get token list based on network
  const tokenList = network === "mainnet" ? CRONOS_TOKENS : CRONOS_TESTNET_TOKENS;
  const availableTokens = Object.keys(tokenList);

  // Redirect to home if not authenticated
  useEffect(() => {
    if (ready && !authenticated) {
      router.push("/");
    }
  }, [ready, authenticated, router]);

  // Reset quote when inputs change
  useEffect(() => {
    setQuote(null);
    setError(null);
  }, [fromToken, toToken, amount, slippage, network]);

  const fetchQuote = async () => {
    if (!privyWallet) throw new Error("No Privy wallet connected.");

    if (!amount || fromToken === toToken) {
      throw new Error("Please enter amount and select different tokens");
    }

    const amountNum = parseFloat(amount);
    if (isNaN(amountNum) || amountNum <= 0) {
      throw new Error("Invalid amount. Must be a positive number.");
    }

    const from = tokenList[fromToken];
    const to = tokenList[toToken];
    if (!from || !to) {
      throw new Error("Invalid token selection");
    }

    const rpcUrl = network === "mainnet" ? CRONOS_MAINNET_RPC : CRONOS_TESTNET_RPC;
    const publicClient = createPublicClient({ transport: http(rpcUrl) });

    const wcroAddress = tokenList["WCRO"]?.address || WCRO;
    const fromAddress = from.isNative ? wcroAddress : from.address;
    const toAddress = to.isNative ? wcroAddress : to.address;

    if (!fromAddress || !toAddress) {
      throw new Error("Token address missing");
    }

    if (fromAddress.toLowerCase() === toAddress.toLowerCase()) {
      throw new Error("Please select different tokens");
    }

    const amountIn = parseUnits(amount, from.decimals);

    const path = [fromAddress as `0x${string}`, ...(fromAddress.toLowerCase() === wcroAddress.toLowerCase() || toAddress.toLowerCase() === wcroAddress.toLowerCase()
      ? []
      : [wcroAddress as `0x${string}`]), toAddress as `0x${string}`].filter((_, idx, arr) => idx === 0 || arr[idx] !== arr[idx - 1]);

    const amountsOut = await publicClient.readContract({
      address: VVS_ROUTER as `0x${string}`,
      abi: routerAbi,
      functionName: "getAmountsOut",
      args: [amountIn, path],
    });

    const out = amountsOut[amountsOut.length - 1];
    const expectedOutput = formatUnits(out as bigint, to.decimals);
    const slip = Number(slippage);
    const minOut = (out * BigInt(Math.floor((100 - (isNaN(slip) ? 0.5 : slip)) * 100))) / BigInt(100 * 100);
    const minimumOutput = formatUnits(minOut as bigint, to.decimals);

    return { expectedOutput, minimumOutput };
  };

  // Auto-refresh quote when inputs change
  useEffect(() => {
    if (!privyWallet) return;
    if (!amount || fromToken === toToken) return;

    const amountNum = parseFloat(amount);
    if (isNaN(amountNum) || amountNum <= 0) return;

    let cancelled = false;
    const timer = setTimeout(async () => {
      setQuoting(true);
      try {
        const quoteResult = await fetchQuote();

        if (cancelled) return;
        setQuote({
          expectedOutput: quoteResult.expectedOutput,
          minimumOutput: quoteResult.minimumOutput,
        });
      } catch (err: any) {
        if (cancelled) return;
        console.error("Auto-quote error:", err);
        setQuote(null);
        setError(err.message || "Failed to get quote. Please try again.");
      } finally {
        if (!cancelled) setQuoting(false);
      }
    }, 500);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [privyWallet, amount, fromToken, toToken, slippage, network, tokenList]);

  useEffect(() => {
    const fetchBalance = async () => {
      if (!privyWallet?.address) {
        setBalance("");
        return;
      }

      setBalanceLoading(true);
      try {
        const rpcUrl = network === "mainnet" ? CRONOS_MAINNET_RPC : CRONOS_TESTNET_RPC;
        const publicClient = createPublicClient({ transport: http(rpcUrl) });
        const token = tokenList[fromToken];

        if (!token) {
          setBalance("");
          return;
        }

        const rawBalance = token.isNative
          ? await publicClient.getBalance({ address: privyWallet.address as `0x${string}` })
          : await publicClient.readContract({
              address: token.address as `0x${string}`,
              abi: erc20BalanceOfAbi,
              functionName: "balanceOf",
              args: [privyWallet.address as `0x${string}`],
            });

        const formatted = formatUnits(rawBalance as bigint, token.decimals);
        const trimmed = Number(formatted).toLocaleString("en-US", {
          maximumFractionDigits: Math.min(token.decimals, 6),
          useGrouping: false,
        });
        setBalance(trimmed);
      } catch (err) {
        console.error("Balance fetch error", err);
        setBalance("");
      } finally {
        setBalanceLoading(false);
      }
    };

    fetchBalance();
  }, [privyWallet?.address, network, fromToken, tokenList, txHash]);

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

  const handleGetQuote = async () => {
    if (!privyWallet) {
      setError("No Privy wallet connected.");
      return;
    }

    setQuoting(true);
    setError(null);

    try {
      const quoteResult = await fetchQuote();
      setQuote({
        expectedOutput: quoteResult.expectedOutput,
        minimumOutput: quoteResult.minimumOutput,
      });
    } catch (err: any) {
      console.error("Quote error:", err);
      setError(err.message || "Failed to get quote. Please try again.");
    } finally {
      setQuoting(false);
    }
  };

  const handleSwap = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!privyWallet) {
      setError("No Privy wallet connected. Please connect your Privy wallet.");
      return;
    }

    // Validation
    if (!amount || fromToken === toToken) {
      setError("Please enter amount and select different tokens");
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
      const from = tokenList[fromToken];
      const to = tokenList[toToken];

      if (!from || !to) {
        throw new Error("Invalid token selection");
      }

      const result = from.isNative
        ? await swapCRO({
            wallet: privyWallet,
            toToken: to.address,
            amountCRO: amount,
            slippage: parseFloat(slippage),
            network,
          })
        : await swapToken({
            wallet: privyWallet,
            fromToken: from.address,
            toToken: to.address,
            amount,
            slippage: parseFloat(slippage),
            network,
          });

      const approxOut = quote?.expectedOutput || "";
      setSuccess(`Swap successful! Swapped ${amount} ${fromToken} for${approxOut ? ` approximately ${approxOut} ` : " "}${toToken}`.trim());
      setTxHash(result.hash);
      
      // Clear form
      setAmount("");
      setQuote(null);
    } catch (err: any) {
      console.error("Swap error:", err);
      setError(err.message || "Swap failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchTokens = () => {
    const temp = fromToken;
    setFromToken(toToken);
    setToToken(temp);
  };

  const handleSetMaxAmount = () => {
    if (!balance) return;
    setAmount(balance);
  };

  const explorerUrl = network === "mainnet" 
    ? `https://explorer.cronos.org/tx/${txHash}`
    : `https://explorer.cronos.org/testnet/tx/${txHash}`;

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
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-pink-500 to-purple-600 flex items-center justify-center">
              <span className="text-lg">🔁</span>
            </div>
            <span className="font-bold text-gray-900">Swap</span>
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
        <div className="flex-shrink-0 border-b border-violet-100 bg-gradient-to-r from-white via-pink-50/30 to-purple-50/30 px-6 py-5 shadow-sm hidden md:block">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-pink-500 to-purple-600 flex items-center justify-center shadow-md shadow-pink-500/30">
              <span className="text-2xl">🔁</span>
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-pink-600 to-purple-600 bg-clip-text text-transparent">
                Token Swap
              </h1>
            </div>
          </div>
          <p className="text-sm text-gray-600 ml-[52px]">
            Swap tokens instantly using VVS Finance on Cronos
          </p>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl mx-auto space-y-6">
            {/* Wallet Info Card */}
            <div className="rounded-xl border border-pink-200 bg-gradient-to-br from-pink-50 to-purple-50 p-6 shadow-sm">
              <div className="flex items-center gap-3 mb-3">
                <div className="h-10 w-10 rounded-xl bg-white/80 flex items-center justify-center">
                  <svg className="h-5 w-5 text-pink-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-xs font-semibold text-pink-700">Your Wallet</p>
                  <p className="text-sm font-mono text-gray-700">{walletAddress ? `${walletAddress.slice(0, 10)}...${walletAddress.slice(-8)}` : 'Not connected'}</p>
                </div>
              </div>
            </div>

            {/* Swap Form */}
            <form onSubmit={handleSwap} className="rounded-2xl border border-violet-200 bg-white p-8 shadow-lg">
              <h2 className="text-xl font-bold text-gray-900 mb-6">Swap Tokens</h2>
              
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
                        ? "border-pink-500 bg-pink-50 text-pink-900"
                        : "border-gray-200 bg-gray-50 text-gray-700 hover:border-pink-300"
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
                        ? "border-pink-500 bg-pink-50 text-pink-900"
                        : "border-gray-200 bg-gray-50 text-gray-700 hover:border-pink-300"
                    }`}
                  >
                    <div className="font-bold text-sm">Cronos Testnet</div>
                    <div className="text-xs mt-1 opacity-75">Chain ID: 338</div>
                  </button>
                </div>
              </div>

              {/* From Token */}
              <div className="mb-4">
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  From
                </label>
                <div className="flex gap-3">
                  <select
                    value={fromToken}
                    onChange={(e) => setFromToken(e.target.value)}
                    className="px-4 py-3 rounded-xl border border-gray-300 focus:border-pink-500 focus:ring-2 focus:ring-pink-500/20 outline-none transition-all font-semibold bg-white"
                    disabled={loading}
                  >
                    {availableTokens.map((token) => (
                      <option key={token} value={token}>
                        {token}
                      </option>
                    ))}
                  </select>
                  <div className="flex-1 flex gap-2">
                    <input
                      type="text"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      placeholder="0.0"
                      className="flex-1 px-4 py-3 rounded-xl border border-gray-300 focus:border-pink-500 focus:ring-2 focus:ring-pink-500/20 outline-none transition-all text-lg font-semibold"
                      disabled={loading}
                    />
                    <button
                      type="button"
                      onClick={handleSetMaxAmount}
                      disabled={loading || balanceLoading || !balance}
                      className="px-3 py-2 rounded-lg border border-pink-200 bg-pink-50 text-pink-700 font-semibold text-sm hover:bg-pink-100 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Max
                    </button>
                  </div>
                </div>
                <div className="mt-2 text-xs text-gray-600 text-right">
                  {balanceLoading ? "Fetching balance..." : `Balance: ${balance || "0"}`}
                </div>
              </div>

              {/* Switch Button */}
              <div className="flex justify-center -my-2 relative z-10">
                <button
                  type="button"
                  onClick={handleSwitchTokens}
                  className="h-10 w-10 rounded-xl bg-gradient-to-br from-pink-500 to-purple-600 flex items-center justify-center text-white shadow-lg hover:shadow-xl hover:scale-110 transition-all"
                  disabled={loading}
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                  </svg>
                </button>
              </div>

              {/* To Token */}
              <div className="mb-6">
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  To
                </label>
                <div className="flex gap-3">
                  <select
                    value={toToken}
                    onChange={(e) => setToToken(e.target.value)}
                    className="px-4 py-3 rounded-xl border border-gray-300 focus:border-pink-500 focus:ring-2 focus:ring-pink-500/20 outline-none transition-all font-semibold bg-white"
                    disabled={loading}
                  >
                    {availableTokens.map((token) => (
                      <option key={token} value={token}>
                        {token}
                      </option>
                    ))}
                  </select>
                  <div className="flex-1 px-4 py-3 rounded-xl border border-gray-200 bg-gray-50 text-lg font-semibold text-gray-500">
                    {quote ? quote.expectedOutput : "0.0"}
                  </div>
                </div>
              </div>

              {/* Slippage */}
              <div className="mb-6">
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Slippage Tolerance (%)
                </label>
                <div className="flex gap-2">
                  {["0.1", "0.5", "1.0"].map((val) => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => setSlippage(val)}
                      className={`px-4 py-2 rounded-lg font-semibold text-sm transition-all ${
                        slippage === val
                          ? "bg-pink-500 text-white"
                          : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                      }`}
                      disabled={loading}
                    >
                      {val}%
                    </button>
                  ))}
                  <input
                    type="text"
                    value={slippage}
                    onChange={(e) => setSlippage(e.target.value)}
                    placeholder="Custom"
                    className="flex-1 px-3 py-2 rounded-lg border border-gray-300 focus:border-pink-500 outline-none text-sm font-semibold"
                    disabled={loading}
                  />
                </div>
              </div>

              {/* Quote Display */}
              {quote && (
                <div className="mb-6 rounded-xl border border-purple-200 bg-purple-50 p-4">
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-purple-700">Expected Output:</span>
                      <span className="font-bold text-purple-900">{quote.expectedOutput} {toToken}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-purple-700">Minimum Received:</span>
                      <span className="font-semibold text-purple-900">{quote.minimumOutput} {toToken}</span>
                    </div>
                  </div>
                </div>
              )}

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

              {/* Action Buttons */}
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={handleGetQuote}
                  disabled={quoting || loading || !privyWallet || !amount}
                  className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-4 font-bold text-white shadow-lg shadow-purple-500/30 hover:shadow-xl hover:scale-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                >
                  {quoting ? (
                    <>
                      <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                      <span>Getting Quote...</span>
                    </>
                  ) : (
                    <>
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                      <span>Get Quote</span>
                    </>
                  )}
                </button>

                <button
                  type="submit"
                  disabled={loading || !privyWallet || !quote}
                  className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-pink-600 to-purple-600 px-6 py-4 font-bold text-white shadow-lg shadow-pink-500/30 hover:shadow-xl hover:scale-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                >
                  {loading ? (
                    <>
                      <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                      <span>Swapping...</span>
                    </>
                  ) : (
                    <>
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                      </svg>
                      <span>Swap</span>
                    </>
                  )}
                </button>
              </div>
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
                  <h3 className="font-bold text-blue-900 mb-2">Swap Information</h3>
                  <ul className="text-sm text-blue-800 space-y-1">
                    <li>• Powered by VVS Finance DEX</li>
                    <li>• Get a quote first to see expected output</li>
                    <li>• Slippage protects you from price changes</li>
                    <li>• Token approvals may require separate transactions</li>
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
