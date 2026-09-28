from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details

def _envelope(request: Request, code: str, message: str, status_code: int, details=None, headers=None):
    request_id = getattr(request.state, 'request_id', 'unknown')
    return JSONResponse(
        status_code=status_code,
        content={
            'error': {
                'code': code,
                'message': message,
                'details': details,
                'request_id': request_id,
            }
        },
        headers=headers or {},
    )

async def app_error_handler(request: Request, exc: AppError):
    headers = {}
    if exc.status_code == 429 and isinstance(exc.details, dict) and exc.details.get('retry_after') is not None:
        headers['Retry-After'] = str(exc.details['retry_after'])
    return _envelope(request, exc.code, exc.message, exc.status_code, exc.details, headers)

async def validation_error_handler(request: Request, exc: RequestValidationError):
    return _envelope(request, 'VALIDATION_ERROR', 'Request validation failed.', 422, {'errors': exc.errors()})

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code = 'UNAUTHORIZED' if exc.status_code == 401 else 'FORBIDDEN' if exc.status_code == 403 else 'NOT_FOUND' if exc.status_code == 404 else 'INTERNAL_ERROR'
    if exc.status_code == 429: code = 'RATE_LIMITED'
    if exc.status_code < 500 and isinstance(exc.detail, str):
        message = exc.detail
    else:
        message = 'The request could not be completed.'
    headers = dict(exc.headers or {})
    return _envelope(request, code, message, exc.status_code, None, headers)

async def unhandled_error_handler(request: Request, exc: Exception):
    import logging
    logging.getLogger(__name__).exception('Unhandled application error')
    return _envelope(request, 'INTERNAL_ERROR', 'An unexpected error occurred.', 500)
