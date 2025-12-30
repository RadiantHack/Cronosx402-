"use client";

import { PrivyProvider } from "@privy-io/react-auth";
import { CopilotKit } from "@copilotkit/react-core";
import { ReactNode, useEffect } from "react";

import {
  Provider as ReduxProvider,
  useDispatch,
  useSelector,
} from "react-redux";

import { store, type RootState, type AppDispatch } from "../store";
import { loadConfig } from "../store/configSlice";
import { useCronosConfig } from "./hooks/useCronosConfig";

interface ProvidersProps {
  children: ReactNode;
}

function ConfigGate({ children }: { children: ReactNode }) {
  const dispatch = useDispatch<AppDispatch>();
  const loaded = useSelector((s: RootState) => s.config.loaded);
  const error = useSelector((s: RootState) => s.config.error);

  useEffect(() => {
    dispatch(loadConfig());
  }, [dispatch]);

  if (!loaded) return null;
  if (error) return <div>Failed to load config: {error}</div>;
  return <>{children}</>;
}

function PrivyProviderWithConfig({
  children,
  appId,
  clientId,
  copilotApiKey,
}: {
  children: ReactNode;
  appId: string;
  clientId: string | undefined;
  copilotApiKey: string | undefined;
}) {
  const config = useCronosConfig();

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
            id: config.cronosChainId, // Cronos mainnet chain ID
            name: "Cronos",
            network: "cronos",
            nativeCurrency: {
              name: "CRO",
              symbol: "CRO",
              decimals: 18,
            },
            rpcUrls: {
              default: {
                http: [config.cronosLabsUrl],
              },
            },
            blockExplorers: {
              default: {
                name: "Cronos Explorer",
                url: config.cronosExplorerUrl,
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
        <ConfigGate>{children}</ConfigGate>
      </CopilotKit>
    </PrivyProvider>
  );
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
    <ReduxProvider store={store}>
      <PrivyProviderWithConfig
        appId={appId}
        clientId={clientId}
        copilotApiKey={copilotApiKey}
      >
        {children}
      </PrivyProviderWithConfig>
    </ReduxProvider>
  );
}
