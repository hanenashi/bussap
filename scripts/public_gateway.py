#!/usr/bin/env python3
"""BUSSAP credential gate for a separately routed HTTPS endpoint.

The existing private server remains unchanged. Never route this listener to
Funnel until its WebAuthn flow has been enrolled and checked on real phones.
"""

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestedCredentialData, AuthenticatorAttachment, PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity, ResidentKeyRequirement, UserVerificationRequirement,
)
from fido2.utils import websafe_decode, websafe_encode

from server import Handler, STATIC_FILES, WEB_DIR


DATA_DIR = Path(__file__).resolve().parents[1] / ".local-data"
DB_PATH = DATA_DIR / "gateway.sqlite3"
PDF_PATHS = {"/network-map", "/network-map.js", "/network-map.pdf"}
PUBLIC_BRANDING = {"/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"}
FLOW_SECONDS = 180
SESSION_SECONDS = 14 * 24 * 3600


def sha(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def connect(db_path):
    db = sqlite3.connect(db_path, timeout=5)
    db.row_factory = sqlite3.Row
    return db


def init_db(db_path):
    db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not db_path.exists():
        fd = os.open(db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    with connect(db_path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS invites (
                digest TEXT PRIMARY KEY, label TEXT NOT NULL, expires INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS credentials (
                id TEXT PRIMARY KEY, label TEXT NOT NULL, data TEXT NOT NULL, added INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS flows (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL,
                invite_digest TEXT, expires INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                digest TEXT PRIMARY KEY, credential_id TEXT NOT NULL,
                expires INTEGER NOT NULL
            );
        """)


def make_invite(db_path, label):
    if not label or len(label) > 40 or not all(c.isalnum() or c in " _-" for c in label):
        raise ValueError("label must be 1–40 simple characters")
    token = websafe_encode(secrets.token_bytes(24))
    digest = sha(token)
    with connect(db_path) as db:
        if db.execute("SELECT count(*) FROM credentials").fetchone()[0] >= 2:
            raise ValueError("two phones are already enrolled")
        db.execute("INSERT INTO invites VALUES (?, ?, ?)", (digest, label, int(time.time()) + 7 * 86400))
    path = DATA_DIR / f"gateway-invite-{digest[:12]}.txt"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as out:
        out.write(token + "\n")
    return path


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, default=lambda item: dict(item)).encode("utf-8")


def active_flow(db, flow_id, kind):
    if not isinstance(flow_id, str) or len(flow_id) != 32:
        return None
    row = db.execute("SELECT * FROM flows WHERE id=? AND kind=? AND expires>?", (flow_id, kind, int(time.time()))).fetchone()
    if row:
        db.execute("DELETE FROM flows WHERE id=?", (flow_id,))
    return row


class GatewayHandler(Handler):
    auth_server = None
    db_path = DB_PATH
    allowed_origins = frozenset()

    def response(self, status, body, content_type="text/html; charset=utf-8", cookie=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def reply(self, status, value, cookie=None):
        self.response(status, json_bytes(value), "application/json; charset=utf-8", cookie)

    def database(self):
        return connect(self.db_path)

    def authenticated(self):
        parts = self.headers.get("Cookie", "").split(";")
        token = next((part.strip()[15:] for part in parts if part.strip().startswith("bussap_session=")), None)
        if not token or len(token) > 128:
            return False
        try:
            digest = sha(token)
        except UnicodeEncodeError:
            return False
        with self.database() as db:
            return bool(db.execute("SELECT 1 FROM sessions WHERE digest=? AND expires>?", (digest, int(time.time()))).fetchone())

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in PUBLIC_BRANDING:
            self.send_static(*STATIC_FILES[path])
            return
        if path == "/auth.js":
            self.response(200, (WEB_DIR / "auth.js").read_bytes(), "text/javascript; charset=utf-8")
            return
        if path == "/auth":
            self.response(200, (WEB_DIR / "auth.html").read_bytes())
            return
        if not self.authenticated():
            if path == "/":
                self.response(200, (WEB_DIR / "auth.html").read_bytes())
            elif path in PDF_PATHS:
                self.reply(404, {"error": "not found"})
            else:
                self.reply(401, {"error": "sign in required"})
            return
        super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in {"/auth/login/begin", "/auth/login/complete", "/auth/enroll/begin", "/auth/enroll/complete", "/auth/logout"}:
            self.reply(405, {"error": "not allowed"})
            return
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin", "")
        if origin not in self.allowed_origins or urlsplit(origin).netloc != host:
            self.reply(403, {"error": "origin denied"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > 16384:
                raise ValueError("request too large")
            payload = json.loads(self.rfile.read(size)) if size else {}
            if not isinstance(payload, dict):
                raise ValueError("invalid request")
            if path == "/auth/login/begin":
                self.login_begin()
            elif path == "/auth/login/complete":
                self.login_complete(payload)
            elif path == "/auth/enroll/begin":
                self.enroll_begin(payload)
            elif path == "/auth/enroll/complete":
                self.enroll_complete(payload)
            else:
                self.logout()
        except (ValueError, KeyError, TypeError, UnicodeEncodeError, sqlite3.IntegrityError) as exc:
            self.reply(400, {"error": str(exc)[:120]})

    def add_flow(self, db, kind, state, invite_digest=None):
        now = int(time.time())
        db.execute("DELETE FROM flows WHERE expires<=?", (now,))
        if db.execute("SELECT count(*) FROM flows").fetchone()[0] >= 100:
            raise ValueError("too many pending attempts")
        flow = websafe_encode(secrets.token_bytes(24))
        db.execute("INSERT INTO flows VALUES (?, ?, ?, ?, ?)", (flow, kind, json.dumps(state), invite_digest, now + FLOW_SECONDS))
        return flow

    def login_begin(self):
        with self.database() as db:
            rows = db.execute("SELECT data FROM credentials").fetchall()
            if not rows:
                self.reply(409, {"error": "no phones enrolled yet"})
                return
            credentials = [AttestedCredentialData(websafe_decode(row["data"])) for row in rows]
            options, state = self.auth_server.authenticate_begin(credentials, user_verification=UserVerificationRequirement.REQUIRED)
            flow = self.add_flow(db, "login", state)
        self.reply(200, {"flow": flow, "options": options})

    def login_complete(self, payload):
        with self.database() as db:
            row = active_flow(db, payload["flow"], "login")
            if not row:
                raise ValueError("sign-in attempt expired")
            credentials = [AttestedCredentialData(websafe_decode(item["data"])) for item in db.execute("SELECT data FROM credentials")]
            credential = self.auth_server.authenticate_complete(json.loads(row["state"]), credentials, payload["credential"])
            credential_id = websafe_encode(credential.credential_id)
            token = websafe_encode(secrets.token_bytes(32))
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (sha(token), credential_id, int(time.time()) + SESSION_SECONDS))
        cookie = f"bussap_session={token}; Path=/; Max-Age={SESSION_SECONDS}; Secure; HttpOnly; SameSite=Lax"
        self.reply(200, {"ok": True}, cookie)

    def enroll_begin(self, payload):
        code = payload.get("code", "")
        if not isinstance(code, str) or len(code) != 32:
            raise ValueError("invalid enrollment code")
        digest = sha(code)
        with self.database() as db:
            invite = db.execute("SELECT label FROM invites WHERE digest=? AND expires>?", (digest, int(time.time()))).fetchone()
            if not invite:
                raise ValueError("enrollment code expired or invalid")
            if db.execute("SELECT count(*) FROM credentials").fetchone()[0] >= 2:
                raise ValueError("two phones are already enrolled")
            label = invite["label"]
            options, state = self.auth_server.register_begin(
                PublicKeyCredentialUserEntity(id=secrets.token_bytes(16), name=label, display_name=label),
                resident_key_requirement=ResidentKeyRequirement.DISCOURAGED,
                user_verification=UserVerificationRequirement.REQUIRED,
                authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            )
            flow = self.add_flow(db, "enroll", state, digest)
        self.reply(200, {"flow": flow, "options": options})

    def enroll_complete(self, payload):
        with self.database() as db:
            row = active_flow(db, payload["flow"], "enroll")
            if not row:
                raise ValueError("enrollment attempt expired")
            invite = db.execute("SELECT label FROM invites WHERE digest=? AND expires>?", (row["invite_digest"], int(time.time()))).fetchone()
            if not invite or db.execute("SELECT count(*) FROM credentials").fetchone()[0] >= 2:
                raise ValueError("enrollment closed")
            auth_data = self.auth_server.register_complete(json.loads(row["state"]), payload["credential"])
            if auth_data.is_backup_eligible():
                raise ValueError("choose a credential stored only on this phone")
            credential = auth_data.credential_data
            credential_id = websafe_encode(credential.credential_id)
            db.execute("INSERT INTO credentials VALUES (?, ?, ?, ?)",
                       (credential_id, invite["label"], websafe_encode(bytes(credential)), int(time.time())))
            db.execute("DELETE FROM invites WHERE digest=?", (row["invite_digest"],))
            token = websafe_encode(secrets.token_bytes(32))
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (sha(token), credential_id, int(time.time()) + SESSION_SECONDS))
        cookie = f"bussap_session={token}; Path=/; Max-Age={SESSION_SECONDS}; Secure; HttpOnly; SameSite=Lax"
        self.reply(200, {"ok": True}, cookie)

    def logout(self):
        token = next((part.strip()[15:] for part in self.headers.get("Cookie", "").split(";") if part.strip().startswith("bussap_session=")), None)
        if token:
            try:
                with self.database() as db:
                    db.execute("DELETE FROM sessions WHERE digest=?", (sha(token),))
            except UnicodeEncodeError:
                pass
        self.reply(200, {"ok": True}, "bussap_session=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Lax")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["serve", "invite", "list", "revoke"])
    parser.add_argument("label", nargs="?")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--rp-id", default="beechan.tail8d9f69.ts.net")
    parser.add_argument("--origins", default="https://beechan.tail8d9f69.ts.net:10003,https://beechan.tail8d9f69.ts.net:10000")
    args = parser.parse_args()
    init_db(args.db)
    if args.command == "invite":
        path = make_invite(args.db, args.label)
        print(f"Enrollment code saved in {path} (mode 0600); open it locally before pairing the phone.")
        return
    if args.command == "list":
        with connect(args.db) as db:
            for row in db.execute("SELECT label, added FROM credentials ORDER BY added"):
                print(row["label"], datetime.fromtimestamp(row["added"], timezone.utc).isoformat())
        return
    if args.command == "revoke":
        if not args.label:
            parser.error("revoke needs the enrolled phone label")
        with connect(args.db) as db:
            rows = db.execute("SELECT id FROM credentials WHERE label=?", (args.label,)).fetchall()
            for row in rows:
                db.execute("DELETE FROM sessions WHERE credential_id=?", (row["id"],))
            db.execute("DELETE FROM credentials WHERE label=?", (args.label,))
        print(f"Revoked {len(rows)} credential(s) for {args.label}.")
        return
    origins = frozenset(value.strip() for value in args.origins.split(",") if value.strip())
    if not origins or any(urlsplit(origin).hostname != args.rp_id for origin in origins):
        parser.error("all allowed origins must use the RP hostname")
    GatewayHandler.auth_server = Fido2Server(
        PublicKeyCredentialRpEntity(id=args.rp_id, name="BUSSAP"),
        verify_origin=lambda origin: origin in origins,
    )
    GatewayHandler.db_path = args.db
    GatewayHandler.allowed_origins = origins
    server = ThreadingHTTPServer(("127.0.0.1", args.port), GatewayHandler)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
