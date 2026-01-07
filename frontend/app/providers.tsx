"use client";

import { PrivyProvider } from "@privy-io/react-auth";
import { CopilotKit } from "@copilotkit/react-core";
import { ReactNode } from "react";

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const appId = process.env.NEXT_PUBLIC_PRIVY_APP_ID;
  const clientId = process.env.NEXT_PUBLIC_PRIVY_CLIENT_ID;
  const copilotApiKey = process.env.NEXT_PUBLIC_COPILOTKIT_API_KEY;

  if (!appId) {
    throw new Error(
      "NEXT_PUBLIC_PRIVY_APP_ID is not set. Please add it to your .env.local file."
    );
  }

  return (
    <PrivyProvider
      appId={appId}
      clientId={clientId}
      config={{
        loginMethods: ["email", "wallet", "sms"],
        appearance: {
          theme: "light",
          accentColor: "#9333ea",
          logo: "https://cronos.org/favicon.ico",
        },
        embeddedWallets: {
          ethereum: {
            createOnLogin: "users-without-wallets",
          },
        },
        supportedChains: [
          {
            id: 25, // Cronos mainnet chain ID
            name: "Cronos",
            network: "cronos",
            nativeCurrency: {
              name: "CRO",
              symbol: "CRO",
              decimals: 18,
            },
            rpcUrls: {
              default: {
                http: ["https://evm.cronos.org"],
              },
            },
            blockExplorers: {
              default: {
                name: "Cronos Explorer",
                url: "https://cronoscan.com",
              },
            },
          },
          {
            id: 338, // Cronos testnet chain ID
            name: "Cronos Testnet",
            network: "cronos-testnet",
            nativeCurrency: {
              name: "TCRO",
              symbol: "TCRO",
              decimals: 18,
            },
            rpcUrls: {
              default: {
                http: ["https://evm-t3.cronos.org"],
              },
            },
            blockExplorers: {
              default: {
                name: "Cronos Testnet Explorer",
                url: "https://testnet.cronoscan.com",
              },
            },
          },
        ],
      }}
    >
      <CopilotKit
        runtimeUrl="/api/copilotkit"
        showDevConsole={false}
        agent="a2a_chat"
        publicApiKey={copilotApiKey}
      >
        {children}
      </CopilotKit>
    </PrivyProvider>
  );
}
