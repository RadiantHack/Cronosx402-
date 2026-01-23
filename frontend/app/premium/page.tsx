"use client";

import { PremiumChatExample } from "../components/premium-chat-example";

export default function PremiumChatPage() {
  // Get backend URL from environment or use default
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;

  return (
    <PremiumChatExample
      agentUrl={`${backendUrl}/premium_chat`}
      agentName="Premium x402 Agent"
    />
  );
}
