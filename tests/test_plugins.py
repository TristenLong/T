"""Unit tests for the hot-loadable swarm plugin loader (no server needed)."""
import os

from swarm_plugin import plugin_loader as pl

GOOD = (
    'def echo_tool(text: str = "ping") -> str:\n'
    '    return "ECHO:" + str(text)\n\n\n'
    'def _self_check() -> str:\n'
    '    return "OK"\n'
)


def _configure(tmp_path):
    pl.configure(str(tmp_path))


def test_grow_valid_registers_and_persists(tmp_path):
    _configure(tmp_path)
    res = pl.grow("utilities", GOOD)
    assert res["ok"]
    assert res["tools"] == ["echo_tool"]
    assert os.path.isfile(os.path.join(str(tmp_path), "utilities.py"))
    assert pl.tool_function("echo_tool")("hi") == "ECHO:hi"


def test_grow_syntax_error_rejected_no_file(tmp_path):
    _configure(tmp_path)
    res = pl.grow("bad", "def echo_tool(text): return } broken")
    assert not res["ok"]
    assert "syntax error" in res["error"]
    assert not os.path.isfile(os.path.join(str(tmp_path), "bad.py"))


def test_grow_no_tools_rejected(tmp_path):
    _configure(tmp_path)
    res = pl.grow("bare", "ANSWER = 42")
    assert not res["ok"]
    assert "no *_tool functions" in res["error"]
    assert not os.path.isfile(os.path.join(str(tmp_path), "bare.py"))


def test_grow_failing_self_check_rejected(tmp_path):
    _configure(tmp_path)
    src = GOOD + 'def _self_check() -> str:\n    return "FAIL: nope"\n'
    res = pl.grow("broken", src)
    assert not res["ok"]
    assert "self_check" in res["error"]
    assert not os.path.isfile(os.path.join(str(tmp_path), "broken.py"))


def test_grow_invalid_name_rejected(tmp_path):
    _configure(tmp_path)
    res = pl.grow("not a name!", GOOD)
    assert not res["ok"]
    assert "invalid plugin name" in res["error"]


def test_grow_empty_source_rejected(tmp_path):
    _configure(tmp_path)
    res = pl.grow("weird", "   ")
    assert not res["ok"]


def test_grow_self_check_passing_is_accepted(tmp_path):
    _configure(tmp_path)
    src = (
        'def probe_tool() -> str:\n'
        '    return "ok"\n\n\n'
        'def _self_check() -> str:\n'
        '    try:\n'
        '        return "OK" if probe_tool() == "ok" else "FAIL: bad"\n'
        '    except Exception as e:\n'
        '        return f"FAIL: {e}"\n'
    )
    res = pl.grow("checked", src)
    assert res["ok"]
    assert res["tools"] == ["probe_tool"]


def test_grow_overwrite_previous_plugin(tmp_path):
    _configure(tmp_path)
    first = "def a_tool() -> str:\n    return 'a'\n"
    second = "def b_tool() -> str:\n    return 'b'\n"
    assert pl.grow("mod", first)["ok"]
    assert pl.tool_function("a_tool")() == "a"
    res = pl.grow("mod", second)
    assert res["ok"]
    assert res["tools"] == ["b_tool"]
    assert pl.tool_function("a_tool") is None
    assert pl.tool_function("b_tool")() == "b"


def test_remove_unregisters_and_deletes(tmp_path):
    _configure(tmp_path)
    pl.grow("utilities", GOOD)
    res = pl.remove("utilities")
    assert res["ok"]
    assert pl.tool_function("echo_tool") is None
    assert not os.path.isfile(os.path.join(str(tmp_path), "utilities.py"))


def test_invoke_filters_args_to_signature(tmp_path):
    _configure(tmp_path)
    src = (
        "def add_tool(a: int = 1, b: int = 2) -> str:\n"
        "    return str(int(a) + int(b))\n"
    )
    pl.grow("math", src)
    assert pl.invoke("add_tool", {"a": 4, "b": 5, "extra": "ignored"}) == "9"
    assert pl.invoke("add_tool", {}) == "3"
    assert pl.invoke("missing_tool") is None


def test_invoke_var_keyword_plugin(tmp_path):
    _configure(tmp_path)
    src = "def probe_tool(**kwargs) -> str:\n    return ','.join(sorted(kwargs))\n"
    pl.grow("probe", src)
    assert pl.invoke("probe_tool", {"x": 1, "y": 2}) == "x,y"


def test_list_plugins(tmp_path):
    _configure(tmp_path)
    pl.grow("one", GOOD)
    names = [p["name"] for p in pl.list_plugins()]
    assert names == ["one"]


def test_reload_all_skips_bad_files_and_init(tmp_path):
    _configure(tmp_path)
    init_path = os.path.join(str(tmp_path), "__init__.py")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write("# package marker")
    bad_path = os.path.join(str(tmp_path), "badmod.py")
    with open(bad_path, "w", encoding="utf-8") as f:
        f.write("def x_tool(:\n")  # syntax error
    good_path = os.path.join(str(tmp_path), "goodmod.py")
    with open(good_path, "w", encoding="utf-8") as f:
        f.write(GOOD)
    pl.reload_all()
    assert set(pl.loaded) == {"goodmod"}