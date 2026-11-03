"""PLANEXUS B3.2: private, invite-only user accounts and session authorization.

Uses hashlib.scrypt password hashes, opaque random HttpOnly cookie sessions
(only SHA-256 token digests in SQLite), origin+CSRF checks and DB ownership.
No public open-signup, email/password recovery or team sharing in this phase.
An operator must create the first admin OFFLINE with this module's CLI.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from .project_store import connection
from .settings import DATA_DIR

COOKIE_NAME = "planexus_session"
SESSION_HOURS = 12
INVITE_HOURS = 48
PASSWORD_MIN = 12
PASSWORD_MAX = 128
LOGIN_LIMIT = 8
LOCK_MINUTES = 15
EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,255}\.[^\s@]{2,63}$")
MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or utc()).isoformat(timespec="seconds")


def _email(value: str) -> str:
    email = value.strip().lower() if isinstance(value, str) else ""
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise HTTPException(422, "Masukkan alamat e-mel yang sah.")
    return email


def _name(value: str) -> str:
    name = value.strip() if isinstance(value, str) else ""
    if not 2 <= len(name) <= 100:
        raise HTTPException(422, "Nama paparan perlu 2–100 aksara.")
    return name


def _password(value: str) -> str:
    if not isinstance(value, str) or not PASSWORD_MIN <= len(value) <= PASSWORD_MAX:
        raise HTTPException(422, "Kata laluan perlu 12–128 aksara.")
    if value.casefold() in {
        "password123456", "123456789012", "qwerty123456",
        "passwordpassword", "admin123456789"
    }:
        raise HTTPException(422, "Kata laluan terlalu mudah.")
    return value


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    result = hashlib.scrypt(_password(password).encode("utf-8"), salt=salt,
                            n=2**14, r=8, p=1, dklen=32)
    return "scrypt:16384:8:1:" + salt.hex() + ":" + result.hex()


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, ns, rs, ps, salt, expected = encoded.split(":")
        if (ns, rs, ps) != ("16384", "8", "1"):
            return False
        secret = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt),
                                n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(secret, bytes.fromhex(expected))
    except (TypeError, ValueError, OverflowError):
        return False


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def schema(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','planner')),
            created_at_utc TEXT NOT NULL,
            disabled INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token_digest TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            csrf_token TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            expires_at_utc TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_auth_sessions_user ON auth_sessions(user_id);
        CREATE TABLE IF NOT EXISTS registration_invites (
            token_digest TEXT PRIMARY KEY,
            created_by TEXT NOT NULL REFERENCES users(id),
            expires_at_utc TEXT NOT NULL,
            used_by TEXT REFERENCES users(id),
            used_at_utc TEXT
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
            email_digest TEXT PRIMARY KEY,
            failures INTEGER NOT NULL,
            first_failed_at_utc TEXT NOT NULL
        );
    """)


def user_public(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["id"], "email": row["email"],
            "display_name": row["display_name"], "role": row["role"]}


def create_user(data_dir: Path, email: str, display_name: str, password: str,
                *, role: str = "planner") -> dict[str, Any]:
    if role not in ("admin", "planner"):
        raise HTTPException(422, "Peranan pengguna tidak sah.")
    email, display_name = _email(email), _name(display_name)
    hashed = hash_password(password)
    user_id = str(uuid.uuid4())
    with connection(data_dir) as db:
        schema(db)
        try:
            with db:
                db.execute(
                    "INSERT INTO users(id,email,display_name,password_hash,role,created_at_utc)"
                    " VALUES(?,?,?,?,?,?)",
                    (user_id, email, display_name, hashed, role, iso()),
                )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Akaun dengan e-mel ini sudah wujud.") from exc
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return user_public(row)


def create_invite(data_dir: Path, admin_email: str, hours: int = INVITE_HOURS) -> str:
    if not 1 <= hours <= 168:
        raise ValueError("Invites must expire within 1–168 hours.")
    with connection(data_dir) as db:
        schema(db)
        admin = db.execute("SELECT id FROM users WHERE email=? AND role='admin' AND disabled=0",
                           (_email(admin_email),)).fetchone()
        if admin is None:
            raise HTTPException(403, "Admin account not found or disabled.")
        token = secrets.token_urlsafe(32)
        with db:
            db.execute(
                "INSERT INTO registration_invites(token_digest,created_by,expires_at_utc)"
                " VALUES(?,?,?)",
                (digest(token), admin["id"], iso(utc()+timedelta(hours=hours))),
            )
        return token


def register(data_dir: Path, email: str, display_name: str,
             password: str, invite_token: str) -> dict[str, Any]:
    email, display_name, password = _email(email), _name(display_name), _password(password)
    if not invite_token or len(invite_token) > 256:
        raise HTTPException(403, "Jemputan tidak sah atau tamat tempoh.")
    hashed = hash_password(password)
    with connection(data_dir) as db:
        schema(db)
        with db:
            invite = db.execute(
                "SELECT token_digest,expires_at_utc,used_by FROM registration_invites "
                "WHERE token_digest=?", (digest(invite_token),)
            ).fetchone()
            if invite is None or invite["used_by"] or invite["expires_at_utc"] <= iso():
                raise HTTPException(403, "Jemputan tidak sah atau tamat tempoh.")
            user_id = str(uuid.uuid4())
            try:
                db.execute(
                    "INSERT INTO users(id,email,display_name,password_hash,role,created_at_utc)"
                    " VALUES(?,?,?,?,'planner',?)",
                    (user_id, email, display_name, hashed, iso()),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, "Akaun ini sudah didaftarkan.") from exc
            changed = db.execute(
                "UPDATE registration_invites SET used_by=?,used_at_utc=? "
                "WHERE token_digest=? AND used_by IS NULL",
                (user_id, iso(), invite["token_digest"]),
            ).rowcount
            if changed != 1:
                raise HTTPException(403, "Jemputan sudah digunakan.")
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return user_public(row)


def authenticate(data_dir: Path, email: str, password: str) -> tuple[dict[str, Any], str, str]:
    # Throttle by normalized email hash; response does not disclose existence.
    email = _email(email)
    hashed_email = digest(email)
    with connection(data_dir) as db:
        schema(db)
        attempt = db.execute("SELECT failures,first_failed_at_utc FROM login_attempts "
                             "WHERE email_digest=?", (hashed_email,)).fetchone()
        if attempt and attempt["failures"] >= LOGIN_LIMIT:
            if attempt["first_failed_at_utc"] > iso(utc()-timedelta(minutes=LOCK_MINUTES)):
                raise HTTPException(429, "Terlalu banyak percubaan. Cuba semula kemudian.")
        row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        valid = bool(row and not row["disabled"] and verify_password(password, row["password_hash"]))
        if not valid:
            with db:
                if not attempt or attempt["first_failed_at_utc"] <= iso(utc()-timedelta(minutes=LOCK_MINUTES)):
                    db.execute("INSERT OR REPLACE INTO login_attempts VALUES (?,?,?)",
                               (hashed_email, 1, iso()))
                else:
                    db.execute("UPDATE login_attempts SET failures=failures+1 "
                               "WHERE email_digest=?", (hashed_email,))
            raise HTTPException(401, "E-mel atau kata laluan salah.")
        with db:
            db.execute("DELETE FROM login_attempts WHERE email_digest=?", (hashed_email,))
            secret = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO auth_sessions(token_digest,user_id,csrf_token,created_at_utc,expires_at_utc)"
                " VALUES(?,?,?,?,?)",
                (digest(secret),row["id"],csrf,iso(),iso(utc()+timedelta(hours=SESSION_HOURS))),
            )
            return user_public(row),secret,csrf


def session(data_dir: Path, token: str | None) -> tuple[dict[str, Any], str] | None:
    if not token or len(token) > 256:
        return None
    with connection(data_dir) as db:
        schema(db)
        row = db.execute(
            "SELECT u.*,s.csrf_token FROM auth_sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.token_digest=? AND s.expires_at_utc>? AND u.disabled=0",
            (digest(token), iso()),
        ).fetchone()
        return (user_public(row), row["csrf_token"]) if row else None


def revoke(data_dir: Path, token: str | None) -> None:
    if token and len(token) <= 256:
        with connection(data_dir) as db:
            schema(db)
            with db:
                db.execute("DELETE FROM auth_sessions WHERE token_digest=?", (digest(token),))


def request_user(request: Request, data_dir: Path) -> dict[str, Any]:
    credentials = session(data_dir, request.cookies.get(COOKIE_NAME))
    if not credentials:
        raise HTTPException(401, "Sesi telah tamat atau belum login.")
    user, csrf = credentials
    if request.method.upper() in MUTATION_METHODS:
        provided = request.headers.get("x-csrf-token","")
        if not provided or not hmac.compare_digest(provided, csrf):
            raise HTTPException(403, "Token keselamatan sesi tidak sah.")
    return user


def require_project(data_dir: Path, project_id: str, user_id: str) -> None:
    try:
        normalized = str(uuid.UUID(project_id))
    except (TypeError, AttributeError, ValueError) as exc:
        raise HTTPException(422,"ID projek tidak sah.") from exc
    with connection(data_dir) as db:
        row = db.execute("SELECT 1 FROM projects WHERE id=? AND owner_user_id=?",
                         (normalized, user_id)).fetchone()
        if not row:
            raise HTTPException(404, "Projek tidak ditemui.")


def require_analysis(data_dir: Path, analysis_id: str, user_id: str) -> None:
    try:
        normalized = str(uuid.UUID(analysis_id))
    except (TypeError, AttributeError, ValueError) as exc:
        raise HTTPException(422, "ID analisis tidak sah.") from exc
    with connection(data_dir) as db:
        row = db.execute(
            "SELECT 1 FROM project_analyses a JOIN projects p ON p.id=a.project_id "
            "WHERE a.analysis_id=? AND p.owner_user_id=?",
            (normalized,user_id)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Analisis tidak ditemui.")


def owned_analyses(data_dir: Path, user_id: str) -> list[dict[str, Any]]:
    with connection(data_dir) as db:
        rows = db.execute(
            "SELECT a.analysis_id,a.created_at_utc,a.site_area_ha,a.source_name "
            "FROM project_analyses a JOIN projects p ON p.id=a.project_id "
            "WHERE p.owner_user_id=? ORDER BY a.created_at_utc DESC LIMIT 50",
            (user_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def account_count(data_dir: Path) -> int:
    with connection(data_dir) as db:
        schema(db)
        return db.execute("SELECT COUNT(*) FROM users WHERE disabled=0").fetchone()[0]


def disable_user(data_dir: Path, admin_email: str, target_email: str) -> None:
    """Offline revocation: immediately kills every active session for the user."""
    with connection(data_dir) as db:
        schema(db)
        operator=db.execute("SELECT id FROM users WHERE email=? AND role='admin' AND disabled=0",
                            (_email(admin_email),)).fetchone()
        target=db.execute("SELECT id FROM users WHERE email=? AND disabled=0",
                          (_email(target_email),)).fetchone()
        if operator is None or target is None:
            raise HTTPException(404, "Active administrator or target account not found.")
        if operator["id"]==target["id"]:
            raise HTTPException(422,"Admin cannot disable own account through this command.")
        with db:
            db.execute("UPDATE users SET disabled=1 WHERE id=?",(target["id"],))
            db.execute("DELETE FROM auth_sessions WHERE user_id=?",(target["id"],))


def claim_legacy(data_dir: Path, owner_email: str) -> int:
    """Offline-only claim, preserves every raster and report; never auto-claim."""
    with connection(data_dir) as db:
        schema(db)
        admin = db.execute("SELECT id FROM users WHERE email=? AND role='admin' AND disabled=0",
                           (_email(owner_email),)).fetchone()
        if admin is None:
            raise HTTPException(403,"Admin does not exist.")
        with db:
            changed = db.execute("UPDATE projects SET owner_user_id=? "
                                 "WHERE owner_user_id IS NULL",(admin["id"],)).rowcount
        return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="PLANEXUS offline account management (NOT public API)")
    cmds = parser.add_subparsers(dest="command",required=True)
    admin = cmds.add_parser("create-admin", help="Create an admin from an offline console")
    admin.add_argument("--email",required=True)
    admin.add_argument("--name",required=True)
    invite = cmds.add_parser("create-invite")
    invite.add_argument("--admin-email",required=True)
    invite.add_argument("--hours",type=int,default=INVITE_HOURS)
    claim = cmds.add_parser("claim-legacy")
    claim.add_argument("--admin-email",required=True)
    disable = cmds.add_parser("disable-user")
    disable.add_argument("--admin-email",required=True)
    disable.add_argument("--email",required=True)
    commands_status=cmds.add_parser("status",help="Count active user accounts")
    arguments = parser.parse_args()
    if arguments.command == "create-admin":
        one = getpass.getpass("Password (12–128 chars): ")
        two = getpass.getpass("Confirm password: ")
        if one != two:
            parser.error("Passwords do not match.")
        user = create_user(DATA_DIR,arguments.email,arguments.name,one,role="admin")
        print("Admin created:",user["email"])
    elif arguments.command == "create-invite":
        print("One-time invitation (keep secret, expires):",
              create_invite(DATA_DIR,arguments.admin_email,arguments.hours))
    elif arguments.command == "claim-legacy":
        print("Legacy projects assigned to the named admin:", claim_legacy(DATA_DIR,arguments.admin_email))
    elif arguments.command == "disable-user":
        disable_user(DATA_DIR,arguments.admin_email,arguments.email)
        print("Account disabled and all its login sessions revoked:",arguments.email)
    elif arguments.command == "status":
        print("Active PLANEXUS accounts:",account_count(DATA_DIR))


if __name__ == "__main__":
    main()
