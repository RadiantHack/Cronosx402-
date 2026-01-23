/**
 * CopilotKit API Route with A2A Middleware
 *
 * This connects the frontend to multiple agents using two protocols:
 * - AG-UI Protocol: Frontend ↔ Orchestrator (via CopilotKit)
 * - A2A Protocol: Orchestrator ↔ Specialized Agents (Balance, etc.)
 *
 * The A2A middleware injects send_message_to_a2a_agent tool into the orchestrator,
 * enabling seamless agent-to-agent communication without the orchestrator needing
 * to understand A2A Protocol directly.
 */

import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { A2AMiddlewareAgent } from "@ag-ui/a2a-middleware";
import { NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  // Get base URL - prioritize NEXT_PUBLIC_BASE_URL for Railway/production
  // Remove trailing slash if present to avoid double slashes
  const rawBaseUrl = process.env.NEXT_PUBLIC_BASE_URL;
  if (!rawBaseUrl) {
    throw new Error("NEXTPUBLIC_BASE_URL is not set in environment variables.");
  }
  const baseUrl = rawBaseUrl.replace(/\/$/, "");

  // Agent URLs - only include agents that are currently implemented
  const balanceAgentUrl = `${baseUrl}/balance`;
  const transferAgentUrl = `${baseUrl}/transfer`;
  // Orchestrator URL needs trailing slash to avoid 307 redirect (POST -> GET conversion)
  // This works for both local (localhost:8000) and Railway (https://backend.railway.app)
  const orchestratorUrl = `${baseUrl}/orchestrator/`;

  // ============================================
  // EXTRACT WALLET ADDRESS FROM REQUEST
  // ============================================
  
  // Try to extract wallet address from request body (CopilotKit may include it in context)
  let connectedWalletAddress: string | null = null;
  try {
    const requestBody = await request.clone().json().catch(() => null);
    if (requestBody) {
      // Check for wallet address in various possible locations
      if (requestBody.context?.walletAddress) {
        connectedWalletAddress = requestBody.context.walletAddress;
      } else if (requestBody.metadata?.walletAddress) {
        connectedWalletAddress = requestBody.metadata.walletAddress;
      } else if (requestBody.walletAddress) {
        connectedWalletAddress = requestBody.walletAddress;
      }
      // Also check in readable context items
      if (!connectedWalletAddress && requestBody.readableItems) {
        for (const item of requestBody.readableItems) {
          if (item.description?.includes("wallet address") && item.value) {
            connectedWalletAddress = item.value;
            break;
          }
        }
      }
    }
  } catch (error) {
    // If parsing fails, continue without wallet address
    console.log("Could not extract wallet address from request:", error);
  }

  // ============================================
  // AUTHENTICATION: Orchestrator (if needed)
  // ============================================

  // Extract orchestrator auth (if different from A2A agents)
  const orchestratorAuth =
    process.env.ORCHESTRATOR_AUTH_TOKEN || request.headers.get("authorization");

  const orchestratorHeaders: Record<string, string> = {};
  if (orchestratorAuth) {
    orchestratorHeaders["Authorization"] = orchestratorAuth.startsWith(
      "Bearer "
    )
      ? orchestratorAuth
      : `Bearer ${orchestratorAuth}`;
  }

  // Connect to orchestrator via AG-UI Protocol with authentication
  const orchestrationAgent = new HttpAgent({
    url: orchestratorUrl,
    headers: orchestratorHeaders, // Pass orchestrator auth headers
  });

  // A2A Middleware: Wraps orchestrator and injects send_message_to_a2a_agent tool
  // This allows orchestrator to communicate with all A2A agents transparently
  const a2aMiddlewareAgent = new A2AMiddlewareAgent({
    description:
      "Web3 and cryptocurrency orchestrator with specialized agents for Cronos operations",
    agentUrls: [
      balanceAgentUrl,
      transferAgentUrl,
    ],
    orchestrationAgent,
    instructions: `
      You are a Web3 and cryptocurrency orchestrator agent. Your role is to coordinate
      specialized agents to help users with blockchain and cryptocurrency operations on Cronos network.
      
      ${connectedWalletAddress 
        ? `\n\n**IMPORTANT USER CONTEXT:**\nThe user has a connected wallet address: ${connectedWalletAddress}\nWhen the user asks for "my balance", "fetch my balance", "check my balance", "get my balance", or similar requests WITHOUT explicitly providing a wallet address, you MUST automatically use this connected wallet address (${connectedWalletAddress}) on the Cronos network. Do NOT ask for the wallet address - use ${connectedWalletAddress} automatically.\n\n`
        : ""
      }

      AVAILABLE SPECIALIZED AGENTS (Cronos Network Only):

      1. **Balance Agent** (LangGraph) - Checks cryptocurrency balances on Cronos
         - Checks native CRO balance on Cronos network
         - Can check ERC-20 token balances (USDC, USDT, DAI, etc.) on Cronos
         - Requires wallet address (0x format) and defaults to Cronos network

      2. **Transfer Agent** (LangGraph) - Native CRO token transfers on Cronos
          - Transfer native CRO tokens between addresses
          - Supports both mainnet and testnet
          - Requires amount, recipient address, and optional network specification
          - Returns structured response with transfer parameters
          - IMPORTANT: If user says "transfer token" or "send token" without specifying which token, the Transfer Agent will ask which token they want to transfer
          - Currently only supports native CRO transfers (not ERC-20 tokens like USDC, USDT, etc.)
          - CRITICAL: Before executing any transfer, you MUST ask the user to confirm which network they want to use (mainnet or testnet)
          - IMPORTANT: After calling Transfer Agent and receiving transfer parameters, you MUST ask the user to confirm the network before calling initiate_transfer
          - Only call initiate_transfer after the user explicitly confirms the network (mainnet or testnet)
          - CRITICAL: After a successful transfer, you MUST communicate the transaction hash to the user
          - The transaction hash is returned in the result from initiate_transfer action
          - Always include the full transaction hash in your response: "Transfer completed successfully. Transaction hash: 0x..."
          - Users need the transaction hash to track their transaction on block explorers

      NOTE: The following features are available through dedicated UI pages:
      - **Swap** - Token swaps on VVS Finance (use /swap page)
      - **Bridge** - Cross-chain bridging (use /bridge page)
      - **Lending/Borrowing** - Tectonic Protocol (use /tectonic or /lendborrow page)

      CRITICAL CONSTRAINTS:
      - You MUST call agents ONE AT A TIME, never make multiple tool calls simultaneously
      - After making a tool call, WAIT for the result before making another tool call
      - Do NOT make parallel/concurrent tool calls - this is not supported
      - Always validate wallet addresses are in 0x format and 42 characters long
      - For transfers: ALWAYS ask the user to confirm which network (mainnet or testnet) before executing any transfer transaction
      - NEVER execute a transfer without explicit network confirmation from the user

      RECOMMENDED WORKFLOW FOR CRYPTO OPERATIONS:

      1. **Balance Agent** - Check cryptocurrency balances
         - CRITICAL: When user says "my balance", "fetch my balance", "check my balance", "get my balance", etc. WITHOUT providing an address:
           * FIRST: Call the get_connected_wallet_address action/tool to get the user's connected wallet address
           * If a connected wallet address is returned, use that address automatically
           * Default to Cronos network if not specified
           * Do NOT ask the user for their wallet address - use the connected wallet automatically
         - If user provides a specific wallet address explicitly, use that address instead (prioritize user-provided address)
         - Extract wallet address from user query (format: 0x...) or use connected wallet from get_connected_wallet_address
         - Network is always Cronos (cronos)
         - Extract token symbol if querying specific token (USDC, USDT, DAI, etc.)
         - Call Balance Agent with appropriate parameters:
           * For native balance: address and network="cronos"
           * For token balance: address, token symbol, and network="cronos"
         - Wait for balance response
         - Present results in a clear, user-friendly format

      WORKFLOW EXAMPLES:

      Example 1: Simple balance check with connected wallet
      - User: "Check my balance"
      - Context: User has connected wallet address 0xE67e4Fb0f9aaa64d18C2970a6Dce833f704e23DD
      - Action: Use connected wallet address automatically
      - Call Balance Agent: address=0xE67e4Fb0f9aaa64d18C2970a6Dce833f704e23DD, network="cronos"
      - Present: Native CRO balance

      Example 2: Token balance
      - User: "Check my USDC balance"
      - Extract: address (from connected wallet), token="USDC", network="cronos"
      - Call Balance Agent: address, token="USDC", network="cronos"
      - Present: USDC token balance on Cronos

      Example 3: Transfer CRO
      - User: "Transfer 1 CRO to 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
      - Extract: amount="1", recipient="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
      - Ask: "Which network? mainnet or testnet?"
      - User confirms: "mainnet"
      - Call Transfer Agent with confirmed network
      - Present: Transaction hash and success message

      ADDRESS VALIDATION:
      - Wallet addresses must start with "0x" and be 42 characters long
      - If user provides invalid address, politely ask for correct format
      - If user says "my balance" or similar and no connected wallet is in context, ask user to provide wallet address
      - Always prioritize user-provided address over connected wallet address
      - When user provides a specific address, use that address even if a connected wallet exists

      NETWORK SUPPORT:
      - Only Cronos network is supported (cronos, cro)
      - All operations default to Cronos mainnet unless testnet is explicitly specified for transfers

      TOKEN SUPPORT:
      - Common tokens on Cronos: USDC, USDT, DAI, WBTC, WETH, VVS, TONIC
      - Token symbols are case-insensitive
      - Always use uppercase for token symbols in responses

      RESPONSE STRATEGY:
      - After each agent response, acknowledge what you received
      - Format balance results clearly with:
        * Network name (Cronos)
        * Token symbol (if applicable)
        * Balance amount with appropriate decimals
        * Wallet address (truncated for display: 0x...last4)
      - For transfers, always confirm the network before execution
      - Always communicate transaction hash after successful transfer
      - If there's an error, explain it clearly and suggest alternatives

      IMPORTANT: Once you have received a response from an agent, do NOT call that same
      agent again for the same information. Use the information you already have.

      ERROR HANDLING:
      - If balance check fails, explain the error clearly
      - Suggest checking: address format, network connectivity, token contract address
      - For transfer errors, explain the issue (insufficient funds, invalid address, etc.)
      - Always provide helpful next steps
    `,
  });

  // CopilotKit runtime connects frontend to agent system
  const runtime = new CopilotRuntime({
    agents: {
      a2a_chat: a2aMiddlewareAgent, // Must match agent prop in <CopilotKit agent="a2a_chat">
    },
  });

  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new ExperimentalEmptyAdapter(),
    endpoint: "/api/copilotkit",
  });

  return handleRequest(request);
}
