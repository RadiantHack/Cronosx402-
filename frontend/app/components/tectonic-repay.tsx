/**
 * Tectonic Repay Component
 *
 * Handles borrow repayment with options to repay partial or full amount
 * Shows current borrow amount and remaining balance after repay
 */

"use client";

import { useState, useEffect } from "react";
import { RotateCcw, AlertCircle, CheckCircle } from "lucide-react";

interface Position {
  borrowed_usdc: number;
}

interface RepayComponentProps {
  userAddress?: string;
  onSuccess?: (txHash: string) => void;
}

export function TectonicRepayComponent({ userAddress, onSuccess, active }: RepayComponentProps & { active?: boolean }) {
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

  const handleRepay = async () => {
    if (!userAddress) {
      setError("Please connect wallet");
      return;
    }

    if (!amount && amount !== "") {
      setError("Please enter an amount or click Repay All");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch("/tectonic/repay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          address: userAddress,
          amount_usdc: amount ? parseFloat(amount) : null, // null = repay all
          private_key: process.env.NEXT_PUBLIC_PRIVATE_KEY,
        }),
      });

      const data = await response.json();

      if (data.success && data.tx_hash) {
        const repayMsg = amount ? `${amount} USDC` : "all debt";
        setSuccess(`✓ Repaid ${repayMsg}. Tx: ${data.tx_hash.substring(0, 10)}...`);
        if (data.position_after) {
          setPosition(data.position_after);
        }
        setAmount("");
        onSuccess?.(data.tx_hash);
      } else {
        setError(data.error || "Repay failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const remainingAfterRepay =
    position && amount ? Math.max(0, position.borrowed_usdc - parseFloat(amount)) : null;

  return (
    <div className="space-y-4 p-4 border border-slate-300 rounded-lg bg-white">
      <div className="flex items-center gap-2">
        <RotateCcw className="w-5 h-5 text-purple-600" />
        <h3 className="font-semibold text-lg">Repay Borrow</h3>
      </div>

      {position && (
        <div className="p-2 bg-slate-50 rounded text-sm">
          <div className="flex justify-between items-center">
            <span className="text-slate-600">Current Borrow:</span>
            <span className="font-semibold text-lg">${position.borrowed_usdc.toFixed(2)}</span>
          </div>
          {remainingAfterRepay !== null && (
            <div className="flex justify-between items-center mt-2 pt-2 border-t border-slate-200">
              <span className="text-slate-600">After Repay:</span>
              <span className="font-semibold text-green-600">
                ${remainingAfterRepay.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      )}

      <div className="space-y-2">
        <label className="text-sm font-medium">Amount (USDC) - Leave blank to repay all</label>
        <div className="flex gap-2">
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="flex-1 px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
            disabled={loading || !position}
            max={position?.borrowed_usdc}
          />
          <button
            onClick={() => setAmount(position?.borrowed_usdc.toString() || "")}
            className="px-3 py-2 text-sm bg-slate-100 border border-slate-300 rounded-md hover:bg-slate-200"
            disabled={loading || !position}
          >
            Max
          </button>
        </div>
      </div>

      {error && (
        <div className="flex gap-2 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="flex gap-2 p-2 bg-green-50 border border-green-200 rounded text-green-700 text-sm">
          <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{success}</span>
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleRepay}
          disabled={loading || !position}
          className="flex-1 px-4 py-2 bg-purple-600 text-white font-medium rounded-md hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
        >
          {loading ? "Repaying..." : amount ? "Repay Amount" : "Repay All"}
        </button>
        {amount && (
          <button
            onClick={() => setAmount("")}
            disabled={loading}
            className="px-3 py-2 border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}
