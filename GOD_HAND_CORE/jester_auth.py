"""Shared secret for the local Jester API.

The Flask server in server.py exposes endpoints that run arbitrary Python
(/api/sandbox), spawn arbitrary subprocesses (/api/execute_tool -> mcp_execute)
and drive the mouse and keyboard (computer_use). Binding to loopback keeps other
machines out, but on its own it still lets *anything* on this machine call them
-- including any browser extension the user installs and any web page, via a
cross-origin fetch to localhost.

This module owns a single token, generated on first use and stored in a file
next to the database. Callers that can read the filesystem as this user (the
Vite dev-server proxy, bot.py) pick it up automatically; browser extensions,
which cannot, must be given it once by the user.

Threat model, stated plainly: this stops a web page or a rogue extension,
because neither can read a file on disk. It does NOT stop a malicious process
running as this same user -- that process can simply read the token file. A
same-user local attacker cannot be defended against with a file-based secret,
and pretending otherwise would be worse than saying so.
"""

import logging
import os
import secrets
import stat

logger = logging.getLogger("JESTER_AUTH")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.getenv("JESTER_TOKEN_FILE", os.path.join(BASE_DIR, ".jester_token"))
TOKEN_HEADER = "X-Jester-Token"
# EventSource cannot set request headers. The React app avoids needing this by
# going through Vite's proxy (which injects the header server-side), but a
# direct EventSource consumer has no other option.
TOKEN_QUERY_PARAM = "jester_token"

_TRUTHY_OFF = ("0", "false", "no", "off")


def auth_required():
    """False disables enforcement entirely (escape hatch if a client breaks)."""
    return os.getenv("JESTER_REQUIRE_AUTH", "1").lower() not in _TRUTHY_OFF


def _harden_permissions(path):
    """Best-effort 0600. On Windows the user-profile ACL is the real control."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def load_token(create=False):
    """Return the shared token, or None if absent and create=False.

    An explicit JESTER_API_TOKEN wins, so a supervisor can inject one without
    touching the filesystem.
    """
    env_token = os.getenv("JESTER_API_TOKEN")
    if env_token:
        return env_token.strip()

    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as handle:
            token = handle.read().strip()
        if token:
            return token
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.warning(f"Could not read token file {TOKEN_FILE}: {e}")

    if not create:
        return None

    token = secrets.token_urlsafe(32)
    try:
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        # x -> fail if another process won the race; re-read theirs instead of
        # clobbering it, or the two would disagree about the secret.
        with open(TOKEN_FILE, "x", encoding="utf-8") as handle:
            handle.write(token)
        _harden_permissions(TOKEN_FILE)
        logger.info(f"Generated new API token at {TOKEN_FILE}")
        return token
    except FileExistsError:
        return load_token(create=False)
    except OSError as e:
        logger.error(f"Could not write token file {TOKEN_FILE}: {e}")
        return token


def token_matches(supplied, expected):
    """Constant-time comparison; None/empty never matches."""
    if not supplied or not expected:
        return False
    return secrets.compare_digest(str(supplied), str(expected))


def auth_headers():
    """Headers a Python client should send. Empty dict if there is no token."""
    token = load_token(create=False)
    return {TOKEN_HEADER: token} if token else {}
