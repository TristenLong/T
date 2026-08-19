import sys
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr

class PythonInterpreter:
    def __init__(self):
        self.globals = {}
        self.locals = {}

    def execute(self, code):
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            try:
                try:
                    compiled = compile(code, "<string>", "eval")
                    result = eval(compiled, self.globals, self.locals)
                    if result is not None:
                        print(repr(result))
                except SyntaxError:
                    exec(code, self.globals, self.locals)
            except Exception:
                traceback.print_exc()

        return {
            "output": stdout_capture.getvalue(),
            "error": stderr_capture.getvalue()
        }

interpreter = PythonInterpreter()

def run(code):
    return interpreter.execute(code)
