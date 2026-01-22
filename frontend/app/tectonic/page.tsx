/**
 * Tectonic Lending Page
 *
 * Main interface for Tectonic lending operations
 * Features:
 * - Tab-based navigation (Supply, Borrow, Repay, Withdraw)
 * - Real-time position monitoring (Health Factor, supplied, borrowed)
 * - Liquidation warnings
 * - Integration with A2A application
 */

"use client";

import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@radix-ui/react-tabs";
import { TrendingUp, BarChart3, AlertCircle } from "lucide-react";
import { TectonicSupplyComponent } from "../components/tectonic-supply";
import { TectonicBorrowComponent } from "../components/tectonic-borrow";
import { TectonicRepayComponent } from "../components/tectonic-repay";
import { TectonicWithdrawComponent } from "../components/tectonic-withdraw";

interface Position {
  supplied_usdc: number;
  borrowed_usdc: number;
  health_factor: number | null;
  health_status: string;
  safe_borrow_limit_usdc: number;
  liquidation_buffer_usdc: number;
  is_collateral_enabled: boolean;
  available_liquidity_usdc: number;
}


export default function TectonicPage() {
  // TODO: Get userAddress from context, hook, or provider
  const userAddress = undefined;
  const [position, setPosition] = useState<Position | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch position on mount and periodically
  useEffect(() => {
    const fetchPosition = async () => {
      if (!userAddress) {
        setPosition(null);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const response = await fetch(`/tectonic/position?address=${userAddress}`);
        const data = await response.json();
        if (data.success && data.position) {
          setPosition(data.position);
          setError(null);
        } else {
          setError(data.error || "Failed to fetch position");
        }
      } catch (err) {
        console.error("Failed to fetch position:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchPosition();
    const interval = setInterval(fetchPosition, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, [userAddress]);

  if (!userAddress) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-b from-slate-50 to-white p-4">
        <div className="text-center max-w-md">
          <TrendingUp className="w-12 h-12 mx-auto text-blue-600 mb-4" />
          <h1 className="text-3xl font-bold mb-2">Tectonic Lending</h1>
          <p className="text-slate-600 mb-6">
            Connect your wallet to start earning yield and accessing credit on Cronos
          </p>
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
            <p>🔗 Please connect your wallet to begin</p>
          </div>
        </div>
      </div>
    );
  }

  const getHealthStatusColor = (status: string) => {
    switch (status) {
      case "healthy":
        return "bg-green-100 text-green-800 border-green-300";
      case "warning":
        return "bg-yellow-100 text-yellow-800 border-yellow-300";
      case "critical":
        return "bg-red-100 text-red-800 border-red-300";
      case "liquidatable":
        return "bg-red-200 text-red-900 border-red-400";
      default:
        return "bg-slate-100 text-slate-800 border-slate-300";
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <BarChart3 className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold">Tectonic Lending Protocol</h1>
          </div>
          <p className="text-slate-600">Earn yield by supplying assets and access credit</p>
        </div>

        {/* Position Overview */}
        {position && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            {/* Supplied */}
            <div className="p-4 bg-white border border-slate-200 rounded-lg">
              <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">
                Supplied
              </div>
              <div className="text-2xl font-bold text-green-600">
                ${position.supplied_usdc.toFixed(2)}
              </div>
              <div className="text-xs text-slate-500 mt-2">USDC in collateral</div>
            </div>

            {/* Borrowed */}
            <div className="p-4 bg-white border border-slate-200 rounded-lg">
              <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">
                Borrowed
              </div>
              <div className="text-2xl font-bold text-blue-600">
                ${position.borrowed_usdc.toFixed(2)}
              </div>
              <div className="text-xs text-slate-500 mt-2">Current debt</div>
            </div>

            {/* Health Factor */}
            <div
              className={`p-4 bg-white border border-slate-200 rounded-lg ${
                position.health_factor === null
                  ? ""
                  : position.health_status === "healthy"
                    ? "border-green-300 bg-green-50"
                    : position.health_status === "warning"
                      ? "border-yellow-300 bg-yellow-50"
                      : "border-red-300 bg-red-50"
              }`}
            >
              <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">
                Health Factor
              </div>
              <div
                className={`text-2xl font-bold ${
                  position.health_factor === null
                    ? "text-slate-600"
                    : position.health_status === "healthy"
                      ? "text-green-600"
                      : position.health_status === "warning"
                        ? "text-yellow-600"
                        : "text-red-600"
                }`}
              >
                {position.health_factor?.toFixed(2) || "N/A"}
              </div>
              <div className="text-xs text-slate-500 mt-2">
                {position.health_status === "healthy" && "✓ Safe"}
                {position.health_status === "warning" && "⚠️ Monitor"}
                {position.health_status === "critical" && "⚠️ Critical"}
                {position.health_status === "liquidatable" && "🚨 Liquidatable"}
              </div>
            </div>

            {/* Available to Borrow */}
            <div className="p-4 bg-white border border-slate-200 rounded-lg">
              <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">
                Safe Borrow Limit
              </div>
              <div className="text-2xl font-bold text-purple-600">
                ${position.safe_borrow_limit_usdc.toFixed(2)}
              </div>
              <div className="text-xs text-slate-500 mt-2">Remaining safe capacity</div>
            </div>
          </div>
        )}

        {/* Warnings */}
        {position && position.health_status === "critical" && (
          <div className="mb-8 p-4 bg-red-50 border border-red-300 rounded-lg flex gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-red-900">⚠️ Critical Health Factor</div>
              <p className="text-sm text-red-700 mt-1">
                Your position is at risk of liquidation. Consider repaying your borrow or
                supplying more collateral.
              </p>
            </div>
          </div>
        )}

        {position && position.health_status === "liquidatable" && (
          <div className="mb-8 p-4 bg-red-100 border-2 border-red-500 rounded-lg flex gap-3">
            <AlertCircle className="w-5 h-5 text-red-700 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-red-900">🚨 LIQUIDATION RISK</div>
              <p className="text-sm text-red-800 mt-1">
                Your Health Factor is below 1.0. Your position can be liquidated at any moment.
                Immediately repay your borrow or add collateral.
              </p>
            </div>
          </div>
        )}

        {/* Main Content: Tabs */}
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <Tabs defaultValue="supply" className="w-full">
            <TabsList className="flex border-b border-slate-200 rounded-t-lg bg-slate-50">
              <TabsTrigger
                value="supply"
                className="flex-1 px-4 py-3 text-center font-medium text-sm data-[state=active]:border-b-2 data-[state=active]:border-green-600 data-[state=active]:text-green-600 data-[state=active]:bg-white text-slate-600 rounded-none"
              >
                📥 Supply
              </TabsTrigger>
              <TabsTrigger
                value="borrow"
                className="flex-1 px-4 py-3 text-center font-medium text-sm data-[state=active]:border-b-2 data-[state=active]:border-blue-600 data-[state=active]:text-blue-600 data-[state=active]:bg-white text-slate-600 rounded-none"
              >
                🏦 Borrow
              </TabsTrigger>
              <TabsTrigger
                value="repay"
                className="flex-1 px-4 py-3 text-center font-medium text-sm data-[state=active]:border-b-2 data-[state=active]:border-purple-600 data-[state=active]:text-purple-600 data-[state=active]:bg-white text-slate-600 rounded-none"
              >
                💳 Repay
              </TabsTrigger>
              <TabsTrigger
                value="withdraw"
                className="flex-1 px-4 py-3 text-center font-medium text-sm data-[state=active]:border-b-2 data-[state=active]:border-orange-600 data-[state=active]:text-orange-600 data-[state=active]:bg-white text-slate-600 rounded-none"
              >
                📤 Withdraw
              </TabsTrigger>
            </TabsList>

            <div className="p-6">
              <TabsContent value="supply">
                <TectonicSupplyComponent userAddress={userAddress} />
              </TabsContent>

              <TabsContent value="borrow">
                <TectonicBorrowComponent userAddress={userAddress} />
              </TabsContent>

              <TabsContent value="repay">
                <TectonicRepayComponent userAddress={userAddress} />
              </TabsContent>

              <TabsContent value="withdraw">
                <TectonicWithdrawComponent userAddress={userAddress} />
              </TabsContent>
            </div>
          </Tabs>
        </div>

        {/* Info Section */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2">📚 How it works</h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>✓ Supply USDC to earn yield</li>
              <li>✓ Enable collateral to borrow against</li>
              <li>✓ Borrow up to your health factor limit</li>
              <li>✓ Repay at any time</li>
            </ul>
          </div>

          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <h3 className="font-semibold text-yellow-900 mb-2">⚠️ Health Factor Guide</h3>
            <ul className="text-sm text-yellow-800 space-y-1">
              <li>✓ HF ≥ 1.2: Healthy position</li>
              <li>⚠️ HF 1.1-1.2: Monitor closely</li>
              <li>🔴 HF 1.0-1.1: Critical risk</li>
              <li>🚨 HF &lt; 1.0: Liquidatable</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
