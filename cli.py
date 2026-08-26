import argparse
import os
import shutil
import subprocess
import sys

from setlhare.parser import StackTraceParser
from setlhare.indexer import CodebaseIndexer

MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "model/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
)

LANGUAGE_MAP = {
    ".py": "PYTHON",
    ".java": "JAVA",
    ".js": "JAVASCRIPT",
    ".jsx": "JAVASCRIPT",
    ".ts": "TYPESCRIPT",
    ".rs": "RUST",
    ".go": "GO",
    ".sh": "SHELL",
    ".c": "C",
    ".cpp": "CPP",
    ".cs": "CSHARP",
}

SYSTEM_PROMPT = (
    "You are Setlhare, an offline terminal pair programmer. Given a task/error "
    "and local codebase context, diagnose the issue, generate a unified Git "
    "diff patch, and explain the fix."
)


def detect_language(filepath: str) -> str:
    ext = os.path.splitext(filepath)[-1].lower()
    return LANGUAGE_MAP.get(ext, "UNKNOWN")


def build_prompt(context: dict) -> str:
    return f"""<|im_start|>system
{SYSTEM_PROMPT}<|im_end|>
<|im_start|>user
### LANGUAGE:
{context['language']}

### ISSUE / TASK:
{context['exception_type']}: {context['error_message']}

### LOCAL CODE CONTEXT:
File: {context['filepath']}
{context['code_snippet']}<|im_end|>
<|im_start|>assistant
"""


def call_llama(context: dict, model_path: str, threads: int, ctx_size: int,
               n_predict: int, timeout: int) -> str:
    if shutil.which("llama-cli") is None:
        raise FileNotFoundError(
            "llama-cli not found on PATH. Install llama.cpp first: "
            "https://github.com/ggml-org/llama.cpp"
        )
    result = subprocess.run(
        [
            "llama-cli",
            "--model", model_path,
            "--threads", str(threads),
            "--ctx-size", str(ctx_size),
            "--temp", "0.1",
            "--prompt", build_prompt(context),
            "--n-predict", str(n_predict),
            "--no-conversation",
            "--single-turn",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def run_fix(run_cmd: str, args) -> int:
    print(f"[Setlhare] Intercepting execution: {run_cmd}")
    try:
        result = subprocess.run(
            run_cmd, shell=True, capture_output=True, text=True
        )
    except KeyboardInterrupt:
        print("\n[Setlhare] Interrupted.")
        return 130

    if result.returncode == 0:
        print("[Setlhare] Execution completed successfully (no errors detected).")
        return 0

    print("[Setlhare] Failure detected! Analyzing output...")
    output = result.stderr or result.stdout
    report = StackTraceParser.parse(output)

    if not report:
        print("[Setlhare] Could not recognize a stack trace. Raw Error Output:")
        print(output[:1000])
        return result.returncode

    if not report.frames:
        print(f"[Setlhare] Exception: {report.exception_type}: {report.error_message}")
        print("[Setlhare] No source frames found; cannot extract code context.")

    if report.frames:
        last_frame = report.frames[-1]
        print(
            f"[Setlhare] Exception: {report.exception_type} "
            f"in {last_frame.filename}:{last_frame.line_number}"
        )

    target = report.frames[-1] if report.frames else None
    ctx = None
    if target:
        ctx = CodebaseIndexer.get_context_around_line(
            target.filename, target.line_number
        )

    if not ctx:
        context = {
            "language": detect_language(target.filename) if target else "UNKNOWN",
            "exception_type": report.exception_type,
            "error_message": report.error_message,
            "filepath": getattr(target, "filename", "unknown"),
            "code_snippet": "(source file unavailable)",
        }
    else:
        context = {
            "language": detect_language(ctx["filepath"]),
            "exception_type": report.exception_type,
            "error_message": report.error_message,
            "filepath": ctx["filepath"],
            "code_snippet": ctx["code_snippet"],
        }

    model_path = args.model or MODEL_PATH
    if not os.path.exists(model_path):
        print(f"[Setlhare] Model not found at {model_path}.")
        print("[Setlhare] Run 'bash download_model.sh' first.")
        return 1

    print(f"\n[Setlhare Engine] Generating patch via llama.cpp ({args.threads} threads)...")
    try:
        response = call_llama(
            context,
            model_path=model_path,
            threads=args.threads,
            ctx_size=args.ctx_size,
            n_predict=args.n_predict,
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"[Setlhare] Inference timed out after {args.timeout}s.")
        return 1
    except FileNotFoundError as exc:
        print(f"[Setlhare] {exc}")
        return 1

    print(response)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="setlhare",
        description="Setlhare: Offline Terminal Pair Programmer & Repair Agent",
    )
    subparsers = parser.add_subparsers(dest="command")

    fix_parser = subparsers.add_parser(
        "fix",
        help="Run a command and capture/repair any stack trace errors",
    )
    fix_parser.add_argument(
        "run_cmd", type=str,
        help="Command to run (e.g., 'python3 script.py' or 'pytest')",
    )
    fix_parser.add_argument(
        "--model", type=str, default=None,
        help=f"Path to a .gguf model (default: {os.path.basename(MODEL_PATH)})",
    )
    fix_parser.add_argument(
        "--threads", type=int, default=4,
        help="CPU threads for inference (default: 4)",
    )
    fix_parser.add_argument(
        "--ctx-size", type=int, default=2048,
        help="Context window size (default: 2048)",
    )
    fix_parser.add_argument(
        "--n-predict", type=int, default=512,
        help="Max tokens to generate (default: 512)",
    )
    fix_parser.add_argument(
        "--timeout", type=int, default=600,
        help="Seconds to wait for inference before giving up (default: 600)",
    )

    hook_parser = subparsers.add_parser(
        "hook",
        help="Output shell hook code for automatic error detection",
    )
    hook_parser.add_argument(
        "--fish", action="store_true",
        help="Output fish shell hook instead of bash/zsh",
    )
    hook_parser.add_argument(
        "--powershell", action="store_true",
        help="Output PowerShell hook instead of bash/zsh",
    )
    hook_parser.add_argument(
        "--auto-apply", action="store_true",
        help="Set SETLHARE_AUTO_APPLY=1 in the hook (skip y/n prompt)",
    )
    hook_parser.add_argument(
        "--uninstall", action="store_true",
        help="Output commands to remove the hook from shell config",
    )

    hook_check_parser = subparsers.add_parser(
        "hook-check",
        help="Check stdin for stack traces (called by shell hook)",
    )
    hook_check_parser.add_argument(
        "--auto-apply", action="store_true",
        help="Apply patches without prompting",
    )
    hook_check_parser.add_argument(
        "--model", type=str, default=None,
        help=f"Path to a .gguf model (default: {os.path.basename(MODEL_PATH)})",
    )
    hook_check_parser.add_argument(
        "--threads", type=int, default=4,
        help="CPU threads for inference (default: 4)",
    )
    hook_check_parser.add_argument(
        "--ctx-size", type=int, default=2048,
        help="Context window size (default: 2048)",
    )
    hook_check_parser.add_argument(
        "--n-predict", type=int, default=512,
        help="Max tokens to generate (default: 512)",
    )
    hook_check_parser.add_argument(
        "--timeout", type=int, default=600,
        help="Seconds to wait for inference before giving up (default: 600)",
    )

    args = parser.parse_args()
    if args.command == "fix":
        return run_fix(args.run_cmd, args)

    if args.command == "hook":
        from setlhare.hook import output_hook
        shell = "powershell" if args.powershell else "fish" if args.fish else "bash"
        hook_code = output_hook(shell)
        if args.auto_apply:
            if shell == "powershell":
                hook_code += '\n$env:SETLHARE_AUTO_APPLY = "1"\n'
            else:
                hook_code += '\nexport SETLHARE_AUTO_APPLY=1\n'
        if args.uninstall:
            print("# To remove the Setlhare hook, delete these lines from your shell config:")
            print("#   eval \"$(setlhare hook)\"          # bash/zsh")
            print("#   setlhare hook --fish | source     # fish")
            print("#   setlhare hook --powershell | Invoke-Expression  # powershell")
            return 0
        print(hook_code, end='')
        return 0

    if args.command == "hook-check":
        from setlhare.hook import HookEngine
        stderr_text = sys.stdin.read()
        auto_apply = args.auto_apply or os.environ.get("SETLHARE_AUTO_APPLY") == "1"
        engine = HookEngine(
            model_path=args.model,
            threads=args.threads,
            ctx_size=args.ctx_size,
            n_predict=args.n_predict,
            timeout=args.timeout,
        )
        return engine.check(stderr_text, auto_apply=auto_apply)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
