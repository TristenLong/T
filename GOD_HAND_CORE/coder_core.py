import asyncio
import os
import subprocess
import sys
import tempfile

from loguru import logger

# Ensure we can import from GOD_HAND_CORE
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'GOD_HAND_CORE')))
from sandbox_core import sandbox_core


class CoderCore:
    def __init__(self, memory_db=None, api_key=None):
        self.memory_db = memory_db

    async def generate_solution(self, prompt: str) -> str:
        import llm_router
        sys_prompt = (
            "You are the ARCHITECT sub-agent of JESTER V2000 Singularity Swarm. "
            "You are an expert autonomous software engineer. "
            "Generate production-grade, bug-free, clean code with clear explanations and inline comments."
        )
        try:
            text, _model = llm_router.generate_completion_with_model([
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ])
            if text and text.strip():
                return text
        except Exception as e:
            logger.warning(f"[CoderCore] Router failed ({e}).")
        return "[CODER_ERROR: No LLM Client available]"

    def validate_python_syntax(self, code_snippet: str) -> tuple[bool, str]:
        """Extracts and validates python code syntax."""
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as temp:
                temp.write(code_snippet)
                temp_path = temp.name
                
            res = subprocess.run([sys.executable, "-m", "py_compile", temp_path], capture_output=True, text=True)
            os.remove(temp_path)
            if res.returncode == 0:
                return True, "SYNTAX_VALID"
            return False, res.stderr
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _extract_code(solution: str) -> str:
        """Pull the first fenced python block out of a solution if present."""
        if "```python" in solution:
            try:
                return solution.split("```python")[1].split("```")[0].strip()
            except Exception:
                pass
        if "```" in solution:
            try:
                return solution.split("```")[1].split("```")[0].strip()
            except Exception:
                pass
        return solution.strip()

    async def run_coding_task(self, prompt: str, path: str = "", execute: bool = False) -> str:
        """Handle a coding request: build new code or fix an existing file.

        `path` (optional) is a target file. When given, its current content is
        read and handed to the model as context, and the regenerated code is
        written back. Python output is syntax-checked; with `execute=True` the
        generated code also runs in the sandbox so the result includes proof.
        """
        logger.info(f"[CoderCore] Executing coding task: {prompt}")
        context = ""
        original_content = ""
        if path:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    original_content = handle.read()
                context = "\n\nExisting file content of {path} (fix/replace it, keep it working):\n----\n{prefix}\n----".format(
                    path=path, prefix=original_content[:8000]
                )
            except Exception as e:
                context = "\n\n(NOTE: could not read {path}: {e})".format(path=path, e=e)

        solution = await self.generate_solution(prompt + context)

        # Save to memory if available
        if self.memory_db and hasattr(self.memory_db, "save"):
            try:
                self.memory_db.save(f"[Architect Task] {prompt[:80]} -> Solved", importance=2)
            except Exception as e:
                logger.warning(f"[CoderCore] Memory save error: {e}")

        code_to_run = self._extract_code(solution)
        report = ["Task: {prompt}".format(prompt=prompt), "\nGenerated code:\n" + solution]

        if path:
            try:
                if not code_to_run and original_content:
                    code_to_run = original_content
                with open(path, "w", encoding="utf-8", newline="") as handle:
                    handle.write(code_to_run)
                report.append("\n[WRITTEN] Updated " + str(path))
            except Exception as e:
                report.append("\n[WRITE_FAILED] {path}: {e}".format(path=path, e=e))

        looks_like_code = code_to_run and (
            path
            or execute
            or code_to_run.lstrip().startswith(("import ", "from ", "def ", "class ", "#", "print("))
        )
        if looks_like_code:
            valid, detail = self.validate_python_syntax(code_to_run)
            if valid:
                report.append("\n[SYNTAX] VALID")
            else:
                report.append("\n[SYNTAX] INVALID\n" + detail)
            if execute and valid:
                result = sandbox_core.execute_python_code(code_to_run)
                if isinstance(result, dict):
                    result = str(result.get('output') or result.get('message') or result)
                report.append("\n[EXECUTED]\n" + result)

        return "".join(report)

if __name__ == "__main__":
    core = CoderCore()
    res = asyncio.run(core.run_coding_task("Write a python function to compute prime numbers."))
    print(res)
