# Changelog

All notable changes to Conf T are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.2.0]: https://github.com/Elshayib/conf-t/releases/tag/v0.2.0
[0.1.0]: https://github.com/Elshayib/conf-t/releases/tag/v0.1.0