"""Мультиюзер: пользователи (тенанты) + текущий тенант запроса.

Этап 1 (фундамент изоляции): у каждого пользователя свой tenant_id; ВСЕ
денежные таблицы фильтруются по нему. Текущий тенант кладётся в contextvar на
время запроса (middleware) — чтобы не протаскивать tenant_id через ~50 сигнатур
и не забыть фильтр (забытый фильтр = чужие деньги на экране).

users: id, login (уникальный), pwhash, email, created_at, email_verified.
Пароли — PBKDF2-HMAC-SHA256 (stdlib hashlib, без внешних зависимостей).

Существующие данные владельца переносятся под tenant_id=1 (см. set_tenant_id
в миграции). Глоссарий (UI/валюты/уведомления) — ОБЩИЙ, без tenant_id.
"""

import hashlib
import hmac
import os
import sqlite3
from contextvars import ContextVar
from datetime import datetime, timezone

from counta.core.db import DB_PATH

# текущий тенант запроса; 0 = не установлен (запрещаем доступ к данным)
_current: ContextVar[int] = ContextVar("tenant_id", default=0)

OWNER_TENANT_ID = 1   # владелец (его данные переносятся при миграции)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    login          TEXT UNIQUE NOT NULL,
    pwhash         TEXT NOT NULL,
    email          TEXT DEFAULT '',
    email_verified INTEGER DEFAULT 0,
    verify_code    TEXT DEFAULT '',
    verify_sent    TEXT DEFAULT '',
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE
);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
    if "verify_code" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN verify_code TEXT DEFAULT ''")
    if "verify_sent" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN verify_sent TEXT DEFAULT ''")
    # одноразовый токен сброса пароля (по почте) + срок годности (ISO UTC)
    if "reset_token" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN reset_token TEXT DEFAULT ''")
    if "reset_expires" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN reset_expires TEXT DEFAULT ''")
    return con


# --- контекст текущего тенанта ---
def set_current(tenant_id: int) -> None:
    _current.set(tenant_id)


def current() -> int:
    return _current.get()


def require_current() -> int:
    t = _current.get()
    if not t:
        raise PermissionError("tenant не установлен")
    return t


# --- пароли (PBKDF2, stdlib) ---
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2$200000${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, dk_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# --- пользователи ---
def create_user(login: str, password: str, email: str = "") -> int:
    login = login.strip().lower()
    if not login or not password:
        raise ValueError("логин и пароль обязательны")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO users (login, pwhash, email, created_at) VALUES (?,?,?,?)",
            (login, hash_password(password), email.strip().lower(), now))
        return cur.lastrowid


def get_by_login(login: str) -> dict | None:
    with _conn() as con:
        r = con.execute(
            "SELECT id, login, pwhash, email, email_verified FROM users WHERE login=?",
            (login.strip().lower(),)).fetchone()
    if not r:
        return None
    return {"id": r[0], "login": r[1], "pwhash": r[2], "email": r[3], "email_verified": r[4]}


def authenticate(login: str, password: str) -> int | None:
    """Вернуть tenant_id при верном пароле, иначе None."""
    u = get_by_login(login)
    if u and verify_password(password, u["pwhash"]):
        return u["id"]
    return None


def login_taken(login: str) -> bool:
    return get_by_login(login) is not None


def count_users() -> int:
    with _conn() as con:
        return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def all_ids() -> list[int]:
    """Все tenant_id — для фоновых задач (планировщик), идущих по каждому юзеру."""
    with _conn() as con:
        return [r[0] for r in con.execute("SELECT id FROM users ORDER BY id")]


# --- смена пароля ---
def change_password(tenant_id: int, old_pw: str, new_pw: str) -> bool:
    """Сменить пароль при верном старом. False если старый неверен."""
    with _conn() as con:
        r = con.execute("SELECT pwhash FROM users WHERE id=?", (tenant_id,)).fetchone()
        if not r or not verify_password(old_pw, r[0]):
            return False
        con.execute("UPDATE users SET pwhash=? WHERE id=?",
                    (hash_password(new_pw), tenant_id))
    return True


# --- подтверждение почты ---
def set_verify_code(tenant_id: int, code: str) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _conn() as con:
        con.execute("UPDATE users SET verify_code=?, verify_sent=? WHERE id=?",
                    (code, now, tenant_id))


_VERIFY_TTL_SECONDS = 30 * 60   # код подтверждения почты живёт 30 минут


def check_verify_code(tenant_id: int, code: str) -> bool:
    """Сверить код; при успехе помечает email_verified=1 и стирает код.
    Код действителен 30 минут с момента отправки (verify_sent)."""
    code = (code or "").strip()
    if not code:
        return False
    now = datetime.now(timezone.utc)
    with _conn() as con:
        r = con.execute("SELECT verify_code, verify_sent FROM users WHERE id=?",
                        (tenant_id,)).fetchone()
        if not r or not r[0] or not hmac.compare_digest(r[0], code):
            return False
        sent = r[1]
        if not sent:
            return False
        try:
            sent_dt = datetime.fromisoformat(sent)
        except Exception:
            return False
        if (now - sent_dt).total_seconds() > _VERIFY_TTL_SECONDS:
            return False
        con.execute("UPDATE users SET email_verified=1, verify_code='', verify_sent='' WHERE id=?",
                    (tenant_id,))
    return True


def get_user(tenant_id: int) -> dict | None:
    with _conn() as con:
        r = con.execute(
            "SELECT id, login, email, email_verified FROM users WHERE id=?",
            (tenant_id,)).fetchone()
    if not r:
        return None
    return {"id": r[0], "login": r[1], "email": r[2], "email_verified": r[3]}


def accounts_for_email(email: str) -> list[dict]:
    """Все аккаунты с этой почтой (для восстановления логина / сброса пароля).
    Почта НЕ уникальна — возвращаем список. Пустой email → пусто."""
    email = (email or "").strip().lower()
    if not email:
        return []
    with _conn() as con:
        rows = con.execute(
            "SELECT id, login, email FROM users WHERE email=? ORDER BY id",
            (email,)).fetchall()
    return [{"id": r[0], "login": r[1], "email": r[2]} for r in rows]


def set_reset_token(tenant_id: int, token: str, expires_iso: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET reset_token=?, reset_expires=? WHERE id=?",
                    (token, expires_iso, tenant_id))


def consume_reset_token(token: str) -> int | None:
    """Проверить одноразовый токен сброса: вернуть tenant_id если валиден и не
    истёк, при этом СРАЗУ его погасить (одноразовость). Иначе None."""
    token = (token or "").strip()
    if not token:
        return None
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _conn() as con:
        r = con.execute(
            "SELECT id, reset_expires FROM users WHERE reset_token=?", (token,)).fetchone()
        if not r or not r[1] or r[1] < now:
            return None
        con.execute("UPDATE users SET reset_token='', reset_expires='' WHERE id=?", (r[0],))
    return r[0]


def set_password(tenant_id: int, new_pw: str) -> None:
    """Принудительно задать пароль (после валидного токена сброса; без старого)."""
    with _conn() as con:
        con.execute("UPDATE users SET pwhash=? WHERE id=?",
                    (hash_password(new_pw), tenant_id))


def delete_user(tenant_id: int) -> None:
    """Полностью удалить пользователя и все его данные."""
    with _conn() as con:
        # tenant-specific tables
        for tbl in (
            "led_accounts", "led_entries", "led_lines", "led_seq",
            "money_accounts", "user_settings", "catalog_i18n",
            "entry_meta", "slept_entries", "lexicon",
            "user_apps", "notifications",
        ):
            try:
                con.execute(f"DELETE FROM {tbl} WHERE tenant=?", (tenant_id,))
            except sqlite3.OperationalError:
                pass  # таблица может ещё не существовать
        con.execute("DELETE FROM users WHERE id=?", (tenant_id,))


def set_email(tenant_id: int, email: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET email=?, email_verified=0 WHERE id=?",
                    (email.strip().lower(), tenant_id))


def ensure_owner(login: str, password: str) -> int:
    """Идемпотентно создать владельца с фиксированным id=1 (для миграции
    существующих данных под него). Возвращает OWNER_TENANT_ID."""
    with _conn() as con:
        exists = con.execute("SELECT id FROM users WHERE id=?", (OWNER_TENANT_ID,)).fetchone()
        if exists:
            return OWNER_TENANT_ID
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        con.execute(
            "INSERT INTO users (id, login, pwhash, email, email_verified, created_at) "
            "VALUES (?,?,?,?,1,?)",
            (OWNER_TENANT_ID, login.strip().lower(), hash_password(password), "", now))
    return OWNER_TENANT_ID


# --- администраторы инстанса (отдельно от OWNER_TENANT_ID) ---
def ensure_admin_table() -> None:
    """Создать таблицу admins, если её ещё нет (для миграций)."""
    with _conn() as con:
        con.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE)")


def is_admin(user_id: int | None) -> bool:
    """Является ли пользователь администратором инстанса."""
    if not user_id:
        return False
    with _conn() as con:
        r = con.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)).fetchone()
    return bool(r)


def list_admins() -> list[dict]:
    """Список администраторов с логинами."""
    with _conn() as con:
        rows = con.execute(
            "SELECT u.id, u.login, u.email, u.created_at FROM admins a "
            "JOIN users u ON u.id=a.user_id ORDER BY u.login"
        ).fetchall()
    return [{"id": r[0], "login": r[1], "email": r[2], "created_at": r[3]} for r in rows]


def add_admin(user_id: int) -> None:
    """Назначить пользователя администратором."""
    ensure_admin_table()
    with _conn() as con:
        con.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))


def remove_admin(user_id: int) -> None:
    """Снять права администратора."""
    with _conn() as con:
        con.execute("DELETE FROM admins WHERE user_id=?", (user_id,))


def get_user_by_login(login: str) -> dict | None:
    """Найти пользователя по логину (без учёта регистра)."""
    login = login.strip().lower()
    with _conn() as con:
        r = con.execute(
            "SELECT id, login, email, email_verified, created_at FROM users WHERE login=?",
            (login,)
        ).fetchone()
    if not r:
        return None
    return {"id": r[0], "login": r[1], "email": r[2], "email_verified": r[3], "created_at": r[4]}
