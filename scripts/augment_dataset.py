"""Generates synthetic error-repair examples and merges them into the training set."""
import difflib
import json
import random

random.seed(42)

SYSTEM = (
    "You are Setlhare, an offline terminal pair programmer. "
    "Given a task/error and local codebase context, diagnose the issue, "
    "generate a unified Git diff patch, and explain the fix."
)

NAMES = ["items", "values", "records", "entries", "elements", "data", "results",
         "rows", "samples", "outputs", "buffer", "queue", "stack", "tokens"]
FNAMES = ["process", "compute", "analyze", "transform", "aggregate", "summarize",
          "validate", "collect", "merge", "resolve", "calculate", "extract"]
DKEYS = ["apple", "banana", "mango", "cherry", "grape", "peach", "plum", "kiwi"]


def pick(seq):
    return random.choice(seq)


# --- Generator functions: each returns (bug, fixed, err_msg, explanation) ---

def gen_indexerror():
    n = random.randint(2, 6)
    name = pick(NAMES)
    vals = [random.choice(["'a'", "'b'", "'x'", "1", "2", "True"]) for _ in range(n)]
    bad_idx = random.randint(n, n + 6)
    style = random.random()
    if style < 0.4:
        bug = f"{name} = [{', '.join(vals)}]\nprint({name}[{bad_idx}])"
        fixed = f"{name} = [{', '.join(vals)}]\nprint({name}[-1])"
        explain = (f"`{name}` has {n} elements with valid indices 0-{n-1}. "
                   f"Index {bad_idx} is out of range. Use `-1` for the last element "
                   f"or check `len({name})` first.")
        err = "IndexError: list index out of range"
    elif style < 0.7:
        fn = pick(FNAMES)
        bug = (f"def {fn}({name}):\n"
               f"    out = []\n"
               f"    for i in range(len({name}) + 1):\n"
               f"        out.append({name}[i])\n"
               f"    return out")
        fixed = (f"def {fn}({name}):\n"
                 f"    out = []\n"
                 f"    for i in range(len({name})):\n"
                 f"        out.append({name}[i])\n"
                 f"    return out")
        explain = ("Off-by-one error: `range(len(" + name + ") + 1)` produces one index "
                   "past the end of the list. Use `range(len(" + name + "))`.")
        err = "IndexError: list index out of range"
    else:
        fn = pick(FNAMES)
        bug = (f"def {fn}({name}, idx):\n"
               f"    return {name}[idx]")
        fixed = (f"def {fn}({name}, idx):\n"
                 f"    if not 0 <= idx < len({name}):\n"
                 f"        raise IndexError(f'index {{idx}} out of range for {{len({name})}} items')\n"
                 f"    return {name}[idx]")
        explain = (f"No bounds validation on `idx`. Guard with `0 <= idx < len({name})` "
                   "and raise a descriptive error before indexing.")
        err = "IndexError: list index out of range"
    return bug, fixed, err, explain


def gen_nameerror():
    real, wrong = random.sample(NAMES, 2)
    fn = pick(FNAMES)
    k = random.randint(2, 5)
    vals = [str(random.randint(1, 99)) for _ in range(k)]
    variant = random.random()
    if variant < 0.5:
        bug = f"def {fn}({real}):\n    total = sum({real})\n    return total / len({wrong})"
        fixed = f"def {fn}({real}):\n    total = sum({real})\n    return total / len({real})"
        explain = f"`{wrong}` is not defined anywhere in scope; the parameter is `{real}`. Use `len({real})`."
        err = f"NameError: name '{wrong}' is not defined"
    else:
        bug = f"def {fn}():\n    {real} = [{', '.join(vals)}]\n    return {wrong}\n\nprint({fn}())"
        fixed = f"def {fn}():\n    {real} = [{', '.join(vals)}]\n    return {real}\n\nprint({fn}())"
        explain = (f"`{wrong}` was never assigned; the local variable is `{real}`. "
                   f"Return `{real}` instead.")
        err = f"NameError: name '{wrong}' is not defined"
    return bug, fixed, err, explain


def gen_typeerror():
    name = pick(NAMES)
    init = random.choice(["''", "'0'", '""'])
    fn = pick(FNAMES)
    upper = random.randint(3, 20)
    bug = f"total = {init}\nfor n in range({upper}):\n    total += n\nprint(total)"
    fixed = f"total = 0\nfor n in range({upper}):\n    total += n\nprint(total)"
    explain = (f"`total` was initialised as a string ({init}), so `+=` with an int raises a "
               f"TypeError. Initialise it as the integer `0`.")
    err = 'TypeError: can only concatenate str (not "int") to str'
    # second family: None + int
    if random.random() < 0.5:
        bug = f"count = None\ncount += 1"
        fixed = f"count = 0\ncount += 1"
        explain = "`count` is None; you cannot add an integer to None. Initialise it as `0`."
        err = "TypeError: unsupported operand type(s) for +=: 'NoneType' and 'int'"
    return bug, fixed, err, explain


def gen_keyerror():
    key_present, key_missing = random.sample(DKEYS, 2)
    price_a = random.randint(1, 50)
    price_b = random.randint(1, 50)
    name = pick(NAMES)
    variant = random.random()
    if variant < 0.5:
        bug = f"{name} = {{'{key_present}': {price_a}, '{key_missing}': {price_b}}}\nprint({name}['orange'])"
        fixed = f"{name} = {{'{key_present}': {price_a}, '{key_missing}': {price_b}}}\nprint({name}.get('orange', 0))"
        explain = ("Key 'orange' does not exist in the dict. Use `.get()` with a default "
                   "value, or check membership with `in` first.")
    else:
        fn = pick(FNAMES)
        bug = (f"def {fn}({name}, key):\n"
               f"    return {name}[key]")
        fixed = (f"def {fn}({name}, key):\n"
                 f"    return {name}.get(key)")
        explain = f"Direct `{name}[key]` access raises KeyError when the key is absent. Use `{name}.get(key)` to return None (or a default) instead."
    err = f"KeyError: 'orange'"
    return bug, fixed, err, explain


def gen_zerodiv():
    fn = pick(FNAMES)
    a, b = random.randint(2, 100), random.choice([0])
    variant = random.random()
    if variant < 0.5:
        bug = f"def divide(a, b):\n    return a / b\n\nprint(divide({a}, 0))"
        fixed = ("def divide(a, b):\n"
                 "    if b == 0:\n"
                 "        raise ValueError('denominator must be non-zero')\n"
                 "    return a / b\n\n"
                 f"print(divide({a}, 0))")
        explain = "Division by zero raises ZeroDivisionError. Validate the denominator first and raise an informative ValueError."
    else:
        bug = f"def {fn}(nums):\n    return sum(nums) / len(nums)\n\nprint({fn}([]))"
        fixed = (f"def {fn}(nums):\n"
                 "    if not nums:\n"
                 "        return 0\n"
                 "    return sum(nums) / len(nums)\n\n"
                 f"print({fn}([]))")
        explain = f"`{fn}([])` divides by `len([]) == 0`. Handle the empty-input case explicitly before dividing."
    err = "ZeroDivisionError: division by zero"
    return bug, fixed, err, explain


def gen_attrnone():
    method = random.choice(["strip", "lower", "upper", "split", "replace"])
    var = pick(NAMES)
    variant = random.random()
    if variant < 0.5:
        bug = f"{var} = None\nprint({var}.{method}())"
        fixed = f"{var} = None\nprint(({var} or '').{method}())"
        explain = (f"`{var}` is None; string methods cannot be called on it. Coalesce to an "
                   f"empty string with `({var} or '')`, or handle the None case explicitly.")
    else:
        fn = pick(FNAMES)
        bug = (f"def {fn}({var}):\n"
               f"    return {var}.{method}()\n\n"
               f"result = {fn}(None)")
        fixed = (f"def {fn}({var}):\n"
                 f"    if {var} is None:\n"
                 f"        return ''\n"
                 f"    return {var}.{method}()\n\n"
                 f"result = {fn}(None)")
        explain = f"`{fn}` receives None and calls `.{method}()` on it. Add an explicit `is None` guard returning a sensible default."
    err = f"AttributeError: 'NoneType' object has no attribute '{method}'"
    return bug, fixed, err, explain


def gen_unboundlocal():
    var = pick(NAMES)
    fn = pick(FNAMES)
    threshold = random.randint(5, 50)
    variant = random.random()
    if variant < 0.5:
        bug = (f"count = 0\n\n"
               f"def {fn}(nums):\n"
               f"    for n in nums:\n"
               f"        if n > {threshold}:\n"
               f"            count += 1\n"
               f"    return count")
        fixed = (f"count = 0\n\n"
                 f"def {fn}(nums):\n"
                 f"    total = 0\n"
                 f"    for n in nums:\n"
                 f"        if n > {threshold}:\n"
                 f"            total += 1\n"
                 f"    return total")
        explain = (f"Assigning to `count` inside `{fn}` makes it local, but it is read before "
                   "assignment -> UnboundLocalError. Use a local counter instead of the global.")
    else:
        bug = (f"def {fn}(flag):\n"
               f"    if flag:\n"
               f"        msg = 'ok'\n"
               f"    return msg")
        fixed = (f"def {fn}(flag):\n"
                 f"    msg = 'missing'\n"
                 f"    if flag:\n"
                 f"        msg = 'ok'\n"
                 f"    return msg")
        explain = ("`msg` is only assigned inside the `if` branch, so it is unbound when the "
                   "condition is false. Assign a default value before the branch.")
    err = "UnboundLocalError: local variable referenced before assignment"
    return bug, fixed, err, explain


GENERATORS = [gen_indexerror, gen_nameerror, gen_typeerror, gen_keyerror,
              gen_zerodiv, gen_attrnone, gen_unboundlocal]


def build_sample(bug_code, fixed_code, err_msg, explanation):
    diff = "".join(difflib.unified_diff(
        bug_code.splitlines(keepends=True),
        fixed_code.splitlines(keepends=True),
        fromfile="a/script.py", tofile="b/script.py",
    ))
    user = (
        "### LANGUAGE:\nPYTHON\n\n"
        f"### ISSUE / TASK:\n{err_msg}\n\n"
        "### LOCAL CODE CONTEXT:\nFile: script.py\n"
        + bug_code
    )
    assistant = (
        "### ROOT CAUSE DIAGNOSIS:\n"
        f"{explanation}\n\n"
        "### GIT DIFF PATCH:\n```diff\n"
        f"{diff}"
        "```\n\n"
        "### EXPLANATION:\n"
        f"{explanation}"
    )
    return {"messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def main(existing_path="data/setlhare_train.jsonl", output_path=None,
         synthetic=1500, max_attempts=50000):
    output_path = output_path or existing_path
    samples, seen = [], set()
    try:
        with open(existing_path) as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    samples.append(entry)
                    seen.add(entry["messages"][1]["content"])
    except FileNotFoundError:
        print(f"[Setlhare] No existing dataset at {existing_path}, starting fresh.")

    existing_count = len(samples)
    added, attempts = 0, 0
    while added < synthetic and attempts < max_attempts:
        attempts += 1
        gen = GENERATORS[attempts % len(GENERATORS)]
        bug, fixed, err, explain = gen()
        s = build_sample(bug, fixed, err, explain)
        key = s["messages"][1]["content"]
        if key in seen or not s["messages"][2]["content"].count("-"):
            continue
        samples.append(s)
        seen.add(key)
        added += 1

    random.shuffle(samples)
    with open(output_path, "w") as f:
        for s in samples:
            f.write(json.dumps(s) + "\n")
    print(f"[Setlhare] Added {added} unique synthetic error-repair samples "
          f"({attempts} attempts).")
    print(f"[Setlhare] Dataset: {existing_count} original + {added} synthetic "
          f"= {len(samples)} -> {output_path}")


if __name__ == "__main__":
    main()
