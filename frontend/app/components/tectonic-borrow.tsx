/**
 * Tectonic Borrow Component
 *
 * Handles USDC borrowing with live health factor display
 * Shows safe borrow limit and warns if HF would drop below 1.2
 */

"use client";

import { useState, useEffect } from "react";
import { TrendingDown, AlertTriangle, AlertCircle, CheckCircle, Zap } from "lucide-react";

interface Position {
  supplied_usdc: number;
  health_factor: number | null;
  health_status: string;
  safe_borrow_limit_usdc: number;
  liquidation_buffer_usdc: number;
  borrowed_usdc: number;
}

interface BorrowComponentProps {
  userAddress?: string;
  onSuccess?: (txHash: string) => void;
}

export function TectonicBorrowComponent({ userAddress, onSuccess, active }: BorrowComponentProps & { active?: boolean }) {
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [projectedHF, setProjectedHF] = useState<number | null>(null);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  // Fetch position on mount and periodically
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

  // Calculate projected HF when amount changes
  useEffect(() => {
    if (position && amount) {
      const borrowAmount = parseFloat(amount);
      const newHF =
        position.health_factor &&
        position.supplied_usdc > 0 &&
        position.borrowed_usdc > 0
          ? position.health_factor * (position.supplied_usdc / (position.supplied_usdc + borrowAmount))
          : null;
      setProjectedHF(newHF);
    } else {
      setProjectedHF(null);
    }
  }, [amount, position]);

  const handleBorrow = async () => {
    if (!amount || !userAddress) {
      setError("Please enter an amount and connect wallet");
      return;
    }

    if (!position) {
      setError("Could not fetch position data");
      return;
    }

    const borrowAmount = parseFloat(amount);
    if (borrowAmount > position.safe_borrow_limit_usdc) {
      setError(
        `Borrow amount exceeds safe limit. Safe limit: ${position.safe_borrow_limit_usdc.toFixed(2)} USDC`
      );
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch(`${apiUrl}/tectonic/borrow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          address: userAddress,
          amount_usdc: borrowAmount,
          check_health_factor: true,
          private_key: process.env.NEXT_PUBLIC_PRIVATE_KEY,
        }),
      });

      const data = await response.json();

      if (data.success && data.tx_hash) {
        setSuccess(`✓ Borrowed ${amount} USDC. Tx: ${data.tx_hash.substring(0, 10)}...`);
        if (data.position_after) {
          setPosition(data.position_after);
        }
        setAmount("");
        onSuccess?.(data.tx_hash);
      } else {
        setError(data.error || "Borrow failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const hfColor =
    !position?.health_factor || position.health_status === "healthy"
      ? "text-green-600"
      : position.health_status === "warning"
        ? "text-yellow-600"
        : "text-red-600";

  return (
    <div className="space-y-4 p-4 border border-slate-300 rounded-lg bg-white">
      <div className="flex items-center gap-2">
        <TrendingDown className="w-5 h-5 text-blue-600" />
        <h3 className="font-semibold text-lg">Borrow USDC</h3>
      </div>

      {position && (
        <div className="grid grid-cols-2 gap-2 p-2 bg-slate-50 rounded text-sm">
          <div>
            <div className="text-xs text-slate-600">Health Factor</div>
            <div className={`font-semibold text-lg ${hfColor}`}>
              {position.health_factor?.toFixed(2) || "N/A"}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-600">Safe Borrow Limit</div>
            <div className="font-semibold">${position.safe_borrow_limit_usdc.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-600">Currently Borrowed</div>
            <div className="font-semibold">${position.borrowed_usdc.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-600">Liquidation Buffer</div>
            <div className="font-semibold text-orange-600">
              ${position.liquidation_buffer_usdc.toFixed(2)}
            </div>
          </div>
        </div>
      )}

      <div className="space-y-2">
        <label className="text-sm font-medium">Amount (USDC)</label>
        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="0.00"
          className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading || !position}
        />
      </div>

      {projectedHF !== null && (
        <div className={`flex items-start gap-2 p-2 rounded text-sm ${
          projectedHF < 1.1
            ? "bg-red-50 border border-red-200 text-red-700"
            : projectedHF < 1.2
              ? "bg-yellow-50 border border-yellow-200 text-yellow-700"
              : "bg-green-50 border border-green-200 text-green-700"
        }`}>
          {projectedHF < 1.1 ? (
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          ) : projectedHF < 1.2 ? (
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          ) : (
            <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          )}
          <div>
            <div className="font-medium">
              Projected HF: {projectedHF.toFixed(2)}
            </div>
            {projectedHF < 1.1 && <div>⚠️ This would make your position liquidatable</div>}
            {projectedHF < 1.2 && projectedHF >= 1.1 && <div>⚠️ Consider less borrowing</div>}
          </div>
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
          <span>{success}</span>
        </div>
      )}

      <button
        onClick={handleBorrow}
        disabled={loading || !amount || !position}
        className="w-full px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition flex items-center justify-center gap-2"
      >
        <Zap className="w-4 h-4" />
        {loading ? "Borrowing..." : "Borrow USDC"}
      </button>
    </div>
  );
}
