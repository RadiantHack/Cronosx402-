// this needs to be moved to super-aptos-sdk

import { store } from "@/store";
import { RuntimeConfig } from "@/store/configSlice";

/**
 * Get current config state from Redux store
 */
export function getConfig(): Partial<RuntimeConfig> & { loaded: boolean } {
  return store.getState().config;
}

/**
 * Get Cronos API base URL
 * Returns undefined if not loaded yet
 */
export function getCronosApiBase(): string | undefined {
  return store.getState().config.cronosApiBase;
}

/**
 * Get Cronos RPC URL
 */
export function getCronosRpc(): string | undefined {
  return store.getState().config.cronosRpc;
}

/**
 * Get Cronos Chain ID
 */
export function getCronosChainId(): number | undefined {
  return store.getState().config.cronosChainId;
}

/**
 * Get Mosaic API base URL
 */
export function getMosaicApiBase(): string | undefined {
  return store.getState().config.mosaicApiBaseUrl;
}

export function getCronosLabsUrl(): string | undefined {
  return store.getState().config.cronosLabsUrl;
}

export function getCronosExplorerUrl(): string | undefined {
  return store.getState().config.cronosExplorerUrl;
}

export function getCronosPositionBrokerUrl(): string | undefined {
  return store.getState().config.cronosPositionBrokerUrl;
}

/**
 * Check if config is loaded
 */
export function isConfigLoaded(): boolean {
  return store.getState().config.loaded;
}

/**
 * Get config value with error if not loaded
 * Throws error if config not loaded - use when config is required
 */
export function requireCronosApiBase(): string {
  const config = store.getState().config;

  if (!config.loaded) {
    throw new Error(
      "Config not loaded yet. Ensure config is loaded before calling this function."
    );
  }

  if (!config.cronosApiBase) {
    throw new Error("cronosApiBase is not configured");
  }

  return config.cronosApiBase;
}

export function requireCronosRpc(): string {
  const config = store.getState().config;

  if (!config.loaded) {
    throw new Error("Config not loaded yet");
  }

  if (!config.cronosRpc) {
    throw new Error("cronosRpc is not configured");
  }

  return config.cronosRpc;
}

export function requireCronosChainId(): number {
  const config = store.getState().config;

  if (!config.loaded) {
    throw new Error("Config not loaded yet");
  }

  if (config.cronosChainId == null) {
    throw new Error("cronosChainId is not configured");
  }

  return config.cronosChainId;
}

export function cronosTestNetChainId(): number {
  const config = store.getState().config;

  if (!config.loaded) {
    throw new Error("Config not loaded yet");
  }

  if (config.cronosTestNetChainId == null) {
    throw new Error("cronosChainId is not configured");
  }

  return config.cronosTestNetChainId;
}

export function requireConfig(): Required<RuntimeConfig> {
  const config = store.getState().config;

  if (!config.loaded) {
    throw new Error("Config not loaded yet");
  }

  if (
    !config.cronosApiBase ||
    !config.cronosRpc ||
    !config.cronosChainId ||
    !config.cronosTestNetChainId ||
    !config.mosaicApiBaseUrl ||
    !config.cronosLabsUrl ||
    !config.cronosExplorerUrl
  ) {
    throw new Error("Config is incomplete");
  }

  return config as Required<RuntimeConfig>;
}
