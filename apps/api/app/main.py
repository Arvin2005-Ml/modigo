from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.concurrency import run_in_threadpool
from app.application import Services
from app.core.config import Settings
from app.core.errors import DomainError
from app.core.storage import StorageUnavailable
from app.core.values import utcnow, uid
from app.http.routes import router


def create_app(settings=None, clock=utcnow, store_factory=None):
    settings = settings or Settings.load()
    settings.validate()

    @asynccontextmanager
    async def lifespan(app):
        logging.getLogger('uvicorn.error').info('API startup: browser origin %s (%s)', settings.app_origin, settings.environment)
        app.state.services = Services(settings, clock, store_factory=store_factory)
        try:
            logging.getLogger('uvicorn.error').info('API startup: recovering interrupted jobs and starting the runner')
            app.state.services.jobs.start()
            logging.getLogger('uvicorn.error').info('API startup: application initialization complete')
            yield
        finally:
            app.state.services.jobs.stop()
            app.state.services.store.close()
            app.state.services = None

    app = FastAPI(title='Moodigo', version='0.2.0', lifespan=lifespan,
                  docs_url='/api/docs', openapi_url='/api/openapi.json', redoc_url=None)
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True,
        allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
        allow_headers=['Content-Type', 'X-CSRF-Token', 'Idempotency-Key'])

    def error(request, code, message, status, fields=None):
        headers = {'Cache-Control': 'no-store'}
        if status == 429:
            headers['Retry-After'] = '60'
        return JSONResponse({'error': dict(code=code, message=message, fields=fields or {},
            request_id=getattr(request.state, 'request_id', uid()))}, status_code=status, headers=headers)

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return error(request, exc.code, exc.message, exc.status, exc.fields)

    @app.exception_handler(StorageUnavailable)
    async def storage_error(request, exc):
        return error(request, 'TEMPORARILY_UNAVAILABLE', 'اتصال ذخیره‌سازی موقتاً در دسترس نیست؛ دوباره امتحان کن.', 503)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        fields = {'.'.join(str(v) for v in e['loc'][1:]): e['type'] for e in exc.errors()}
        return error(request, 'VALIDATION_ERROR', 'چندتا از پاسخ‌ها نیاز به اصلاح دارن.', 422, fields)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(request, 'NOT_FOUND' if exc.status_code == 404 else 'INVALID_REQUEST',
                     'این درخواست قابل انجام نیست.', exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        # Deliberately omit exception text and payloads from the response and logs.
        return error(request, 'TEMPORARILY_UNAVAILABLE', 'یه مشکلی پیش اومد؛دوباره امتحان کن.', 503)

    @app.middleware('http')
    async def security(request: Request, call_next):
        request.state.request_id = uid()
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            size, chunks = 0, []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 65536:
                    return error(request, 'INVALID_REQUEST', 'اندازهٔ درخواست بیش از حد مجازه.', 413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
            try:
                await run_in_threadpool(app.state.services.identity.check_csrf, request.cookies.get(settings.session_cookie),
                    request.cookies.get('funilo_preauth'), request.headers.get('x-csrf-token'), request.headers.get('origin'))
            except DomainError as exc:
                return error(request, exc.code, exc.message, exc.status)
            except StorageUnavailable:
                return error(request, 'TEMPORARILY_UNAVAILABLE', 'اتصال ذخیره‌سازی موقتاً در دسترس نیست؛ دوباره امتحان کن.', 503)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Request-ID'] = request.state.request_id
        return response

    app.include_router(router, prefix='/api/v1')
    return app
