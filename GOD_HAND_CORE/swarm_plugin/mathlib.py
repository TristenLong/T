def fib_tool(n: str = "8") -> str:
    """Return the nth Fibonacci number as text (real math, no deps)."""
    try:
        count = int(n)
    except ValueError:
        count = 8
    count = max(0, min(count, 100))
    a, b = 0, 1
    for _ in range(count):
        a, b = b, a + b
    return str(a)


def _self_check() -> str:
    try:
        return "OK" if fib_tool("6") == "8" else "FAIL: fib wrong"
    except Exception as e:
        return f"FAIL: {e}"