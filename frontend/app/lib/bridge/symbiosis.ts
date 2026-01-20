/**
 * Symbiosis Finance Bridge Integration - Client Side Utilities
 * 
 * Server actions are in symbiosis-server.ts
 */

export interface SymbiosisQuote {
  minAmountOut: string;
  fee: string;
  estimatedTime: number;
  chainIdTo: number;
  callData: string;
  tokenAmountOut: string;
}

export interface SymbiosisBridgeResult {
  txHash: string;
  fromChain: string;
  toChain: string;
  amount: string;
  estimatedTime: string;
}

/**
 * Get list of supported destination chains for bridging from Cronos
 */
export function getSupportedDestinations(): Record<string, { name: string; chainId: number }> {
  return {
    ethereum: { name: 'Ethereum', chainId: 1 },
    polygon: { name: 'Polygon', chainId: 137 },
    arbitrum: { name: 'Arbitrum', chainId: 42161 },
    optimism: { name: 'Optimism', chainId: 10 },
    base: { name: 'Base', chainId: 8453 },
    bsc: { name: 'BSC', chainId: 56 },
  };
}
