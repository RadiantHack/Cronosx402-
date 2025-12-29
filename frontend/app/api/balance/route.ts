/**
 * Balance API Route
 *
 * This route proxies requests to the Balance Agent backend service.
 * The Balance Agent uses Bitquery API to fetch Cronos blockchain balances.
 *
 * The frontend typically accesses the Balance Agent through:
 * - CopilotKit → A2A Middleware → Balance Agent (recommended)
 * - Direct API calls to this route (for programmatic access)
 */

import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    // Get base URL - prioritize NEXT_PUBLIC_BASE_URL for Railway/production
    const rawBaseUrl =
      process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:8000";
    const baseUrl = rawBaseUrl.replace(/\/$/, "");

    // Balance Agent URL
    const balanceAgentUrl = `${baseUrl}/balance`;

    // Get request body
    const body = await request.json();

    // Forward request to Balance Agent
    const response = await fetch(balanceAgentUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        // Forward authorization header if present
        ...(request.headers.get("authorization") && {
          Authorization: request.headers.get("authorization")!,
        }),
      },
      body: JSON.stringify(body),
    });

    // Get response data
    const data = await response.json();

    // Return response with same status code
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Balance API route error:", error);
    return NextResponse.json(
      {
        error: "Failed to connect to Balance Agent",
        message: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    // Get base URL
    const rawBaseUrl =
      process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:8000";
    const baseUrl = rawBaseUrl.replace(/\/$/, "");

    // Balance Agent URL
    const balanceAgentUrl = `${baseUrl}/balance`;

    // Forward GET request to Balance Agent (for agent card, health checks, etc.)
    const response = await fetch(balanceAgentUrl, {
      method: "GET",
      headers: {
        Accept: "application/json",
        // Forward authorization header if present
        ...(request.headers.get("authorization") && {
          Authorization: request.headers.get("authorization")!,
        }),
      },
    });

    // Get response data
    const data = await response.json();

    // Return response with same status code
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Balance API route error:", error);
    return NextResponse.json(
      {
        error: "Failed to connect to Balance Agent",
        message: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}

