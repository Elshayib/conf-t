# Changelog

All notable changes to Conf T are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.3] - 2026-07-04

### Added

- **CLI flags** for power users (interactive menu remains the default):
  - `conf-t --list` — list lessons with progress
  - `conf-t --list --platform Cisco` — filter by platform
  - `conf-t --lesson cisco_basic` — jump into a lesson (resume flow applies)
  - `conf-t --review` — run daily review for due tasks
  - `conf-t --review-all` — review entire failed queue
  - `conf-t --stats` — print progress stats and exit
  - `conf-t --version` — show version

### Changed

- Version bumped to **0.3.3**

---

## [0.3.2] - 2026-07-04

### Added

- **Spaced repetition** — failed/skipped tasks resurface on a schedule (due now → 1d → 3d → 7d)
- **Daily Review (N due)** — promoted to the top of the main menu when tasks are ready
- Shared review session flow for daily review and manual failed-command review
- Stats panel shows **Due for Review** count

### Changed

- "Review Failed Commands" renamed to **Review All Failed Commands** (manual full queue)
- Correct-but-not-first-try in review reschedules the task instead of clearing it
- Progress file version bumped to **4** with automatic migration
- Version bumped to **0.3.2**

---

## [0.3.1] - 2026-07-04

### Added

- **Resume mid-lesson** — when re-entering a lesson with progress, choose:
  - Resume at first incomplete task
  - Start over (reset lesson progress)
  - Pick a task to start from
- Lesson browser shows **passed/total** progress (e.g. `7/12`) per lesson
- Lesson detail panel shows progress summary before starting
- Lessons marked completed only when **all tasks** are passed first-try

### Changed

- Version bumped to **0.3.1**

---

## [0.3.0] - 2026-07-04

### Added

- **Task-level progress tracking** — per-task status (`passed`, `failed`, `skipped`), attempt count, and timestamps in `task_progress`
- **First-try-only pass semantics** — a task counts as passed only on a correct first attempt; retries stay in the review queue
- `get_lesson_task_summary()` and `is_task_passed()` helpers for upcoming resume and browser features
- Automatic **migration** from v0.2.x progress files (`failed_tasks` → `task_progress`, `progress_version: 3`)

### Changed

- Minimum Python version raised to **3.10** (3.8 removed from CI matrix)
- Version bumped to **0.3.0**

### Migration

Existing `~/.conf_t_progress.json` files from v0.2.x are upgraded automatically on first launch. Completed lessons and aggregate stats are preserved; failed tasks gain per-task records. Legacy v0.1.x files with old task IDs should still be reset manually.

---

## [0.2.0] - 2026-07-04

### Added

- **68 lessons** and **640 practice tasks** across five platforms:
  - Cisco IOS (21 lessons, 231 tasks) — CCNA-aligned curriculum
  - Linux (15 lessons, 144 tasks)
  - PowerShell (12 lessons, 102 tasks)
  - Git (10 lessons, 80 tasks)
  - Docker (10 lessons, 83 tasks)
- Structured lesson metadata: `difficulty`, `tags`, `prerequisites`, `estimated_minutes`
- Capstone troubleshooting labs per platform (`*_troubleshooting_lab`)
- **Curriculum-aware lesson browser** with difficulty grouping, progress icons, and recommended next lesson
- Soft prerequisite warnings before starting a lesson (start anyway or go back)
- Lesson detail preview (description, difficulty, task count, prerequisites)
- `attempted_lessons` progress tracking for in-progress lesson status
- Lesson validation test suite (`tests/test_lessons.py`) — IDs, regex, prerequisites, difficulty
- Curriculum engine helpers in `engine.py` (sorting, prerequisites, recommendations)

### Changed

- Task IDs now use a globally-unique format: `{lesson_id}__{action_slug}`
- Skip/reveal shows human-readable answers (aliases) instead of raw regex patterns
- Lessons are only marked completed when all tasks are finished (early exit no longer counts)
- Version bumped to **0.2.0**

### Removed

- Monolithic `cisco_routing_vlans.json` — split into focused Cisco lesson packs

### Migration

If you have an older `~/.conf_t_progress.json` from v0.1.x, reset progress from the main menu after upgrading. Task IDs changed and old progress will not map correctly.

---

## [0.1.0] - Initial release

- Interactive CLI trainer with simulated prompts
- Regex-based command validation with alias support
- Review mode for failed/skipped commands
- Progress tracking saved to `~/.conf_t_progress.json`
- Lesson creator wizard
- Starter lessons for Cisco, Linux, PowerShell, Git, and Docker

[0.3.3]: https://github.com/Elshayib/conf-t/releases/tag/v0.3.3
[0.3.2]: https://github.com/Elshayib/conf-t/releases/tag/v0.3.2
[0.3.1]: https://github.com/Elshayib/conf-t/releases/tag/v0.3.1
[0.3.0]: https://github.com/Elshayib/conf-t/releases/tag/v0.3.0
[0.2.0]: https://github.com/Elshayib/conf-t/releases/tag/v0.2.0
[0.1.0]: https://github.com/Elshayib/conf-t/releases/tag/v0.1.0