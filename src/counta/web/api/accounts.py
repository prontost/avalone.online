"""Counta API domain router."""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from counta.core import catalog, config, currency, engine, entry_meta, money, notify, security, tenant
from counta.web.api.common import (
    _label, _money_label,
)

log = logging.getLogger(__name__)
router = APIRouter()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?"))


def _is_money_account(account: str) -> bool:
    """Счёт является денежным (зарегистрирован в реестре money)."""
    return account in money.registered()


@router.get("/account/me")
async def account_me():
    """Профиль текущего пользователя: логин, почта, подтверждена ли, админ ли."""
    tid = tenant.current()
    u = tenant.get_user(tid)
    if not u:
        return {}
    return {**u, "is_admin": tenant.is_admin(tid)}


@router.post("/accounts/forget")
async def forget_account(request: Request, payload: dict):
    """Удалить аккаунт из списка сохранённых в этом браузере (cookies)."""
    from counta.web.app import _accounts, _save_accounts
    tid = int(payload.get("tenant_id") or 0)
    accounts = [a for a in _accounts(request) if a != tid]
    resp = JSONResponse({"ok": True})
    _save_accounts(resp, accounts)
    return resp

@router.post("/account/password")
async def change_password(payload: dict):
    """Смена пароля: нужен старый + новый (policy-aware)."""
    old = payload.get("old") or ""
    new = payload.get("new") or ""
    ok, err = security.validate_password(new, strict=config.strict_password_policy())
    if not ok:
        return JSONResponse({"error": err}, status_code=400)
    if not tenant.change_password(tenant.current(), old, new):
        return JSONResponse({"error": "Старый пароль неверен"}, status_code=400)
    return {"ok": True}

@router.post("/account/email")
async def set_email(payload: dict):
    """Задать/сменить почту (сбрасывает подтверждение)."""
    email = (payload.get("email") or "").strip().lower()
    if "@" not in email or "." not in email:
        return JSONResponse({"error": "Некорректная почта"}, status_code=400)
    tenant.set_email(tenant.current(), email)
    return {"ok": True}

@router.post("/account/verify/send")
async def verify_send(request: Request):
    """Отправить 6-значный код на почту пользователя (rate-limited)."""
    from counta.core import security
    fwd = request.headers.get("x-forwarded-for", "")
    ip = (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?"))
    if not security.allow_verify(ip):
        return JSONResponse({"error": "Слишком часто. Подождите."}, status_code=429)
    u = tenant.get_user(tenant.current())
    if not u or not u["email"]:
        return JSONResponse({"error": "Сначала укажите почту"}, status_code=400)
    if u["email_verified"]:
        return {"ok": True, "already": True}
    code = security.new_code()
    tenant.set_verify_code(tenant.current(), code)
    sent = notify._send_email(u["email"], "Код подтверждения Counta",
                              f"Ваш код подтверждения: {code}")
    if not sent:
        return JSONResponse({"error": "Почта не настроена на сервере"}, status_code=503)
    return {"ok": True}

@router.post("/account/verify/check")
async def verify_check(payload: dict):
    """Сверить код подтверждения почты."""
    if tenant.check_verify_code(tenant.current(), payload.get("code") or ""):
        return {"ok": True}
    return JSONResponse({"error": "Неверный код"}, status_code=400)


@router.post("/account/reset-password-request")
async def reset_password_request(request: Request):
    """Пользователь запрашивает ссылку для сброса пароля на свой email.

    Требование: email указан и верифицирован. Ссылка одноразовая, 30 минут.
    """
    ip = _client_ip(request)
    if not security.allow_recover(ip):
        return JSONResponse({"error": "rate_limit"}, status_code=429)
    tid = tenant.current()
    u = tenant.get_user(tid)
    if not u or not u.get("email") or not u.get("email_verified"):
        return JSONResponse({"error": "email_required"}, status_code=400)
    token = security.new_token()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds")
    tenant.set_reset_token(tid, token, expires)
    link = f"{config.web_base_url()}/reset?token={token}"
    body = (
        f"Вы запросили сброс пароля Counta.\n\n"
        f"Перейдите по ссылке, чтобы задать новый пароль:\n{link}\n\n"
        f"Ссылка действительна 30 минут. Если вы не запрашивали сброс — проигнорируйте письмо."
    )
    ok = notify._send_email(u["email"], "Сброс пароля", body)
    if not ok:
        return JSONResponse({"error": "email_not_configured"}, status_code=503)
    return {"ok": True}

@router.get("/accounts")
async def accounts_list(lang: str = "ru"):
    """Денежные счета для раздела правки: имя, kind, валюта + флаг disabled
    (скрытые показываются блёкло с кнопкой возврата, как отменённые проводки)."""
    accs = await engine.list_accounts(include_disabled=True)
    label_of = {a["name"]: a for a in accs}
    reg = money.registered_full()
    out = []
    for pk, meta in reg.items():
        a = label_of.get(pk)
        raw = a["account_name"] if a else _label(pk)
        out.append({"name": pk, "label": _money_label(pk, raw, lang),
                    "currency": meta["currency"],
                    "disabled": bool(a.get("disabled")) if a else False})
    return {"accounts": out, "currencies": currency.options(lang)}

@router.post("/income")
async def create_income(payload: dict):
    """Создать источник поступления (счёт типа Income + перевод в catalog_i18n,
    тот же инвариант, что у категорий)."""
    name = (payload.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "пустое имя"}, status_code=400)
    lang = payload.get("lang", "ru")
    existing = next((a for a in await engine.list_accounts(leaf_only=False, include_disabled=True)
                     if a["account_name"] == name and a["root_type"] == "Income"), None)
    if existing:
        acc = existing["name"]
    else:
        parent = await engine.group_parent("Income")
        acc = await engine.create_account(name, parent, "Income")
    catalog.set_labels(acc, name, name, name)
    return {"name": acc, "label": catalog.label(acc, name, lang)}

@router.post("/account")
async def create_account(payload: dict):
    """Создать денежный счёт: имя + валюта. `kind` упразднён (был наследием
    ERPNext — мапил cash/bank/credit_card в актив/обязательство; после модели
    «счёт = баланс по знаку» он ни на что не влиял). В реестре всегда 'other'."""
    name = (payload.get("name") or "").strip()
    cur = (payload.get("currency") or "").upper()
    if not name:
        return JSONResponse({"error": "пустое имя"}, status_code=400)
    if not currency.known(cur):
        return JSONResponse({"error": "неизвестная валюта"}, status_code=400)
    existing = next((a for a in await engine.list_accounts(leaf_only=False, include_disabled=True)
                     if a["account_name"] == name and a["root_type"] == "Asset"), None)
    if existing:
        pk = existing["name"]
    else:
        parent = await engine.group_parent("Asset")
        pk = await engine.create_account(name, parent, "Asset")
    ordv = len(money.registered())
    money.register(pk, "other", ordv, currency=cur)
    return {"name": pk, "currency": cur}

@router.post("/account/{account:path}/rename")
async def account_rename(account: str, payload: dict):
    """Переименовать счёт = сменить ТОЛЬКО отображаемое имя в нашей БД. PK счёта
    (account) неизменен → журнал, балансы, реестр продолжают работать (ссылаются
    на стабильный id, а не на имя). Тот же приём, что у категорий."""
    label = (payload.get("label") or "").strip()
    if not label:
        return JSONResponse({"error": "пустое имя"}, status_code=400)
    money.set_label(account, label)
    return {"name": account, "label": label}

@router.post("/account/{account:path}/disable")
async def account_disable(account: str):
    """B3: скрытие денежного счёта УСЫПЛЯЕТ его проводки — снимок в slept_entries
    + отмена (cancel убирает из балансов/журнала, обратимо). Восстановление будит.
    Для категорий/источников каскада нет (их записи держит денежная сторона)."""
    try:
        if _is_money_account(account):
            for v in await engine.entries_of_account(account, docstatus=(1,)):
                snap = await engine.entry_detail(v)
                if not snap:
                    continue
                occ = entry_meta.occurred_map([v]).get(v)
                entry_meta.sleep_record(account, snap, occ)
                await engine.cancel_journal_entry(v)   # cancel = усыпление (обратимо)
                entry_meta.forget(v)
        await engine.disable_account(account)
    except engine.EngineError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}

@router.post("/account/{account:path}/enable")
async def account_enable(account: str):
    try:
        await engine.enable_account(account)
        if _is_money_account(account):
            # будим усыплённые проводки — пересоздаём из снимков
            for s in entry_meta.sleeping_for(account):
                new_id = await engine.post_journal_entry(
                    date.fromisoformat(s["posting_date"]),
                    s["remark"], s["debit"], s["credit"], Decimal(str(s["amount"])))
                if s.get("occurred_at"):
                    entry_meta.set_occurred(new_id, s["occurred_at"])
            entry_meta.clear_sleeping(account)
    except engine.EngineError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}

@router.get("/account/{account:path}/usage")
async def account_usage(account: str):
    """Сколько проводок затрагивает счёт/категорию — для диалога удаления."""
    n = len(await engine.entries_of_account(account, docstatus=(1, 2)))
    return {"name": account, "count": n}

@router.post("/account/{account:path}/purge")
async def account_purge(account: str, payload: dict):
    """ОКОНЧАТЕЛЬНОЕ удаление ДЕНЕЖНОГО счёта: физически стирает ВСЕ его проводки
    + сам счёт + метаданные. История гибнет навсегда. Трение: payload.confirm
    должен быть точным словом-подтверждением (передаёт фронт; проверяем непусто)."""
    if not (payload.get("confirm") or "").strip():
        return JSONResponse({"error": "confirm_required"}, status_code=400)
    try:
        for v in await engine.entries_of_account(account, docstatus=(1, 2)):
            await engine.delete_entry(v)
            entry_meta.forget(v)
        entry_meta.clear_sleeping(account)
        money.unregister(account)
        await engine.delete_account(account)
    except engine.EngineError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}

@router.post("/account/{account:path}/purge-category")
async def category_purge(account: str, payload: dict):
    """ОКОНЧАТЕЛЬНОЕ удаление КАТЕГОРИИ/ИСТОЧНИКА: КАСКАДНЫЙ перенос — все его
    проводки переносятся на другой ярлык (move_to, выбирается вручную), затем
    пустой счёт удаляется. История цела (траты/доходы остаются под новым ярлыком)."""
    move_to = (payload.get("move_to") or "").strip()
    if not move_to:
        return JSONResponse({"error": "move_to_required"}, status_code=400)
    valid = {a["name"] for a in await engine.list_accounts(include_disabled=True)}
    if move_to not in valid or move_to == account:
        return JSONResponse({"error": "bad_target"}, status_code=400)
    try:
        # переносим каждую проводку: пересоздаём с заменой нужной стороны на move_to
        for v in await engine.entries_of_account(account, docstatus=(1, 2)):
            det = await engine.entry_detail(v)
            if not det:
                continue
            debit = move_to if det["debit"] == account else det["debit"]
            credit = move_to if det["credit"] == account else det["credit"]
            occ = entry_meta.occurred_map([v]).get(v)
            pdate = date.fromisoformat(str(det["posting_date"]))
            new_id = await engine.post_journal_entry(
                pdate, det["remark"], debit, credit, Decimal(str(det["amount"])))
            if occ:
                entry_meta.set_occurred(new_id, occ)
            await engine.delete_entry(v)
            entry_meta.forget(v)
        money.unregister(account)
        await engine.delete_account(account)
        catalog.forget_labels(account)   # стереть переводы ярлыка из catalog_i18n
    except engine.EngineError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}

@router.post("/category")
async def create_category(payload: dict):
    """Создать пользовательскую категорию расхода.

    ИНВАРИАНТ (см. память «category-lifecycle»): любая новая категория обязана
    (1) создаться счётом в ERPNext, (2) получить переводы ru/en/ko в catalog_i18n,
    (3) стать видимой в form-data. Без шага (2) категория-призрак (баг «Бизнес»).
    Перевод на момент создания — введённое имя на всех языках (заглушка, лучше
    чем русское слово в EN-интерфейсе); пользователь уточнит через переименование.
    """
    name = (payload.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "пустое имя"}, status_code=400)
    lang = payload.get("lang", "ru")
    cap = name.capitalize()
    # если счёт с таким именем уже есть (в т.ч. «призрак» без перевода) —
    # переиспользуем его, иначе создаём. В обоих случаях гарантируем перевод.
    existing = next((a for a in await engine.list_accounts(leaf_only=False, include_disabled=True)
                     if a["account_name"] == cap and a["root_type"] == "Expense"), None)
    if existing:
        acc = existing["name"]
    else:
        acc = await engine.create_account(cap, None, "Expense")
    # переводы: введённое имя во все языки (заглушка для не-введённых)
    catalog.set_labels(acc, name, name, name)
    return {"name": acc, "label": catalog.label(acc, name, lang)}

@router.post("/category/{account}/rename")
async def rename_category(account: str, payload: dict):
    """Переименование = смена лейбла на ТЕКУЩЕМ языке в catalog_i18n (приоритет
    над каноном). account_name в ERPNext не трогаем — это системный ключ; меняем
    только то, что видит пользователь. Так перевод не рассинхронизируется (баг:
    раньше rename менял account_name мимо catalog_i18n)."""
    label = (payload.get("label") or "").strip()
    if not label:
        return JSONResponse({"error": "пустое имя"}, status_code=400)
    lang = payload.get("lang", "ru")
    # текущие лейблы (из catalog_i18n или канона) + перезапись текущего языка
    cur = catalog._user_labels().get(account, {})
    acc_name = next((a["account_name"] for a in await engine.list_accounts(include_disabled=True)
                     if a["name"] == account), account)
    base = catalog.CANON.get(acc_name, {})
    vals = {lng: (cur.get(lng) or base.get(lng) or label) for lng in ("ru", "en", "ko")}
    vals[lang] = label
    catalog.set_labels(account, vals["ru"], vals["en"], vals["ko"])
    return {"name": account, "label": label}
