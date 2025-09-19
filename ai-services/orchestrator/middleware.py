# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

import time
import uuid
import logging
import sys
from fastapi import Request, Response
from fastapi.responses import JSONResponse

# Basic structured logging setup
LOG_LEVEL = logging.INFO
if logging.root.handlers:
    logging.root.handlers.clear()

logging.basicConfig(
    level=LOG_LEVEL,
    format='{"ts": "%(asctime)s", "level": "%(levelname)s", "service": "orchestrator", "correlation_id": "%(correlation_id)s", "message": "%(message)s"}',
    stream=sys.stdout,
)

class CorrelationIdLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra']['correlation_id'] = self.extra.get('correlation_id', 'N/A')
        return msg, kwargs

def get_logger(correlation_id: str = None):
    logger = logging.getLogger(__name__)
    return CorrelationIdLoggerAdapter(logger, {'correlation_id': correlation_id})

async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    request.state.correlation_id = correlation_id
    
    logger = get_logger(correlation_id)
    logger.info(f"Request started: {request.method} {request.url.path}")

    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

async def idempotency_key_middleware(request: Request, call_next):
    idempotency_key = request.headers.get("Idempotency-Key")
    request.state.idempotency_key = idempotency_key
    response = await call_next(request)
    return response

async def central_exception_handler(request: Request, call_next):
    correlation_id = getattr(request.state, 'correlation_id', 'N/A')
    logger = get_logger(correlation_id)
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "An unexpected internal error occurred.",
                "retryable": False,
                "correlation_id": correlation_id,
            },
        )
