import sys
import subprocess
import argparse
from setlhare.parser import StackTraceParser
from setlhare.indexer import CodebaseIndexer

def main():
    parser = argparse.ArgumentParser(description="Setlhare: Offline Terminal Pair Programmer & Repair Agent")
    subparsers = parser.add_subparsers(dest="command")

    # `setlhare fix "<cmd>"`
    fix_parser = subparsers.add_parser("fix", help="Run a command and capture/repair any stack trace errors")
    fix_parser.add_argument("run_cmd", type=str, help="Command to run (e.g., 'python3 script.py' or 'pytest')")

    args = parser.parse_args()

    if args.command == "fix":
        print(f"[Setlhare] Intercepting execution: {args.run_cmd}")
        result = subprocess.run(args.run_cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            print("[Setlhare] Execution completed successfully (no errors detected).")
            sys.exit(0)

        print("[Setlhare] Failure detected! Analyzing output...")
        output = result.stderr or result.stdout
        report = StackTraceParser.parse(output)

        if report and report.frames:
            last_frame = report.frames[-1]
            print(f"[Setlhare] Exception: {report.exception_type} in {last_frame.filename}:{last_frame.line_number}")
            
            ctx = CodebaseIndexer.get_context_around_line(last_frame.filename, last_frame.line_number)
            if ctx:
                print(f"[Setlhare] Context extracted around line {last_frame.line_number}:")
                print(ctx["code_snippet"])
                print("\n[Setlhare Engine] Generating patch via Qwen2.5-Coder...")
                # llama.cpp inference call will be plugged in here
        else:
            print("[Setlhare] Raw Error Output:")
            print(output[:500])

if __name__ == "__main__":
    main()