"use client";

import { useSelector } from "react-redux";
import { type RootState } from "@/store";

export function useCronosConfig() {
  const config = useSelector((state: RootState) => state.config);

  return {
    cronosApiBase: config.cronosApiBase || "",
    cronosFullNode: config.cronosFullNode || "",
    cronosRpc: config.cronosRpc || "",
    cronosChainId: config.cronosChainId || 25,
    cronosTestNetChainId: config.cronosTestNetChainId || 250,
    mosaicApiBaseUrl: config.mosaicApiBaseUrl || "",
    cronosLabsUrl: config.cronosLabsUrl || "",
    cronosExplorerUrl: config.cronosExplorerUrl || "",
    cronosPositionBrokerUrl: config.cronosPositionBrokerUrl || "",
    loaded: config.loaded,
    error: config.error,
  };
}
