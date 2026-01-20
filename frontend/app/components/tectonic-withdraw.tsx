/**
 * Tectonic Withdraw Component
 *
 * Handles USDC withdrawal from supply with liquidation warnings
 * Shows max withdrawable without triggering liquidation
 */

"use client";

import { useState, useEffect } from "react";
import { ArrowDown, AlertTriangle, AlertCircle, CheckCircle } from "lucide-react";

interface Position {
  supplied_usdc: number;
  health_factor: number | null;
  health_status: string;
  liquidation_buffer_usdc: number;
}

interface WithdrawComponentProps {
  userAddress?: string;
  onSuccess?: (txHash: string) => void;
}

export function TectonicWithdrawComponent({ userAddress, onSuccess, active }: WithdrawComponentProps & { active?: boolean }) {
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [position, setPosition] = useState<Position | null>(null);

  // Fetch position on mount and periodically
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
  useEffect(() => {
    if (!active) return;
    const fetchPosition = async () => {
      if (!userAddress) return;
      try {
        const response = await fetch(`${apiUrl}/tectonic/position?address=${userAddress}`);
        const data = await response.json();
        if (data.success && data.position) {
          setPosition(data.position);
        }
      } catch (err) {
        console.error("Failed to fetch position:", err);
      }
    };
    fetchPosition();
  }, [userAddress, apiUrl, active]);

  const handleWithdraw = async () => {
    if (!userAddress) {
      setError("Please connect wallet");
      return;
    }

    if (!amount) {
      setError("Please enter an amount");
      return;
    }

    const withdrawAmount = parseFloat(amount);
    if (withdrawAmount > (position?.supplied_usdc || 0)) {
      setError("Insufficient supplied amount");
      return;
    }

    // Warning if close to liquidation
    if (position && withdrawAmount > position.liquidation_buffer_usdc * 0.8) {
      const confirmed = window.confirm(
        "⚠️ This withdrawal is close to liquidation risk. Continue?"
      );
      if (!confirmed) return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const response = await fetch(`${apiUrl}/tectonic/withdraw`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          address: userAddress,
          amount_usdc: withdrawAmount,
          private_key: process.env.NEXT_PUBLIC_PRIVATE_KEY,
        }),
      });

      const data = await response.json();

      if (data.success && data.tx_hash) {
        setSuccess(`✓ Withdrew ${amount} USDC. Tx: ${data.tx_hash}`);
        if (data.position_after) {
          setPosition(data.position_after);
        }
        setAmount("");
        onSuccess?.(data.tx_hash);
      } else {
        setError(data.error || "Withdraw failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const remainingAfterWithdraw =
    position && amount
      ? Math.max(0, position.supplied_usdc - parseFloat(amount))
      : null;

  const maxSafeWithdraw =
    position && position.health_factor
      ? Math.max(0, position.liquidation_buffer_usdc * 0.9)
      : null;

  return (
    <div className="space-y-4 p-4 border border-slate-300 rounded-lg bg-white">
      <div className="flex items-center gap-2">
        <ArrowDown className="w-5 h-5 text-orange-600" />
        <h3 className="font-semibold text-lg">Withdraw USDC</h3>
      </div>

      {position && (
        <div className="space-y-2 p-2 bg-slate-50 rounded text-sm">
          <div className="flex justify-between items-center">
            <span className="text-slate-600">Supplied:</span>
            <span className="font-semibold">${position.supplied_usdc.toFixed(2)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-600">Health Factor:</span>
            <span
              className={`font-semibold ${
                position.health_status === "healthy"
                  ? "text-green-600"
                  : position.health_status === "warning"
                    ? "text-yellow-600"
                    : "text-red-600"
              }`}
            >
              {position.health_factor?.toFixed(2) || "N/A"}
            </span>
          </div>
          {maxSafeWithdraw !== null && (
            <div className="flex justify-between items-center pt-2 border-t border-slate-200">
              <span className="text-slate-600 text-xs">Max Safe Withdraw:</span>
              <span className="font-semibold text-orange-600">
                ${maxSafeWithdraw.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      )}

      <div className="space-y-2">
        <label className="text-sm font-medium">Amount (USDC)</label>
        <div className="flex gap-2">
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="flex-1 px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
            disabled={loading || !position}
            max={position?.supplied_usdc}
          />
          <button
            onClick={() => setAmount(position?.supplied_usdc.toString() || "")}
            className="px-3 py-2 text-sm bg-slate-100 border border-slate-300 rounded-md hover:bg-slate-200"
            disabled={loading || !position}
          >
            Max
          </button>
        </div>
      </div>

      {amount && remainingAfterWithdraw !== null && (
        <div className="p-2 bg-slate-50 rounded text-sm">
          <div className="flex justify-between items-center">
            <span className="text-slate-600">After Withdrawal:</span>
            <span className="font-semibold">
              ${remainingAfterWithdraw.toFixed(2)}
            </span>
          </div>
        </div>
      )}

      {amount && position && parseFloat(amount) > position.liquidation_buffer_usdc * 0.8 && (
        <div className="flex gap-2 p-2 bg-yellow-50 border border-yellow-200 rounded text-yellow-700 text-sm">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>⚠️ Withdrawal is close to liquidation risk</span>
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
            {success.includes('Tx:') && (() => {
              const txHash = success.split('Tx:')[1].trim();
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
            })()}
          </span>
        </div>
      )}

      <button
        onClick={handleWithdraw}
        disabled={loading || !amount || !position}
        className="w-full px-4 py-2 bg-orange-600 text-white font-medium rounded-md hover:bg-orange-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
      >
        {loading ? "Withdrawing..." : "Withdraw USDC"}
      </button>
    </div>
  );
}
