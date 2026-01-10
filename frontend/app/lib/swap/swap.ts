import {
  createPublicClient,
  createWalletClient,
  custom,
  http,
  parseEther,
  isAddress,
  getAddress,
  formatUnits,
  parseUnits,
  encodeFunctionData,
  serializeTransaction,
  keccak256,
} from 'viem';

import type { ConnectedWallet } from '@privy-io/react-auth';

const CRONOS_MAINNET_CHAIN_ID = 25;
const CRONOS_TESTNET_CHAIN_ID = 338;
const CRONOS_MAINNET_RPC = 'https://cronos-evm.publicnode.com';
const CRONOS_TESTNET_RPC = 'https://cronos-testnet.publicnode.com';

export const VVS_ROUTER = '0x145863Eb42Cf62847A6Ca784e6416C1682b1b2Ae';
export const WCRO = '0x5C7F8A570d578ED84E63fdFA7b1eE72dEae1AE23';
const NATIVE_TOKEN = '0x0000000000000000000000000000000000000000';

export type CronosNetwork = 'mainnet' | 'testnet';

function getChainId(network: CronosNetwork): number {
  return network === 'testnet' ? CRONOS_TESTNET_CHAIN_ID : CRONOS_MAINNET_CHAIN_ID;
}

function getRpcUrl(network: CronosNetwork): string {
  return network === 'testnet' ? CRONOS_TESTNET_RPC : CRONOS_MAINNET_RPC;
}

// Helper: sign and send raw legacy transaction via Privy embedded wallet (no popup)
async function signAndSendRaw({
  provider,
  publicClient,
  tx,
  chainId,
}: {
  provider: any;
  publicClient: ReturnType<typeof createPublicClient>;
  tx: {
    to: `0x${string}`;
    data?: `0x${string}`;
    value?: bigint;
    gas: bigint;
    gasPrice: bigint;
    nonce: number;
  };
  chainId: number;
}): Promise<`0x${string}`> {
  const legacyTx = {
    type: 'legacy' as const,
    to: tx.to,
    data: tx.data,
    value: tx.value ?? 0n,
    gas: tx.gas,
    gasPrice: tx.gasPrice,
    nonce: tx.nonce,
    chainId,
  };

  const serialized = serializeTransaction(legacyTx);
  const hash = keccak256(serialized);

  const signature = await provider.request({ method: 'secp256k1_sign', params: [hash] }) as string;
  if (!signature || signature.length < 132) {
    throw new Error('Invalid signature returned from Privy wallet');
  }

  const r = `0x${signature.slice(2, 66)}` as `0x${string}`;
  const s = `0x${signature.slice(66, 130)}` as `0x${string}`;
  const recoveryByte = parseInt(signature.slice(130, 132), 16);
  const recoveryId = recoveryByte >= 27 ? recoveryByte - 27 : recoveryByte;
  const v = BigInt(recoveryId + chainId * 2 + 35);

  const signedTx = serializeTransaction(legacyTx, { r, s, v });
  const txHash = await publicClient.sendRawTransaction({ serializedTransaction: signedTx });
  return txHash;
}

export interface SwapParams {
  wallet: ConnectedWallet;
  toToken: string;      // ERC20 address
  amountCRO: string;    // CRO amount as string
  slippage?: number;    // percent (e.g., 1 = 1%)
  network?: CronosNetwork;
  useManualSigning?: boolean; // when true, sign via secp256k1_sign (no popups)
}

export interface TokenSwapParams {
  wallet: ConnectedWallet;
  fromToken: string;    // Source token address
  toToken: string;      // Destination token address
  amount: string;       // Amount as string (in token's native decimals)
  slippage?: number;    // percent (e.g., 1 = 1%)
  network?: CronosNetwork;
  useManualSigning?: boolean; // when true, sign via secp256k1_sign (no popups)
}

export interface ManualSwapParams extends TokenSwapParams {
  // When true, the swap/approval will be signed programmatically via secp256k1_sign (no popups)
  useManualSigning?: boolean;
}

export interface SwapResult {
  hash: string;
  status: 'pending';
}

// Minimal ABI for VVS router
export const routerAbi = [
  {
    type: 'function',
    name: 'getAmountsOut',
    stateMutability: 'view',
    inputs: [
      { name: 'amountIn', type: 'uint256' },
      { name: 'path', type: 'address[]' },
    ],
    outputs: [{ name: 'amounts', type: 'uint256[]' }],
  },
  {
    type: 'function',
    name: 'swapExactETHForTokens',
    stateMutability: 'payable',
    inputs: [
      { name: 'amountOutMin', type: 'uint256' },
      { name: 'path', type: 'address[]' },
      { name: 'to', type: 'address' },
      { name: 'deadline', type: 'uint256' },
    ],
    outputs: [{ name: 'amounts', type: 'uint256[]' }],
  },
  {
    type: 'function',
    name: 'swapExactTokensForTokens',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'amountIn', type: 'uint256' },
      { name: 'amountOutMin', type: 'uint256' },
      { name: 'path', type: 'address[]' },
      { name: 'to', type: 'address' },
      { name: 'deadline', type: 'uint256' },
    ],
    outputs: [{ name: 'amounts', type: 'uint256[]' }],
  },
  {
    type: 'function',
    name: 'swapExactTokensForETH',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'amountIn', type: 'uint256' },
      { name: 'amountOutMin', type: 'uint256' },
      { name: 'path', type: 'address[]' },
      { name: 'to', type: 'address' },
      { name: 'deadline', type: 'uint256' },
    ],
    outputs: [{ name: 'amounts', type: 'uint256[]' }],
  },
] as const;

// ERC20 ABI for approve and decimals
export const erc20Abi = [
  {
    type: 'function',
    name: 'approve',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'spender', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [{ name: '', type: 'bool' }],
  },
  {
    type: 'function',
    name: 'decimals',
    stateMutability: 'view',
    outputs: [{ name: '', type: 'uint8' }],
  },
  {
    type: 'function',
    name: 'allowance',
    stateMutability: 'view',
    inputs: [
      { name: 'owner', type: 'address' },
      { name: 'spender', type: 'address' },
    ],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    type: 'function',
    name: 'balanceOf',
    stateMutability: 'view',
    inputs: [{ name: 'account', type: 'address' }],
    outputs: [{ name: '', type: 'uint256' }],
  },
] as const;

export async function swapCRO(params: SwapParams): Promise<SwapResult> {
  const { wallet, toToken, amountCRO, slippage = 2, network = 'mainnet' } = params;

  // Route to manual signing flow if requested
  const manualSigning = params.useManualSigning ?? true; // default to no-popup
  if (manualSigning) {
    return swapCROManual(params);
  }

  if (!wallet?.address) throw new Error('Wallet address unavailable.');
  if (!isAddress(toToken)) throw new Error('Invalid toToken address. Must be 0x + 40 hex chars.');

  const toTokenAddress = getAddress(toToken);
  const wCRO = getAddress(WCRO);
  const walletAddress = getAddress(wallet.address as string);

  if (wallet.walletClientType && wallet.walletClientType !== 'privy') {
    throw new Error('Unsupported wallet type; expected Privy wallet.');
  }

  const provider = await wallet.getEthereumProvider();
  const targetChainId = getChainId(network);

  await wallet.switchChain(targetChainId);

  const publicClient = createPublicClient({
    transport: http(getRpcUrl(network)),
  });

  const walletClient = createWalletClient({
    account: walletAddress,
    transport: custom(provider),
    chain: {
      id: targetChainId,
      name: network === 'testnet' ? 'Cronos Testnet' : 'Cronos',
      nativeCurrency: { name: 'CRO', symbol: 'CRO', decimals: 18 },
      rpcUrls: { default: { http: [getRpcUrl(network)] } },
    },
  });

  const amountInWei = parseEther(amountCRO);

  // Build swap path: CRO -> WCRO -> toToken (or direct WCRO)
  const path = toTokenAddress.toLowerCase() === wCRO.toLowerCase()
    ? [wCRO]
    : [wCRO, toTokenAddress];

  // Quote expected out
  const amountsOut = await publicClient.readContract({
    address: VVS_ROUTER,
    abi: routerAbi,
    functionName: 'getAmountsOut',
    args: [amountInWei, path],
  });

  const amountOut = amountsOut[amountsOut.length - 1];
  const minOut =
    (amountOut * BigInt(Math.floor((100 - slippage) * 100))) / BigInt(100 * 100); // slippage %

  const deadline = BigInt(Math.floor(Date.now() / 1000) + 60 * 10); // 10 minutes

  // Estimate gas and double it to pass Privy's internal validation
  let gasLimit: bigint;
  try {
    const gasEstimate = await publicClient.estimateContractGas({
      address: VVS_ROUTER,
      abi: routerAbi,
      functionName: 'swapExactETHForTokens',
      args: [minOut, path, walletAddress, deadline],
      account: walletAddress,
      value: amountInWei,
    });
    gasLimit = gasEstimate * BigInt(2);
    if (gasLimit < BigInt(250000)) gasLimit = BigInt(250000);
  } catch (error) {
    gasLimit = BigInt(300000);
  }

  const hash = await walletClient.writeContract({
    address: VVS_ROUTER,
    abi: routerAbi,
    functionName: 'swapExactETHForTokens',
    args: [minOut, path, walletAddress, deadline],
    value: amountInWei,
    gas: gasLimit,
  });

  return { hash, status: 'pending' };
}

// Manual-sign (no popup) CRO -> token swap using secp256k1_sign
export async function swapCROManual(params: SwapParams): Promise<SwapResult> {
  const { wallet, toToken, amountCRO, slippage = 2, network = 'mainnet' } = params;

  if (!wallet?.address) throw new Error('Wallet address unavailable.');
  if (!isAddress(toToken)) throw new Error('Invalid toToken address. Must be 0x + 40 hex chars.');

  if (wallet.walletClientType && wallet.walletClientType !== 'privy') {
    throw new Error('Unsupported wallet type; expected Privy wallet.');
  }

  const provider = await wallet.getEthereumProvider();
  const walletAddress = getAddress(wallet.address as string);
  const targetChainId = getChainId(network);
  await wallet.switchChain(targetChainId);

  const toTokenAddress = getAddress(toToken);
  const wCRO = getAddress(WCRO);
  const publicClient = createPublicClient({ transport: http(getRpcUrl(network)) });

  const amountInWei = parseEther(amountCRO);

  // Build swap path: CRO -> WCRO -> toToken (or direct WCRO)
  const path = toTokenAddress.toLowerCase() === wCRO.toLowerCase()
    ? [wCRO]
    : [wCRO, toTokenAddress];

  const amountsOut = await publicClient.readContract({
    address: VVS_ROUTER,
    abi: routerAbi,
    functionName: 'getAmountsOut',
    args: [amountInWei, path],
  });

  const amountOut = amountsOut[amountsOut.length - 1];
  const minOut = (amountOut * BigInt(Math.floor((100 - slippage) * 100))) / BigInt(100 * 100);

  // Nonce
  const nonce = await publicClient.getTransactionCount({ address: walletAddress });

  const deadline = BigInt(Math.floor(Date.now() / 1000) + 60 * 10);
  const swapData = encodeFunctionData({
    abi: routerAbi,
    functionName: 'swapExactETHForTokens',
    args: [minOut, path, walletAddress, deadline],
  });

  let swapGas: bigint;
  try {
    const gasEstimate = await publicClient.estimateGas({
      account: walletAddress,
      to: VVS_ROUTER,
      data: swapData,
      value: amountInWei,
    });
    swapGas = gasEstimate * 2n;
    if (swapGas < 250000n) swapGas = 250000n;
  } catch {
    swapGas = 300000n;
  }

  const gasPrice = await publicClient.getGasPrice();
  const txHash = await signAndSendRaw({
    provider,
    publicClient,
    chainId: targetChainId,
    tx: {
      to: VVS_ROUTER,
      data: swapData,
      value: amountInWei,
      gas: swapGas,
      gasPrice,
      nonce: Number(nonce),
    },
  });

  return { hash: txHash, status: 'pending' };
}

export async function swapToken(params: TokenSwapParams): Promise<SwapResult> {
  const { wallet, fromToken, toToken, amount, slippage = 2, network = 'mainnet' } = params;

  // Route to manual signing flow if requested
  const manualSigning = params.useManualSigning ?? true; // default to no-popup
  if (manualSigning) {
    return swapTokenManual(params);
  }

  if (!wallet?.address) throw new Error('Wallet address unavailable.');
  if (!isAddress(fromToken)) throw new Error('Invalid fromToken address. Must be 0x + 40 hex chars.');
  if (!isAddress(toToken)) throw new Error('Invalid toToken address. Must be 0x + 40 hex chars.');

  const fromTokenAddress = getAddress(fromToken);
  const toTokenAddress = getAddress(toToken);
  const wCRO = getAddress(WCRO);
  const walletAddress = getAddress(wallet.address as string);
  const isToNative = toTokenAddress.toLowerCase() === NATIVE_TOKEN.toLowerCase();

  if (wallet.walletClientType && wallet.walletClientType !== 'privy') {
    throw new Error('Unsupported wallet type; expected Privy wallet.');
  }

  const provider = await wallet.getEthereumProvider();
  const targetChainId = getChainId(network);

  await wallet.switchChain(targetChainId);

  const publicClient = createPublicClient({
    transport: http(getRpcUrl(network)),
  });

  const walletClient = createWalletClient({
    account: walletAddress,
    transport: custom(provider),
    chain: {
      id: targetChainId,
      name: network === 'testnet' ? 'Cronos Testnet' : 'Cronos',
      nativeCurrency: { name: 'CRO', symbol: 'CRO', decimals: 18 },
      rpcUrls: { default: { http: [getRpcUrl(network)] } },
    },
  });

  // Get decimals for fromToken
  const fromDecimals = await publicClient.readContract({
    address: fromTokenAddress,
    abi: erc20Abi,
    functionName: 'decimals',
  }) as number;

  const amountInWei = parseUnits(amount, fromDecimals);

  // Build swap path
  let path: `0x${string}`[] = [];
  if (fromTokenAddress.toLowerCase() === toTokenAddress.toLowerCase()) {
    throw new Error('Cannot swap token to itself');
  }

  // Determine path (avoid ZERO_ADDRESS in path)
  if (isToNative) {
    // ERC20 → CRO (native): route through WCRO
    path = [fromTokenAddress, wCRO];
  } else if (fromTokenAddress.toLowerCase() === wCRO.toLowerCase()) {
    path = [wCRO, toTokenAddress];
  } else if (toTokenAddress.toLowerCase() === wCRO.toLowerCase()) {
    path = [fromTokenAddress, wCRO];
  } else {
    path = [fromTokenAddress, wCRO, toTokenAddress];
  }

  // Quote expected out
  const amountsOut = await publicClient.readContract({
    address: VVS_ROUTER,
    abi: routerAbi,
    functionName: 'getAmountsOut',
    args: [amountInWei, path],
  });

  const amountOut = amountsOut[amountsOut.length - 1];
  const minOut =
    (amountOut * BigInt(Math.floor((100 - slippage) * 100))) / BigInt(100 * 100); // slippage %

  // Check and approve if necessary
  const allowance = await publicClient.readContract({
    address: fromTokenAddress,
    abi: erc20Abi,
    functionName: 'allowance',
    args: [walletAddress, VVS_ROUTER],
  }) as bigint;

  if (allowance < amountInWei) {
    console.log('📝 Approving token spend...');
    
    // Estimate gas for approval with 2x buffer
    let approvalGas: bigint;
    try {
      const gasEstimate = await publicClient.estimateContractGas({
        address: fromTokenAddress,
        abi: erc20Abi,
        functionName: 'approve',
        args: [VVS_ROUTER, BigInt(2) ** BigInt(256) - BigInt(1)],
        account: walletAddress,
      });
      approvalGas = gasEstimate * BigInt(2);
      if (approvalGas < BigInt(100000)) approvalGas = BigInt(100000);
    } catch (error) {
      approvalGas = BigInt(150000);
    }
    
    const approveTx = await walletClient.writeContract({
      address: fromTokenAddress,
      abi: erc20Abi,
      functionName: 'approve',
      args: [VVS_ROUTER, BigInt(2) ** BigInt(256) - BigInt(1)], // Max uint256
      gas: approvalGas,
    });
    console.log('✅ Approval confirmed:', approveTx);
  }

  const deadline = BigInt(Math.floor(Date.now() / 1000) + 60 * 10); // 10 minutes

  // Estimate gas and double it to pass Privy's internal validation
  let gasLimit: bigint;
  try {
    const gasEstimate = await publicClient.estimateContractGas({
      address: VVS_ROUTER,
      abi: routerAbi,
      functionName: isToNative ? 'swapExactTokensForETH' : 'swapExactTokensForTokens',
      args: [amountInWei, minOut, path, walletAddress, deadline],
      account: walletAddress,
    });
    console.log('🔍 Gas estimate:', gasEstimate.toString());
    // Double the estimate and ensure minimum 300k for token swaps
    gasLimit = gasEstimate * BigInt(2);
    console.log('🔍 Gas limit after 2x:', gasLimit.toString());
    if (gasLimit < BigInt(300000)) gasLimit = BigInt(300000);
    console.log('🔍 Final gas limit:', gasLimit.toString());
  } catch (error) {
    console.error('⚠️ Gas estimation failed:', error);
    // If estimation fails, use safe default
    gasLimit = BigInt(350000);
  }

  const hash = await walletClient.writeContract({
    address: VVS_ROUTER,
    abi: routerAbi,
    functionName: isToNative ? 'swapExactTokensForETH' : 'swapExactTokensForTokens',
    args: [
      amountInWei,
      minOut,
      path,
      walletAddress,
      deadline,
    ],
    gas: gasLimit,
  });

  return { hash, status: 'pending' };
}

// Manual-sign (no popup) token swap using secp256k1_sign for both approval and swap
export async function swapTokenManual(params: ManualSwapParams): Promise<SwapResult> {
  const { wallet, fromToken, toToken, amount, slippage = 2, network = 'mainnet' } = params;

  if (!wallet?.address) throw new Error('Wallet address unavailable.');
  if (!isAddress(fromToken)) throw new Error('Invalid fromToken address. Must be 0x + 40 hex chars.');
  if (!isAddress(toToken)) throw new Error('Invalid toToken address. Must be 0x + 40 hex chars.');

  if (wallet.walletClientType && wallet.walletClientType !== 'privy') {
    throw new Error('Unsupported wallet type; expected Privy wallet.');
  }

  const provider = await wallet.getEthereumProvider();
  const walletAddress = getAddress(wallet.address as string);
  const targetChainId = getChainId(network);
  await wallet.switchChain(targetChainId);

  const fromTokenAddress = getAddress(fromToken);
  const toTokenAddress = getAddress(toToken);
  const wCRO = getAddress(WCRO);
  const isToNative = toTokenAddress.toLowerCase() === NATIVE_TOKEN.toLowerCase();

  const publicClient = createPublicClient({ transport: http(getRpcUrl(network)) });

  const fromDecimals = await publicClient.readContract({
    address: fromTokenAddress,
    abi: erc20Abi,
    functionName: 'decimals',
  }) as number;

  const amountInWei = parseUnits(amount, fromDecimals);

  let path: `0x${string}`[] = [];
  if (fromTokenAddress.toLowerCase() === toTokenAddress.toLowerCase()) {
    throw new Error('Cannot swap token to itself');
  }
  if (isToNative) {
    path = [fromTokenAddress, wCRO];
  } else if (fromTokenAddress.toLowerCase() === wCRO.toLowerCase()) {
    path = [wCRO, toTokenAddress];
  } else if (toTokenAddress.toLowerCase() === wCRO.toLowerCase()) {
    path = [fromTokenAddress, wCRO];
  } else {
    path = [fromTokenAddress, wCRO, toTokenAddress];
  }

  const amountsOut = await publicClient.readContract({
    address: VVS_ROUTER,
    abi: routerAbi,
    functionName: 'getAmountsOut',
    args: [amountInWei, path],
  });
  const amountOut = amountsOut[amountsOut.length - 1];
  const minOut = (amountOut * BigInt(Math.floor((100 - slippage) * 100))) / BigInt(100 * 100);

  // Base nonce
  let nextNonce = await publicClient.getTransactionCount({ address: walletAddress });

  // Approve if needed (manual sign)
  const allowance = await publicClient.readContract({
    address: fromTokenAddress,
    abi: erc20Abi,
    functionName: 'allowance',
    args: [walletAddress, VVS_ROUTER],
  }) as bigint;

  if (allowance < amountInWei) {
    const approveData = encodeFunctionData({
      abi: erc20Abi,
      functionName: 'approve',
      args: [VVS_ROUTER, BigInt(2) ** BigInt(256) - BigInt(1)],
    });

    let approvalGas: bigint;
    try {
      const gasEstimate = await publicClient.estimateGas({
        account: walletAddress,
        to: fromTokenAddress,
        data: approveData,
        value: 0n,
      });
      approvalGas = gasEstimate * 2n;
      if (approvalGas < 100000n) approvalGas = 100000n;
    } catch {
      approvalGas = 150000n;
    }

    const gasPrice = await publicClient.getGasPrice();
    await signAndSendRaw({
      provider,
      publicClient,
      chainId: targetChainId,
      tx: {
        to: fromTokenAddress,
        data: approveData,
        value: 0n,
        gas: approvalGas,
        gasPrice,
        nonce: Number(nextNonce),
      },
    });
    nextNonce += 1;
  }

  const deadline = BigInt(Math.floor(Date.now() / 1000) + 60 * 10);
  const functionName = isToNative ? 'swapExactTokensForETH' : 'swapExactTokensForTokens';
  const swapData = encodeFunctionData({
    abi: routerAbi,
    functionName,
    args: [amountInWei, minOut, path, walletAddress, deadline],
  });

  let swapGas: bigint;
  try {
    const gasEstimate = await publicClient.estimateGas({
      account: walletAddress,
      to: VVS_ROUTER,
      data: swapData,
      value: 0n,
    });
    swapGas = gasEstimate * 2n;
    if (swapGas < 300000n) swapGas = 300000n;
  } catch {
    swapGas = 350000n;
  }

  const gasPriceSwap = await publicClient.getGasPrice();
  const txHash = await signAndSendRaw({
    provider,
    publicClient,
    chainId: targetChainId,
    tx: {
      to: VVS_ROUTER,
      data: swapData,
      value: 0n,
      gas: swapGas,
      gasPrice: gasPriceSwap,
      nonce: Number(nextNonce),
    },
  });

  return { hash: txHash, status: 'pending' };
}
