import { NextResponse } from "next/server";

export async function GET() {
  const apiBase = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const start = performance.now();
  
  try {
    const res = await fetch(`${apiBase}/health`, {
      cache: "no-store",
      headers: {
        "Accept": "application/json",
      },
    });
    
    if (!res.ok) {
      const errorText = await res.text();
      return NextResponse.json({
        status: "error",
        timestamp: new Date().toISOString(),
        error: `Core API returned HTTP ${res.status}: ${errorText.slice(0, 150)}`,
        services: {
          gemini: { name: "Google Gemini", status: "error", message: "API Gateway HTTP error" },
          supabase: { name: "Supabase", status: "error", message: "API Gateway HTTP error" },
          paypal: { name: "PayPal Sandbox", status: "error", message: "API Gateway HTTP error" }
        }
      }, { status: 502 });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    const latency = Math.round(performance.now() - start);
    return NextResponse.json({
      status: "unreachable",
      timestamp: new Date().toISOString(),
      error: `Could not connect to FastAPI Core API at ${apiBase}: ${errorMsg}`,
      services: {
        gemini: { name: "Google Gemini", status: "unconfigured", latency_ms: latency, message: `Core API unreachable: ${errorMsg}` },
        supabase: { name: "Supabase", status: "unconfigured", latency_ms: latency, message: `Core API unreachable: ${errorMsg}` },
        paypal: { name: "PayPal Sandbox", status: "unconfigured", latency_ms: latency, message: `Core API unreachable: ${errorMsg}` }
      },
      proof: {
        error: errorMsg,
        apiBase
      }
    }, { status: 503 });
  }
}

