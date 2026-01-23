"use client";

/**
 * Example: Premium Chat Component with x402 Payments
 * 
 * This is a simple example showing how to integrate x402 payments
 * with a chat interface for premium agents.
 */

import { useState, useRef } from "react";
import { Send, Loader2, Crown } from "lucide-react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import {
  A2APremiumClient,
  PaymentRequiredError,
  isPaymentRequiredError,
} from "../lib/a2a-premium-client";
import { PaymentModal } from "./payment-modal";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface PremiumChatExampleProps {
  agentUrl: string;
  agentName?: string;
}

export function PremiumChatExample({
  agentUrl,
  agentName = "Premium Agent",
}: PremiumChatExampleProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentRequirements, setPaymentRequirements] = useState<any>(null);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);

  const { ready, authenticated } = usePrivy();
  const { wallets } = useWallets();
  const clientRef = useRef<A2APremiumClient>(new A2APremiumClient(agentUrl));

  // Get Privy wallet
  const privyWallet = wallets.find((w) => {
    if (w.walletClientType === "privy") return true;
    return !w.walletClientType || (w as any).chainType === "ethereum";
  });

  const walletAddress = privyWallet?.address;

  const handleSendMessage = async (message: string) => {
    if (!message.trim() || isLoading) return;

    setIsLoading(true);
    setPendingMessage(message);

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: message,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    try {
      // Send message to agent
      const response = await clientRef.current.sendMessage({
        message,
        conversationHistory: messages.map((m) => ({
          role: m.role,
          content: m.content,
        })),
      });

      // Add assistant response
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response.response || response.message || JSON.stringify(response),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error: any) {
      console.error("Error sending message:", error);
      console.log("Error type:", error.constructor.name);
      console.log("Error status:", error.statusCode);

      // Handle payment required error
      if (isPaymentRequiredError(error)) {
        console.log("Payment required! Opening modal...");
        setPaymentRequirements(error.paymentRequirements);
        setShowPaymentModal(true);
      } else {
        // Add error message
        let errorContent = error.message;
        
        // Provide helpful error messages
        if (error.message.includes("Cannot connect to backend")) {
          errorContent = `⚠️ Cannot connect to backend server.\n\nPlease check:\n1. Backend is running at ${process.env.NEXT_PUBLIC_BACKEND_URL}\n2. CORS is enabled\n3. Backend URL is correct in .env.local`;
        }
        
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: errorContent,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handlePaymentComplete = async (paymentHeader: string) => {
    console.log("Setting payment header on client:", paymentHeader.substring(0, 50));
    
    // Set payment header on client
    clientRef.current.setHeaders({ "x-payment": paymentHeader });
    
    console.log("Payment header set, retrying message:", pendingMessage);

    // Retry the pending message
    if (pendingMessage) {
      await handleSendMessage(pendingMessage);
      setPendingMessage(null);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-violet-600 to-purple-600 rounded-full flex items-center justify-center">
            <Crown className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900 dark:text-white">
              {agentName}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Premium x402 Agent
            </p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 dark:text-gray-400 mt-8">
            <Crown className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="text-lg font-medium mb-2">Premium Agent</p>
            <p className="text-sm">
              Send a message to start. Payment may be required.
            </p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                message.role === "user"
                  ? "bg-violet-600 text-white"
                  : "bg-white dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-200 dark:border-gray-700"
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white dark:bg-gray-800 rounded-2xl px-4 py-3 border border-gray-200 dark:border-gray-700">
              <Loader2 className="w-5 h-5 animate-spin text-violet-600" />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-4">
        {!ready || !authenticated ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-3">
            Please connect your wallet to use this agent
          </div>
        ) : (
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage(input);
                }
              }}
              placeholder="Type your message..."
              className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-600"
              disabled={isLoading}
            />
            <button
              onClick={() => handleSendMessage(input)}
              disabled={isLoading || !input.trim()}
              className="px-6 py-3 bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        )}
      </div>

      {/* Payment Modal */}
      <PaymentModal
        isOpen={showPaymentModal}
        onClose={() => setShowPaymentModal(false)}
        onPaymentComplete={handlePaymentComplete}
        paymentRequirements={paymentRequirements}
      />
    </div>
  );
}
