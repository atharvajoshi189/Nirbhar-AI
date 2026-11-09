export interface HealthResponse {
  status: string;
  timestamp: string;
  services: {
    gemini: ServiceStatus;
    supabase: ServiceStatus;
    paypal: ServiceStatus;
  };
}

export interface ServiceStatus {
  status: "operational" | "degraded" | "error" | "unconfigured";
  latency_ms: number;
  message?: string;
  metadata?: Record<string, unknown>;
}

export class AgentTrustClient {
  private baseUrl: string;
  private apiKey?: string;

  constructor(baseUrl: string = "http://localhost:8000", apiKey?: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.apiKey = apiKey;
  }

  async getHealth(): Promise<HealthResponse> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }

    const res = await fetch(`${this.baseUrl}/health`, { headers });
    if (!res.ok) {
      throw new Error(`Failed to fetch health: ${res.statusText}`);
    }
    return res.json();
  }
}

