"use client";

import { CopilotChat } from "@copilotkit/react-ui";
import { useCopilotReadable, useCopilotAction } from "@copilotkit/react-core";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Sidebar } from "../components/sidebar";
import { RightSidebar } from "../components/right-sidebar";
import { transferCRO } from "@/app/lib/transfer/transfer";
import type { CronosNetwork } from "@/app/lib/transfer/transfer";
import { ConnectedWallet } from "@privy-io/react-auth";

// Component to inject wallet address into CopilotKit context and handle transfer actions
function WalletContextInjector() {
  const { wallets, ready } = useWallets();
  
  // Get Privy embedded wallet only (exclude MetaMask and other external wallets)
  const privyWallet = wallets.find(w => {
    // Explicit Privy embedded wallet
    if (w.walletClientType === 'privy') {
      return true;
    }
    // Embedded wallet (no walletClientType or chainType === 'ethereum')
    if (!w.walletClientType || (w as any).chainType === 'ethereum') {
      // Make sure it's not an external wallet
      return w.walletClientType !== 'metamask' && 
             w.walletClientType !== 'coinbase_wallet' &&
             w.walletClientType !== 'wallet_connect' &&
             w.walletClientType !== 'phantom';
    }
    return false;
  });
  
  const wallet = privyWallet;
  const walletAddress = privyWallet?.address;

  // Make wallet address readable by CopilotKit
  useCopilotReadable({
    description: `User's connected Privy embedded wallet address: ${walletAddress || "Not connected"}`,
    value: walletAddress || null,
  });

  // Create an action that exposes the wallet address
  useCopilotAction({
    name: "get_connected_wallet_address",
    description: "Get the user's connected wallet address. Use this when the user asks for 'my balance' or 'my wallet' without providing an address.",
    parameters: [],
    handler: async () => {
      return {
        walletAddress: walletAddress || null,
        message: walletAddress 
          ? `The user's connected wallet address is ${walletAddress}. Use this address when they ask for their balance.`
          : "No wallet is currently connected.",
      };
    },
  });

  // Handle transfer action from transfer agent
  useCopilotAction({
    name: "initiate_transfer",
    description: "Transfer native CRO tokens on Cronos. This action is triggered when the transfer agent returns a transfer request.",
    parameters: [
      {
        name: "amount",
        type: "string",
        description: "Amount of CRO to transfer (e.g., '1.0')",
        required: true,
      },
      {
        name: "recipient",
        type: "string",
        description: "Recipient wallet address (0x format, 42 characters)",
        required: true,
      },
      {
        name: "network",
        type: "string",
        description: "Network to use: 'mainnet' or 'testnet'. Must be explicitly confirmed by the user before execution.",
        required: true,
      },
    ],
    handler: async ({ amount, recipient, network }) => {
      // Validate network is provided
      if (!network || (network !== "mainnet" && network !== "testnet")) {
        return {
          success: false,
          error: "Network must be explicitly specified as 'mainnet' or 'testnet'. Please confirm which network you want to use before executing the transfer.",
        };
      }
      if (!wallet) {
        return {
          success: false,
          error: "No wallet connected. Please connect your Privy wallet first.",
        };
      }
      
      // Verify it's a Privy embedded wallet (not MetaMask or other external wallets)
      if (!wallet) {
        return {
          success: false,
          error: "No Privy embedded wallet found. Please connect your Privy embedded wallet (not MetaMask or other external wallets).",
        };
      }
      
      // Check if it's an external wallet (MetaMask, Coinbase, etc.)
      if (wallet.walletClientType && 
          wallet.walletClientType !== 'privy' &&
          wallet.walletClientType !== undefined &&
          wallet.walletClientType !== null) {
        return {
          success: false,
          error: `Invalid wallet type. This function requires a Privy embedded wallet, but found: ${wallet.walletClientType}. Please connect your Privy embedded wallet (not MetaMask or other external wallets).`,
        };
      }
      
      // Verify wallet has an address
      if (!wallet.address) {
        return {
          success: false,
          error: "Privy embedded wallet is not properly connected. Please ensure your Privy embedded wallet is connected and has an address.",
        };
      }

      try {
        const result = await transferCRO({
          wallet,
          recipient,
          amount,
          network: network as CronosNetwork,
        });

        return {
          success: true,
          message: `Transfer completed successfully! Sent ${amount} ${network === 'testnet' ? 'TCRO' : 'CRO'} to ${recipient}. Transaction hash: ${result.hash}. You can track this transaction on the Cronos block explorer using the transaction hash.`,
          transactionHash: result.hash,
        };
      } catch (error: any) {
        return {
          success: false,
          error: error.message || "Transfer failed. Please try again.",
        };
      }
    },
  });

    return null;
}

export default function ChatPage() {
  const { ready, authenticated } = usePrivy();
  const { wallets } = useWallets();
  const router = useRouter();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  
  // Get Privy embedded wallet only (exclude MetaMask and other external wallets)
  const privyWallet = wallets.find(w => {
    // Explicit Privy embedded wallet
    if (w.walletClientType === 'privy') {
      return true;
    }
    // Embedded wallet (no walletClientType or chainType === 'ethereum')
    if (!w.walletClientType || (w as any).chainType === 'ethereum') {
      // Make sure it's not an external wallet
      return w.walletClientType !== 'metamask' && 
             w.walletClientType !== 'coinbase_wallet' &&
             w.walletClientType !== 'wallet_connect' &&
             w.walletClientType !== 'phantom';
    }
    return false;
  });
  
  // Get connected wallet address from Privy embedded wallet
  const walletAddress = privyWallet?.address || null;

  // Redirect to home if not authenticated
  useEffect(() => {
    if (ready && !authenticated) {
      router.push("/");
    }
  }, [ready, authenticated, router]);

  // Show loading while checking authentication status
  if (!ready) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gradient-to-br from-violet-50 via-purple-50 to-blue-50 font-sans">
        <div className="text-center">
          <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-violet-200 border-t-violet-600"></div>
          <div className="text-lg font-medium text-gray-700">
            Loading...
          </div>
        </div>
      </div>
    );
  }

  // Redirect if not authenticated (handled by useEffect, but show nothing while redirecting)
  if (!authenticated) {
    return null;
  }

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
            <svg
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
              <svg className="h-4 w-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="font-bold text-gray-900">
              Cronos x402
            </span>
          </div>
          <button
            onClick={() => setIsRightSidebarOpen(true)}
            className="rounded-lg p-2 text-gray-600 hover:bg-violet-50 transition-colors"
          >
            <svg
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
              />
            </svg>
          </button>
        </div>

        <div className="flex-shrink-0 border-b border-violet-100 bg-gradient-to-r from-white via-violet-50/30 to-purple-50/30 px-6 py-5 shadow-sm hidden md:block">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-md shadow-violet-500/30">
              <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-violet-600 to-purple-600 bg-clip-text text-transparent">
                Agent Workspace
              </h1>
            </div>
          </div>
          <p className="text-sm text-gray-600 ml-[52px]">
            Orchestrate intelligent DeFi agents and execute strategies
          </p>
        </div>
        <div className="flex flex-1 flex-col overflow-hidden">
          <WalletContextInjector />
          <CopilotChat
            className="h-full"
            instructions={`You are a Web3 and cryptocurrency assistant. Help users with blockchain operations, balance checks, token swaps, and market analysis. Always be helpful and provide clear, actionable information.${
              walletAddress
                ? `\n\nIMPORTANT: The user has a connected wallet address: ${walletAddress}. When the user asks for "my balance", "fetch my balance", "check my balance", or similar requests without providing an address, automatically use this connected wallet address (${walletAddress}) on the Cronos network.`
                : ""
            }`}
            labels={{
              title: "Cronos Assistant",
              initial: "Hi! 👋 How can I assist you today?",
            }}
          />
        </div>
      </div>

      <RightSidebar
        isOpen={isRightSidebarOpen}
        onClose={() => setIsRightSidebarOpen(false)}
      />
    </div>
  );
}
