from __future__ import annotations

import os
import sys
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.align import Align
from rich import box

from conf_t import __version__
from conf_t.models import Lesson, Task, SessionStats
from conf_t.engine import (
    DIFFICULTY_ORDER,
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    LESSON_STATUS_NOT_STARTED,
    LessonLoader,
    ProgressManager,
    are_prerequisites_met,
    collect_all_tags,
    filter_lessons_by_tags,
    format_display_answer,
    get_continue_target,
    get_failed_lesson_ids,
    get_lesson_status,
    get_missing_prerequisites,
    get_recommended_lesson,
    parse_tags_csv,
    sort_lessons_by_curriculum,
    validate_input,
)

console = Console()

class ConfTCLI:
    def __init__(self):
        self.loader = LessonLoader()
        self.progress = ProgressManager()

    def _main_menu_choices(self) -> list[str]:
        due_count = self.progress.get_due_review_count()
        choices = []
        if due_count > 0:
            choices.append(f"★ Daily Review ({due_count} due)")
        choices.append("↩ Continue where I left off")
        choices.extend([
            "1. Practice a Lesson",
            "2. Review All Failed Commands",
            "3. View Progress & Stats",
            "4. Reset All Progress",
            "5. Create a Custom Lesson",
            "6. Exit",
        ])
        return choices

    def list_lessons(
        self,
        platform: str | None = None,
        tags: str | None = None,
    ) -> None:
        lessons = self.loader.load_all_lessons()
        if platform:
            lessons = [
                lesson
                for lesson in lessons
                if lesson.platform.lower() == platform.lower()
            ]
        tag_list = parse_tags_csv(tags)
        lessons = filter_lessons_by_tags(lessons, tag_list)

        if not lessons:
            console.print("[yellow]No lessons match the selected filters.[/]")
            if platform:
                console.print(f"[dim]Platform: {platform}[/]")
            if tag_list:
                console.print(f"[dim]Tags: {', '.join(tag_list)}[/]")
            return

        sorted_lessons = sort_lessons_by_curriculum(lessons)
        title = "[bold cyan]Conf T Lessons[/]"
        if platform or tag_list:
            filters = []
            if platform:
                filters.append(platform)
            if tag_list:
                filters.append(", ".join(tag_list))
            title = f"[bold cyan]Conf T Lessons[/] [dim]({' · '.join(filters)})[/]"

        table = Table(title=title, box=box.ROUNDED, border_style="cyan")
        table.add_column("ID", style="dim")
        table.add_column("Title", style="white")
        table.add_column("Platform", style="cyan")
        table.add_column("Difficulty", style="yellow")
        table.add_column("Tags", style="dim")
        table.add_column("Progress", style="green")

        for lesson in sorted_lessons:
            task_ids = [task.id for task in lesson.tasks]
            summary = self.progress.get_lesson_task_summary(lesson.id, task_ids)
            tags_display = ", ".join(lesson.tags) if lesson.tags else "—"
            total = summary["total"]
            passed = summary["passed"]
            progress = (
                f"{passed}/{total} ({int((passed / total) * 100)}%)"
                if total
                else "0/0"
            )
            table.add_row(
                lesson.id,
                lesson.title,
                lesson.platform,
                lesson.difficulty,
                tags_display,
                progress,
            )

        console.print(table)
        console.print(f"\n[dim]{len(sorted_lessons)} lesson(s) shown[/]")

    def _prompt_tag_filter(self, lessons: list[Lesson], context: str) -> list[Lesson]:
        available_tags = collect_all_tags(lessons)
        if not available_tags:
            return lessons

        choices = [questionary.Choice("All topics", value="__all__")]
        for tag in available_tags:
            count = sum(1 for lesson in lessons if tag in {t.lower() for t in lesson.tags})
            choices.append(questionary.Choice(f"{tag} ({count})", value=tag))
        choices.append(questionary.Choice("Custom tags (comma-separated)", value="__custom__"))

        selected = questionary.select(
            f"Filter {context} by topic:",
            choices=choices,
        ).ask()

        if not selected or selected == "__all__":
            return lessons
        if selected == "__custom__":
            raw = questionary.text("Enter tags (comma-separated, e.g. vlan,ospf):").ask()
            tag_list = parse_tags_csv(raw)
            if not tag_list:
                return lessons
            filtered = filter_lessons_by_tags(lessons, tag_list)
            if not filtered:
                console.print("[yellow]No lessons match those tags. Showing all topics.[/]")
                return lessons
            return filtered

        filtered = filter_lessons_by_tags(lessons, [selected])
        return filtered if filtered else lessons

    def run_lesson_by_id(self, lesson_id: str) -> None:
        lesson = self.loader.get_lesson_by_id(lesson_id)
        if not lesson:
            console.print(f"[bold red]Lesson not found:[/] {lesson_id}")
            console.print("[dim]Use --list to see available lesson IDs.[/]")
            sys.exit(1)

        lessons = self.loader.load_all_lessons()
        if not self._confirm_lesson_start(lesson, lessons):
            return

        tasks_to_run = self._choose_lesson_tasks(lesson)
        if tasks_to_run is None:
            return
        self.run_practice_session(lesson, tasks_to_run=tasks_to_run)

    def run_from_args(self, args) -> None:
        if args.list:
            self.list_lessons(args.platform, args.tags)
            return
        if args.stats:
            self.view_stats(interactive=False)
            return
        if args.continue_session:
            self.run_continue(interactive=False)
            return
        if args.review:
            self.daily_review_menu(interactive=False)
            return
        if args.review_all:
            self.review_failed_menu(interactive=False)
            return
        if args.lesson:
            self.run_lesson_by_id(args.lesson)
            return

    def show_first_run_welcome(self) -> None:
        if self.progress.data.get("onboarding_complete"):
            return
        if self.progress.data.get("total_attempts", 0) > 0:
            return

        console.print(Panel(
            "[bold white]Welcome! Here's the fastest way to get started:[/]\n\n"
            "1. Run [bold cyan]conf-t --continue[/] anytime to jump back in\n"
            "2. Try [bold cyan]cisco_basic[/] (Cisco) or [bold cyan]linux_basic[/] (Linux)\n"
            "3. Type [bold cyan]hint[/] during practice · [bold cyan]skip[/] to see answers\n"
            "4. [bold cyan]Daily Review[/] appears when spaced-repetition tasks are due\n\n"
            "[dim]Install tip: pipx install conf-t  (or pip install conf-t)[/]",
            title="[bold green]First time with Conf T?[/]",
            border_style="green",
            box=box.ROUNDED,
        ))
        self.progress.data["onboarding_complete"] = True
        self.progress.save()

    def run_continue(self, interactive: bool = True) -> None:
        lessons = self.loader.load_all_lessons()
        if not lessons:
            console.print("[bold red]No lessons found.[/]")
            return

        target = get_continue_target(
            lessons=lessons,
            completed_lessons=self.progress.data.get("completed_lessons", []),
            attempted_lessons=self.progress.data.get("attempted_lessons", []),
            due_review_count=self.progress.get_due_review_count(),
            lesson_has_resume_state_fn=self.progress.lesson_has_resume_state,
            is_lesson_fully_passed_fn=self.progress.is_lesson_fully_passed,
        )

        if not target:
            console.print("[yellow]Nothing to continue yet. Try --list to pick a lesson.[/]")
            return

        if target["action"] == "daily_review":
            due = self.progress.get_due_review_count()
            console.print(
                f"\n[bold yellow]Continuing:[/] [white]Daily Review[/] "
                f"[dim]({due} task(s) due)[/]\n"
            )
            self.daily_review_menu(interactive=interactive)
            return

        lesson_id = target["lesson_id"]
        lesson = next((item for item in lessons if item.id == lesson_id), None)
        if not lesson:
            console.print(f"[red]Lesson not found: {lesson_id}[/]")
            return

        console.print(
            f"\n[bold yellow]Continuing:[/] [white]{lesson.title}[/] "
            f"[dim]({lesson.platform})[/]\n"
        )
        tasks_to_run = self._choose_lesson_tasks(lesson)
        if tasks_to_run is None:
            return
        self.run_practice_session(lesson, tasks_to_run=tasks_to_run)

    def run(self):
        """Main application execution loop."""
        self.show_welcome_banner()
        self.show_first_run_welcome()
        
        while True:
            try:
                due_count = self.progress.get_due_review_count()
                prompt = "Select an option:"
                if due_count > 0:
                    prompt = f"[bold yellow]{due_count} task(s) due for review.[/] Select an option:"

                choice = questionary.select(
                    prompt,
                    choices=self._main_menu_choices(),
                    style=questionary.Style([
                        ('pointer', 'fg:#00ffff bold'),
                        ('highlighted', 'fg:#00ffff bold'),
                        ('selected', 'fg:#00ff00'),
                    ])
                ).ask()

                if not choice:
                    break

                if "Daily Review" in choice:
                    self.daily_review_menu()
                elif "Continue where" in choice:
                    self.run_continue()
                elif "1. Practice" in choice:
                    self.practice_lessons_menu()
                elif "2. Review" in choice:
                    self.review_failed_menu()
                elif "3. View" in choice:
                    self.view_stats()
                elif "4. Reset" in choice:
                    self.reset_progress_menu()
                elif "5. Create" in choice:
                    self.create_lesson_menu()
                elif "6. Exit" in choice:
                    console.print("\n[bold cyan]Thank you for training with Conf T! Keep practicing.[/]")
                    break
            except KeyboardInterrupt:
                console.print("\n\n[bold yellow]Session interrupted. Returning to main menu.[/]")
                continue

    def show_welcome_banner(self):
        """Displays a visually premium banner on start."""
        banner = """
  [bold cyan]██████╗  ██████╗ ███╗   ██╗███████╗   ████████╗[/]
 [bold cyan]██╔════╝ ██╔═══██╗████╗  ██║██╔════╝   ╚══██╔══╝[/]
 [bold cyan]██║      ██║   ██║██╔██╗ ██║█████╗        ██║   [/]
 [bold cyan]██║      ██║   ██║██║╚██╗██║██╔══╝        ██║   [/]
 [bold cyan]╚██████╗ ╚██████╔╝██║ ╚████║██║           ██║   [/]
  [bold cyan]╚══════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝           ╚═╝   [/]
                                                
   [bold white]Learn and Master Command Lines Interactively[/]
        [dim cyan]Cisco IOS • Linux Shell • PowerShell • & More[/]
        """
        console.print(Panel(
            Align.center(banner),
            box=box.DOUBLE,
            border_style="cyan",
            title=f"[bold yellow]Welcome to Conf T v{__version__}[/]",
            title_align="center"
        ))

    def _lesson_status_icon(self, status: str) -> str:
        return {
            LESSON_STATUS_COMPLETED: "✓",
            LESSON_STATUS_IN_PROGRESS: "◐",
            LESSON_STATUS_NOT_STARTED: "○",
        }.get(status, "○")

    def _format_lesson_choice_label(
        self,
        lesson: Lesson,
        status: str,
        passed_count: int,
        failed_count: int,
        prereqs_met: bool,
    ) -> str:
        icon = self._lesson_status_icon(status)
        total = len(lesson.tasks)
        if total:
            percent = int((passed_count / total) * 100)
            progress = f"{passed_count}/{total} · {percent}%"
        else:
            progress = "0/0"
        label = f"{icon} {lesson.title} ({progress})"
        if lesson.tags:
            label += f" [{', '.join(lesson.tags[:2])}{'…' if len(lesson.tags) > 2 else ''}]"
        if lesson.estimated_minutes:
            label += f" · ~{lesson.estimated_minutes}m"
        if failed_count:
            label += f" · {failed_count} failed"
        if not prereqs_met:
            label += " · prereqs"
        return label

    def _choose_lesson_tasks(self, lesson: Lesson) -> list[Task] | None:
        task_ids = [task.id for task in lesson.tasks]
        summary = self.progress.get_lesson_task_summary(lesson.id, task_ids)

        if summary["total"] == 0:
            return []

        if summary["passed"] == summary["total"]:
            practice_again = questionary.confirm(
                f"All {summary['total']} tasks passed. Practice this lesson again from the start?",
                default=True,
            ).ask()
            if not practice_again:
                return None
            self.progress.reset_lesson_progress(lesson.id, task_ids)
            return list(lesson.tasks)

        if not self.progress.lesson_has_resume_state(lesson):
            return list(lesson.tasks)

        choice = questionary.select(
            f"Progress: {summary['passed']}/{summary['total']} tasks passed. How do you want to continue?",
            choices=[
                questionary.Choice("Resume at first incomplete task", value="resume"),
                questionary.Choice("Start over (reset lesson progress)", value="restart"),
                questionary.Choice("Pick a task to start from", value="pick"),
                questionary.Choice("Cancel", value="cancel"),
            ],
        ).ask()

        if not choice or choice == "cancel":
            return None
        if choice == "restart":
            self.progress.reset_lesson_progress(lesson.id, task_ids)
            return list(lesson.tasks)
        if choice == "resume":
            incomplete = self.progress.get_incomplete_tasks(lesson.tasks)
            if not incomplete:
                console.print("[yellow]No incomplete tasks found.[/]")
                return None
            return incomplete
        if choice == "pick":
            return self._pick_lesson_start_task(lesson)

        return None

    def _pick_lesson_start_task(self, lesson: Lesson) -> list[Task] | None:
        task_choices = []
        for index, task in enumerate(lesson.tasks):
            status = "✓" if self.progress.is_task_passed(task.id) else "○"
            prompt_preview = task.prompt if len(task.prompt) <= 60 else f"{task.prompt[:57]}..."
            task_choices.append(
                questionary.Choice(
                    title=f"{status} Task {index + 1}: {prompt_preview}",
                    value=index,
                )
            )
        task_choices.append(questionary.Choice(title="Cancel", value=-1))

        selected_index = questionary.select(
            "Pick a task to start from:",
            choices=task_choices,
        ).ask()

        if selected_index is None or selected_index == -1:
            return None
        return lesson.tasks[selected_index:]

    def _confirm_lesson_start(self, lesson: Lesson, all_lessons: list[Lesson]) -> bool:
        completed = self.progress.data.get("completed_lessons", [])
        missing_ids = get_missing_prerequisites(lesson, completed)
        lesson_map = {item.id: item for item in all_lessons}

        console.print("\n")
        task_ids = [task.id for task in lesson.tasks]
        summary = self.progress.get_lesson_task_summary(lesson.id, task_ids)
        detail_lines = [
            f"[bold white]{lesson.description}[/]",
            "",
            f"[cyan]Difficulty:[/] {lesson.difficulty.title()}",
            f"[cyan]Progress:[/] {summary['passed']}/{summary['total']} tasks passed",
        ]
        if lesson.estimated_minutes:
            detail_lines.append(f"[cyan]Estimated time:[/] ~{lesson.estimated_minutes} minutes")
        if lesson.tags:
            detail_lines.append(f"[cyan]Tags:[/] {', '.join(lesson.tags)}")
        if lesson.prerequisites:
            prereq_titles = [
                lesson_map[prereq_id].title
                for prereq_id in lesson.prerequisites
                if prereq_id in lesson_map
            ]
            if prereq_titles:
                detail_lines.append(f"[cyan]Prerequisites:[/] {', '.join(prereq_titles)}")

        console.print(Panel(
            "\n".join(detail_lines),
            title=f"[bold yellow]{lesson.title}[/]",
            border_style="cyan",
            box=box.ROUNDED,
        ))

        if missing_ids:
            missing_titles = [
                lesson_map[prereq_id].title
                for prereq_id in missing_ids
                if prereq_id in lesson_map
            ]
            missing_text = ", ".join(missing_titles) if missing_titles else ", ".join(missing_ids)
            return questionary.confirm(
                f"Prerequisites not completed: {missing_text}. Start anyway?",
                default=True,
            ).ask()

        return True

    def practice_lessons_menu(self):
        """Displays curriculum-aware lesson selection grouped by platform."""
        lessons = self.loader.load_all_lessons()
        if not lessons:
            console.print("[bold red]No lessons found in the database. Please add lessons to conf_t/lessons/.[/]")
            return

        platforms = sorted({lesson.platform for lesson in lessons})
        platform_choices = platforms + ["< Go Back"]

        selected_platform = questionary.select(
            "Choose a platform:",
            choices=platform_choices,
        ).ask()

        if not selected_platform or selected_platform == "< Go Back":
            return

        filtered_lessons = [lesson for lesson in lessons if lesson.platform == selected_platform]
        filtered_lessons = self._prompt_tag_filter(
            filtered_lessons, f"{selected_platform} lessons"
        )
        if not filtered_lessons:
            console.print("[yellow]No lessons available for the selected filters.[/]")
            return

        sorted_lessons = sort_lessons_by_curriculum(filtered_lessons)
        completed = self.progress.data.get("completed_lessons", [])
        attempted = self.progress.data.get("attempted_lessons", [])
        failed_entries = self.progress.get_failed_task_entries()
        failed_lesson_ids = get_failed_lesson_ids(failed_entries)
        failed_counts: dict[str, int] = {}
        for entry in failed_entries:
            lesson_id = entry["lesson_id"]
            failed_counts[lesson_id] = failed_counts.get(lesson_id, 0) + 1

        recommended = get_recommended_lesson(sorted_lessons, completed)
        if recommended:
            console.print(
                f"\n[bold green]★ Recommended next:[/] [white]{recommended.title}[/] "
                f"[dim]({recommended.difficulty})[/]\n"
            )

        lesson_choices = []
        if recommended:
            lesson_choices.append(
                questionary.Choice(
                    title=f"★ Recommended: {recommended.title}",
                    value=recommended.id,
                )
            )
            lesson_choices.append(questionary.Choice(title="─────────────", value="__sep__", disabled=True))

        for difficulty in sorted(DIFFICULTY_ORDER, key=lambda key: DIFFICULTY_ORDER[key]):
            group = [lesson for lesson in sorted_lessons if lesson.difficulty == difficulty]
            if not group:
                continue
            lesson_choices.append(
                questionary.Choice(
                    title=f"── {difficulty.title()} ──",
                    value=f"__header_{difficulty}__",
                    disabled=True,
                )
            )
            for lesson in group:
                task_ids = [task.id for task in lesson.tasks]
                lesson_summary = self.progress.get_lesson_task_summary(lesson.id, task_ids)
                status = get_lesson_status(
                    lesson.id, completed, attempted, failed_lesson_ids
                )
                if (
                    lesson_summary["total"] > 0
                    and lesson_summary["passed"] == lesson_summary["total"]
                ):
                    status = LESSON_STATUS_COMPLETED
                label = self._format_lesson_choice_label(
                    lesson,
                    status,
                    lesson_summary["passed"],
                    failed_counts.get(lesson.id, 0),
                    are_prerequisites_met(lesson, completed),
                )
                lesson_choices.append(questionary.Choice(title=label, value=lesson.id))

        lesson_choices.append(questionary.Choice(title="< Go Back", value="__back__"))

        selected_lesson_id = questionary.select(
            f"Choose a {selected_platform} lesson:",
            choices=lesson_choices,
        ).ask()

        if not selected_lesson_id or selected_lesson_id in {"__back__", "__sep__"} or selected_lesson_id.startswith("__header_"):
            if selected_lesson_id and selected_lesson_id not in {"__back__", "__sep__"}:
                self.practice_lessons_menu()
            return

        selected_lesson = next(
            (lesson for lesson in filtered_lessons if lesson.id == selected_lesson_id),
            None,
        )
        if not selected_lesson:
            return

        if not self._confirm_lesson_start(selected_lesson, lessons):
            return

        tasks_to_run = self._choose_lesson_tasks(selected_lesson)
        if tasks_to_run is None:
            return
        self.run_practice_session(selected_lesson, tasks_to_run=tasks_to_run)

    def run_practice_session(
        self,
        lesson: Lesson,
        review_mode: bool = False,
        review_tasks: list | None = None,
        tasks_to_run: list[Task] | None = None,
    ):
        """
        Runs the interactive prompt loop for a lesson or a custom set of review tasks.
        """
        if review_mode:
            tasks_to_run = review_tasks or []
        elif tasks_to_run is None:
            tasks_to_run = list(lesson.tasks)

        if not tasks_to_run:
            console.print("[yellow]No tasks to practice in this session.[/]")
            return

        if not review_mode:
            self.progress.mark_lesson_attempted(lesson.id)

        title_text = f"Reviewing {len(tasks_to_run)} Failed Commands" if review_mode else f"Lesson: {lesson.title}"
        if not review_mode and len(tasks_to_run) < len(lesson.tasks):
            title_text = f"{lesson.title} — {len(tasks_to_run)} of {len(lesson.tasks)} tasks"
        desc_text = "Retrying commands you previously missed." if review_mode else lesson.description

        console.print("\n")
        console.print(Panel(
            f"[bold white]{desc_text}[/]\n\n"
            f"[dim green]Type 'hint' for a hint, 'skip' to see the explanation and move on, or 'exit' to quit.[/]",
            title=f"[bold yellow]{title_text}[/]",
            border_style="green",
            box=box.ROUNDED
        ))

        stats = SessionStats(total_questions=len(tasks_to_run))

        for idx, task in enumerate(tasks_to_run, 1):
            console.print(f"\n[bold cyan]Task {idx}/{len(tasks_to_run)}:[/] [bold white]{task.prompt}[/]")
            
            is_first_try = True
            is_skipped = False
            
            while True:
                # Prompt the user
                try:
                    prompt_str = f"{task.prefix} "
                    user_input = console.input(prompt_str)
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[yellow]Practice aborted.[/]")
                    return

                cleaned_input = user_input.strip()

                if not cleaned_input:
                    continue

                # If the user typed an exit command, check if it's the expected correct answer first
                is_flow_exit = cleaned_input.lower() in ["exit", "quit"]
                is_expected_exit = False
                if is_flow_exit:
                    is_expected_exit = validate_input(cleaned_input, task, lesson.platform)

                if is_flow_exit and not is_expected_exit:
                    confirm = questionary.confirm("Are you sure you want to exit this lesson?").ask()
                    if confirm:
                        console.print("[bold yellow]Exited practice session.[/]")
                        return
                    else:
                        continue

                if cleaned_input.lower() == "hint":
                    if task.hint:
                        console.print(Panel(
                            f"[bold yellow]Hint:[/] {task.hint}",
                            border_style="yellow",
                            box=box.MINIMAL
                        ))
                    else:
                        console.print("[dim yellow]No hint available for this task.[/]")
                    continue

                if cleaned_input.lower() == "skip":
                    is_skipped = True
                    stats.skipped_count += 1
                    stats.total_attempts += 1
                    
                    # Record progress
                    self.progress.record_attempt(
                        lesson_id=lesson.id,
                        platform=lesson.platform,
                        task_id=task.id,
                        is_correct=False,
                        is_first_try=is_first_try,
                        is_skipped=True
                    )

                    console.print(Panel(
                        f"[bold red]Skipped.[/]\n\n[bold white]Correct Command:[/] [bold cyan]{format_display_answer(task, lesson.platform)}[/]\n\n"
                        f"[bold white]Explanation:[/] {task.explanation}",
                        border_style="red",
                        title="[bold red]Task Explanation[/]"
                    ))
                    break

                # Validate command
                is_correct = validate_input(cleaned_input, task, lesson.platform)
                
                if is_correct:
                    stats.total_attempts += 1
                    if is_first_try:
                        stats.correct_first_try += 1

                    # Record progress
                    self.progress.record_attempt(
                        lesson_id=lesson.id,
                        platform=lesson.platform,
                        task_id=task.id,
                        is_correct=True,
                        is_first_try=is_first_try,
                        is_skipped=False
                    )

                    console.print(Panel(
                        f"[bold green]✓ Correct![/]\n\n"
                        f"[bold white]Explanation:[/] {task.explanation}",
                        border_style="green",
                        box=box.ROUNDED
                    ))
                    break
                else:
                    stats.total_attempts += 1
                    is_first_try = False
                    
                    # Record progress
                    self.progress.record_attempt(
                        lesson_id=lesson.id,
                        platform=lesson.platform,
                        task_id=task.id,
                        is_correct=False,
                        is_first_try=is_first_try,
                        is_skipped=False
                    )
                    
                    console.print("[bold red]✗ Incorrect command. Try again, or type 'hint' / 'skip' / 'exit'.[/]")

        if not review_mode and self.progress.is_lesson_fully_passed(lesson):
            self.progress.mark_lesson_completed(lesson.id)

        # Display session stats
        accuracy = (stats.correct_first_try / stats.total_questions) * 100 if stats.total_questions > 0 else 0
        summary_table = Table(title="[bold yellow]Session Summary[/]", box=box.ROUNDED, border_style="cyan")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="magenta")
        
        summary_table.add_row("Total Tasks", str(stats.total_questions))
        summary_table.add_row("Correct First Try", f"{stats.correct_first_try} / {stats.total_questions}")
        summary_table.add_row("First-Try Accuracy", f"{accuracy:.1f}%")
        summary_table.add_row("Skipped Tasks", str(stats.skipped_count))
        summary_table.add_row("Total Typing Attempts", str(stats.total_attempts))

        console.print("\n")
        console.print(Align.center(summary_table))
        console.print("[bold green]Practice Session Completed![/]\n")
        questionary.press_any_key_to_continue().ask()

    def _resolve_review_entries(
        self, entries: list[dict[str, str]]
    ) -> list[tuple[Lesson, Task]]:
        all_lessons = self.loader.load_all_lessons()
        tasks_to_review: list[tuple[Lesson, Task]] = []
        for entry in entries:
            lesson_id = entry["lesson_id"]
            task_id = entry["task_id"]
            lesson = next((item for item in all_lessons if item.id == lesson_id), None)
            if not lesson:
                continue
            task = next((item for item in lesson.tasks if item.id == task_id), None)
            if task:
                tasks_to_review.append((lesson, task))
        return tasks_to_review

    def _run_review_session(
        self,
        tasks_to_review: list[tuple[Lesson, Task]],
        title: str,
        description: str,
        interactive: bool = True,
    ) -> None:
        if not tasks_to_review:
            console.print("[red]Could not load review tasks. The source lesson files might have changed.[/]")
            return

        console.print("\n")
        console.print(Panel(
            f"[bold white]{description}[/]\n\n"
            f"[dim green]Type 'hint' for a hint, 'skip' to see the explanation, or 'exit' to quit.[/]",
            title=f"[bold yellow]{title}[/]",
            border_style="yellow",
            box=box.ROUNDED,
        ))

        for idx, (lesson, task) in enumerate(tasks_to_review, 1):
            console.print(
                f"\n[bold cyan]Task {idx}/{len(tasks_to_review)} [{lesson.platform}]:[/] "
                f"[bold white]{task.prompt}[/]"
            )
            is_first_try = True

            while True:
                try:
                    prompt_str = f"{task.prefix} "
                    user_input = console.input(prompt_str)
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[yellow]Practice aborted.[/]")
                    return

                cleaned_input = user_input.strip()
                if not cleaned_input:
                    continue

                is_flow_exit = cleaned_input.lower() in ["exit", "quit"]
                is_expected_exit = False
                if is_flow_exit:
                    is_expected_exit = validate_input(cleaned_input, task, lesson.platform)

                if is_flow_exit and not is_expected_exit:
                    confirm = questionary.confirm("Are you sure you want to exit review mode?").ask()
                    if confirm:
                        return
                    continue

                if cleaned_input.lower() == "hint":
                    if task.hint:
                        console.print(Panel(
                            f"[bold yellow]Hint:[/] {task.hint}",
                            border_style="yellow",
                            box=box.MINIMAL,
                        ))
                    else:
                        console.print("[dim yellow]No hint available.[/]")
                    continue

                if cleaned_input.lower() == "skip":
                    self.progress.record_attempt(
                        lesson_id=lesson.id,
                        platform=lesson.platform,
                        task_id=task.id,
                        is_correct=False,
                        is_first_try=is_first_try,
                        is_skipped=True,
                    )
                    console.print(Panel(
                        f"[bold red]Skipped.[/]\n\n"
                        f"[bold white]Correct Command:[/] [bold cyan]{format_display_answer(task, lesson.platform)}[/]\n\n"
                        f"[bold white]Explanation:[/] {task.explanation}",
                        border_style="red",
                        title="[bold red]Task Explanation[/]",
                    ))
                    break

                is_correct = validate_input(cleaned_input, task, lesson.platform)
                if is_correct:
                    self.progress.record_attempt(
                        lesson_id=lesson.id,
                        platform=lesson.platform,
                        task_id=task.id,
                        is_correct=True,
                        is_first_try=is_first_try,
                        is_skipped=False,
                    )
                    cleared = is_first_try
                    status_msg = (
                        "✓ Correct! (Removed from review queue)"
                        if cleared
                        else "✓ Correct, but not first-try — rescheduled for later review"
                    )
                    console.print(Panel(
                        f"[bold green]{status_msg}[/]\n\n"
                        f"[bold white]Explanation:[/] {task.explanation}",
                        border_style="green",
                        box=box.ROUNDED,
                    ))
                    break

                is_first_try = False
                self.progress.record_attempt(
                    lesson_id=lesson.id,
                    platform=lesson.platform,
                    task_id=task.id,
                    is_correct=False,
                    is_first_try=is_first_try,
                    is_skipped=False,
                )
                console.print("[bold red]✗ Incorrect command. Try again, or type 'hint' / 'skip' / 'exit'.[/]")

        console.print("\n[bold green]Review Session Completed![/]\n")
        if interactive:
            questionary.press_any_key_to_continue().ask()

    def daily_review_menu(self, interactive: bool = True) -> None:
        due_entries = self.progress.get_due_review_entries()
        if not due_entries:
            console.print("\n[bold green]★ No tasks due for review right now. Check back later![/]\n")
            if interactive:
                questionary.press_any_key_to_continue().ask()
            return

        tasks_to_review = self._resolve_review_entries(due_entries)
        self._run_review_session(
            tasks_to_review,
            title=f"Daily Review ({len(tasks_to_review)} due)",
            description=(
                f"Spaced repetition review for {len(tasks_to_review)} due command(s). "
                "First-try correct answers clear the task from your queue."
            ),
            interactive=interactive,
        )

    def review_failed_menu(self, interactive: bool = True) -> None:
        """Loads all failed tasks and allows practicing them."""
        failed_entries = self.progress.get_failed_task_entries()
        if not failed_entries:
            console.print("\n[bold green]★ Nice job! You have no failed commands to review.[/]\n")
            if interactive:
                questionary.press_any_key_to_continue().ask()
            return

        if interactive:
            console.print(f"\n[yellow]You have {len(failed_entries)} failed commands in your queue.[/]")
            confirm = questionary.confirm("Start practicing all failed commands?").ask()
            if not confirm:
                return
        else:
            console.print(
                f"\n[yellow]Reviewing {len(failed_entries)} failed command(s) from the queue.[/]"
            )

        tasks_to_review = self._resolve_review_entries(failed_entries)
        self._run_review_session(
            tasks_to_review,
            title="Review All Failed Commands",
            description=f"Retrying {len(tasks_to_review)} commands you previously struggled with.",
            interactive=interactive,
        )

    def view_stats(self, interactive: bool = True) -> None:
        """Displays user stats and accuracy summary."""
        data = self.progress.data
        console.print("\n")
        
        overview = Table(title="[bold cyan]Global Performance Overview[/]", box=box.ROUNDED, border_style="cyan")
        overview.add_column("Metric", style="cyan")
        overview.add_column("Value", style="magenta")

        completed_count = len(data.get("completed_lessons", []))
        failed_count = len(data.get("failed_tasks", []))
        due_count = self.progress.get_due_review_count()
        
        overview.add_row("Completed Lessons", str(completed_count))
        overview.add_row("Due for Review", str(due_count))
        overview.add_row("Failed Commands Queue Size", str(failed_count))
        overview.add_row("Total Attempts Registered", str(data.get("total_attempts", 0)))
        overview.add_row("First-Try Correct Commands", str(data.get("correct_first_try", 0)))
        overview.add_row("Skipped Commands", str(data.get("skipped_count", 0)))
        
        console.print(overview)

        p_stats = data.get("platform_stats", {})
        if p_stats:
            p_table = Table(title="[bold yellow]Breakdown by Platform[/]", box=box.ROUNDED, border_style="yellow")
            p_table.add_column("Platform", style="cyan")
            p_table.add_column("Attempts", style="magenta")
            p_table.add_column("First-Try Correct", style="green")
            p_table.add_column("Skipped", style="red")

            for platform, stats in p_stats.items():
                p_table.add_row(
                    platform,
                    str(stats.get("attempts", 0)),
                    str(stats.get("correct_first_try", 0)),
                    str(stats.get("skipped", 0))
                )
            console.print("\n")
            console.print(p_table)
        else:
            console.print("\n[dim yellow]No platform stats recorded yet. Complete some lessons to view platform breakdowns.[/]\n")

        if interactive:
            questionary.press_any_key_to_continue().ask()

    def reset_progress_menu(self):
        """Prompts for resetting all stats."""
        confirm = questionary.confirm(
            "Are you sure you want to reset all of your progress, failed tasks, and stats? This cannot be undone.",
            default=False
        ).ask()
        
        if confirm:
            self.progress.reset_progress()
            console.print("[bold green]✔ All progress and statistics have been reset successfully.[/]\n")
        else:
            console.print("[yellow]Reset cancelled.[/]\n")
            
        questionary.press_any_key_to_continue().ask()

    def create_lesson_menu(self):
        """Interactive CLI wizard to design and save a custom lesson JSON."""
        console.print("\n")
        console.print(Panel(
            "[bold white]Welcome to the Conf T Lesson Creator Wizard![/]\n\n"
            "This guide will walk you through creating a new custom command-line lesson "
            "and automatically saving it to the lessons database.",
            title="[bold yellow]Conf T Lesson Creator[/]",
            border_style="yellow",
            box=box.ROUNDED
        ))

        title = questionary.text("1. Enter Lesson Title (e.g., Git Advanced):").ask()
        if not title:
            console.print("[yellow]Cancelled lesson creation.[/]")
            return

        # Generate a slug-based ID
        suggested_id = title.lower().strip().replace(" ", "_")
        suggested_id = "".join([c for c in suggested_id if c.isalnum() or c == "_"])
        lesson_id = questionary.text("2. Enter Lesson ID (slug filename):", default=suggested_id).ask()
        if not lesson_id:
            return

        # Check if already exists
        if self.loader.get_lesson_by_id(lesson_id):
            overwrite = questionary.confirm(f"A lesson with ID '{lesson_id}' already exists. Overwrite it?").ask()
            if not overwrite:
                return

        platform = questionary.select(
            "3. Select Platform (or type a custom one in other option):",
            choices=["Cisco", "Linux", "PowerShell", "Git", "Docker", "Other"]
        ).ask()

        if platform == "Other":
            platform = questionary.text("Enter custom platform name:").ask()
            if not platform:
                return

        description = questionary.text("4. Enter Lesson Description:").ask()
        
        # Determine default prompt prefix
        default_prefix = "$"
        if platform.lower() == "cisco":
            default_prefix = "Router#"
        elif platform.lower() == "powershell":
            default_prefix = "PS C:\\"
        elif platform.lower() == "git":
            default_prefix = "user@git:~$"

        tasks = []
        console.print("\n[bold yellow]--- Task Creator Loop ---[/]")
        console.print("[dim cyan]Let's configure tasks/commands for this lesson. You must add at least 1 task.[/]\n")

        task_index = 1
        while True:
            console.print(f"\n[bold yellow]Configuring Task #{task_index}[/]")
            task_prompt = questionary.text(f"Task Prompt / Instruction:").ask()
            if not task_prompt:
                if len(tasks) > 0:
                    break
                else:
                    console.print("[red]You must add at least one task to create a lesson.[/]")
                    continue

            task_expected = questionary.text(
                "Expected command regex pattern (e.g., ^git\\s+stash$):",
                validate=lambda val: len(val.strip()) > 0 or "Expected regex cannot be empty."
            ).ask()

            task_aliases_raw = questionary.text(
                "Acceptable aliases (comma-separated shortcuts, e.g. git stash, git stash save):"
            ).ask()
            aliases = [a.strip() for a in task_aliases_raw.split(",") if a.strip()]

            task_prefix = questionary.text("Interface Prompt Prefix:", default=default_prefix).ask()
            task_hint = questionary.text("Short Hint (optional):").ask()
            task_explanation = questionary.text("Task Explanation / Command details:").ask()

            t_id = f"{lesson_id}__task_{task_index}"

            from conf_t.models import Task
            task_obj = Task(
                id=t_id,
                prompt=task_prompt,
                prefix=task_prefix,
                expected=task_expected,
                aliases=aliases,
                hint=task_hint,
                explanation=task_explanation
            )
            tasks.append(task_obj)
            task_index += 1

            more = questionary.confirm("Do you want to add another task?").ask()
            if not more:
                break

        from conf_t.models import Lesson
        new_lesson = Lesson(
            id=lesson_id,
            title=title,
            platform=platform,
            description=description,
            tasks=tasks
        )

        success = self.loader.save_lesson(new_lesson)
        if success:
            console.print(f"\n[bold green]✔ Success! Lesson '{title}' has been saved to the database.[/]\n")
        else:
            console.print("\n[bold red]✗ Error: Could not write the lesson to the directory.[/]\n")

        questionary.press_any_key_to_continue().ask()
