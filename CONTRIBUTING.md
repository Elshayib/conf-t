# Contributing to Conf T

Thank you for your interest in contributing! Contributions of all kinds are welcome — bug fixes, new lessons, platform support, documentation improvements, and feature requests.

---

## Getting Started

1. **Fork** the repository and clone your fork:
   ```bash
   git clone https://github.com/<your-username>/conf-t.git
   cd conf-t
   ```

2. **Create a virtual environment** and install in editable mode:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   .\venv\Scripts\Activate.ps1  # Windows PowerShell
   pip install -e ".[dev]"
   ```

3. **Create a feature branch:**
   ```bash
   git checkout -b feat/my-new-feature
   ```

4. **Run tests before submitting:**
   ```bash
   pytest tests/
   ```

---

## Adding a New Lesson

The easiest way to contribute is to add a new lesson JSON file.

1. Create a file in `conf_t/lessons/<lesson_id>.json`.
2. Follow the [Lesson JSON Schema](README.md#-adding-custom-lessons) documented in the README.
3. Use **hybrid task IDs**: `{lesson_id}__{action_slug}` (e.g. `cisco_basic__enable`).
4. Ensure every `expected` field is a **valid Python regex** (test it with `re.compile()`).
5. Ensure every `task.id` is **globally unique** across all lesson files.
6. Run `pytest tests/test_lessons.py` — it validates parsing, regex, IDs, and prerequisites.

### Optional Lesson Metadata

| Field | Values | Purpose |
|---|---|---|
| `difficulty` | `beginner`, `intermediate`, `advanced` | Curriculum ordering |
| `tags` | string array | Topic labels (e.g. `["vlan", "ccna"]`) |
| `prerequisites` | lesson ID array | Required prior lessons |
| `estimated_minutes` | integer | Expected completion time |

---

## Lesson Quality Checklist

Before opening a PR with new lessons, verify:

- [ ] One distinct concept per task — no duplicate prompts or regex within a lesson
- [ ] `prefix` reflects the real shell/IOS mode for that step
- [ ] Cisco tasks include common abbreviations in `aliases` (`conf t`, `no shut`, etc.)
- [ ] `hint` nudges without giving away the answer; `explanation` teaches the why
- [ ] `difficulty` and `prerequisites` form a sensible learning path
- [ ] `pytest tests/` passes

---

## Adding a New Platform

1. Create a lesson file: `conf_t/lessons/<lesson_id>.json`
2. Update `validate_input()` in [`engine.py`](conf_t/engine.py) to set the correct case sensitivity:
   - Case-insensitive: add to the `["cisco", "powershell"]` list
   - Case-sensitive: it is already the default
3. Update the platform choices list in `create_lesson_menu()` in [`cli.py`](conf_t/cli.py).

---

## Code Style Guidelines

- Follow **PEP 8** for all Python code.
- Use **type hints** for all function signatures.
- **No UI code** (`print`, `input`, `questionary`, `rich`) in `engine.py` — it must stay pure.
- All data models must implement `to_dict()` and `from_dict()` methods.

---

## Submitting a Pull Request

1. Make sure CI passes (GitHub Actions will run automatically on push).
2. Write a clear PR description explaining **what** changed and **why**.
3. Link any related issues in the PR description.
4. PRs without meaningful descriptions may be closed without review.

---

## Reporting Bugs

Please open a [GitHub Issue](https://github.com/Elshayib/conf-t/issues) and include:
- Your OS and Python version
- Steps to reproduce the bug
- Expected vs actual behavior
- Any relevant error output

---

Thank you for helping make Conf T better!