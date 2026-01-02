/**
 * Cronos Transfer Function
 * 
 * Native CRO token transfer using Privy with manual signing (no popup).
 * This version uses secp256k1_sign to sign transactions programmatically.
 */

import { ConnectedWallet } from '@privy-io/react-auth';
import { createWalletClient, createPublicClient, http, custom, serializeTransaction, keccak256, recoverAddress } from 'viem';

const CRONOS_MAINNET_CHAIN_ID = 25;
const CRONOS_TESTNET_CHAIN_ID = 338;
const CRONOS_MAINNET_RPC = 'https://evm.cronos.org';
const CRONOS_TESTNET_RPC = 'https://evm-t3.cronos.org';

export type CronosNetwork = 'mainnet' | 'testnet';

function getChainId(network: CronosNetwork): number {
  return network === 'testnet' ? CRONOS_TESTNET_CHAIN_ID : CRONOS_MAINNET_CHAIN_ID;
}

function getRpcUrl(network: CronosNetwork): string {
  return network === 'testnet' ? CRONOS_TESTNET_RPC : CRONOS_MAINNET_RPC;
}

export interface TransferParams {
  wallet: ConnectedWallet;
  recipient: string;
  amount: string;
  network?: CronosNetwork;
}

export interface TransferResult {
  hash: string;
  status: 'pending';
}

/**
 * Transfer native CRO tokens using Privy with manual signing (no popup)
 */
export async function transferCRO(params: TransferParams): Promise<TransferResult> {
  const { wallet, recipient, amount, network = 'mainnet' } = params;
  
  // Verify this is a Privy embedded wallet
  if (wallet.walletClientType && wallet.walletClientType !== 'privy') {
    throw new Error(
      `This function requires a Privy embedded wallet. ` +
      `Current wallet type: ${wallet.walletClientType}. ` +
      `Please use a Privy embedded wallet for programmatic signing.`
    );
  }
  
  // Verify wallet is connected and has an address
  if (!wallet.address) {
    throw new Error(
      `Privy wallet is not connected. ` +
      `Please ensure the Privy embedded wallet is connected before attempting transfers.`
    );
  }
  
  // Get Ethereum provider
  const provider = await wallet.getEthereumProvider();
  const walletAddress = wallet.address.toLowerCase();
  
  // Switch to correct network
  const targetChainId = getChainId(network);
  await wallet.switchChain(targetChainId);
  
  // Wait a bit for network switch to complete
  await new Promise(resolve => setTimeout(resolve, 1000));
  
  // Verify we're on the correct network
  const currentChainId = await provider.request({ method: 'eth_chainId' }) as string;
  const currentChainIdNum = parseInt(currentChainId, 16);
  if (currentChainIdNum !== targetChainId) {
    throw new Error(`Network mismatch. Expected chain ID ${targetChainId} but wallet is on ${currentChainIdNum}. Please switch to ${network === 'testnet' ? 'Cronos Testnet' : 'Cronos Mainnet'}.`);
  }

  // Create viem clients
  const publicClient = createPublicClient({
    transport: http(getRpcUrl(network)),
  });

  const walletClient = createWalletClient({
    account: wallet.address as `0x${string}`,
    transport: custom(provider),
    chain: {
      id: targetChainId,
      name: network === 'testnet' ? 'Cronos Testnet' : 'Cronos',
      nativeCurrency: {
        name: network === 'testnet' ? 'TCRO' : 'CRO',
        symbol: network === 'testnet' ? 'TCRO' : 'CRO',
        decimals: 18,
      },
      rpcUrls: {
        default: { http: [getRpcUrl(network)] },
      },
    },
  });

  // Convert amount to wei
  const value = BigInt(Math.floor(parseFloat(amount) * 1e18));

  // Check wallet balance before attempting transfer
  const balance = await publicClient.getBalance({
    address: wallet.address as `0x${string}`,
  });

  // Prepare transaction - viem auto-fills nonce, gas, gasPrice, etc.
  const prepared = await walletClient.prepareTransactionRequest({
    to: recipient as `0x${string}`,
    value: value,
  });

  // Get gas price from RPC (fallback if prepared doesn't include it)
  const fetchedGasPrice = await publicClient.getGasPrice();
  
  // Use prepared gasPrice if available, otherwise use fetched gasPrice
  // Use the higher of the two if both are available
  const gas = prepared.gas || BigInt(21000);
  const gasPrice = prepared.gasPrice && prepared.gasPrice > fetchedGasPrice
    ? prepared.gasPrice
    : fetchedGasPrice;

  // Calculate total cost (transfer amount + gas fees)
  const gasCost = gas * gasPrice;
  const totalCost = value + gasCost;

  // Check if wallet has sufficient balance
  if (balance < totalCost) {
    const balanceFormatted = (Number(balance) / 1e18).toFixed(6);
    const requiredFormatted = (Number(totalCost) / 1e18).toFixed(6);
    const tokenSymbol = network === 'testnet' ? 'TCRO' : 'CRO';
    throw new Error(
      `Insufficient funds. Your wallet has ${balanceFormatted} ${tokenSymbol}, but you need ${requiredFormatted} ${tokenSymbol} ` +
      `(${(Number(value) / 1e18).toFixed(6)} ${tokenSymbol} for transfer + ${(Number(gasCost) / 1e18).toFixed(6)} ${tokenSymbol} for gas fees). ` +
      `Please add more ${tokenSymbol} to your wallet and try again.`
    );
  }

  // Construct transaction from prepared request
  const transaction = {
    type: 'legacy' as const,
    to: recipient as `0x${string}`,
    value: value,
    gas: gas,
    gasPrice: gasPrice,
    nonce: prepared.nonce,
    chainId: targetChainId,
  };

  // Serialize transaction (unsigned) - this creates the RLP-encoded transaction
  // For EIP-155, the transaction is serialized with chainId included
  const serialized = serializeTransaction(transaction);
  
  // For EIP-155 transactions, we need to hash the serialized transaction
  // The hash is what gets signed - this is the transaction hash (not message hash)
  const hash = keccak256(serialized);

  // Sign hash with Privy embedded wallet (no popup)
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
    throw new Error(
      `Failed to sign transaction with Privy wallet: ${errorMsg}. ` +
      `Please ensure you are using a Privy embedded wallet (walletClientType: 'privy'). ` +
      `Current wallet address: ${wallet.address}`
    );
  }

  // Extract r (32 bytes = 64 hex chars), s (32 bytes = 64 hex chars)
  const r = `0x${signature.slice(2, 66)}` as `0x${string}`;
  const s = `0x${signature.slice(66, 130)}` as `0x${string}`;
  
  // Determine recovery ID from signature
  // Privy's signature includes recovery byte (legacy v value: 27 or 28)
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
  
  // Recover address to verify signature (Privy uses legacy format for recovery)
  const recoveryV = BigInt(recoveryId + 27);
  const recoveredAddr = await recoverAddress({ hash, signature: { r, s, v: recoveryV } });
  
  // Verify recovered address matches wallet address
  if (recoveredAddr.toLowerCase() !== walletAddress) {
    throw new Error(
      `Signature recovery verification failed. ` +
      `Recovered: ${recoveredAddr}, Expected: ${wallet.address}`
    );
  }
  
  // For the transaction, we always use EIP-155 format: v = recovery_id + chain_id * 2 + 35
  const v = BigInt(recoveryId + targetChainId * 2 + 35);

  // Reconstruct signed transaction with correct v value
  const signedTx = serializeTransaction(transaction, { 
    r, 
    s, 
    v 
  });

  // Send raw transaction
  try {
    const txHash = await publicClient.sendRawTransaction({
      serializedTransaction: signedTx as `0x${string}`,
    });
    
    return {
      hash: txHash,
      status: 'pending' as const,
    };
  } catch (error: any) {
    const errorMessage = error?.message || error?.toString() || 'Unknown error';
    const errorData = error?.data || error?.error?.data || error?.error;
    const errorCode = error?.code || error?.error?.code;
    
    if (errorMessage.includes('insufficient funds') || errorMessage.includes('sender balance') || errorCode === -32000) {
      const details = errorData ? ` Details: ${JSON.stringify(errorData)}` : '';
      throw new Error(`Transaction failed due to insufficient funds. ${errorMessage}${details}`);
    }
    
    if (errorMessage.includes('nonce') || errorMessage.includes('Nonce')) {
      throw new Error(`Transaction failed: Nonce error. Please try again. ${errorMessage}`);
    }
    
    if (errorMessage.includes('network') || errorMessage.includes('chain')) {
      throw new Error(`Network error: ${errorMessage}`);
    }
    
    throw new Error(`Transaction failed: ${errorMessage}${errorData ? ` (${JSON.stringify(errorData)})` : ''}${errorCode ? ` [Code: ${errorCode}]` : ''}`);
  }
}

