import asyncio
import os
import subprocess
import sys
import tempfile

from google import genai
from loguru import logger
from openai import OpenAI

# Ensure we can import from GOD_HAND_CORE
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'GOD_HAND_CORE')))
from sandbox_core import sandbox_core


class CoderCore:
    def __init__(self, memory_db=None, api_key=None):
        self.memory_db = memory_db
        self.openai_key = api_key or os.getenv("OPENAI_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.primary_model = os.getenv("JESTER_PRIMARY_LLM", "gemini-3.1-pro")
        self.openai_model = os.getenv("JESTER_OPENAI_MODEL", "gpt-4o")
        
        self.gemini_client = None
        self.openai_client = None
        if self.gemini_key:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_key)
            except Exception as e:
                logger.warning(f"[CoderCore] Gemini init failed: {e}")
                
        if self.openai_key:
            try:
                self.openai_client = OpenAI(api_key=self.openai_key)
            except Exception as e:
                logger.warning(f"[CoderCore] OpenAI init failed: {e}")

    async def generate_solution(self, prompt: str) -> str:
        sys_prompt = (
            "You are the ARCHITECT sub-agent of JESTER V2000 Singularity Swarm. "
            "You are an expert autonomous software engineer. "
            "Generate production-grade, bug-free, clean code with clear explanations and inline comments."
        )
        # Try OpenAI (GPT-4o) first for coding precision, fallback to Gemini 3.7
        if self.openai_client:
            try:
                resp = self.openai_client.chat.completions.create(
                    model=self.openai_model,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt}
                    ]
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                logger.warning(f"[CoderCore] OpenAI failed ({e}), falling back to Gemini.")

        if self.gemini_client:
            try:
                resp = self.gemini_client.models.generate_content(
                    model=self.primary_model,
                    contents=[sys_prompt, prompt] # type: ignore
                )
                return resp.text or ""
            except Exception as e:
                logger.error(f"[CoderCore] Gemini failed: {e}")
                return f"[CODER_ERROR: {str(e)}]"
                
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

    async def run_coding_task(self, prompt: str, execute: bool = False) -> str:
        logger.info(f"[CoderCore] Executing coding task: {prompt}")
        solution = await self.generate_solution(prompt)
        
        # Save to memory if available
        if self.memory_db and hasattr(self.memory_db, "save"):
            try:
                self.memory_db.save(f"[Architect Task] {prompt[:80]} -> Solved", importance=2)
            except Exception as e:
                logger.warning(f"[CoderCore] Memory save error: {e}")
                
        if execute:
            logger.info("[CoderCore] Executing solution in sandbox...")
            # Very primitive extraction of python code from markdown if needed
            code_to_run = solution
            if "```python" in solution:
                code_to_run = solution.split("```python")[1].split("```")[0].strip()
            
            result = sandbox_core.execute_python_code(code_to_run)
            return f"Code Generated:\n{solution}\n\nExecution Result:\n{result}"
            
        return solution

if __name__ == "__main__":
    core = CoderCore()
    res = asyncio.run(core.run_coding_task("Write a python function to compute prime numbers."))
    print(res)
