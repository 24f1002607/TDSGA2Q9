import time
import uuid
import asyncio
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# ---------------------------------------------------------------------------
# YOUR ASSIGNED VALUES  ->  fill in the two TODOs below
# ---------------------------------------------------------------------------
MY_EMAIL = "24f1002607@ds.study.iitm.ac.in"                      # TODO: your logged-in email
ASSIGNED_ORIGIN = "https://app-1mmybu.example.com"

# TODO: the origin of the exam page (see step 6 in the write-up for how to find it).
# It looks like  https://something.example.com  with NO path at the end.
EXAM_ORIGIN = "https://exam.sanand.workers.dev"

ALLOWED_ORIGINS = [ASSIGNED_ORIGIN, EXAM_ORIGIN]

RATE_LIMIT = 11        # B = 11 requests...
WINDOW_SECONDS = 10    # ...per 10 seconds

app = FastAPI()


# ---------------------------------------------------------------------------
# MIDDLEWARE 3 - per-client rate limiting  (innermost)
# ---------------------------------------------------------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # client_id -> deque of timestamps of its recent requests
        self.hits = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def dispatch(self, request, call_next):
        # Never count browser preflight checks against the limit.
        if request.method == "OPTIONS":
            return await call_next(request)

        client_id = request.headers.get("X-Client-Id", "anonymous")
        now = time.monotonic()

        async with self.lock:
            dq = self.hits[client_id]
            # forget anything older than the window
            while dq and dq[0] <= now - WINDOW_SECONDS:
                dq.popleft()

            if len(dq) >= RATE_LIMIT:
                return JSONResponse(
                    {"detail": "rate limit exceeded"}, status_code=429
                )

            dq.append(now)  # record this request

        return await call_next(request)


# ---------------------------------------------------------------------------
# MIDDLEWARE 1 - request context  (middle)
# ---------------------------------------------------------------------------
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # reuse the incoming ID if there is one, otherwise make a fresh one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id            # so the endpoint can read it

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id    # always echo it back
        return response


# ---------------------------------------------------------------------------
# Register middleware.  Rule: the LAST one added is the OUTERMOST layer.
# We want CORS on the outside so every reply (even a 429) gets CORS headers.
# ---------------------------------------------------------------------------
app.add_middleware(RateLimitMiddleware)          # innermost
app.add_middleware(RequestContextMiddleware)     # middle
app.add_middleware(                              # MIDDLEWARE 2 - CORS (outermost)
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # an exact list -> no "*" wildcard
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["X-Request-ID", "X-Client-Id", "Content-Type"],
    expose_headers=["X-Request-ID"], # lets browser JS READ the response header
    max_age=600,
)


# ---------------------------------------------------------------------------
# THE ENDPOINT
# ---------------------------------------------------------------------------
@app.get("/ping")
async def ping(request: Request):
    return {"email": MY_EMAIL, "request_id": request.state.request_id}
