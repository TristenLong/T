"""Error Learning: capture, categorize, and recall error patterns.

Every error the app encounters is logged with context. When the same error
recurs, the system suggests the resolution that worked last time. This gives
JESTER the ability to learn from its mistakes instead of repeating them.

Uses the same SQLite database as memory_core (jester_brain.db).
"""

import json
import logging
import os
import sqlite3
import time

logger = logging.getLogger("ERROR_LEARNING")

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jester_brain.db')

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_TABLE = '''CREATE TABLE IF NOT EXISTS error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    context TEXT DEFAULT '',
    resolution TEXT DEFAULT NULL,
    occurrences INTEGER DEFAULT 1,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved INTEGER DEFAULT 0
)'''

_CREATE_INDEX = 'CREATE INDEX IF NOT EXISTS idx_error_source ON error_log(source)'
_CREATE_INDEX2 = 'CREATE INDEX IF NOT EXISTS idx_error_type ON error_log(error_type)'


def _init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(_CREATE_TABLE)
        c.execute(_CREATE_INDEX)
        c.execute(_CREATE_INDEX2)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"error_learning init failed: {e}")


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

_ERROR_PATTERNS = [
    ('network',  ('connection', 'connect', 'network', 'dns', 'socket', 'timed out',
                  'read timed', 'connect timeout', 'connectionreset', 'broken pipe')),
    ('quota',    ('quota', 'rate limit', '429', 'resource_exhausted', 'too many requests',
                  'exceeded')),
    ('auth',     ('401', '403', 'unauthorized', 'forbidden', 'invalid api key',
                  'permission denied', 'token')),
    ('model',    ('model not found', 'model_not_found', 'does not exist',
                  'not available', 'context length', 'maximum context')),
    ('config',   ('not set', 'missing', 'empty', 'key', 'token', 'env')),
    ('timeout',  ('timeout', 'timed out', 'deadline', 'deadline exceeded')),
    ('plugin',   ('plugin', 'grow', 'import', 'syntax error', 'compilation')),
]


def classify_error(error_text: str) -> str:
    low = error_text.lower()
    for cat, keywords in _ERROR_PATTERNS:
        for kw in keywords:
            if kw in low:
                return cat
    return 'unknown'


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def record_error(source: str, error: Exception | str, context: str = '',
                 resolution: str | None = None) -> str:
    """Record an error. Returns 'RECORDED' or an error string.

    If the same source+message was seen before, increments the occurrence
    count and optionally updates the resolution.
    """
    try:
        error_type = classify_error(str(error))
        error_msg = str(error)[:500]

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # Look for an existing unresolved match
        c.execute(
            '''SELECT id, occurrences, resolution FROM error_log
               WHERE source = ? AND error_message = ? AND resolved = 0
               ORDER BY id DESC LIMIT 1''',
            (source, error_msg))
        row = c.fetchone()

        if row:
            eid, occ, existing_res = row
            new_occ = occ + 1
            res = resolution if resolution else existing_res
            c.execute(
                '''UPDATE error_log
                   SET occurrences = ?, last_seen = CURRENT_TIMESTAMP,
                       resolution = ?
                   WHERE id = ?''',
                (new_occ, res, eid))
        else:
            c.execute(
                '''INSERT INTO error_log
                   (source, error_type, error_message, context, resolution)
                   VALUES (?, ?, ?, ?, ?)''',
                (source, error_type, error_msg, context[:2000], resolution))

        conn.commit()
        conn.close()
        return 'RECORDED'
    except Exception as e:
        return f'ERROR_LEARNING: {e}'


def mark_resolved(source: str, error_message: str, resolution: str) -> str:
    """Mark an error as resolved with the fix that worked."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            '''UPDATE error_log SET resolved = 1, resolution = ?
               WHERE source = ? AND error_message = ?''',
            (resolution, source, error_message[:500]))
        conn.commit()
        conn.close()
        return 'RESOLVED'
    except Exception as e:
        return f'ERROR_LEARNING: {e}'


def get_resolution_hint(source: str, error: Exception | str) -> str | None:
    """If this exact error was seen before and resolved, return the fix."""
    try:
        error_msg = str(error)[:500]
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            '''SELECT resolution FROM error_log
               WHERE source = ? AND error_message = ? AND resolved = 1
               ORDER BY last_seen DESC LIMIT 1''',
            (source, error_msg))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return None


def get_error_patterns(limit: int = 20, unresolved_only: bool = False) -> str:
    """Return a summary of error patterns for inspection."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        where = 'WHERE resolved = 0' if unresolved_only else ''
        c.execute(
            f'''SELECT source, error_type, error_message, occurrences,
                       last_seen, resolution, resolved
                FROM error_log {where}
                ORDER BY occurrences DESC, last_seen DESC LIMIT ?''',
            (limit,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            return 'NO_ERRORS_RECORDED'
        lines = []
        for r in rows:
            status = 'RESOLVED' if r[6] else 'OPEN'
            lines.append(
                f'[{status}] {r[0]}::{r[1]} (x{r[3]}) last={r[4]}\n'
                f'  msg: {r[2][:120]}\n'
                f'  fix: {r[5] or "none yet"}')
        return '\n\n'.join(lines)
    except Exception as e:
        return f'ERROR_LEARNING: {e}'


def error_summary() -> str:
    """One-line stats: total errors, unresolved, top error types."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM error_log')
        total = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM error_log WHERE resolved = 0')
        open_count = c.fetchone()[0]
        c.execute(
            '''SELECT error_type, COUNT(*) as cnt FROM error_log
               GROUP BY error_type ORDER BY cnt DESC LIMIT 5''')
        top_types = c.fetchall()
        conn.close()
        types_str = ', '.join(f'{t[0]}={t[1]}' for t in top_types)
        return f'TOTAL={total} OPEN={open_count} TOP=[{types_str}]'
    except Exception as e:
        return f'ERROR_LEARNING: {e}'


def prune_old(max_age_days: int = 30, max_resolved: int = 200) -> str:
    """Delete old resolved errors to keep the table tidy."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        cutoff = time.time() - (max_age_days * 86400)
        cutoff_str = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(cutoff))
        c.execute(
            '''DELETE FROM error_log
               WHERE resolved = 1 AND last_seen < ?''',
            (cutoff_str,))
        deleted = c.rowcount
        # Also cap total resolved entries
        c.execute(
            '''DELETE FROM error_log WHERE resolved = 1
               AND id NOT IN (
                 SELECT id FROM error_log WHERE resolved = 1
                 ORDER BY last_seen DESC LIMIT ?
               )''', (max_resolved,))
        deleted += c.rowcount
        conn.commit()
        conn.close()
        return f'PRUNED={deleted}'
    except Exception as e:
        return f'ERROR_LEARNING: {e}'


# Auto-init on import
_init_db()
