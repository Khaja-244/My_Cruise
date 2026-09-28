import logging
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        response = await call_next(request)
        response.headers['X-Request-ID'] = request.state.request_id
        logging.getLogger('my_cruise.request').info(
            'request_complete', extra={'request_id': request.state.request_id, 'path': request.url.path, 'method': request.method, 'status_code': response.status_code}
        )
        return response

def configure_logging():
    try:
        from pythonjsonlogger import jsonlogger
        handler = logging.StreamHandler()
        handler.setFormatter(jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s'))
        root = logging.getLogger()
        root.handlers.clear(); root.addHandler(handler); root.setLevel(logging.INFO)
    except Exception:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
