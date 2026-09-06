"""Tests for error_learning module."""
import os
import sqlite3
import tempfile
import time

# Point DB at a temp file before import
_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
os.environ.setdefault('ERROR_LEARNING_DB', _tmp.name)

import error_learning

# Override DB_FILE to use temp
error_learning.DB_FILE = _tmp.name
error_learning._init_db()


def test_record_and_retrieve():
    res = error_learning.record_error('test_source', 'Connection refused', context='unit test')
    assert res == 'RECORDED'
    patterns = error_learning.get_error_patterns(limit=5)
    assert 'test_source' in patterns
    assert 'network' in patterns  # classified correctly


def test_duplicate_increments():
    error_learning.record_error('dup_test', 'quota exceeded')
    error_learning.record_error('dup_test', 'quota exceeded')
    patterns = error_learning.get_error_patterns(limit=5)
    assert 'x2' in patterns


def test_classify_error():
    assert error_learning.classify_error('Connection refused') == 'network'
    assert error_learning.classify_error('429 rate limit') == 'quota'
    assert error_learning.classify_error('401 unauthorized') == 'auth'
    assert error_learning.classify_error('model not found') == 'model'
    assert error_learning.classify_error('timeout occurred') == 'timeout'
    assert error_learning.classify_error('something weird') == 'unknown'


def test_mark_resolved_and_hint():
    error_learning.record_error('hint_test', 'DNS failed')
    res = error_learning.mark_resolved('hint_test', 'DNS failed', 'Restart DNS service')
    assert res == 'RESOLVED'
    hint = error_learning.get_resolution_hint('hint_test', 'DNS failed')
    assert hint == 'Restart DNS service'


def test_resolution_hint_none_when_unresolved():
    hint = error_learning.get_resolution_hint('no_resolve', 'Some error')
    assert hint is None


def test_error_summary():
    error_learning.record_error('summary_test', 'generic error')
    summary = error_learning.error_summary()
    assert 'TOTAL=' in summary
    assert 'OPEN=' in summary


def test_prune_old():
    error_learning.record_error('prune_test', 'stale error')
    res = error_learning.prune_old(max_age_days=0, max_resolved=0)
    assert 'PRUNED=' in res


def test_unresolved_only_filter():
    error_learning.record_error('filter_test', 'open error here')
    error_learning.record_error('filter_test2', 'closed error here')
    error_learning.mark_resolved('filter_test2', 'closed error here', 'fixed')
    patterns = error_learning.get_error_patterns(limit=10, unresolved_only=True)
    assert 'open error here' in patterns
    assert 'closed error here' not in patterns
