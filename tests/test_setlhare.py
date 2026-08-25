import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from setlhare.parser import StackTraceParser
from setlhare.indexer import CodebaseIndexer
from cli import detect_language, build_prompt

PYTHON_TRACE = """Traceback (most recent call last):
  File "app.py", line 5, in average
    return total / len(items)
NameError: name 'items' is not defined"""

JAVA_TRACE = """Exception in thread "main" java.lang.NullPointerException
	at com.example.App.main(App.java:12)"""

JAVA_WITH_MSG = """Exception in thread "main" java.lang.ArithmeticException: / by zero
	at com.example.Calc.divide(Calc.java:8)"""

NODE_TRACE = """TypeError: Cannot read properties of undefined (reading 'name')
    at Object.<anonymous> (/home/user/app/server.js:10:15)
    at Module._compile (node:internal/modules/cjs/loader:1105:14)"""


class TestParser(unittest.TestCase):
    def test_python_trace(self):
        r = StackTraceParser.parse(PYTHON_TRACE)
        self.assertEqual(r.exception_type, "NameError")
        self.assertEqual(r.frames[-1].filename, "app.py")
        self.assertEqual(r.frames[-1].line_number, 5)

    def test_java_bare_npe(self):
        r = StackTraceParser.parse(JAVA_TRACE)
        self.assertEqual(r.exception_type, "NullPointerException")
        self.assertEqual(r.frames[-1].filename, "App.java")
        self.assertEqual(r.frames[-1].line_number, 12)

    def test_java_with_message(self):
        r = StackTraceParser.parse(JAVA_WITH_MSG)
        self.assertEqual(r.exception_type, "ArithmeticException")
        self.assertEqual(r.error_message, "/ by zero")

    def test_node_trace(self):
        r = StackTraceParser.parse(NODE_TRACE)
        self.assertEqual(r.exception_type, "TypeError")
        self.assertTrue(r.frames[-1].filename.endswith("server.js"))
        self.assertEqual(r.frames[-1].line_number, 10)

    def test_empty_returns_none(self):
        self.assertIsNone(StackTraceParser.parse(""))
        self.assertIsNone(StackTraceParser.parse("\n  \n"))

    def test_garbage_returns_none(self):
        self.assertIsNone(StackTraceParser.parse("hello world, all fine"))


class TestIndexer(unittest.TestCase):
    def test_context_extraction(self):
        path = os.path.join(os.path.dirname(__file__), "sample_for_indexer.py")
        ctx = CodebaseIndexer.get_context_around_line(path, 4)
        self.assertIsNotNone(ctx)
        self.assertIn("def average", ctx["code_snippet"])
        self.assertEqual(ctx["enclosing_function"], "average")

    def test_missing_file(self):
        self.assertIsNone(CodebaseIndexer.get_context_around_line("/no/such/file.py", 1))


class TestCliHelpers(unittest.TestCase):
    def test_detect_language(self):
        self.assertEqual(detect_language("a/b/main.py"), "PYTHON")
        self.assertEqual(detect_language("App.java"), "JAVA")
        self.assertEqual(detect_language("server.ts"), "TYPESCRIPT")
        self.assertEqual(detect_language("notes.txt"), "UNKNOWN")

    def test_build_prompt_contains_sections(self):
        p = build_prompt({
            "language": "PYTHON",
            "exception_type": "NameError",
            "error_message": "x not defined",
            "filepath": "app.py",
            "code_snippet": "x = 1",
        })
        for section in ("LANGUAGE", "ISSUE / TASK", "LOCAL CODE CONTEXT", "assistant"):
            self.assertIn(section, p)


if __name__ == "__main__":
    unittest.main()
