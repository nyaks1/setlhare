import re
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class StackTraceFrame:
    filename: str
    line_number: int
    function_name: str
    code_line: str

@dataclass
class ErrorReport:
    exception_type: str
    error_message: str
    frames: List[StackTraceFrame]
    raw_trace: str

class StackTraceParser:
    """Parses terminal stderr/stdout for Python and CLI tracebacks."""
    
    PYTHON_FRAME_REGEX = re.compile(
        r'File "(?P<filename>[^"]+)", line (?P<line>\d+), in (?P<function>\w+)\n\s*(?P<code>.+)'
    )
    PYTHON_EXC_REGEX = re.compile(r'^(?P<exc_type>[A-Za-z_]\w*Error|Exception):\s*(?P<message>.*)$', re.MULTILINE)

    @classmethod
    def parse(cls, output: str) -> Optional[ErrorReport]:
        frames = []
        for match in cls.PYTHON_FRAME_REGEX.finditer(output):
            frames.append(StackTraceFrame(
                filename=match.group("filename"),
                line_number=int(match.group("line")),
                function_name=match.group("function"),
                code_line=match.group("code").strip()
            ))
        
        exc_match = cls.PYTHON_EXC_REGEX.search(output)
        if not exc_match and not frames:
            return None

        exc_type = exc_match.group("exc_type") if exc_match else "RuntimeError"
        error_msg = exc_match.group("message") if exc_match else output.strip().splitlines()[-1]

        return ErrorReport(
            exception_type=exc_type,
            error_message=error_msg,
            frames=frames,
            raw_trace=output
        )