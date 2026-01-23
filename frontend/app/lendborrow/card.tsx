"use client";
import { useState } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { Sidebar } from "../components/sidebar";
import { RightSidebar } from "../components/right-sidebar";
import LendBorrowPanel from "../components/LendBorrowPanel";

export default function LendBorrowDashboardCard() {
  const { ready, authenticated } = usePrivy();
  const { wallets } = useWallets();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  const walletAddress = wallets[0]?.address || "";

  // Redirect to home if not authenticated
  if (!ready) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gradient-to-br from-violet-50 via-purple-50 to-blue-50 font-sans">
        <div className="text-center">
          <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-violet-200 border-t-violet-600"></div>
          <div className="text-lg font-medium text-gray-700">Loading...</div>
        </div>
      </div>
    );
  }
  if (!authenticated) {
    return null;
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-gradient-to-br from-violet-50/30 via-purple-50/30 to-blue-50/30">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      <div className="flex flex-1 flex-col overflow-hidden border-x border-violet-100 bg-white/80 backdrop-blur-sm">
        {/* Desktop Header */}
        <div className="flex-shrink-0 border-b border-violet-100 bg-gradient-to-r from-white via-blue-50/30 to-green-50/30 px-6 py-5 shadow-sm hidden md:block">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-green-500 to-blue-600 flex items-center justify-center shadow-md shadow-green-500/30">
              <span className="text-2xl">🏦</span>
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-green-600 to-blue-600 bg-clip-text text-transparent">
                Lend/Borrow (Tectonic)
              </h1>
            </div>
          </div>
          <p className="text-sm text-gray-600 ml-[52px]">
            Supply, borrow, repay, and withdraw USDC using Tectonic
          </p>
        </div>
        {/* Main Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto space-y-6">
            <LendBorrowPanel userAddress={walletAddress} />
          </div>
        </div>
      </div>
      <RightSidebar isOpen={isRightSidebarOpen} onClose={() => setIsRightSidebarOpen(false)} />
    </div>
  );
}
