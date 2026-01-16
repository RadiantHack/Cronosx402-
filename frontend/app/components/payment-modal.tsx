"use client";

import { useState, useEffect } from "react";
import { X, CreditCard, Loader2, Wallet } from "lucide-react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import {
  createWalletClient,
  createPublicClient,
  http,
  custom,
  parseEther,
  serializeTransaction,
  keccak256,
  recoverAddress,
  type Address,
  type WalletClient,
} from "viem";
import { cronos, cronosTestnet } from "viem/chains";

/**
 * Build x402 payment header from signed EVM transaction
 */
function buildEvmPaymentHeader(params: {
  signedTransaction: string;
  network: string;
  scheme?: string;
}): string {
  const header = {
    x402Version: 1,
    scheme: params.scheme || "exact",
    network: params.network,
    payload: {
      rawTransaction: params.signedTransaction,
    },
  };
  return btoa(JSON.stringify(header));
}

interface PaymentRequirements {
  payTo: string;
  maxAmountRequired: string;
  network?: string;
  asset?: string;
  description?: string;
  resource?: string;
  scheme?: string;
}

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPaymentComplete: (paymentHeader: string) => void;
  paymentRequirements?: PaymentRequirements;
}

/**
 * Payment Modal Component for x402 Payment Protocol on Cronos
 * Opens when a 402 Payment Required error is encountered.
 * Uses Privy wallet to sign and pay with CRO tokens.
 */
export function PaymentModal({
  isOpen,
  onClose,
  onPaymentComplete,
  paymentRequirements,
}: PaymentModalProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { ready, authenticated } = usePrivy();
  const { wallets } = useWallets();

  // Get Privy embedded wallet
  const privyWallet = wallets.find((w) => {
    if (w.walletClientType === "privy") return true;
    if (!w.walletClientType || (w as any).chainType === "ethereum") {
      return (
        w.walletClientType !== "metamask" &&
        w.walletClientType !== "coinbase_wallet" &&
        w.walletClientType !== "wallet_connect" &&
        w.walletClientType !== "phantom"
      );
    }
    return false;
  });

  const walletAddress = privyWallet?.address;

  useEffect(() => {
    if (!isOpen) {
      setError(null);
      setIsProcessing(false);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  // Determine network
  const network =
    paymentRequirements?.network === "cronos-testnet"
      ? cronosTestnet
      : cronos;
  const isTestnet = network.id === 338;

  // Calculate amount in CRO (18 decimals)
  const amountInCro = paymentRequirements
    ? (
        parseInt(paymentRequirements.maxAmountRequired, 10) /
        1e18
      ).toFixed(4)
    : "1.0";

  const handlePayment = async () => {
    if (!paymentRequirements) {
      setError("Payment requirements not provided");
      return;
    }

    if (!ready || !authenticated || !privyWallet || !walletAddress) {
      setError("Please connect your Cronos wallet first");
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      // Get EIP-1193 provider from Privy wallet
      const provider = await privyWallet.getEthereumProvider();

      // Create viem wallet client
      const walletClient = createWalletClient({
        account: walletAddress as Address,
        chain: network,
        transport: custom(provider),
      });

      // Create public client for reading blockchain state
      const publicClient = createPublicClient({
        chain: network,
        transport: http('https://cronos-evm.publicnode.com'),
      });

      // Get current chain ID
      const chainId = await walletClient.getChainId();
      if (chainId !== network.id) {
        throw new Error(
          `Please switch to ${isTestnet ? "Cronos Testnet" : "Cronos Mainnet"} (Chain ID ${network.id})`
        );
      }

      // Get nonce and gas price using public client
      const nonce = await publicClient.getTransactionCount({
        address: walletAddress as Address,
      });

      const gasPrice = await publicClient.getGasPrice();

      // Prepare transaction
      const transaction = {
        type: 'legacy' as const,
        to: paymentRequirements.payTo as Address,
        value: BigInt(paymentRequirements.maxAmountRequired),
        nonce,
        gasPrice,
        gas: 21000n, // Standard gas limit for native transfer
        chainId: network.id,
      };

      // Serialize transaction (unsigned) for signing
      const serialized = serializeTransaction(transaction);
      
      // Hash the serialized transaction (this is what gets signed)
      const hash = keccak256(serialized);

      // Sign hash with Privy embedded wallet (no popup!)
      let signature: string;
      try {
        signature = await provider.request({
          method: 'secp256k1_sign',
          params: [hash],
        }) as string;
        
        if (!signature || typeof signature !== 'string') {
          throw new Error('Invalid signature returned from Privy wallet');
        }
      } catch (signError: any) {
        const errorMsg = signError?.message || signError?.toString() || 'Unknown error';
        throw new Error(`Failed to sign transaction: ${errorMsg}`);
      }

      // Extract r, s from signature
      const r = `0x${signature.slice(2, 66)}` as `0x${string}`;
      const s = `0x${signature.slice(66, 130)}` as `0x${string}`;
      
      // Get recovery ID from signature
      if (signature.length < 132) {
        throw new Error(`Invalid signature format. Expected 132 characters, got ${signature.length}`);
      }
      
      const recoveryByte = parseInt(signature.slice(130, 132), 16);
      let recoveryId: number;
      
      if (recoveryByte >= 27 && recoveryByte <= 28) {
        recoveryId = recoveryByte - 27;
      } else if (recoveryByte === 0 || recoveryByte === 1) {
        recoveryId = recoveryByte;
      } else {
        throw new Error(`Invalid recovery byte: ${recoveryByte}`);
      }
      
      // Verify signature by recovering address
      const recoveryV = BigInt(recoveryId + 27);
      const recoveredAddr = await recoverAddress({ 
        hash, 
        signature: { r, s, v: recoveryV } 
      });
      
      // Verify recovered address matches wallet address
      if (recoveredAddr.toLowerCase() !== walletAddress.toLowerCase()) {
        throw new Error(
          `Signature verification failed. ` +
          `Recovered: ${recoveredAddr}, Expected: ${walletAddress}`
        );
      }
      
      // Calculate EIP-155 v value: v = recovery_id + chain_id * 2 + 35
      const v = BigInt(recoveryId + network.id * 2 + 35);

      // Serialize signed transaction
      const signedTx = serializeTransaction(transaction, { r, s, v });

      // Build x402 payment header using x402plus
      const paymentHeader = buildEvmPaymentHeader({
        signedTransaction: signedTx,
        network: isTestnet ? "cronos-testnet" : "cronos",
        scheme: "exact",
      });

      console.log("Payment header created:", paymentHeader.substring(0, 100));

      // Pass payment header back to parent
      onPaymentComplete(paymentHeader);
      onClose();
    } catch (err: any) {
      console.error("Payment error:", err);
      setError(
        err.message ||
          "Payment failed. Please check your wallet and try again."
      );
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl max-w-md w-full p-6 relative">
        {/* Close button */}
        <button
          onClick={onClose}
          disabled={isProcessing}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 bg-violet-100 dark:bg-violet-900/30 rounded-full flex items-center justify-center">
            <CreditCard className="w-6 h-6 text-violet-600 dark:text-violet-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              Payment Required
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              x402 Payment Protocol - Cronos Network
            </p>
          </div>
        </div>

        {/* Payment details */}
        <div className="space-y-4 mb-6">
          <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Amount
              </span>
              <span className="text-lg font-bold text-gray-900 dark:text-white">
                {amountInCro} CRO
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Network
              </span>
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                {isTestnet ? "Cronos Testnet" : "Cronos Mainnet"}
              </span>
            </div>

            {paymentRequirements?.description && (
              <div className="pt-3 border-t border-gray-200 dark:border-gray-700">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {paymentRequirements.description}
                </p>
              </div>
            )}
          </div>

          {/* Wallet info */}
          {walletAddress && (
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              <Wallet className="w-4 h-4" />
              <span className="font-mono">
                {walletAddress.slice(0, 6)}...{walletAddress.slice(-4)}
              </span>
            </div>
          )}

          {/* Error message */}
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            onClick={handlePayment}
            disabled={isProcessing || !ready || !authenticated || !walletAddress}
            className="flex-1 px-4 py-3 bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <CreditCard className="w-5 h-5" />
                Pay {amountInCro} CRO
              </>
            )}
          </button>
        </div>

        {/* Info text */}
        <p className="text-xs text-center text-gray-500 dark:text-gray-400 mt-4">
          This payment unlocks premium access. Your transaction will be signed
          with your Privy wallet.
        </p>
      </div>
    </div>
  );
}
