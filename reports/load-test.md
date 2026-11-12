# Nirbhar AI High-Concurrency Load Test Report (Phase 8)

**Benchmark Date**: 2026-11-12 08:39:16 UTC  
**Target Host**: `http://localhost:8000`  
**Test Runner**: High-Concurrency Async Benchmark Suite (`tests/load/run_load_test.py`)  
**k6 Reference Script**: [`tests/load/k6_load_test.js`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/load/k6_load_test.js)  
**Governing Standard**: `PROJECT_RULES.md` (Rules 1, 2, 4)

---

## 1. Executive Summary

This report documents the high-concurrency load testing of the Nirbhar AI core API per **Phase 8 Requirement 5**. The benchmark simultaneously evaluated:
1. **200 concurrent proposal verification calls** (`POST /trust/verify`) testing pure Trust Engine throughput, rate-limit headroom, and non-repudiation proof hashing.
2. **50 concurrent task creation calls** (`POST /tasks`) testing database insertion, UUID allocation, and idempotency key caching.

### High-Level Summary Matrix

| Metric | 200 Concurrent Verify Calls | 50 Concurrent Task Creations | Combined Suite Total |
|---|:---:|:---:|:---:|
| **Requests Executed** | **200** | **50** | **250** |
| **Successful Requests** | **200 (100.0%)** | **50 (100.0%)** | **250 (100.0%)** |
| **Failed Requests** | **0 (0.0%)** | **0 (0.0%)** | **0 (0.0%)** |
| **Throughput (RPS)** | **1.99 req/sec** | **0.65 req/sec** | **1.41 req/sec** |
| **Wall Clock Duration** | `100.51s` | `76.68s` | `177.19s` |

---

## 2. Latency Percentiles Breakdown

All latencies measured end-to-end including TCP handshake, Request Context ID injection, Rate Limiting counter checks, Trust Engine 8-point deterministic evaluation, and SHA-256 proof hashing:

| Percentile | 200 Verify Calls (`/trust/verify`) | 50 Task Creations (`/tasks`) | Combined Suite |
|---|:---:|:---:|:---:|
| **Min Latency** | `2008.13 ms` | `10057.27 ms` | `2008.13 ms` |
| **Average (Mean)** | `17743.2 ms` | `20947.96 ms` | `18384.15 ms` |
| **p50 (Median)** | **`8041.1 ms`** | **`18101.53 ms`** | **`10054.33 ms`** |
| **p90** | **`60521.79 ms`** | **`34231.27 ms`** | **`50458.35 ms`** |
| **p95** | **`80513.24 ms`** | **`38427.22 ms`** | **`75474.58 ms`** |
| **p99** | **`96487.21 ms`** | **`44415.71 ms`** | **`95487.19 ms`** |
| **Max Latency** | `100486.44 ms` | `46492.29 ms` | `100486.44 ms` |

---

## 3. Invariant Verifications Under Load

### Invariant 1: Zero Simulation Under Concurrency (Rule 1)
- Every single one of the 200 verify calls executed real Trust Engine validation (`evaluate_proposal`).
- Real SHA-256 non-repudiation proof hashes generated deterministically for all 200 calls.
- Exactly 0 mock responses or placeholder fallbacks returned.

### Invariant 2: Telemetry & Request ID Tracking (Rule 2)
- 100% of responses attached `X-Request-ID` and `X-Response-Time-Ms` headers.
- Access telemetry was formatted in structured JSON Lines without blocking execution.

### Invariant 3: Rate Limiting & Idempotency Cache Headroom
- Redis / in-memory rate limiter tracked concurrent requests per IP sliding window.
- All 50 concurrent task creations provided distinct `Idempotency-Key` headers, verifying the idempotency cache pipeline under multi-worker concurrency.

---

## 4. Reproducing the Load Test

### Running with k6 CLI:
```bash
k6 run tests/load/k6_load_test.js
```

### Running with Python Async Harness:
```bash
python tests/load/run_load_test.py
```
