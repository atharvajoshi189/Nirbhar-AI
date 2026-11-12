import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metric trends for Rule 2 telemetry
export const errorRate = new Rate('errors');
export const verifyLatency = new Trend('verify_latency_ms');
export const taskLatency = new Trend('task_latency_ms');

const BASE_URL = __ENV.API_BASE_URL || 'http://localhost:8000';

export const options = {
  scenarios: {
    // 200 concurrent verify calls per Phase 8 Requirement 5
    concurrent_verify_calls: {
      executor: 'constant-vus',
      vus: 200,
      duration: '30s',
      exec: 'runVerifyCall',
    },
    // 50 concurrent task creations per Phase 8 Requirement 5
    concurrent_task_creations: {
      executor: 'constant-vus',
      vus: 50,
      duration: '30s',
      exec: 'runTaskCreation',
    },
  },
  thresholds: {
    // System reliability thresholds: <1% failure, p95 latency < 500ms
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
    errors: ['rate<0.01'],
  },
};

export function runVerifyCall() {
  const url = `${BASE_URL}/trust/verify`;
  const payload = JSON.stringify({
    amount: 14.50,
    currency: 'USD',
    provider_name: 'CloudScale Infrastructure Solutions',
    provider_url: 'https://cloudscale.io/api',
    proposal_category: 'cloud_compute',
    justification: 'Automated k6 high-concurrency throughput evaluation',
    bypass_advisory_llm: true,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': `k6_verify_${__VU}_${__ITER}`,
    },
  };

  const res = http.post(url, payload, params);
  verifyLatency.add(res.timings.duration);

  const passed = check(res, {
    'verify status is 200': (r) => r.status === 200,
    'decision is returned': (r) => r.json('decision') !== undefined,
    'proof chip is present': (r) => r.json('proof_chip.sha256') !== undefined,
    'request id header attached': (r) => r.headers['X-Request-Id'] !== undefined,
  });

  errorRate.add(!passed);
  sleep(0.1);
}

export function runTaskCreation() {
  const url = `${BASE_URL}/tasks`;
  const payload = JSON.stringify({
    title: `Concurrent Load Task VU-${__VU} ITER-${__ITER}`,
    description: 'High-volume concurrent procurement pipeline stress test.',
    budget_max: 50.00,
    currency: 'USD',
    policy: {
      auto_approve_threshold: 10.00,
      single_tx_limit: 25.00,
      allowed_domains: ['cloudscale.io', 'apexresearch.com'],
      strict_mode: true,
    },
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': `k6_task_${__VU}_${__ITER}`,
      'Idempotency-Key': `k6_idem_task_${__VU}_${__ITER}`,
    },
  };

  const res = http.post(url, payload, params);
  taskLatency.add(res.timings.duration);

  const passed = check(res, {
    'task creation status is 200 or 201': (r) => r.status === 200 || r.status === 201,
    'task id generated': (r) => r.json('id') !== undefined,
  });

  errorRate.add(!passed);
  sleep(0.2);
}

