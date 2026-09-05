import os
import re
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REPO_URL = "https://github.com/TristenLong/T.git"


def _git(*args):
    """Run a git command in the project root, returning (returncode, stdout)."""
    try:
        proc = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
            timeout=60,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return 1, str(e)


def _is_git_repo():
    code, _ = _git("rev-parse", "--is-inside-work-tree")
    return code == 0


def _current_branch():
    code, out = _git("rev-parse", "--abbrev-ref", "HEAD")
    if code != 0:
        return "main"
    branch = out.strip()
    return branch if branch and branch != "HEAD" else "main"


def _remote_url():
    code, out = _git("remote", "get-url", "origin")
    if code == 0:
        url = out.strip()
        if url:
            return _strip_credentials(url)
    return DEFAULT_REPO_URL


def _strip_credentials(url):
    """Remove any userinfo (e.g. an embedded token) from a git URL."""
    return re.sub(r"://[^/@]+@", "://", url)


def _remote_ahead_of_local(branch):
    """True when origin/<branch> is strictly ahead of HEAD (safe to pull).

    `git merge-base --is-ancestor HEAD origin/<branch>` exits 0 only when the
    local tip is reachable from the remote tip. If it fails, the remote is
    either exactly equal, behind, or diverged from local -- upgrading then
    would silently discard committed local work (this branch is normally ahead
    until it is pushed).
    """
    code, _ = _git("merge-base", "--is-ancestor", "HEAD", "origin/" + branch)
    if code != 0:
        return False
    code, out = _git("rev-parse", "--verify", "origin/" + branch)
    return code == 0 and bool(out.strip())


def check_for_updates():
    """Compare local HEAD against origin/<branch>.

    Returns a dict with current/latest SHAs, whether an update is available,
    the tracked branch, and the remote URL.
    """
    result = {"ok": False, "error": None, "available": False}
    if not _is_git_repo():
        result["error"] = "NOT_A_GIT_REPO"
        return result

    branch = _current_branch()
    code, _ = _git("remote", "add", "origin", DEFAULT_REPO_URL) if _git("remote", "get-url", "origin")[0] != 0 else (0, "")
    code, out = _git("fetch", "origin", branch)
    if code != 0:
        result["error"] = "FETCH_FAILED: " + out.strip()[:300]
        return result

    _, local = _git("rev-parse", "HEAD")
    _, remote = _git("rev-parse", "origin/" + branch)
    local_sha = local.strip()
    remote_sha = remote.strip()

    result.update(
        {
            "ok": True,
            "branch": branch,
            "current": local_sha,
            "latest": remote_sha,
            "remote_url": _remote_url(),
            "available": (
                bool(remote_sha)
                and remote_sha != local_sha
                and _remote_ahead_of_local(branch)
            ),
        }
    )
    return result


def do_upgrade():
    """Hard-reset the working tree to origin/<tracked branch>.

    Discards local changes to tracked files and pins the repo to the latest
    remote commit. Returns a summary dict.

    Guards: refuses to run when the remote is NOT strictly ahead of HEAD
    (otherwise an unre-pushed local branch would be downgraded); runtime state
    (chroma_db, DBs, xp) is untracked and gitignored so the reset can never hit
    the Windows file locks a live server holds on them.
    """
    result = {"ok": False, "error": None}
    if not _is_git_repo():
        result["error"] = "NOT_A_GIT_REPO"
        return result

    branch = _current_branch()
    code, out = _git("fetch", "origin", branch)
    if code != 0:
        result["error"] = "FETCH_FAILED: " + out.strip()[:300]
        return result

    _, remote = _git("rev-parse", "origin/" + branch)
    remote_sha = remote.strip()
    _, local = _git("rev-parse", "HEAD")
    local_sha = local.strip()

    if not remote_sha:
        result["error"] = "NO_REMOTE_COMMIT"
        return result
    if remote_sha == local_sha:
        result.update({"ok": True, "already_up_to_date": True, "sha": local_sha, "branch": branch})
        return result
    if not _remote_ahead_of_local(branch):
        result["error"] = (
            "REMOTE_NOT_AHEAD: origin/" + branch + " contains no new commits on "
            "top of local history (local is ahead or diverged). Upgrade would "
            "discard committed local work. Push local commits first, then retry."
        )
        return result

    code, out = _git("reset", "--hard", "origin/" + branch)
    if code != 0:
        result["error"] = (
            "RESET_FAILED: " + out.strip()[:300] +
            " (if a file is locked, stop the app and run: "
            "git reset --hard origin/" + branch + ")"
        )
        return result

    result.update(
        {
            "ok": True,
            "already_up_to_date": False,
            "branch": branch,
            "from": local_sha,
            "to": remote_sha,
            "output": out.strip()[:1000],
        }
    )
    return result


if __name__ == "__main__":
    print("Fetching update status...")
    print(check_for_updates())