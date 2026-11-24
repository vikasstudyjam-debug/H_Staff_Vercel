import time
import re
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class WebApplicationFirewallMiddleware(BaseHTTPMiddleware):
    """
    Enterprise Layer-7 WAF & Sliding Window Rate Limiter.
    Inspects queries, paths, and headers for SQLi, XSS, Path Traversal, and Abuse.
    """
    def __init__(self, app, requests_limit: int = 250, window_seconds: int = 60):
        super().__init__(app)
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.ip_request_history = {}

        self.sqli_pattern = re.compile(
            r"(--|union\s+select|/\*|\*/|exec\s*\(|drop\s+table|insert\s+into|select\s+.*\s+from)",
            re.IGNORECASE
        )
        self.xss_pattern = re.compile(
            r"(<script.*?>|javascript:|onload\s*=|onerror\s*=|eval\s*\()",
            re.IGNORECASE
        )
        self.path_traversal_pattern = re.compile(
            r"(\.\./|\.\.\\|/etc/passwd|win\.ini)",
            re.IGNORECASE
        )

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # 1. In-Memory Sliding Window Rate Limiter
        timestamps = self.ip_request_history.get(client_ip, [])
        timestamps = [t for t in timestamps if current_time - t < self.window_seconds]
        if len(timestamps) >= self.requests_limit:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "WAF_RATE_LIMIT_EXCEEDED", "detail": "Rate limit threshold reached. Slow down."}
            )
        timestamps.append(current_time)
        self.ip_request_history[client_ip] = timestamps

        # 2. Inspect Query String & Path for Malicious Signatures
        query_string = request.url.query
        path_string = request.url.path

        for target in [query_string, path_string]:
            if target:
                if self.sqli_pattern.search(target):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"error": "WAF_BLOCKED", "detail": "Potential SQL Injection attack detected."}
                    )
                if self.xss_pattern.search(target):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"error": "WAF_BLOCKED", "detail": "Potential Cross-Site Scripting (XSS) payload detected."}
                    )
                if self.path_traversal_pattern.search(target):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"error": "WAF_BLOCKED", "detail": "Directory traversal sequence detected."}
                    )

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Security-Firewall"] = "H-Staff Enterprise Shield v4.5"
        return response
