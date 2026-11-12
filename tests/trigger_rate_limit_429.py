import asyncio
import httpx
import time
import sys

async def trigger_rate_limit():
    url = "http://127.0.0.1:8000/trust/verify"
    payload = {
        "amount": 5.0,
        "currency": "USD",
        "provider_name": "RateLimitProbe",
        "provider_url": "https://ratelimit.probe",
        "proposal_category": "test",
        "justification": "Testing rate limiting 429 response",
        "bypass_advisory_llm": True
    }
    # Use a unique client header so it isolates to a specific rate limit bucket
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer rate_limit_test_client_key_429_probe"
    }
    
    print("=" * 65, flush=True)
    print("VERIFICATION TASK 3: TRIGGER RATE LIMITER (HTTP 429)", flush=True)
    print(f"Target URL: {url}", flush=True)
    print("Sending rapid burst of requests to trigger HTTP 429...", flush=True)
    print("=" * 65, flush=True)
    
    got_429 = False
    status_429_response = None
    req_count = 0
    start_time = time.time()
    
    limits = httpx.Limits(max_keepalive_connections=100, max_connections=150)
    async with httpx.AsyncClient(timeout=10.0, limits=limits) as client:
        batch_size = 100
        while not got_429 and req_count < 2500:
            tasks = [client.post(url, json=payload, headers=headers) for _ in range(batch_size)]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for resp in responses:
                req_count += 1
                if isinstance(resp, httpx.Response):
                    if resp.status_code == 429:
                        got_429 = True
                        status_429_response = resp
                        break
                elif isinstance(resp, Exception):
                    pass
            
            if got_429:
                break
            print(f"Dispatched {req_count} requests...", flush=True)

    elapsed = time.time() - start_time
    print("\n" + "=" * 65, flush=True)
    if got_429 and status_429_response is not None:
        print(f"[SUCCESS] Triggered HTTP 429 Too Many Requests after {req_count} requests in {elapsed:.2f}s!", flush=True)
        print("=" * 65, flush=True)
        print(f"Status Code:            {status_429_response.status_code}", flush=True)
        print(f"Response Body:          {status_429_response.text}", flush=True)
        print(f"X-RateLimit-Limit:      {status_429_response.headers.get('X-RateLimit-Limit')}", flush=True)
        print(f"X-RateLimit-Remaining:  {status_429_response.headers.get('X-RateLimit-Remaining')}", flush=True)
        print(f"X-RateLimit-Reset:      {status_429_response.headers.get('X-RateLimit-Reset')}", flush=True)
        print(f"Retry-After:            {status_429_response.headers.get('Retry-After')} seconds", flush=True)
        print(f"X-Request-ID:           {status_429_response.headers.get('X-Request-ID')}", flush=True)
        print(f"X-Response-Time-Ms:     {status_429_response.headers.get('X-Response-Time-Ms')}", flush=True)
        print("=" * 65, flush=True)
        return True
    else:
        print(f"[FAILED] Did not trigger HTTP 429 within {req_count} requests.", flush=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(trigger_rate_limit())
    sys.exit(0 if success else 1)
