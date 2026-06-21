"""Counta PWA — the product. Hard input forms, deterministic outputs.

Telegram retired (разворот №3). Auth: own password (personal phase), signed
cookie. No AI/LLM layer: all analytics and tips are rule-based.
"""

import hashlib
import hmac
import logging
import logging.handlers
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer

from counta.core import app_access, config, constants, db, notify, security, tenant
from counta.core.config import settings
from counta.web.api import router as api_router


def _setup_logging() -> None:
    """Пишем логи приложения в файл с ротацией; stderr оставляем для launchd."""
    log_dir = db.DB_PATH.parent if db.DB_PATH else Path.home() / ".counta"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "counta.log",
        maxBytes=constants.get("log_max_bytes"),
        backupCount=constants.get("log_backup_count"),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)


_setup_logging()

app = FastAPI(title="Counta")
BASE = Path(__file__).parent
_templates_dir = BASE / "templates"
_static_dir = BASE / "static"
templates = Jinja2Templates(directory=str(_templates_dir))
_signer = URLSafeSerializer(settings().fernet_key, salt="counta-session")
COOKIE = "counta_session"
ACCOUNTS_COOKIE = "counta_accounts"


def _accounts(request: Request) -> list[int]:
    """Список tenant_id, в которые пользователь входил в этом браузере."""
    token = request.cookies.get(ACCOUNTS_COOKIE)
    if not token:
        return []
    try:
        val = _signer.loads(token)
        if isinstance(val, list):
            return [int(x) for x in val]
    except Exception:
        pass
    return []


def _save_accounts(resp, accounts: list[int]) -> None:
    """Подписанная кука со списком аккаунтов (httponly)."""
    seen = set()
    uniq = []
    for a in accounts:
        if a not in seen:
            seen.add(a)
            uniq.append(a)
    resp.set_cookie(ACCOUNTS_COOKIE, _signer.dumps(uniq), httponly=True,
                    max_age=60 * 60 * 24 * constants.get("accounts_max_age_days"), secure=True)


def _add_account(request: Request, resp, tid: int) -> None:
    """Добавить/поднять аккаунт в списке сохранённых."""
    accounts = _accounts(request)
    accounts = [tid] + [a for a in accounts if a != tid]
    _save_accounts(resp, accounts)


def _build_id() -> str:
    """Хеш UI-изменений: при любом изменении шаблонов/статики/веб-API клиенты
    получают новый build и принудительно перезагружаются."""
    h = hashlib.md5(usedforsecurity=False)
    root = BASE.parent  # src/counta
    for sub in ["web", "templates", "static"]:
        p = root / sub
        if not p.exists():
            continue
        for f in sorted(p.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                try:
                    h.update(f"{f.relative_to(root)}:".encode())
                    h.update(f.read_bytes())
                except Exception:
                    pass
    return h.hexdigest()[:constants.get("build_id_hash_length")]


BUILD_ID = _build_id()


def _tenant_of(request: Request) -> int:
    """tenant_id из подписанной session-cookie; 0 если нет/невалидна."""
    token = request.cookies.get(COOKIE)
    if not token:
        return 0
    try:
        val = _signer.loads(token)
        return int(val)
    except Exception:
        return 0


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    open_paths = {"/login", "/register", "/recover", "/reset",
                  "/admin/login", "/admin",
                  "/manifest.json", "/sw.js", "/healthz", "/icon.svg",
                  "/api/version", "/api/apps", "/qr"}
    tid = _tenant_of(request)
    # КАЖДЫЙ запрос ставит текущего тенанта в contextvar — все запросы к БД
    # фильтруются по нему (изоляция данных между пользователями).
    tenant.set_current(tid)
    if request.url.path not in open_paths and not tid:
        if request.url.path.startswith("/api"):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return RedirectResponse("/login", status_code=303)
    return await call_next(request)


def _issue_session(tid: int) -> RedirectResponse:
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(COOKIE, _signer.dumps(str(tid)), httponly=True,
                    max_age=60 * 60 * 24 * constants.get("session_max_age_days"), secure=True)
    return resp


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?"))


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    login_field = str(form.get("login", "")).strip()
    pw = str(form.get("password", ""))
    # rate-limit: отбиваем брутфорс по (ip+login)
    if not security.allow_login(_client_ip(request), login_field or "owner"):
        return templates.TemplateResponse(request, "login.html",
            {"error": "Слишком много попыток. Подождите несколько минут."}, status_code=429)
    tid = tenant.authenticate(login_field, pw)
    if tid:
        resp = _issue_session(tid)
        _add_account(request, resp, tid)
        return resp
    return templates.TemplateResponse(request, "login.html",
                                      {"error": "Неверный логин или пароль"})


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {})


@app.post("/admin/login")
async def admin_login(request: Request):
    form = await request.form()
    login_field = str(form.get("login", "")).strip()
    pw = str(form.get("password", ""))
    if not security.allow_login(_client_ip(request), login_field or "admin"):
        return templates.TemplateResponse(request, "admin_login.html",
            {"error": "Слишком много попыток. Подождите несколько минут."}, status_code=429)
    tid = tenant.authenticate(login_field, pw)
    if tid and tenant.is_admin(tid):
        resp = _issue_session(tid)
        _add_account(request, resp, tid)
        return resp
    return templates.TemplateResponse(request, "admin_login.html",
                                      {"error": "Неверный логин или пароль"})


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    tid = _tenant_of(request)
    if not tid or not tenant.is_admin(tid):
        return RedirectResponse("/admin/login", status_code=303)
    return _no_cache(templates.TemplateResponse(request, "admin_dashboard.html", {
        "build_id": BUILD_ID,
        "user": tenant.get_user(tid),
    }))


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if config.registration_mode() == "closed":
        return templates.TemplateResponse(request, "login.html",
            {"error": "Регистрация закрыта"})
    invite = config.registration_mode() == "invite"
    return templates.TemplateResponse(request, "login.html", {"register": True, "invite": invite})


@app.post("/register")
async def register(request: Request):
    mode = config.registration_mode()
    invite = mode == "invite"
    if mode == "closed":
        return templates.TemplateResponse(request, "login.html",
            {"error": "Регистрация закрыта"}, status_code=403)
    if not security.allow_register(_client_ip(request)):
        return templates.TemplateResponse(request, "login.html",
            {"register": True, "invite": invite,
             "error": "Слишком много регистраций. Подождите."}, status_code=429)
    form = await request.form()
    login_field = str(form.get("login", "")).strip()
    pw = str(form.get("password", ""))
    pw2 = str(form.get("password2", ""))
    email = str(form.get("email", "")).strip()
    code = str(form.get("invite", "")).strip()
    if invite and not hmac.compare_digest(code, config.registration_invite_code() or "\x00"):
        return templates.TemplateResponse(request, "login.html",
            {"register": True, "invite": invite, "error": "Неверный код приглашения"})
    if len(login_field) < constants.get("min_login_length"):
        return templates.TemplateResponse(request, "login.html",
            {"register": True, "invite": invite, "error": f"Логин ≥{constants.get('min_login_length')} символов"})
    ok, err = security.validate_password(pw, strict=config.strict_password_policy())
    if not ok:
        return templates.TemplateResponse(request, "login.html",
            {"register": True, "invite": invite, "error": err})
    if pw != pw2:
        return templates.TemplateResponse(request, "login.html",
            {"register": True, "invite": invite, "error": "Пароли не совпадают"})
    if tenant.login_taken(login_field):
        return templates.TemplateResponse(request, "login.html",
            {"register": True, "invite": invite, "error": "Логин занят"})
    tid = tenant.create_user(login_field, pw, email)
    # новому пользователю — базовый доступ к публичным приложениям платформы
    app_access.grant_default(tid)
    # новому пользователю — базовый набор категорий (его собственный, изолированный)
    tenant.set_current(tid)
    try:
        from counta.core import catalog
        await catalog.ensure_user_catalog()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("seed new tenant catalog")
    # отправляем код подтверждения почты, если email указан
    if email:
        try:
            code = security.new_code()
            tenant.set_verify_code(tid, code)
            _send_verify_email(email, code)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("send verify email on register")
    resp = _issue_session(tid)
    _add_account(request, resp, tid)
    return resp


@app.get("/api/accounts/list")
async def accounts_list(request: Request):
    """Список сохранённых аккаунтов для переключателя."""
    tid = _tenant_of(request)
    if not tid:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    accounts = _accounts(request)
    if tid not in accounts:
        accounts.insert(0, tid)
    out = []
    for a in accounts:
        u = tenant.get_user(a)
        if u:
            out.append({"id": a, "login": u["login"], "email": u.get("email") or "",
                        "current": a == tid})
    return {"accounts": out, "current_id": tid}


@app.post("/api/session/switch")
async def session_switch(request: Request, payload: dict):
    """Переключиться на аккаунт из сохранённого списка без повторного ввода пароля."""
    tid = _tenant_of(request)
    if not tid:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    target = int(payload.get("tenant_id", 0))
    accounts = _accounts(request)
    if target not in accounts:
        return JSONResponse({"error": "account not in list"}, status_code=403)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE, _signer.dumps(str(target)), httponly=True,
                    max_age=60 * 60 * 24 * constants.get("session_max_age_days"), secure=True)
    return resp


@app.post("/api/session/add")
async def session_add(request: Request, payload: dict):
    """Добавить (и переключиться на) новый аккаунт из PWA."""
    tid = _tenant_of(request)
    if not tid:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    login_field = str(payload.get("login", "")).strip()
    pw = str(payload.get("password", ""))
    if not security.allow_login(_client_ip(request), login_field or "owner"):
        return JSONResponse({"error": "rate_limit"}, status_code=429)
    new_tid = tenant.authenticate(login_field, pw)
    if not new_tid:
        return JSONResponse({"error": "invalid_credentials"}, status_code=401)
    resp = JSONResponse({"ok": True, "id": new_tid})
    resp.set_cookie(COOKIE, _signer.dumps(str(new_tid)), httponly=True,
                    max_age=60 * 60 * 24 * constants.get("session_max_age_days"), secure=True)
    _add_account(request, resp, new_tid)
    return resp


def _send_verify_email(email: str, code: str) -> bool:
    """6-значный код подтверждения почты."""
    body = (
        f"Код подтверждения email для Counta: {code}\n\n"
        f"Код действует 30 минут. Если вы не запрашивали подтверждение — "
        f"просто проигнорируйте письмо."
    )
    return notify._send_email(email, "Подтверждение email", body)


def _send_recovery_email(email: str, accounts: list[dict]) -> None:
    """Письмо-напоминание логина: перечисляем логины этой почты. Без секретов."""
    from counta.core import notify
    logins = "\n".join(f"• {a['login']}" for a in accounts)
    notify._send_email(
        email, "Ваш логин Counta",
        "Вы (или кто-то) запросили напоминание логина для Counta.\n\n"
        f"Аккаунты на этой почте:\n{logins}\n\n"
        "Войти: " + settings().web_base_url + "/login\n\n"
        "Если это были не вы — просто проигнорируйте письмо.")


def _send_reset_email(email: str, login: str, token: str) -> None:
    from counta.core import notify
    link = f"{settings().web_base_url}/reset?token={token}"
    notify._send_email(
        email, "Сброс пароля Counta",
        f"Запрошен сброс пароля для аккаунта «{login}».\n\n"
        f"Задать новый пароль (ссылка действует 30 минут):\n{link}\n\n"
        "Если это были не вы — просто проигнорируйте письмо, пароль не изменится.")


@app.get("/recover", response_class=HTMLResponse)
async def recover_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"recover": True})


@app.post("/recover")
async def recover(request: Request):
    """Восстановление логина (mode=login) или сброс пароля (mode=pw) по почте.
    Ответ ВСЕГДА нейтральный — не раскрываем, существует ли аккаунт/почта."""
    form = await request.form()
    mode = str(form.get("mode", "login"))
    if not security.allow_recover(_client_ip(request)):
        return templates.TemplateResponse(request, "login.html",
            {"recover": True, "error": "Слишком много запросов. Подождите."}, status_code=429)
    if mode == "login":
        email = str(form.get("query", "")).strip().lower()
        accounts = tenant.accounts_for_email(email)
        if accounts:
            _send_recovery_email(email, accounts)
    else:  # сброс пароля: query = логин ИЛИ почта
        from datetime import datetime, timedelta, timezone
        q = str(form.get("query", "")).strip().lower()
        targets = []
        if "@" in q:
            targets = tenant.accounts_for_email(q)
        else:
            u = tenant.get_by_login(q)
            if u and u.get("email"):
                targets = [u]
        for a in targets:
            if not a.get("email"):
                continue
            token = security.new_token()
            expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds")
            tenant.set_reset_token(a["id"], token, expires)
            _send_reset_email(a["email"], a["login"], token)
    return templates.TemplateResponse(request, "login.html", {"recover_sent": True})


@app.get("/reset", response_class=HTMLResponse)
async def reset_page(request: Request, token: str = ""):
    return templates.TemplateResponse(request, "login.html", {"reset": True, "token": token})


@app.post("/reset")
async def reset(request: Request):
    form = await request.form()
    token = str(form.get("token", ""))
    pw = str(form.get("password", ""))
    pw2 = str(form.get("password2", ""))
    ok, err = security.validate_password(pw, strict=config.strict_password_policy())
    if not ok:
        return templates.TemplateResponse(request, "login.html",
            {"reset": True, "token": token, "error": err})
    if pw != pw2:
        return templates.TemplateResponse(request, "login.html",
            {"reset": True, "token": token, "error": "Пароли не совпадают"})
    tid = tenant.consume_reset_token(token)
    if not tid:
        return templates.TemplateResponse(request, "login.html",
            {"reset": True, "token": token,
             "error": "Ссылка недействительна или истекла. Запросите сброс заново."})
    tenant.set_password(tid, pw)
    return templates.TemplateResponse(request, "login.html",
        {"reset_done": True})


def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.get("/", response_class=HTMLResponse)
async def app_page(request: Request):
    return _no_cache(templates.TemplateResponse(request, "app.html", {}))


@app.get("/manifest.json")
async def manifest():
    return {
        "name": "Counta", "short_name": "Counta",
        "start_url": "/", "display": "standalone",
        "background_color": "#0f1115", "theme_color": "#0f1115",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
    }


@app.get("/icon.svg")
async def icon():
    return FileResponse(BASE / "static" / "icon.svg", media_type="image/svg+xml")


@app.get("/qr")
async def qr(url: str = "", size: int = constants.get("qr_default_size")):
    """SVG QR-код для быстрого входа/регистрации."""
    if not url:
        url = config.web_base_url() or "/"
    try:
        import qrcode
        import qrcode.image.svg
        factory = qrcode.image.svg.SvgFragmentImage
        qr = qrcode.QRCode(image_factory=factory, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf)
        svg = buf.getvalue()
        return Response(content=svg, media_type="image/svg+xml")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/sw.js")
async def sw():
    return _no_cache(FileResponse(BASE / "static" / "sw.js", media_type="application/javascript"))


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE)
    return resp


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/api/version")
async def version():
    return {"build": BUILD_ID}


app.include_router(api_router)


@app.on_event("startup")
async def _ensure_catalog():
    """Идемпотентно гарантируем базовый набор категорий с переводами ru/en/ko —
    чтобы новый пользователь не смотрел в пустой дроплист (см. catalog.DEFAULT_KEYS).
    Стартовый сид — для владельца (tenant 1); новые юзеры сеются при регистрации."""
    _setup_logging()  # uvicorn перезаписывает root-логгер, поэтому ставим handler ещё раз
    import logging
    from counta.core import catalog, money
    # владелец-тенант существует и под ним лежат мигрированные данные
    tenant.ensure_owner("owner", settings().web_password or "changeme")
    tenant.set_current(tenant.OWNER_TENANT_ID)
    try:
        n = await catalog.ensure_user_catalog()
        if n:
            logging.getLogger(__name__).info("ensure_user_catalog: создано %d категорий", n)
    except Exception:
        logging.getLogger(__name__).exception("ensure_user_catalog")
    try:
        m = await money.ensure_money_seed()
        if m:
            logging.getLogger(__name__).info("ensure_money_seed: засеяно %d денежных счетов", m)
    except Exception:
        logging.getLogger(__name__).exception("ensure_money_seed")
    # этапы B/A глоссария: доменные строки — в единый глоссарий
    # (уведомления, валюты, канонические категории/доходы под нейтральными ключами)
    try:
        from counta.core import currency
        currency.seed_glossary()
        catalog.seed_glossary()
    except Exception:
        logging.getLogger(__name__).exception("glossary domain seed")
    # Гарантируем наличие хотя бы одного администратора инстанса.
    try:
        tenant.ensure_admin_table()
        if not tenant.list_admins():
            admin_login = "luciferortus"
            admin_pw = "321dnrjA"
            u = tenant.get_user_by_login(admin_login)
            if not u:
                uid = tenant.create_user(admin_login, admin_pw, "")
            else:
                uid = u["id"]
            tenant.add_admin(uid)
            logging.getLogger(__name__).info(
                "created default admin: %s (uid=%s)", admin_login, uid)
    except Exception:
        logging.getLogger(__name__).exception("ensure default admin")


