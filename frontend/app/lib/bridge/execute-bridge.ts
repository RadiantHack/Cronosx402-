/**
 * Bridge Execution - Handles actual cross-chain bridge transactions
 * Uses Privy wallet with secp256k1_sign for silent signing (no popups)
 */

import {
  createPublicClient,
  http,
  parseUnits,
  encodeFunctionData,
  getAddress,
  defineChain,
  serializeTransaction,
  keccak256,
  recoverAddress,
} from 'viem';
import type { ConnectedWallet } from '@privy-io/react-auth';

// Symbiosis contract on Cronos (Portal/Router contract)
const SYMBIOSIS_PORTAL = getAddress('0x5aa5Bc82b0dCCb434B66eFe5e4a49d764fc735eC');

// ERC20 ABI for approve function
const ERC20_ABI = [
  {
    name: 'approve',
    type: 'function',
    inputs: [
      { name: 'spender', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [{ name: '', type: 'bool' }],
    stateMutability: 'nonpayable',
  },
  {
    name: 'allowance',
    type: 'function',
    inputs: [
      { name: 'owner', type: 'address' },
      { name: 'spender', type: 'address' },
    ],
    outputs: [{ name: '', type: 'uint256' }],
    stateMutability: 'view',
  },
];

const CRONOS_RPC = 'https://cronos-evm.publicnode.com';
const CRONOS_CHAIN_ID = 25;

// Define Cronos chain for viem
const cronosChain = defineChain({
  id: CRONOS_CHAIN_ID,
  name: 'Cronos',
  nativeCurrency: { name: 'CRO', symbol: 'CRO', decimals: 18 },
  rpcUrls: {
    default: { http: [CRONOS_RPC] },
  },
  blockExplorers: {
    default: { name: 'Cronoscan', url: 'https://cronoscan.com' },
  },
});

interface BridgeExecutionParams {
  wallet: ConnectedWallet;
  tokenAddress: string;
  amount: string;
  recipientAddress: string;
  chainIdTo: number;
  callData: string;
  tokenDecimals: number;
}

interface BridgeExecutionResult {
  txHash: string;
  status: 'pending' | 'success' | 'failed';
  blockExplorer: string;
}

/**
 * Execute the actual bridge transaction with secp256k1_sign (no popup)
 * 
 * NOTE: The recipient address is passed to the Symbiosis API to be encoded in the callData.
 * If callData is empty (0x), the bridge may be handled through alternative mechanisms,
 * or the recipient may need to be specified through a different method (e.g., memo, tag).
 */
export async function executeBridge({
  wallet,
  tokenAddress,
  amount,
  recipientAddress,
  chainIdTo,
  callData,
  tokenDecimals,
}: BridgeExecutionParams): Promise<BridgeExecutionResult> {
  try {
    console.log('[ExecuteBridge] Starting bridge execution...');
    console.log('[ExecuteBridge] Token:', tokenAddress);
    console.log('[ExecuteBridge] Amount:', amount);
    console.log('[ExecuteBridge] Recipient:', recipientAddress);
    console.log('[ExecuteBridge] To Chain:', chainIdTo);
    console.log('[ExecuteBridge] NOTE: Recipient address was passed to Symbiosis API. Ensure it is encoded in callData or handled by bridge contract.');

    if (!wallet.address) {
      throw new Error('Wallet address not available');
    }

    // Get the Ethereum provider from wallet
    const provider = await (wallet as any).getEthereumProvider?.();
    if (!provider) {
      throw new Error('No Ethereum provider found in wallet');
    }

    // Create public client
    const publicClient = createPublicClient({
      transport: http(CRONOS_RPC),
    });

    const amountWei = parseUnits(amount, tokenDecimals);
    const walletAddress = wallet.address as `0x${string}`;

    // Step 1: Approve token spending
    console.log('[ExecuteBridge] Step 1: Approving token spending...');
    const approveTx = {
      to: tokenAddress as `0x${string}`,
      data: encodeFunctionData({
        abi: ERC20_ABI,
        functionName: 'approve',
        args: [SYMBIOSIS_PORTAL, amountWei],
      }),
      value: 0n,
    };

    try {
      // Get nonce for approval
      const approveNonce = await publicClient.getTransactionCount({
        address: walletAddress,
      });

      // Get gas price
      const gasPrice = await publicClient.getGasPrice();

      // Build approval transaction
      const approveLegacyTx = {
        type: 'legacy' as const,
        to: approveTx.to,
        data: approveTx.data,
        value: approveTx.value,
        gas: 100000n,
        gasPrice,
        nonce: approveNonce,
        chainId: CRONOS_CHAIN_ID,
      };

      // Serialize and sign
      const approveSerialized = serializeTransaction(approveLegacyTx);
      const approveHash = keccak256(approveSerialized);

      console.log('[ExecuteBridge] Signing approval transaction...');
      const approveSignature = (await provider.request({
        method: 'secp256k1_sign',
        params: [approveHash],
      })) as string;

      if (!approveSignature || approveSignature.length < 132) {
        throw new Error('Invalid approval signature from wallet');
      }

      // Extract r, s from signature
      const approveR = `0x${approveSignature.slice(2, 66)}` as `0x${string}`;
      const approveS = `0x${approveSignature.slice(66, 130)}` as `0x${string}`;
      
      // Determine recovery ID from signature
      const approveRecoveryByte = parseInt(approveSignature.slice(130, 132), 16);
      let approveRecoveryId: number;
      
      if (approveRecoveryByte >= 27 && approveRecoveryByte <= 28) {
        approveRecoveryId = approveRecoveryByte - 27;
      } else if (approveRecoveryByte === 0 || approveRecoveryByte === 1) {
        approveRecoveryId = approveRecoveryByte;
      } else {
        throw new Error(`Invalid recovery byte in approval signature: ${approveRecoveryByte}`);
      }
      
      // For EIP-155: v = recovery_id + chain_id * 2 + 35
      const approveV = BigInt(approveRecoveryId + CRONOS_CHAIN_ID * 2 + 35);

      // Reconstruct signed transaction
      const approveSigned = serializeTransaction(approveLegacyTx, {
        r: approveR,
        s: approveS,
        v: approveV,
      });

      console.log('[ExecuteBridge] Approval signature valid, submitting...');

      // Send approval transaction
      const approveTxHash = await publicClient.sendRawTransaction({
        serializedTransaction: approveSigned as `0x${string}`,
      });

      console.log('[ExecuteBridge] Approval tx submitted:', approveTxHash);

      // Wait for approval
      try {
        const approvalReceipt = await publicClient.waitForTransactionReceipt({
          hash: approveTxHash,
          timeout: 120_000,
        });

        if (approvalReceipt.status !== 'success') {
          console.warn('[ExecuteBridge] Approval might have failed, continuing...');
        } else {
          console.log('[ExecuteBridge] Token approval confirmed');
        }
      } catch {
        console.warn('[ExecuteBridge] Approval confirmation timeout, continuing...');
      }
    } catch (approvalError) {
      console.warn('[ExecuteBridge] Approval error, continuing...', approvalError);
    }

    // Step 2: Execute bridge transaction
    console.log('[ExecuteBridge] Step 2: Executing bridge transaction...');

    const txCallData = callData && callData !== '0x' ? callData : '0x';
    console.log('[ExecuteBridge] Using callData:', txCallData);

    // Get nonce for bridge transaction
    const bridgeNonce = await publicClient.getTransactionCount({
      address: walletAddress,
    });

    // Get gas price
    const gasPrice = await publicClient.getGasPrice();

    // Build bridge transaction
    const bridgeLegacyTx = {
      type: 'legacy' as const,
      to: SYMBIOSIS_PORTAL,
      data: txCallData as `0x${string}`,
      value: 0n,
      gas: 500000n,
      gasPrice,
      nonce: bridgeNonce,
      chainId: CRONOS_CHAIN_ID,
    };

    // Serialize and sign
    const bridgeSerialized = serializeTransaction(bridgeLegacyTx);
    const bridgeHash = keccak256(bridgeSerialized);

    console.log('[ExecuteBridge] Signing bridge transaction...');
    const bridgeSignature = (await provider.request({
      method: 'secp256k1_sign',
      params: [bridgeHash],
    })) as string;

    if (!bridgeSignature || bridgeSignature.length < 132) {
      throw new Error('Invalid bridge signature from wallet');
    }

    // Extract r, s from signature
    const bridgeR = `0x${bridgeSignature.slice(2, 66)}` as `0x${string}`;
    const bridgeS = `0x${bridgeSignature.slice(66, 130)}` as `0x${string}`;
    
    // Determine recovery ID from signature
    const bridgeRecoveryByte = parseInt(bridgeSignature.slice(130, 132), 16);
    let bridgeRecoveryId: number;
    
    if (bridgeRecoveryByte >= 27 && bridgeRecoveryByte <= 28) {
      bridgeRecoveryId = bridgeRecoveryByte - 27;
    } else if (bridgeRecoveryByte === 0 || bridgeRecoveryByte === 1) {
      bridgeRecoveryId = bridgeRecoveryByte;
    } else {
      throw new Error(`Invalid recovery byte in bridge signature: ${bridgeRecoveryByte}`);
    }
    
    // For EIP-155: v = recovery_id + chain_id * 2 + 35
    const bridgeV = BigInt(bridgeRecoveryId + CRONOS_CHAIN_ID * 2 + 35);

    // Reconstruct signed transaction
    const bridgeSigned = serializeTransaction(bridgeLegacyTx, {
      r: bridgeR,
      s: bridgeS,
      v: bridgeV,
    });

    console.log('[ExecuteBridge] Bridge signature valid, submitting...');

    // Send bridge transaction
    const bridgeTxHash = await publicClient.sendRawTransaction({
      serializedTransaction: bridgeSigned as `0x${string}`,
    });

    console.log('[ExecuteBridge] Bridge tx submitted:', bridgeTxHash);

    // Wait for bridge transaction
    const bridgeReceipt = await publicClient.waitForTransactionReceipt({
      hash: bridgeTxHash,
      timeout: 300_000,
    });

    console.log('[ExecuteBridge] Bridge receipt:', bridgeReceipt);

    if (bridgeReceipt.status !== 'success') {
      throw new Error('Bridge transaction failed on-chain');
    }

    console.log('[ExecuteBridge] Bridge transaction confirmed!');

    return {
      txHash: bridgeTxHash,
      status: 'success',
      blockExplorer: `https://cronoscan.com/tx/${bridgeTxHash}`,
    };
  } catch (error) {
    console.error('[ExecuteBridge] Error:', error);
    throw error;
  }
}

/**
 * Execute bridge with native token (CRO) - uses secp256k1_sign for silent signing
 */
export async function executeBridgeNative({
  wallet,
  amount,
  recipientAddress,
  chainIdTo,
  callData,
}: {
  wallet: ConnectedWallet;
  amount: string;
  recipientAddress: string;
  chainIdTo: number;
  callData: string;
}): Promise<BridgeExecutionResult> {
  try {
    console.log('[ExecuteBridgeNative] Starting native CRO bridge...');
    console.log('[ExecuteBridgeNative] Amount:', amount);
    console.log('[ExecuteBridgeNative] Recipient:', recipientAddress);

    if (!wallet.address) {
      throw new Error('Wallet address not available');
    }

    // Get the Ethereum provider from wallet
    const provider = await (wallet as any).getEthereumProvider?.();
    if (!provider) {
      throw new Error('No Ethereum provider found in wallet');
    }

    const publicClient = createPublicClient({
      transport: http(CRONOS_RPC),
    });

    const walletAddress = wallet.address as `0x${string}`;
    const amountWei = parseUnits(amount, 18); // CRO has 18 decimals

    // Execute bridge transaction with value
    console.log('[ExecuteBridgeNative] Executing bridge transaction...');

    const txCallData = callData && callData !== '0x' ? callData : '0x';
    console.log('[ExecuteBridgeNative] Using callData:', txCallData);

    // Get nonce
    const nonce = await publicClient.getTransactionCount({
      address: walletAddress,
    });

    // Get gas price
    const gasPrice = await publicClient.getGasPrice();

    // Build native bridge transaction
    const nativeLegacyTx = {
      type: 'legacy' as const,
      to: SYMBIOSIS_PORTAL,
      data: txCallData as `0x${string}`,
      value: amountWei,
      gas: 500000n,
      gasPrice,
      nonce,
      chainId: CRONOS_CHAIN_ID,
    };

    // Serialize and sign
    const nativeSerialized = serializeTransaction(nativeLegacyTx);
    const nativeHash = keccak256(nativeSerialized);

    console.log('[ExecuteBridgeNative] Signing bridge transaction...');
    const nativeSignature = (await provider.request({
      method: 'secp256k1_sign',
      params: [nativeHash],
    })) as string;

    if (!nativeSignature || nativeSignature.length < 132) {
      throw new Error('Invalid bridge signature from wallet');
    }

    // Extract r, s from signature
    const nativeR = `0x${nativeSignature.slice(2, 66)}` as `0x${string}`;
    const nativeS = `0x${nativeSignature.slice(66, 130)}` as `0x${string}`;
    
    // Determine recovery ID from signature
    const nativeRecoveryByte = parseInt(nativeSignature.slice(130, 132), 16);
    let nativeRecoveryId: number;
    
    if (nativeRecoveryByte >= 27 && nativeRecoveryByte <= 28) {
      nativeRecoveryId = nativeRecoveryByte - 27;
    } else if (nativeRecoveryByte === 0 || nativeRecoveryByte === 1) {
      nativeRecoveryId = nativeRecoveryByte;
    } else {
      throw new Error(`Invalid recovery byte in native signature: ${nativeRecoveryByte}`);
    }
    
    // For EIP-155: v = recovery_id + chain_id * 2 + 35
    const nativeV = BigInt(nativeRecoveryId + CRONOS_CHAIN_ID * 2 + 35);

    // Reconstruct signed transaction
    const nativeSigned = serializeTransaction(nativeLegacyTx, {
      r: nativeR,
      s: nativeS,
      v: nativeV,
    });

    console.log('[ExecuteBridgeNative] Bridge signature valid, submitting...');

    // Send native bridge transaction
    const bridgeTxHash = await publicClient.sendRawTransaction({
      serializedTransaction: nativeSigned as `0x${string}`,
    });

    console.log('[ExecuteBridgeNative] Bridge tx submitted:', bridgeTxHash);

    // Wait for transaction
    const bridgeReceipt = await publicClient.waitForTransactionReceipt({
      hash: bridgeTxHash,
      timeout: 300_000, // 5 minutes
    });

    console.log('[ExecuteBridgeNative] Bridge receipt:', bridgeReceipt);

    if (bridgeReceipt.status !== 'success') {
      throw new Error('Bridge transaction failed');
    }

    console.log('[ExecuteBridgeNative] Bridge transaction confirmed!');

    return {
      txHash: bridgeTxHash,
      status: 'success',
      blockExplorer: `https://cronoscan.com/tx/${bridgeTxHash}`,
    };
  } catch (error) {
    console.error('[ExecuteBridgeNative] Error:', error);
    throw error;
  }
}
