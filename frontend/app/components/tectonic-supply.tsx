/**
 * Tectonic Supply Component
 *
 * Handles USDC deposit with collateral toggle
 * Displays current supplied amount and available to withdraw
 */

"use client";

import { useState, useEffect } from "react";
import { ArrowUp, AlertCircle, CheckCircle } from "lucide-react";

interface SupplyComponentProps {
  userAddress?: string;
  onSuccess?: (txHash: string) => void;
}

export function TectonicSupplyComponent({ userAddress, onSuccess, active }: SupplyComponentProps & { active?: boolean }) {
  const [amount, setAmount] = useState("");
  const [useAsCollateral, setUseAsCollateral] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [suppliedAmount, setSuppliedAmount] = useState(0);
  const [usdcBalance, setUsdcBalance] = useState(0);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  useEffect(() => {
    if (!active) return;
    const fetchBalance = async () => {
      if (!userAddress) return;
      try {
        const response = await fetch(`${apiUrl}/tectonic/position?address=${userAddress}`);
        const data = await response.json();
        if (data.success && data.position) {
          setUsdcBalance(data.position.supplied_usdc || 0);
        }
      } catch (err) {
        // Ignore balance fetch errors for now
      }
    };
    fetchBalance();
  }, [userAddress, apiUrl, active]);

  const handleSupply = async () => {
    if (!amount || !userAddress) {
      setError("Please enter an amount and connect wallet");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch(`${apiUrl}/tectonic/supply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          address: userAddress,
          amount_usdc: parseFloat(amount),
          use_as_collateral: useAsCollateral,
          private_key: process.env.NEXT_PUBLIC_PRIVATE_KEY, // Note: Never hardcode in production
        }),
      });

      const data = await response.json();

      if (data.success && data.tx_hash) {
        setSuccess(`✓ Supplied ${amount} USDC. Tx: ${data.tx_hash.substring(0, 10)}...`);
        setSuppliedAmount(data.position_after?.supplied_usdc || 0);
        setAmount("");
        onSuccess?.(data.tx_hash);
      } else {
        setError(data.error || "Supply failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-green-50 p-8 shadow-lg max-w-xl mx-auto">
      <div className="flex items-center gap-2">
        <ArrowUp className="w-5 h-5 text-green-600" />
        <h3 className="font-semibold text-lg">Supply USDC</h3>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Amount (USDC)</label>
        <div className="flex gap-2">
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="flex-1 px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
            disabled={loading}
          />
          <button
            onClick={() => setAmount(usdcBalance.toString())}
            className="px-3 py-2 text-sm bg-slate-100 border border-slate-300 rounded-md hover:bg-slate-200"
            disabled={loading}
          >
            Max
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="collateral"
          checked={useAsCollateral}
          onChange={(e) => setUseAsCollateral(e.target.checked)}
          disabled={loading}
          className="w-4 h-4"
        />
        <label htmlFor="collateral" className="text-sm font-medium cursor-pointer">
          Use as collateral (enables borrowing)
        </label>
      </div>

      {suppliedAmount > 0 && (
        <div className="text-sm text-slate-600">
          Currently supplied: {suppliedAmount.toFixed(2)} USDC
        </div>
      )}

      {error && (
        <div className="flex gap-2 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="flex gap-2 p-2 bg-green-50 border border-green-200 rounded text-green-700 text-sm">
          <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>
            {success}
            {success.includes('Tx:') && (
              (() => {
                const txHash = success.split('Tx:')[1].trim().replace('...', '');
                const explorerUrl = `https://explorer.cronos.org/tx/${txHash}`;
                return (
                  <>
                    {' '}
                    <a
                      href={explorerUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-700 underline ml-2"
                    >
                      View on Explorer
                    </a>
                  </>
                );
              })()
            )}
          </span>
        </div>
      )}

      <button
        onClick={handleSupply}
        disabled={loading || !amount}
        className="w-full px-4 py-2 bg-green-600 text-white font-medium rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
      >
        {loading ? "Supplying..." : "Supply USDC"}
      </button>
    </div>
  );
}
