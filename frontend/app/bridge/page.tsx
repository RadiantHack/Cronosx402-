'use client';

import { useState } from 'react';
import { useWallets } from '@privy-io/react-auth';
import { bridgeWithSymbiosis, getBridgeTransaction, type SymbiosisBridgeResult } from '@/app/lib/bridge/symbiosis-server';
import { getSupportedDestinations } from '@/app/lib/bridge/symbiosis';
import { executeBridge, executeBridgeNative } from '@/app/lib/bridge/execute-bridge';

type TokenType = 'CRO' | 'USDC';

const TOKEN_DECIMALS = {
  CRO: 18,
  USDC: 6,
};

const CHAIN_IDS: Record<string, number> = {
  cronos: 25,
  ethereum: 1,
  polygon: 137,
  arbitrum: 42161,
  optimism: 10,
  base: 8453,
  bsc: 56,
};

export default function BridgePage() {
  const { wallets } = useWallets();
  const [token, setToken] = useState<TokenType>('CRO');
  const [toChain, setToChain] = useState('ethereum');
  const [amount, setAmount] = useState('');
  const [recipientAddress, setRecipientAddress] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SymbiosisBridgeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);

  const evmWallet = wallets.find((w) => w.walletClientType === 'privy');
  const supportedChains = getSupportedDestinations();
  const availableDestinations = Object.entries(supportedChains).map(([key, val]) => ({
    key,
    ...val,
  }));

  const handleBridge = async () => {
    setError(null);
    setResult(null);
    setTxHash(null);
    
    try {
      if (!amount || parseFloat(amount) <= 0) {
        throw new Error('Please enter a valid amount');
      }
      
      if (!recipientAddress || recipientAddress.length !== 42 || !recipientAddress.startsWith('0x')) {
        throw new Error('Please enter a valid Ethereum address');
      }

      if (!evmWallet) {
        throw new Error('No Privy wallet found. Please connect your wallet first.');
      }

      setLoading(true);

      const chainName = supportedChains[toChain as keyof typeof supportedChains]?.name || toChain;
      console.log(`[BridgePage] Starting bridge: ${amount} ${token} from Cronos to ${chainName}`);
      
      // Get token info
      const tokenDecimals = TOKEN_DECIMALS[token];
      let tokenAddress = '';
      const chainIdFrom = CHAIN_IDS['cronos'];
      const chainIdTo = CHAIN_IDS[toChain as keyof typeof CHAIN_IDS] || 1;

      // Determine token address
      if (token === 'CRO') {
        // WCRO address on Cronos
        tokenAddress = '0x5C7F8A570d578ED84E63fdFA7b1eE72dEae1AE23';
      } else {
        // USDC on Cronos
        tokenAddress = '0xf951eC28187D9E5Ca673Da8FE6757E6f0Be5F77C';
      }

      // Step 1: Get the bridge transaction data from Symbiosis
      console.log('[BridgePage] Getting bridge transaction data...');
      const txData = await getBridgeTransaction({
        tokenIn: tokenAddress,
        tokenSymbol: token,
        chainIdFrom,
        chainIdTo,
        amount,
        fromAddress: evmWallet.address,
        toAddress: recipientAddress,
        slippage: 0.5,
      });

      console.log('[BridgePage] Transaction data:', txData);

      // Allow proceeding even with empty callData (will use fallback)
      // For CRO, we send value directly; for tokens, we approve and use callData if available
      if (!txData.to) {
        throw new Error('Failed to get bridge contract address');
      }

      // Step 2: Execute the bridge transaction with wallet signing
      console.log('[BridgePage] Executing bridge transaction...');
      let executionResult;

      if (token === 'CRO') {
        // Native CRO bridge
        executionResult = await executeBridgeNative({
          wallet: evmWallet,
          amount,
          recipientAddress,
          chainIdTo,
          callData: txData.data,
        });
      } else {
        // USDC token bridge
        executionResult = await executeBridge({
          wallet: evmWallet,
          tokenAddress,
          amount,
          recipientAddress,
          chainIdTo,
          callData: txData.data,
          tokenDecimals,
        });
      }

      console.log('[BridgePage] Execution result:', executionResult);
      setTxHash(executionResult.txHash);

      // Set success result
      setResult({
        txHash: executionResult.txHash,
        fromChain: 'cronos',
        toChain,
        token,
        amount,
        estimatedTime: '15 minutes',
        blockExplorer: executionResult.blockExplorer,
      });
    } catch (err: any) {
      console.error('[BridgePage] Bridge failed:', err);
      setError(err.message || 'Bridge transaction failed');
    } finally {
      setLoading(false);
    }
  };

  const fillMyAddress = () => {
    if (evmWallet?.address) {
      setRecipientAddress(evmWallet.address);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-black to-blue-900 p-8">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Bridge Assets</h1>
          <p className="text-gray-300">Bridge your CRO or USDC from Cronos to other chains using Symbiosis Finance</p>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 shadow-xl">
          {/* Wallet Info */}
          {evmWallet?.address && (
            <div className="mb-6 bg-blue-900/30 border border-blue-500 rounded-lg p-4">
              <p className="text-blue-200 text-sm">
                <strong>💼 Connected Wallet:</strong>
              </p>
              <p className="text-white font-mono text-xs mt-1">{evmWallet.address}</p>
            </div>
          )}

          {/* Bridge Form */}
          <div className="space-y-4">
            {/* Token Selection */}
            <div>
              <label className="block text-white text-sm font-medium mb-2">Select Token</label>
              <div className="flex gap-2">
                {(['CRO', 'USDC'] as const).map((tokenOption) => (
                  <button
                    key={tokenOption}
                    onClick={() => setToken(tokenOption)}
                    className={`flex-1 py-3 rounded-lg font-semibold transition-colors ${
                      token === tokenOption
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    {tokenOption}
                  </button>
                ))}
              </div>
            </div>

            {/* From Chain - Always Cronos */}
            <div>
              <label className="block text-white text-sm font-medium mb-2">From Chain</label>
              <div className="bg-gray-700 rounded-lg px-4 py-3">
                <p className="text-white font-medium">Cronos</p>
              </div>
            </div>

            {/* To Chain */}
            <div>
              <label className="block text-white text-sm font-medium mb-2">To Chain</label>
              <select
                value={toChain}
                onChange={(e) => setToChain(e.target.value)}
                className="w-full bg-gray-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {availableDestinations.map((chain) => (
                  <option key={chain.key} value={chain.key}>
                    {chain.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Amount */}
            <div>
              <label className="block text-white text-sm font-medium mb-2">Amount ({token})</label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.0"
                className="w-full bg-gray-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                step={token === 'CRO' ? '0.1' : '0.000001'}
                min="0"
              />
            </div>

            {/* Recipient Address */}
            <div>
              <label className="block text-white text-sm font-medium mb-2">
                Recipient Address on {supportedChains[toChain as keyof typeof supportedChains]?.name || toChain}
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={recipientAddress}
                  onChange={(e) => setRecipientAddress(e.target.value)}
                  placeholder="0x..."
                  className="flex-1 bg-gray-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <button
                  onClick={() => {
                    if (evmWallet?.address) {
                      setRecipientAddress(evmWallet.address);
                    }
                  }}
                  className="bg-gray-600 hover:bg-gray-500 text-white px-4 py-3 rounded-lg transition-colors"
                  title="Use my wallet address"
                >
                  My Address
                </button>
              </div>
            </div>

            {/* Bridge Button */}
            <button
              onClick={handleBridge}
              disabled={loading || !amount || !recipientAddress}
              className={`w-full py-4 rounded-lg font-bold text-white transition-all ${
                loading || !amount || !recipientAddress
                  ? 'bg-gray-600 cursor-not-allowed'
                  : 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700'
              }`}
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Bridging...
                </span>
              ) : (
                `Bridge ${token} to ${supportedChains[toChain as keyof typeof supportedChains]?.name || toChain}`
              )}
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mt-4 bg-red-900 border border-red-600 rounded-lg p-4">
              <p className="text-red-200 text-sm">❌ {error}</p>
            </div>
          )}

          {/* Success Result */}
          {result && (
            <div className="mt-4 bg-green-900 border border-green-600 rounded-lg p-4">
              <h3 className="text-green-400 font-bold mb-3">✓ Bridge Transaction Submitted!</h3>
              <div className="text-green-200 text-sm space-y-2">
                <p><strong>From:</strong> Cronos</p>
                <p><strong>To:</strong> {result.toChain}</p>
                <p><strong>Token:</strong> {result.token}</p>
                <p><strong>Amount:</strong> {result.amount} {result.token}</p>
                <p><strong>Estimated Time:</strong> {result.estimatedTime}</p>
                
                {txHash && (
                  <div className="mt-3 pt-3 border-t border-green-600">
                    <p className="text-green-300 font-semibold mb-1">Transaction Hash:</p>
                    <div className="bg-green-950 rounded p-2 break-all text-xs font-mono mb-2">
                      {txHash}
                    </div>
                    <a
                      href={`https://cronoscan.com/tx/${txHash}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-xs font-semibold transition-colors"
                    >
                      View on Cronoscan ↗
                    </a>
                  </div>
                )}
                
                <p className="text-green-300 text-xs mt-2">
                  ⏳ Bridge processing can take 10-30 minutes depending on network conditions.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Info Section */}
        <div className="mt-8 bg-gray-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4 text-white">Bridge Information</h2>
          
          <div className="bg-blue-950 border border-blue-600 rounded p-4 mb-4">
            <p className="text-blue-300 text-sm mb-2">
              <strong>Recipient Address Requirement:</strong>
            </p>
            <p className="text-blue-200 text-xs">
              Your specified recipient address ({recipientAddress || 'None'}) must be included in the Symbiosis bridge transaction callData. 
              Verify that your destination address is correct before confirming the transaction. 
              Some bridges may require additional configuration to route tokens to the recipient.
            </p>
          </div>
          <h2 className="text-xl font-bold text-white mb-4">How It Works</h2>
          <div className="space-y-3 text-gray-300 text-sm">
            <div className="flex items-start">
              <span className="text-purple-400 mr-3 font-bold">1.</span>
              <p>Select the token you want to bridge (CRO or USDC)</p>
            </div>
            <div className="flex items-start">
              <span className="text-purple-400 mr-3 font-bold">2.</span>
              <p>Enter the amount from your Cronos wallet</p>
            </div>
            <div className="flex items-start">
              <span className="text-purple-400 mr-3 font-bold">3.</span>
              <p>Select your destination chain (Ethereum, Polygon, Arbitrum, etc.)</p>
            </div>
            <div className="flex items-start">
              <span className="text-purple-400 mr-3 font-bold">4.</span>
              <p>Enter the recipient address (can be your own wallet)</p>
            </div>
            <div className="flex items-start">
              <span className="text-purple-400 mr-3 font-bold">5.</span>
              <p>Click "Bridge" and wait for confirmation</p>
            </div>
          </div>

          <div className="mt-4 p-3 bg-blue-900/30 border border-blue-500 rounded">
            <p className="text-blue-200 text-sm">
              🔗 <strong>Powered by Symbiosis Finance</strong> - A secure, decentralized cross-chain bridge
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
