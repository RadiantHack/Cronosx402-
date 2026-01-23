/**
 * Balance API utilities
 * 
 * Helper functions to fetch and parse balance data from the Balance Agent
 */

export interface TokenBalance {
  symbol: string;
  name: string;
  value: string;
  decimals: number;
  contract: string;
  is_native: boolean;
}

export interface BalanceData {
  address: string;
  balances: TokenBalance[];
  success: boolean;
  error?: string;
  total_fetched?: number;
  filtered_out?: number;
}

export interface BalanceResponse {
  success: boolean;
  data?: BalanceData;
  error?: string;
}

/**
 * Fetch balance data for a wallet address on Cronos
 * 
 * @param address - Wallet address (0x format)
 * @param network - Network name (default: "cronos")
 * @returns Promise with balance data
 */
export async function fetchWalletBalance(
  address: string,
  network: string = "cronos"
): Promise<BalanceResponse> {
  try {
    // Call the Balance Agent through the API route
    const response = await fetch("/api/balance", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messages: [
          {
            role: "user",
            content: `Get balance for ${address} on ${network}`,
          },
        ],
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.error || `HTTP ${response.status}: ${response.statusText}`,
      };
    }

    const data = await response.json();
    
    // The agent returns a wrapped response, we need to extract the actual balance data
    // Try to parse the agent's response
    if (data.response) {
      try {
        const parsedResponse = JSON.parse(data.response);
        
        // Check if it's the structured response we expect
        if (parsedResponse.success && parsedResponse.response) {
          // The agent returns text response, we need to parse structured data
          // For now, we'll make a direct call to get structured data
          return await fetchBalanceDirectly(address, network);
        }
      } catch (e) {
        // Response might be plain text from agent, fall through to direct call
        console.warn("Could not parse agent response, falling back to direct call", e);
      }
    }

    // Fallback to direct backend call
    return await fetchBalanceDirectly(address, network);
  } catch (error) {
    console.error("Error fetching wallet balance:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error occurred",
    };
  }
}

/**
 * Directly call the backend Balance Agent to get structured data
 * 
 * This bypasses the agent's text formatting and gets raw balance data
 */
async function fetchBalanceDirectly(
  address: string,
  network: string = "cronos"
): Promise<BalanceResponse> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL;
    if (!baseUrl) {
      throw new Error("NEXTPUBLIC_BASE_URL is not set in environment variables.");
    }
    
    // Direct call to backend to get structured balance data
    // We'll need to add an endpoint that returns JSON directly
    // For now, parse from agent response
    const response = await fetch(`${baseUrl}/balance`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messages: [
          {
            role: "user",
            content: `Get balance for ${address} on ${network}`,
          },
        ],
      }),
    });

    if (!response.ok) {
      return {
        success: false,
        error: `Backend error: ${response.status}`,
      };
    }

    const result = await response.json();
    
    // Parse the agent's response to extract balance information
    // The agent returns text, so we need to extract the data
    // For a better solution, we should add a structured endpoint
    
    // For now, return mock structure and let the backend be called
    // In production, you'd want to modify the backend to return structured JSON
    return {
      success: false,
      error: "Direct balance fetch requires structured endpoint - using agent response",
    };
  } catch (error) {
    console.error("Direct balance fetch error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Direct fetch failed",
    };
  }
}

/**
 * Format balance from smallest unit (wei) to human-readable format
 * 
 * @param value - Balance in smallest units (string)
 * @param decimals - Number of decimal places (default: 18)
 * @returns Formatted balance string
 */
export function formatBalance(value: string, decimals: number = 18): string {
  try {
    const valueInt = BigInt(value);
    const divisor = BigInt(10) ** BigInt(decimals);
    const wholePart = valueInt / divisor;
    const fractionalPart = valueInt % divisor;
    
    // Convert fractional part to decimal string
    const fractionalStr = fractionalPart.toString().padStart(decimals, '0');
    const decimalValue = `${wholePart}.${fractionalStr}`;
    
    // Parse and format with up to 6 decimal places
    const formatted = parseFloat(decimalValue).toFixed(6);
    
    // Remove trailing zeros
    return formatted.replace(/\.?0+$/, '') || '0';
  } catch (error) {
    console.error("Error formatting balance:", error);
    return "0";
  }
}

/**
 * Calculate total portfolio value in USD (placeholder)
 * 
 * @param balances - Array of token balances
 * @returns Total value in USD (requires price oracle integration)
 */
export function calculateTotalValue(balances: TokenBalance[]): number {
  // TODO: Integrate with price oracle (CoinGecko, etc.)
  // For now, return 0 as we don't have price data
  return 0;
}
