import ast
import os
from typing import Optional, Dict

class CodebaseIndexer:
    """Extracts local file context around stack trace line numbers."""

    @staticmethod
    def get_context_around_line(filepath: str, target_line: int, window: int = 15) -> Optional[Dict[str, str]]:
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        
        start = max(0, target_line - window - 1)
        end = min(len(lines), target_line + window)
        
        snippet = "".join([f"{i+1:4d} | {lines[i]}" for i in range(start, end)])
        
        # Try extracting enclosing function using AST
        enclosing_function = "Global Scope"
        try:
            tree = ast.parse("".join(lines))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.lineno <= target_line <= getattr(node, "end_lineno", target_line):
                        enclosing_function = node.name
                        break
        except Exception:
            pass

        return {
            "filepath": filepath,
            "target_line": str(target_line),
            "enclosing_function": enclosing_function,
            "code_snippet": snippet
        }