import { createSlice, createAsyncThunk } from "@reduxjs/toolkit";

// will change it to cronos
export interface RuntimeConfig {
  cronosApiBase: string;
  cronosFullNode: string;
  cronosRpc: string;
  cronosChainId: number;
  cronosTestNetChainId: number;
  mosaicApiBaseUrl: string;
  cronosLabsUrl: string;
  cronosExplorerUrl: string;
  cronosPositionBrokerUrl: string;
}

interface ConfigState extends Partial<RuntimeConfig> {
  loaded: boolean;
  error?: string;
}

const initialState: ConfigState = { loaded: false };

export const loadConfig = createAsyncThunk("config/load", async () => {
  const res = await fetch("/config.json", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load /config.json");
  return (await res.json()) as RuntimeConfig;
});

const configSlice = createSlice({
  name: "config",
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder.addCase(loadConfig.fulfilled, (state, { payload }) => {
      state.loaded = true;
      state.cronosApiBase = payload.cronosApiBase;
      state.cronosFullNode = payload.cronosFullNode;
      state.cronosRpc = payload.cronosRpc;
      state.cronosChainId = payload.cronosChainId;
      state.cronosTestNetChainId = payload.cronosTestNetChainId;
      state.mosaicApiBaseUrl = payload.mosaicApiBaseUrl;
      state.cronosLabsUrl = payload.cronosLabsUrl;
      state.cronosExplorerUrl = payload.cronosExplorerUrl;
      state.cronosPositionBrokerUrl = payload.cronosPositionBrokerUrl;
    });
    builder.addCase(loadConfig.rejected, (state, action) => {
      state.loaded = true;
      state.error = action.error.message || "Config load failed";
    });
  },
});

export default configSlice.reducer;
