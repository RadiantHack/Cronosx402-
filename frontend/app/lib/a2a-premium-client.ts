/**
 * A2A Premium Client with x402 Payment Support
 * 
 * This client extends the standard A2A protocol to support x402 payment headers.
 * It handles 402 Payment Required responses and provides payment requirements.
 */

export class PaymentRequiredError extends Error {
  constructor(
    message: string,
    public paymentRequirements: any,
    public statusCode: number = 402
  ) {
    super(message);
    this.name = "PaymentRequiredError";
  }
}

export interface MessageSendParams {
  message: string;
  conversationHistory?: Array<{ role: string; content: string }>;
}

export class A2APremiumClient {
  private baseUrl: string;
  private headers: Record<string, string> = {};

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, ""); // Remove trailing slash
  }

  /**
   * Set custom headers (e.g., x-payment header)
   */
  setHeaders(headers: Record<string, string>) {
    this.headers = { ...this.headers, ...headers };
  }

  /**
   * Get agent card (may require payment for premium agents)
   */
  async getAgentCard() {
    const response = await fetch(`${this.baseUrl}/.well-known/agent.json`, {
      headers: {
        "Content-Type": "application/json",
        ...this.headers,
      },
    });

    if (response.status === 402) {
      const body = await response.json();
      throw new PaymentRequiredError(
        "Payment required to access this agent",
        body.accepts?.[0] || body,
        402
      );
    }

    if (!response.ok) {
      throw new Error(`Failed to fetch agent card: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Send a message to the agent (may require payment for premium agents)
   */
  async sendMessage(params: MessageSendParams) {
    try {
      console.log("[A2APremiumClient] Sending message with headers:", Object.keys(this.headers));
      console.log("[A2APremiumClient] x-payment header present:", !!this.headers["x-payment"]);
      
      const response = await fetch(`${this.baseUrl}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...this.headers,
        },
        body: JSON.stringify({
          message: params.message,
          conversation_history: params.conversationHistory || [],
        }),
      });

      if (response.status === 402) {
        const body = await response.json();
        throw new PaymentRequiredError(
          "Payment required to use this agent",
          body.accepts?.[0] || body,
          402
        );
      }

      if (!response.ok) {
        const errorBody = await response.text();
        throw new Error(
          `Agent request failed: ${response.statusText} - ${errorBody}`
        );
      }

      return response.json();
    } catch (error: any) {
      // Re-throw PaymentRequiredError as-is
      if (error instanceof PaymentRequiredError) {
        throw error;
      }
      
      // Handle network/connection errors
      if (error.message.includes("Failed to fetch") || error.name === "TypeError") {
        throw new Error(
          `Cannot connect to backend at ${this.baseUrl}. Is the backend server running?`
        );
      }
      
      throw error;
    }
  }
}

/**
 * Helper to check if an error is a payment required error
 */
export function isPaymentRequiredError(error: any): error is PaymentRequiredError {
  return error instanceof PaymentRequiredError || error?.statusCode === 402;
}
