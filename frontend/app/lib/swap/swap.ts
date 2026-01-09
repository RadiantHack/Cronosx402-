/**
 * Cronos Token Swap Function
 * 
 * Token swap using VVS Finance router on Cronos with Privy wallet
 * Supports CRO->Token, Token->CRO, and Token->Token swaps
 */

import { ConnectedWallet } from '@privy-io/react-auth';
import { createWalletClient, createPublicClient, http, custom, parseUnits, formatUnits } from 'viem';

const CRONOS_MAINNET_CHAIN_ID = 25;
const CRONOS_TESTNET_CHAIN_ID = 338;
const CRONOS_MAINNET_RPC = 'https://evm.cronos.org';
const CRONOS_TESTNET_RPC = 'https://evm-t3.cronos.org';

// VVS Finance Router Addresses
const VVS_ROUTER_MAINNET = '0x145863Eb42Cf62847A6Ca784e6416C1682b1b2Ae';
const VVS_ROUTER_TESTNET = '0x145863Eb42Cf62847A6Ca784e6416C1682b1b2Ae'; // Update if different

// Wrapped CRO addresses
const WCRO_MAINNET = '0x5C7F8A570d578ED84E63fdFA7b1eE72dEae1AE23';
const WCRO_TESTNET = '0x6a3173618859C7cd40fAF6921b5E9eB6A76f1fD4';

export type CronosNetwork = 'mainnet' | 'testnet';

function getChainId(network: CronosNetwork): number {
  return network === 'testnet' ? CRONOS_TESTNET_CHAIN_ID : CRONOS_MAINNET_CHAIN_ID;
}

function getRpcUrl(network: CronosNetwork): string {
  return network === 'testnet' ? CRONOS_TESTNET_RPC : CRONOS_MAINNET_RPC;
}

function getVVSRouter(network: CronosNetwork): string {
  return network === 'testnet' ? VVS_ROUTER_TESTNET : VVS_ROUTER_MAINNET;
}

function getWCRO(network: CronosNetwork): string {
  return network === 'testnet' ? WCRO_TESTNET : WCRO_MAINNET;
}

export interface TokenInfo {
  address: string;
  symbol: string;
  decimals: number;
  isNative?: boolean;
}

export interface SwapParams {
  wallet: ConnectedWallet;
  fromToken: TokenInfo;
  toToken: TokenInfo;
  amount: string;
  slippage?: number; // in percentage, default 0.5%
  network?: CronosNetwork;
}

export interface SwapResult {
  hash: string;
  status: 'pending';
  amountIn: string;
  expectedAmountOut: string;
}

export interface SwapQuote {
  amountIn: string;
  expectedAmountOut: string;
  minimumAmountOut: string;
  priceImpact: string;
  route: string[];
}

// ERC20 ABI (minimal)
const ERC20_ABI = [
  {
    "constant": true,
    "inputs": [{"name": "_owner", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "type": "function"
  },
  {
    "constant": false,
    "inputs": [
      {"name": "_spender", "type": "address"},
      {"name": "_value", "type": "uint256"}
    ],
    "name": "approve",
    "outputs": [{"name": "", "type": "bool"}],
    "type": "function"
  },
  {
    "constant": true,
    "inputs": [
      {"name": "_owner", "type": "address"},
      {"name": "_spender", "type": "address"}
    ],
    "name": "allowance",
    "outputs": [{"name": "", "type": "uint256"}],
    "type": "function"
  }
] as const;

// VVS Router ABI (minimal for swaps)
const VVS_ROUTER_ABI = [
  {
    "inputs": [
      {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
      {"internalType": "address[]", "name": "path", "type": "address[]"}
    ],
    "name": "getAmountsOut",
    "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
      {"internalType": "address[]", "name": "path", "type": "address[]"},
      {"internalType": "address", "name": "to", "type": "address"},
      {"internalType": "uint256", "name": "deadline", "type": "uint256"}
    ],
    "name": "swapExactETHForTokens",
    "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
    "stateMutability": "payable",
    "type": "function"
  },
  {
    "inputs": [
      {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
      {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
      {"internalType": "address[]", "name": "path", "type": "address[]"},
      {"internalType": "address", "name": "to", "type": "address"},
      {"internalType": "uint256", "name": "deadline", "type": "uint256"}
    ],
    "name": "swapExactTokensForETH",
    "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
      {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
      {"internalType": "address[]", "name": "path", "type": "address[]"},
      {"internalType": "address", "name": "to", "type": "address"},
      {"internalType": "uint256", "name": "deadline", "type": "uint256"}
    ],
    "name": "swapExactTokensForTokens",
    "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
    "stateMutability": "nonpayable",
    "type": "function"
  }
] as const;

/**
 * Get a quote for a swap without executing it
 */
export async function getSwapQuote(params: SwapParams): Promise<SwapQuote> {
  const { fromToken, toToken, amount, slippage = 0.5, network = 'mainnet' } = params;

  const publicClient = createPublicClient({
    transport: http(getRpcUrl(network)),
  });

  // Convert amount to wei
  const amountIn = parseUnits(amount, fromToken.decimals);

  // Build swap path
  const wcroAddress = getWCRO(network);
  let path: string[];
  
  if (fromToken.isNative) {
    path = [wcroAddress, toToken.address];
  } else if (toToken.isNative) {
    path = [fromToken.address, wcroAddress];
  } else {
    path = [fromToken.address, wcroAddress, toToken.address];
  }

  // Get amounts out from VVS router
  const routerAddress = getVVSRouter(network);
  const amounts = await publicClient.readContract({
    address: routerAddress as `0x${string}`,
    abi: VVS_ROUTER_ABI,
    functionName: 'getAmountsOut',
    args: [amountIn, path as `0x${string}`[]],
  }) as bigint[];

  const expectedAmountOut = amounts[amounts.length - 1];
  const minimumAmountOut = (expectedAmountOut * BigInt(Math.floor((100 - slippage) * 100))) / BigInt(10000);

  return {
    amountIn: formatUnits(amountIn, fromToken.decimals),
    expectedAmountOut: formatUnits(expectedAmountOut, toToken.decimals),
    minimumAmountOut: formatUnits(minimumAmountOut, toToken.decimals),
    priceImpact: '0', // Calculate if needed
    route: path,
  };
}

/**
 * Execute a token swap on Cronos using VVS Finance
 */
export async function swapTokens(params: SwapParams): Promise<SwapResult> {
  const { wallet, fromToken, toToken, amount, slippage = 0.5, network = 'mainnet' } = params;

  // Verify this is a Privy embedded wallet
  if (wallet.walletClientType && wallet.walletClientType !== 'privy') {
    throw new Error(
      `This function requires a Privy embedded wallet. ` +
      `Current wallet type: ${wallet.walletClientType}.`
    );
  }

  if (!wallet.address) {
    throw new Error('Privy wallet is not connected.');
  }

  // Get Ethereum provider
  const provider = await wallet.getEthereumProvider();

  // Switch to correct network
  const targetChainId = getChainId(network);
  await wallet.switchChain(targetChainId);
  await new Promise(resolve => setTimeout(resolve, 1000));

  // Create clients
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
  const amountIn = parseUnits(amount, fromToken.decimals);

  // Build swap path
  const wcroAddress = getWCRO(network);
  let path: string[];
  
  if (fromToken.isNative) {
    path = [wcroAddress, toToken.address];
  } else if (toToken.isNative) {
    path = [fromToken.address, wcroAddress];
  } else {
    path = [fromToken.address, wcroAddress, toToken.address];
  }

  // Get quote
  const routerAddress = getVVSRouter(network);
  const amounts = await publicClient.readContract({
    address: routerAddress as `0x${string}`,
    abi: VVS_ROUTER_ABI,
    functionName: 'getAmountsOut',
    args: [amountIn, path as `0x${string}`[]],
  }) as bigint[];

  const expectedAmountOut = amounts[amounts.length - 1];
  const minimumAmountOut = (expectedAmountOut * BigInt(Math.floor((100 - slippage) * 100))) / BigInt(10000);

  // Set deadline (10 minutes from now)
  const deadline = BigInt(Math.floor(Date.now() / 1000) + 600);

  let hash: string;

  // Execute swap based on token types
  if (fromToken.isNative) {
    // CRO -> Token: swapExactETHForTokens
    hash = await walletClient.writeContract({
      address: routerAddress as `0x${string}`,
      abi: VVS_ROUTER_ABI,
      functionName: 'swapExactETHForTokens',
      args: [minimumAmountOut, path as `0x${string}`[], wallet.address as `0x${string}`, deadline],
      value: amountIn,
    });
  } else if (toToken.isNative) {
    // Token -> CRO: swapExactTokensForETH
    // First approve router to spend tokens
    await approveToken(
      walletClient,
      publicClient,
      fromToken.address as `0x${string}`,
      routerAddress as `0x${string}`,
      amountIn,
      wallet.address as `0x${string}`
    );

    hash = await walletClient.writeContract({
      address: routerAddress as `0x${string}`,
      abi: VVS_ROUTER_ABI,
      functionName: 'swapExactTokensForETH',
      args: [amountIn, minimumAmountOut, path as `0x${string}`[], wallet.address as `0x${string}`, deadline],
    });
  } else {
    // Token -> Token: swapExactTokensForTokens
    // First approve router to spend tokens
    await approveToken(
      walletClient,
      publicClient,
      fromToken.address as `0x${string}`,
      routerAddress as `0x${string}`,
      amountIn,
      wallet.address as `0x${string}`
    );

    hash = await walletClient.writeContract({
      address: routerAddress as `0x${string}`,
      abi: VVS_ROUTER_ABI,
      functionName: 'swapExactTokensForTokens',
      args: [amountIn, minimumAmountOut, path as `0x${string}`[], wallet.address as `0x${string}`, deadline],
    });
  }

  return {
    hash,
    status: 'pending',
    amountIn: formatUnits(amountIn, fromToken.decimals),
    expectedAmountOut: formatUnits(expectedAmountOut, toToken.decimals),
  };
}

/**
 * Approve token spending for router
 */
async function approveToken(
  walletClient: any,
  publicClient: any,
  tokenAddress: `0x${string}`,
  spenderAddress: `0x${string}`,
  amount: bigint,
  ownerAddress: `0x${string}`
): Promise<void> {
  // Check current allowance
  const allowance = await publicClient.readContract({
    address: tokenAddress,
    abi: ERC20_ABI,
    functionName: 'allowance',
    args: [ownerAddress, spenderAddress],
  }) as bigint;

  // If allowance is sufficient, no need to approve
  if (allowance >= amount) {
    return;
  }

  // Approve the router to spend tokens
  const hash = await walletClient.writeContract({
    address: tokenAddress,
    abi: ERC20_ABI,
    functionName: 'approve',
    args: [spenderAddress, amount],
  });

  // Wait for approval transaction to be mined
  await publicClient.waitForTransactionReceipt({ hash });
}
