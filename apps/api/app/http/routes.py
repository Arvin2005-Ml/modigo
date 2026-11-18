from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.core.schemas import AccountEmail, ResetPassword, PasswordConfirm, ChangePassword, Signup, Credentials, Empty, Context, SlateInput, ReplaceInput, NavigateInput, StartInput, CatalogStartInput, Feedback, PreferencesUpdate
from app.core.errors import DomainError
from app.core.outing import OUTING_ORIGINS
from app.modules.catalog.schemas import DraftUpdate, ReviewInput, WithdrawInput, CloneInput, CookInput
from app.modules.activity_assistant.schemas import AssetKind, AssistantState, ChatInput, ChatReply
from app.modules.catalog.activation import ActivationStatus, activation_queue
from app.modules.recommendations.eligibility import VENUE_POLICY_VERSION
from app.modules.recommendations.ranking import ALGORITHM_VERSION
from app.http.presentation import public_response, with_venue_programs

router = APIRouter()



def services(request: Request):
    return request.app.state.services


def user(request: Request):
    s = services(request)
    return s.identity.session(request.cookies.get(s.settings.session_cookie))


User = Annotated[dict, Depends(user)]


def send(s, data, status=200):
    return JSONResponse(jsonable_encoder(with_venue_programs(public_response(data, s.store), s.store)),
                        status_code=status)


def idem(request, actor, scope, payload, action, status=200, *, on_replay=None):
    s = services(request)
    s.identity.user(actor['id'])
    value = s.idempotency.run(actor['id'], scope, request.headers.get('idempotency-key'), payload, action,
                              on_replay=on_replay)
    return send(s, value, status)


@router.get('/health/ready')
def ready(request: Request):
    s = services(request)
    s.store.ping()
    return {'status': 'ready', 'data_backend': s.settings.data_backend, 'provider': s.settings.provider,
            'venue_policy': VENUE_POLICY_VERSION,
            'recommendation_algorithm': ALGORITHM_VERSION,
            'local_demo_content': s.settings.demo_content and s.settings.catalog_release == 'legacy',
            'catalog_release': s.settings.catalog_release if s.settings.demo_content else None}


@router.get('/health/live')
def live():
    return {'status': 'alive'}


@router.get('/auth/csrf')
def csrf(request: Request, response: Response):
    s = services(request)
    token, raw = s.identity.issue_csrf(request.cookies.get(s.settings.session_cookie), request.cookies.get('funilo_preauth'))
    if raw:
        response.set_cookie('funilo_preauth', raw, httponly=True, secure=s.settings.secure_cookies,
                            samesite='lax', path='/', max_age=3600)
    return {'csrf_token': token}


@router.post('/auth/signup', status_code=202)
def signup(data: Signup, request: Request):
    return services(request).identity.signup(data, request.client.host if request.client else 'unknown')


@router.post('/auth/login')
def login(data: Credentials, request: Request, response: Response):
    s = services(request)
    raw, result = s.identity.login(data, request.client.host if request.client else 'unknown', request.cookies.get(s.settings.session_cookie))
    response.set_cookie(s.settings.session_cookie, raw, httponly=True, secure=s.settings.secure_cookies,
        samesite='lax', path='/', max_age=14 * 86400 if result['user']['role'] == 'user' else 8 * 3600)
    response.delete_cookie('funilo_preauth', path='/', secure=s.settings.secure_cookies, httponly=True, samesite='lax')
    return result


@router.post('/auth/logout', status_code=204)
def logout(data: Empty, request: Request, response: Response):
    s = services(request)
    s.identity.logout(request.cookies.get(s.settings.session_cookie))
    response.delete_cookie(s.settings.session_cookie, path='/', secure=s.settings.secure_cookies, httponly=True, samesite='lax')


@router.get('/me')
def me(actor: User, request: Request):
    return services(request).identity.public(actor)


@router.get('/me/preferences')
def preferences(actor: User, request: Request):
    return services(request).identity.preferences(actor['id'])


@router.put('/me/preferences')
def preferences_update(data: PreferencesUpdate, actor: User, request: Request):
    return services(request).identity.update_preferences(actor['id'], data)


@router.post('/check-ins', status_code=201)
def check_in(data: Context, actor: User, request: Request):
    s = services(request)
    s.limiter.take('check_in', actor['id'], 20, 60)
    return idem(request, actor, 'check_ins', data.model_dump(exclude_unset=True), lambda: s.recommendations.check_in(actor['id'], data), 201)


@router.post('/recommendation-sessions', status_code=201)
def create_slate(data: SlateInput, actor: User, request: Request):
    s = services(request)
    s.limiter.take('slate', actor['id'], 20, 60)
    return idem(request, actor, 'slate', data.model_dump(), lambda: s.recommendations.create(actor['id'], data.check_in_id), 201,
                on_replay=lambda receipt: s.recommendations.replay(actor['id'], receipt['id'], receipt))


@router.get('/recommendation-sessions/{session_id}')
def get_slate(session_id: str, actor: User, request: Request):
    s = services(request)
    return with_venue_programs(s.recommendations.get(actor['id'], session_id), s.store)


@router.post('/recommendation-sessions/{session_id}/slots/{slot_id}/replace')
def replace_slot(session_id: str, slot_id: str, data: ReplaceInput, actor: User, request: Request):
    s = services(request)
    s.limiter.take('replace', actor['id'], 30, 60)
    return idem(request, actor, f'replace:{session_id}:{slot_id}', data.model_dump(),
                lambda: s.recommendations.replace_slot(actor['id'], session_id, slot_id, data.expected_version),
                on_replay=lambda receipt: s.recommendations.replay(actor['id'], session_id, receipt))


@router.post('/recommendation-sessions/{session_id}/navigate')
def navigate_suggestion(session_id: str, data: NavigateInput, actor: User, request: Request):
    s = services(request)
    s.limiter.take('navigate_suggestion', actor['id'], 120, 60)
    return idem(request, actor, f'navigate:{session_id}', data.model_dump(),
                lambda: s.recommendations.navigate(actor['id'], session_id, data.direction, data.expected_version),
                on_replay=lambda receipt: s.recommendations.replay(actor['id'], session_id, receipt))


@router.get('/activity-revisions/{revision_id}')
def revision(revision_id: str, actor: User, request: Request):
    s = services(request)
    return with_venue_programs(s.catalog.visible_revision(revision_id, include_start_options=True), s.store)


@router.get('/activity-revisions/{revision_id}/assistant', response_model=AssistantState)
def assistant_state(revision_id: str, actor: User, request: Request):
    return services(request).activity_assistant.get(revision_id)


@router.post('/activity-revisions/{revision_id}/assistant/assets/{kind}', response_model=AssistantState,
             responses={202: {'model': AssistantState, 'description': 'Generation pending'}})
def request_assistant_asset(revision_id: str, kind: AssetKind, data: Empty, actor: User,
                            request: Request, response: Response, background: BackgroundTasks):
    response.status_code, result = services(request).activity_assistant.request(
        actor['id'], revision_id, kind, background.add_task)
    return result


@router.get('/activity-revisions/{revision_id}/assistant/image', response_class=Response,
            responses={200: {'content': {kind: {'schema': {'type': 'string', 'format': 'binary'}}
                                         for kind in ('image/png', 'image/jpeg', 'image/webp')}}})
def assistant_image(revision_id: str, actor: User, request: Request):
    data, media_type = services(request).activity_assistant.image(revision_id)
    return Response(content=data, media_type=media_type)


@router.post('/activity-revisions/{revision_id}/assistant/chat', response_model=ChatReply)
def assistant_chat(revision_id: str, data: ChatInput, actor: User, request: Request):
    return services(request).activity_assistant.chat(actor['id'], revision_id, data)


@router.get('/activity-cities')
def activity_cities(actor: User, request: Request):
    return {'cities': services(request).catalog.cities()}


@router.get('/outing-origins')
def outing_origins(actor: User):
    return {'cities': list(OUTING_ORIGINS.values())}


@router.get('/discover')
def discover(actor: User, request: Request):
    return {'items': services(request).catalog.discover()}


@router.post('/experiences', status_code=201)
def start(data: StartInput | CatalogStartInput, actor: User, request: Request):
    s = services(request)
    # Keep the same receipt hash for old recommendation clients and retries.
    exclude = {'conditions_confirmed'} if isinstance(data, StartInput) and not data.conditions_confirmed else None
    return idem(request, actor, 'start', data.model_dump(exclude=exclude), lambda: s.experiences.start(actor['id'], data), 201)


@router.get('/experiences/active')
def active(actor: User, request: Request):
    s = services(request)
    return with_venue_programs(s.experiences.active(actor['id']), s.store)


@router.get('/experiences')
def history(actor: User, request: Request, limit: int = Query(default=20, ge=1, le=100)):
    s = services(request)
    items = s.experiences.history(actor['id'])
    return with_venue_programs({'items': items[:limit], 'next_cursor': None,
                                'has_more': len(items) > limit}, s.store)


@router.get('/experiences/{experience_id}')
def experience(experience_id: str, actor: User, request: Request):
    s = services(request)
    return with_venue_programs(s.experiences.get(actor['id'], experience_id), s.store)


@router.post('/experiences/{experience_id}/complete')
def complete(experience_id: str, data: Empty, actor: User, request: Request):
    s = services(request)
    return idem(request, actor, f'complete:{experience_id}', {}, lambda: s.experiences.complete(actor['id'], experience_id))


@router.post('/experiences/{experience_id}/cancel')
def cancel(experience_id: str, data: Empty, actor: User, request: Request):
    s = services(request)
    return with_venue_programs(s.experiences.cancel(actor['id'], experience_id), s.store)


@router.put('/experiences/{experience_id}/feedback')
def feedback(experience_id: str, data: Feedback, actor: User, request: Request):
    return services(request).experiences.feedback(actor['id'], experience_id, data)


@router.delete('/experiences/{experience_id}/feedback', status_code=204)
def delete_feedback(experience_id: str, actor: User, request: Request):
    services(request).experiences.delete_feedback(actor['id'], experience_id)


@router.get('/me/journey')
def journey(actor: User, request: Request):
    return services(request).experiences.journey(actor['id'])


@router.get('/saved')
def saved(actor: User, request: Request):
    s = services(request)
    return with_venue_programs({'items': s.experiences.saved(actor['id']), 'next_cursor': None}, s.store)


@router.put('/saved/{activity_id}', status_code=204)
def save(activity_id: str, data: Empty, actor: User, request: Request):
    services(request).experiences.save(actor['id'], activity_id)


@router.delete('/saved/{activity_id}', status_code=204)
def unsave(activity_id: str, actor: User, request: Request):
    services(request).experiences.unsave(actor['id'], activity_id)


@router.get('/admin/activities')
def admin_list(actor: User, request: Request, limit: int = Query(default=20, ge=1, le=100),
               offset: int = Query(default=0, ge=0, le=10000), state: str | None = None):
    s = services(request)
    s.catalog.authorize(actor)
    items = s.store.list('activities')
    if state:
        ids = {r['activity_id'] for r in s.store.list('activity_revisions') if r['state'] == state}
        items = [a for a in items if a['id'] in ids]
    items.sort(key=lambda a: a['seed_key'])
    return {'items': items[offset:offset + limit], 'total': len(items), 'next_offset': offset + limit if len(items) > offset + limit else None}


@router.get('/admin/catalog/activation')
def admin_activation(actor: User, request: Request, status: ActivationStatus | None = None,
                     limit: int = Query(default=20, ge=1, le=100),
                     offset: int = Query(default=0, ge=0)):
    return activation_queue(services(request).catalog, actor, status, offset, limit)


@router.get('/admin/activities/{activity_id}')
def admin_detail(activity_id: str, actor: User, request: Request):
    return services(request).catalog.detail(actor, activity_id)


@router.post('/admin/activities/{activity_id}/revisions', status_code=201)
def clone(activity_id: str, data: CloneInput, actor: User, request: Request):
    return services(request).catalog.clone(actor, activity_id, data.source_revision_id)


@router.patch('/admin/revisions/{revision_id}')
def draft_update(revision_id: str, data: DraftUpdate, actor: User, request: Request):
    return services(request).catalog.update(actor, revision_id, data)


@router.post('/admin/revisions/{revision_id}/submit')
def submit(revision_id: str, data: ReviewInput, actor: User, request: Request):
    return services(request).catalog.submit(actor, revision_id, data.expected_draft_version)


@router.post('/admin/revisions/{revision_id}/publish')
def publish(revision_id: str, data: ReviewInput, actor: User, request: Request):
    return services(request).catalog.publish(actor, revision_id, data.expected_draft_version)


@router.post('/admin/activities/{activity_id}/withdraw')
def withdraw(activity_id: str, data: WithdrawInput, actor: User, request: Request):
    return services(request).catalog.withdraw(actor, activity_id, data.reason)


@router.post('/admin/activities/{activity_id}/reactivate')
def reactivate(activity_id: str, data: WithdrawInput, actor: User, request: Request):
    return services(request).catalog.reactivate(actor, activity_id, data.reason)


@router.post('/admin/activities/{activity_id}/cook', status_code=202)
def cook(activity_id: str, data: CookInput, actor: User, request: Request):
    s = services(request)
    return idem(request, actor, f'cook:{activity_id}', data.model_dump(),
                lambda: s.jobs.enqueue(actor, activity_id, data), 202)


@router.get('/admin/jobs')
def jobs(actor: User, request: Request):
    return {'items': services(request).jobs.list(actor)}


@router.get('/admin/jobs/{job_id}')
def job(job_id: str, actor: User, request: Request):
    return services(request).jobs.get(actor, job_id)


@router.post('/admin/jobs/{job_id}/cancel')
def cancel_job(job_id: str, data: Empty, actor: User, request: Request):
    return services(request).jobs.cancel(actor, job_id)


@router.post('/auth/forgot-password', status_code=202)
def forgot(data: AccountEmail, request: Request):
    return services(request).identity.account_email(data.email, request.client.host if request.client else 'unknown', 'reset_password')


@router.post('/auth/reset-password', status_code=204)
def reset_password(data: ResetPassword, request: Request):
    services(request).identity.reset_password(data.token, data.new_password)


@router.post('/auth/logout-all', status_code=204)
def logout_all(data: PasswordConfirm, actor: User, request: Request):
    services(request).identity.logout_all(actor['id'], data.password)


@router.post('/me/change-password', status_code=204)
def change_password(data: ChangePassword, actor: User, request: Request):
    services(request).identity.change_password(actor['id'], data.current_password, data.new_password)
