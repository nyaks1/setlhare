import sys
import os
import subprocess
import argparse
from setlhare.parser import StackTraceParser
from setlhare.indexer import CodebaseIndexer

MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "model/setlhare-qwen2.5-1.5b-q4_k_m.gguf"
)

LANGUAGE_MAP = {
    ".py": "PYTHON",
    ".java": "JAVA",
    ".js": "JAVASCRIPT",
    ".ts": "TYPESCRIPT",
    ".rs": "RUST",
    ".go": "GO",
    ".sh": "SHELL",
}

def detect_language(filepath: str) -> str:
    ext = os.path.splitext(filepath)[-1].lower()
    return LANGUAGE_MAP.get(ext, "UNKNOWN")

def call_llama(context: dict, model_path: str) -> str:
    prompt = f"""<|im_start|>system
You are Setlhare, an offline terminal pair programmer. Given a task/error and local codebase context, diagnose the issue, generate a unified Git diff patch, and explain the fix.<|im_end|>
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
    result = subprocess.run(
        [
            "llama-cli",
            "--model", model_path,
            "--threads", "4",
            "--ctx-size", "2048",
            "--temp", "0.1",
            "--prompt", prompt,
            "--n-predict", "512",
            "--no-conversation",
            "--single-turn"
        ],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def main():
    parser = argparse.ArgumentParser(
        description="Setlhare: Offline Terminal Pair Programmer & Repair Agent"
    )
    subparsers = parser.add_subparsers(dest="command")

    fix_parser = subparsers.add_parser(
        "fix",
        help="Run a command and capture/repair any stack trace errors"
    )
    fix_parser.add_argument(
        "run_cmd",
        type=str,
        help="Command to run (e.g., 'python3 script.py' or 'pytest')"
    )

    args = parser.parse_args()

    if args.command == "fix":
        print(f"[Setlhare] Intercepting execution: {args.run_cmd}")
        result = subprocess.run(
            args.run_cmd, shell=True, capture_output=True, text=True
        )

        if result.returncode == 0:
            print("[Setlhare] Execution completed successfully (no errors detected).")
            sys.exit(0)

        print("[Setlhare] Failure detected! Analyzing output...")
        output = result.stderr or result.stdout
        report = StackTraceParser.parse(output)

        if report and report.frames:
            last_frame = report.frames[-1]
            print(
                f"[Setlhare] Exception: {report.exception_type} "
                f"in {last_frame.filename}:{last_frame.line_number}"
            )

            ctx = CodebaseIndexer.get_context_around_line(
                last_frame.filename, last_frame.line_number
            )
            if ctx:
                language = detect_language(last_frame.filename)
                print("\n[Setlhare Engine] Generating patch via Qwen2.5-Coder...")

                response = call_llama(
                    {
                        "exception_type": report.exception_type,
                        "error_message": report.error_message,
                        "filepath": last_frame.filename,
                        "code_snippet": ctx["code_snippet"],
                        "language": language,
                    },
                    model_path=MODEL_PATH
                )
                print(response)
            else:
                print("[Setlhare] Could not extract file context.")
                print(f"[Setlhare] Error: {report.exception_type}: {report.error_message}")
        else:
            print("[Setlhare] Raw Error Output:")
            print(output[:500])

if __name__ == "__main__":
    main()