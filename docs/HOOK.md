# Shell Hook Setup

Setlhare can sit in your terminal and automatically detect stack traces when any command fails. No wrapping needed — just run commands normally.

---

## Quick start

```bash
# Bash — add to ~/.bashrc
eval "$(setlhare hook)"

# Zsh — add to ~/.zshrc
eval "$(setlhare hook)"

# Fish — add to ~/.config/fish/config.fish
setlhare hook --fish | source

# PowerShell — add to $PROFILE
setlhare hook --powershell | Invoke-Expression
```

After adding the line, restart your shell or run `source ~/.bashrc` (or equivalent).

---

## How it works

1. **Before each command**, Setlhare silently captures stderr to a temp file
2. **After each command**, if stderr has content, Setlhare checks it for a real stack trace
3. **If a stack trace is found** → shows a diagnosis and fix, prompts you to apply
4. **If no stack trace** → shows the raw stderr (fallback for unrecognized errors)
5. **If auto-apply is set** → applies the patch without prompting

The detection uses a real parser — it checks for Python tracebacks, Java exceptions, and JavaScript errors. Exit codes are not used for detection, so `grep` returning 1 (no match) doesn't trigger Setlhare.

---

## Bash setup

Add to `~/.bashrc`:

```bash
eval "$(setlhare hook)"
```

How it works:
- A `DEBUG` trap fires before each command → redirects stderr to a temp file
- `PROMPT_COMMAND` fires after each command → checks the temp file
- If the temp file has content → `hook-check` runs the parser
- The DEBUG trap is disabled during `hook-check` to prevent recursion

**Troubleshooting:**

If you already have a `DEBUG` trap or `PROMPT_COMMAND`, the hook will append to them. If there are conflicts, you can manually merge the hook code.

---

## Zsh setup

Add to `~/.zshrc`:

```bash
eval "$(setlhare hook)"
```

Uses `preexec` and `precmd` hooks via `add-zsh-hook`. More reliable than bash for per-command detection.

---

## Fish setup

Add to `~/.config/fish/config.fish`:

```fish
setlhare hook --fish | source
```

Uses Fish's native `fish_posterror` event — simpler and more reliable than bash/zsh hooks.

---

## PowerShell setup

Add to `$PROFILE`:

```powershell
setlhare hook --powershell | Invoke-Expression
```

Overrides the `Prompt` function to check for errors after each command. Works for most use cases but may have edge cases with nested prompts or background jobs.

---

## Auto-apply mode

By default, Setlhare prompts `Apply? [y/N]` before applying any patch. To skip the prompt:

```bash
eval "$(setlhare hook --auto-apply)"
```

This sets `export SETLHARE_AUTO_APPLY=1` in the hook. To disable temporarily:

```bash
unset SETLHARE_AUTO_APPLY
```

---

## Uninstalling the hook

Remove the `eval "$(setlhare hook)"` line from your shell config file:

- Bash: `~/.bashrc`
- Zsh: `~/.zshrc`
- Fish: `~/.config/fish/config.fish`
- PowerShell: `$PROFILE`

Or run:

```bash
setlhare hook --uninstall
```

This prints the lines to remove.

---

## What triggers Setlhare

| Situation | Setlhare fires? |
|---|---|
| Python traceback (NameError, TypeError, etc.) | Yes |
| Java exception (NullPointerException, etc.) | Yes |
| JavaScript error (TypeError, ReferenceError) | Yes |
| `grep` returning 1 (no match) | No |
| `diff` returning 1 (files differ) | No |
| `test` / `[` returning 1 (false condition) | No |
| Any non-zero exit code with no stderr | No |
| Any non-zero exit code with unrecognized stderr | Shows raw stderr (fallback) |

---

## Performance

The hook adds minimal overhead:
- **Before command**: one `exec` redirect (~0.001s)
- **After command**: file existence check + stat (~0.001s)
- **No LLM call** unless a real stack trace is detected

Commands that succeed with no stderr incur virtually zero cost.

---

## Troubleshooting

### "Hook doesn't fire"

- Check the hook is loaded: `type __setlhare_preexec` (bash/zsh)
- Check `PROMPT_COMMAND` includes the hook: `echo $PROMPT_COMMAND` (bash)
- Restart your shell after adding the hook

### "stderr still shows during command"

- The `DEBUG` trap may be overridden by another tool (e.g., `direnv`, `nvm`)
- Try disabling other DEBUG traps temporarily

### "Fix not offered for my error"

- The parser may not recognize the error format
- Setlhare falls back to printing raw stderr so you still see the output
- Open an issue with the traceback format so we can add support

### "Patch doesn't apply"

- Setlhare uses `git apply` — your working directory must be a git repo
- If the patch conflicts, it prints the diff for you to apply manually
- Try `git stash` to get a clean working tree first
