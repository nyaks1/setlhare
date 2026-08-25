import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StackTraceFrame:
    filename: str
    line_number: int
    function_name: str
    code_line: str = ""


@dataclass
class ErrorReport:
    exception_type: str
    error_message: str
    frames: List[StackTraceFrame] = field(default_factory=list)
    raw_trace: str = ""


class StackTraceParser:
    """Parses terminal stderr/stdout for Python, Java, and JavaScript stack traces."""

    PYTHON_FRAME_REGEX = re.compile(
        r'File "(?P<filename>[^"]+)", line (?P<line>\d+), in (?P<function>[\w<>]+)'
        r'(?:\n\s*(?P<code>[^\n^~]+))?'
    )
    JAVA_FRAME_REGEX = re.compile(
        r'at (?P<function>[\w$.]+)\((?P<filename>[\w./$-]+\.java):(?P<line>\d+)\)'
    )
    JS_FRAME_REGEX = re.compile(
        r'at .+?\(?(?P<filename>[^\s()]+\.(?:js|jsx|ts|mjs|cjs)):(?P<line>\d+):\d+\)?'
    )

    EXC_PATTERNS = [
        (re.compile(r"^Exception in thread \"[^\"]*\" (?P<exc>[\w.$]+)\s*:\s*(?P<msg>.*)$", re.MULTILINE), "java"),
        (re.compile(r"^Caused by:\s*(?P<exc>[\w.$]+)\s*:\s*(?P<msg>.*)$", re.MULTILINE), "java-caused"),
        (re.compile(r"^Exception in thread \"[^\"]*\" (?P<exc>[\w.$]*(?:Error|Exception))\s*$", re.MULTILINE), "java-bare"),
        (re.compile(r"^(?P<exc>[A-Za-z_][\w.]*(?:Error|Exception|Interrupt)[\w.]*)\s*:\s*(?P<msg>.*)$", re.MULTILINE), "generic"),
        (re.compile(r"^(?P<exc>[\w$]*Error)\s*:?\s*(?P<msg>.*)$", re.MULTILINE), "node"),
    ]

    @classmethod
    def parse(cls, output: str) -> Optional[ErrorReport]:
        if not output or not output.strip():
            return None

        exc_type, error_msg = cls._extract_exception(output)

        frames = (
            cls._match_frames(cls.PYTHON_FRAME_REGEX, output)
            or cls._match_frames(cls.JAVA_FRAME_REGEX, output)
            or cls._match_frames(cls.JS_FRAME_REGEX, output)
        )

        if not exc_type and not frames:
            return None

        return ErrorReport(
            exception_type=exc_type or "UnknownError",
            error_message=error_msg or output.strip().splitlines()[-1],
            frames=frames,
            raw_trace=output,
        )

    @classmethod
    def _extract_exception(cls, output: str):
        for regex, kind in cls.EXC_PATTERNS:
            match = regex.search(output)
            if match:
                groups = match.groupdict()
                exc = (groups.get("exc") or "").split(".")[-1]
                msg = (groups.get("msg") or "").strip()
                return exc, msg
        return None, None

    @classmethod
    def _match_frames(cls, regex, output: str) -> List[StackTraceFrame]:
        frames = []
        for m in regex.finditer(output):
            groups = m.groupdict()
            code_line = (groups.get("code") or "").strip()
            frames.append(StackTraceFrame(
                filename=groups["filename"],
                line_number=int(groups["line"]),
                function_name=groups.get("function") or "",
                code_line=code_line,
            ))
        return frames
