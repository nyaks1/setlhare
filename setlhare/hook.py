import os
import re
import subprocess
import sys
import tempfile
from typing import Optional

from setlhare.parser import StackTraceParser
from setlhare.indexer import CodebaseIndexer

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
import cli


def _extract_diff(llm_output: str) -> Optional[str]:
    """Extract unified diff from LLM output (```diff ... ``` blocks)."""
    pattern = r'```diff\s*\n(.*?)```'
    matches = re.findall(pattern, llm_output, re.DOTALL)
    if matches:
        return matches[0].strip()
    if '--- a/' in llm_output and '+++ b/' in llm_output:
        lines = llm_output.splitlines()
        diff_lines = []
        capturing = False
        for line in lines:
            if line.startswith('--- a/') or line.startswith('--- '):
                capturing = True
            if capturing:
                diff_lines.append(line)
            if capturing and (line.startswith('@@') or line.startswith('@@ ')):
                continue
        if diff_lines:
            return '\n'.join(diff_lines)
    return None


def _apply_patch(diff_text: str) -> tuple[bool, str]:
    """Try to apply a unified diff. Returns (success, message)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as f:
        f.write(diff_text)
        f.flush()
        diff_path = f.name

    try:
        result = subprocess.run(
            ['git', 'apply', '--check', diff_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            apply_result = subprocess.run(
                ['git', 'apply', diff_path],
                capture_output=True, text=True, timeout=10,
            )
            if apply_result.returncode == 0:
                return True, "Patch applied successfully."
            else:
                return False, f"git apply failed: {apply_result.stderr.strip()}"
        else:
            return False, f"Patch does not apply cleanly: {result.stderr.strip()}"
    except FileNotFoundError:
        return False, "git not found — cannot apply patch automatically."
    except subprocess.TimeoutExpired:
        return False, "git apply timed out."
    finally:
        os.unlink(diff_path)


class HookEngine:
    """Detects stack traces in stderr and offers fixes."""

    def __init__(self, model_path: str = None, threads: int = 4,
                 ctx_size: int = 2048, n_predict: int = 512, timeout: int = 600):
        self.model_path = model_path or cli.MODEL_PATH
        self.threads = threads
        self.ctx_size = ctx_size
        self.n_predict = n_predict
        self.timeout = timeout

    def check(self, stderr_text: str, auto_apply: bool = False) -> int:
        """Check stderr for a stack trace. Returns 0 if handled, 1 if fallback."""
        if not stderr_text or not stderr_text.strip():
            return 0

        report = StackTraceParser.parse(stderr_text)

        if not report:
            print(stderr_text, end='')
            return 1

        if not report.frames:
            print(f"\n[Setlhare] {report.exception_type}: {report.error_message}")
            print("[Setlhare] No source location found in stack trace.")
            return 1

        last_frame = report.frames[-1]
        print(
            f"\n[Setlhare] Detected: {report.exception_type} "
            f"in {last_frame.filename}:{last_frame.line_number}"
        )

        ctx = CodebaseIndexer.get_context_around_line(
            last_frame.filename, last_frame.line_number
        )

        if ctx:
            context = {
                "language": cli.detect_language(ctx["filepath"]),
                "exception_type": report.exception_type,
                "error_message": report.error_message,
                "filepath": ctx["filepath"],
                "code_snippet": ctx["code_snippet"],
            }
        else:
            context = {
                "language": cli.detect_language(last_frame.filename),
                "exception_type": report.exception_type,
                "error_message": report.error_message,
                "filepath": last_frame.filename,
                "code_snippet": "(source file unavailable)",
            }

        if not os.path.exists(self.model_path):
            print("[Setlhare] Model not found. Run 'bash download_model.sh' first.")
            return 1

        print(f"[Setlhare] Generating fix via llama.cpp ({self.threads} threads)...")
        try:
            response = cli.call_llama(
                context,
                model_path=self.model_path,
                threads=self.threads,
                ctx_size=self.ctx_size,
                n_predict=self.n_predict,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            print(f"[Setlhare] {exc}")
            return 1
        except subprocess.TimeoutExpired:
            print(f"[Setlhare] Inference timed out after {self.timeout}s.")
            return 1

        print(f"\n{response}\n")

        diff = _extract_diff(response)
        if not diff:
            return 0

        if auto_apply:
            success, msg = _apply_patch(diff)
            print(f"[Setlhare] {msg}")
            return 0

        try:
            answer = input("[Setlhare] Apply patch? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if answer == 'y':
            success, msg = _apply_patch(diff)
            print(f"[Setlhare] {msg}")
        else:
            print("[Setlhare] Patch not applied.")

        return 0


BASH_HOOK = """\
# Setlhare hook — auto-detects stack traces and offers fixes
# Add to ~/.bashrc: eval "$(setlhare hook)"
__setlhare_stderr=$(mktemp)
__setlhare_preexec() {
    exec 9>&2
    exec 2>"$__setlhare_stderr"
}
__setlhare_postcmd() {
    exec 2>&9 9>&-
    if [ -s "$__setlhare_stderr" ]; then
        trap - DEBUG
        setlhare hook-check <"$__setlhare_stderr" 2>/dev/null
        trap '__setlhare_preexec' DEBUG
        : >"$__setlhare_stderr"
    fi
}
trap '__setlhare_preexec' DEBUG
PROMPT_COMMAND="__setlhare_postcmd;${PROMPT_COMMAND}"
"""

ZSH_HOOK = """\
# Setlhare hook — auto-detects stack traces and offers fixes
# Add to ~/.zshrc: eval "$(setlhare hook)"
__setlhare_stderr=$(mktemp)
__setlhare_preexec() {
    exec 9>&2
    exec 2>"$__setlhare_stderr"
}
__setlhare_postcmd() {
    exec 2>&9 9>&-
    if [ -s "$__setlhare_stderr" ]; then
        setlhare hook-check <"$__setlhare_stderr" 2>/dev/null
        : >"$__setlhare_stderr"
    fi
}
autoload -Uz add-zsh-hook
add-zsh-hook preexec __setlhare_preexec
add-zsh-hook precmd __setlhare_postcmd
"""

FISH_HOOK = """\
# Setlhare hook — auto-detects stack traces and offers fixes
# Add to ~/.config/fish/config.fish: setlhare hook --fish | source
function __setlhare_hook --on-event fish_posterror
    setlhare hook-check 2>/dev/null
end
"""

POWERSHELL_HOOK = """\
# Setlhare hook — auto-detects stack traces and offers fixes
# Add to $PROFILE: setlhare hook --powershell | Invoke-Expression
$__setlhare_stderr = [System.IO.Path]::GetTempFileName()
$__setlhare_original_prompt = $function:Prompt

function Prompt {
    if (Test-Path $__setlhare_stderr) {
        $__content = Get-Content $__setlhare_stderr -Raw -ErrorAction SilentlyContinue
        if ($__content) {
            setlhare hook-check $__content 2>$null
            Set-Content $__setlhare_stderr ""
        }
    }
    & $__setlhare_original_prompt
}
"""


def output_hook(shell: str = "bash") -> str:
    """Return shell code for the hook."""
    hooks = {
        "bash": BASH_HOOK,
        "zsh": ZSH_HOOK,
        "fish": FISH_HOOK,
        "powershell": POWERSHELL_HOOK,
    }
    return hooks.get(shell, BASH_HOOK)
