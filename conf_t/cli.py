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
from conf_t.models import Lesson, Task
from conf_t.catalog import (
    DIFFICULTY_ORDER,
    Catalog,
    CatalogRefusal,
    collect_all_tags,
    filter_lessons_by_tags,
    parse_tags_csv,
    platform_names,
    same_platform,
)
from conf_t.platform import Platform
from conf_t.engine import (
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    LESSON_STATUS_NOT_STARTED,
)
from conf_t.session import (
    Session,
    TURN_CORRECT,
    TURN_HINT,
    TURN_IGNORE,
    TURN_INCORRECT,
    TURN_LEAVE,
    TURN_SKIPPED,
    practice_summary,
)

console = Console()

MENU_DUE_REVIEW = "due_review"
MENU_CONTINUE = "continue"
MENU_PRACTICE = "practice"
MENU_FAILED_DRILL = "failed_drill"
MENU_STATS = "stats"
MENU_RESET = "reset"
MENU_CREATE = "create"
MENU_EXIT = "exit"


def interrupt_message(*, review: bool) -> str:
    """What an interrupt says. Review names Review; Practice keeps its line."""
    if review:
        return "You left Review."
    return "Practice aborted."


def review_correct_message(*, first_try: bool) -> str:
    if first_try:
        return "✓ Correct! This Task left the drill."
    return "✓ Correct, but not first-try — rescheduled for later review"


class ConfTCLI:
    def __init__(
        self,
        catalog: Catalog | None = None,
        session: Session | None = None,
    ) -> None:
        self.catalog = catalog if catalog is not None else Catalog()
        self.session = session if session is not None else Session()

    def _lessons(
        self,
        platform: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Lesson]:
        try:
            return self.catalog.lessons(platform=platform, tags=tags)
        except CatalogRefusal as refusal:
            console.print(
                f"[bold red]Cannot open lessons.[/] Problem in [bold]{refusal.path.name}[/]."
            )
            console.print(f"[dim]{refusal}[/]")
            sys.exit(1)

    def _main_menu_choices(
        self, lessons: list[Lesson] | None = None
    ) -> list[questionary.Choice]:
        if lessons is None:
            lessons = self._lessons()
        due_count = len(self.session.due_review(lessons))
        choices = []
        if due_count > 0:
            choices.append(
                questionary.Choice(
                    title=f"★ Daily Review ({due_count} due)",
                    value=MENU_DUE_REVIEW,
                )
            )
        choices.append(
            questionary.Choice(
                title="↩ Continue where I left off",
                value=MENU_CONTINUE,
            )
        )
        choices.extend([
            questionary.Choice(title="1. Practice a Lesson", value=MENU_PRACTICE),
            questionary.Choice(
                title="2. Review All Failed Commands",
                value=MENU_FAILED_DRILL,
            ),
            questionary.Choice(title="3. View Progress & Stats", value=MENU_STATS),
            questionary.Choice(title="4. Reset All Progress", value=MENU_RESET),
            questionary.Choice(title="5. Create a Custom Lesson", value=MENU_CREATE),
            questionary.Choice(title="6. Exit", value=MENU_EXIT),
        ])
        return choices

    def _dispatch_menu(self, choice: str) -> bool:
        """Run the action for a stable menu value. A label is not an action."""
        actions = {
            MENU_DUE_REVIEW: self.daily_review_menu,
            MENU_CONTINUE: self.run_continue,
            MENU_PRACTICE: self.practice_lessons_menu,
            MENU_FAILED_DRILL: self.review_failed_menu,
            MENU_STATS: self.view_stats,
            MENU_RESET: self.reset_progress_menu,
            MENU_CREATE: self.create_lesson_menu,
        }
        action = actions.get(choice)
        if action is None:
            return False
        action()
        return True

    def list_lessons(
        self,
        platform: str | None = None,
        tags: str | None = None,
    ) -> None:
        tag_list = parse_tags_csv(tags)
        lessons = self._lessons(platform=platform, tags=tag_list)

        if not lessons:
            console.print("[yellow]No lessons match the selected filters.[/]")
            if platform:
                console.print(f"[dim]Platform: {platform}[/]")
            if tag_list:
                console.print(f"[dim]Tags: {', '.join(tag_list)}[/]")
            return

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

        for lesson in lessons:
            standing = self.session.lesson_standing(lesson)
            tags_display = ", ".join(lesson.tags) if lesson.tags else "—"
            total = standing.total
            passed = standing.passed
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
        console.print(f"\n[dim]{len(lessons)} lesson(s) shown[/]")

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
        lessons = self._lessons()
        lesson = next((item for item in lessons if item.id == lesson_id), None)
        if not lesson:
            console.print(f"[bold red]Lesson not found:[/] {lesson_id}")
            console.print("[dim]Use --list to see available lesson IDs.[/]")
            sys.exit(1)

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
        if not self.session.should_show_welcome():
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
        self.session.dismiss_welcome()

    def run_continue(self, interactive: bool = True) -> None:
        lessons = self._lessons()
        target = self.session.continue_target(lessons)

        if not target:
            console.print("[bold red]No lessons found.[/]")
            return

        if target.action == "daily_review":
            due_count = len(self.session.due_review(lessons))
            console.print(
                f"\n[bold yellow]Continuing:[/] [white]Daily Review[/] "
                f"[dim]({due_count} task(s) due)[/]\n"
            )
            self.daily_review_menu(interactive=interactive)
            return

        lesson_id = target.lesson_id
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
        self._lessons()
        self.show_welcome_banner()
        self.show_first_run_welcome()
        
        while True:
            try:
                lessons = self._lessons()
                due_count = len(self.session.due_review(lessons))
                prompt = "Select an option:"
                if due_count > 0:
                    prompt = f"[bold yellow]{due_count} task(s) due for review.[/] Select an option:"

                choice = questionary.select(
                    prompt,
                    choices=self._main_menu_choices(lessons),
                    style=questionary.Style([
                        ('pointer', 'fg:#00ffff bold'),
                        ('highlighted', 'fg:#00ffff bold'),
                        ('selected', 'fg:#00ff00'),
                    ])
                ).ask()

                if not choice:
                    break

                if choice == MENU_EXIT:
                    console.print("\n[bold cyan]Thank you for training with Conf T! Keep practicing.[/]")
                    break

                self._dispatch_menu(choice)
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
        standing = self.session.lesson_standing(lesson)

        if standing.total == 0:
            return []

        if standing.status == LESSON_STATUS_COMPLETED:
            practice_again = questionary.confirm(
                f"All {standing.total} tasks passed. Practice this lesson again from the start?",
                default=True,
            ).ask()
            if not practice_again:
                return None
            self.session.start_over(lesson)
            return list(lesson.tasks)

        can_resume = (
            standing.status == LESSON_STATUS_IN_PROGRESS
            and standing.passed < standing.total
        )
        if not can_resume:
            return list(lesson.tasks)

        choice = questionary.select(
            f"Progress: {standing.passed}/{standing.total} tasks passed. How do you want to continue?",
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
            self.session.start_over(lesson)
            return list(lesson.tasks)
        if choice == "resume":
            incomplete = self.session.resume_tasks(lesson)
            if not incomplete:
                console.print("[yellow]No incomplete tasks found.[/]")
                return None
            return incomplete
        if choice == "pick":
            return self._pick_lesson_start_task(lesson)

        return None

    def _pick_lesson_start_task(self, lesson: Lesson) -> list[Task] | None:
        resume_ids = {task.id for task in self.session.resume_tasks(lesson)}
        task_choices = []
        for index, task in enumerate(lesson.tasks):
            status = "○" if task.id in resume_ids else "✓"
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
        lesson_map = {item.id: item for item in all_lessons}
        missing_titles = self.session.missing_prerequisite_titles(lesson, all_lessons)

        console.print("\n")
        standing = self.session.lesson_standing(lesson)
        detail_lines = [
            f"[bold white]{lesson.description}[/]",
            "",
            f"[cyan]Difficulty:[/] {lesson.difficulty.title()}",
            f"[cyan]Progress:[/] {standing.passed}/{standing.total} tasks passed",
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

        if missing_titles:
            missing_text = ", ".join(missing_titles)
            return questionary.confirm(
                f"Prerequisites not completed: {missing_text}. Start anyway?",
                default=True,
            ).ask()

        return True

    def practice_lessons_menu(self):
        """Displays curriculum-aware lesson selection grouped by platform."""
        lessons = self._lessons()
        if not lessons:
            console.print("[bold red]No lessons found in the database. Please add lessons to conf_t/lessons/.[/]")
            return

        platforms = platform_names(lessons)
        platform_choices = platforms + ["< Go Back"]

        selected_platform = questionary.select(
            "Choose a platform:",
            choices=platform_choices,
        ).ask()

        if not selected_platform or selected_platform == "< Go Back":
            return

        filtered_lessons = [
            lesson for lesson in lessons if same_platform(lesson, selected_platform)
        ]
        filtered_lessons = self._prompt_tag_filter(
            filtered_lessons, f"{selected_platform} lessons"
        )
        if not filtered_lessons:
            console.print("[yellow]No lessons available for the selected filters.[/]")
            return

        failed_counts: dict[str, int] = {}
        for lesson, _task in self.session.failed_queue(lessons):
            failed_counts[lesson.id] = failed_counts.get(lesson.id, 0) + 1

        recommended = self.session.recommended_lesson(filtered_lessons, catalog=lessons)
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
            group = [lesson for lesson in filtered_lessons if lesson.difficulty == difficulty]
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
                standing = self.session.lesson_standing(lesson)
                missing = self.session.missing_prerequisite_titles(lesson, lessons)
                label = self._format_lesson_choice_label(
                    lesson,
                    standing.status,
                    standing.passed,
                    failed_counts.get(lesson.id, 0),
                    not missing,
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

    def _run_sitting(
        self,
        tasks: list[tuple[Lesson, Task]],
        *,
        review: bool,
    ) -> list | None:
        """One turn loop for Practice and Review.

        Returns the graded turns, or None when the Learner leaves.
        """
        graded = []
        total = len(tasks)
        for index, (lesson, task) in enumerate(tasks, 1):
            if review:
                console.print(
                    f"\n[bold cyan]Task {index}/{total} [{lesson.platform}]:[/] "
                    f"[bold white]{task.prompt}[/]"
                )
            else:
                console.print(
                    f"\n[bold cyan]Task {index}/{total}:[/] "
                    f"[bold white]{task.prompt}[/]"
                )
            self.session.begin_task(task)

            while True:
                try:
                    user_input = console.input(f"{task.prefix} ")
                except (KeyboardInterrupt, EOFError):
                    console.print(f"\n[yellow]{interrupt_message(review=review)}[/]")
                    return None

                result = self.session.submit(lesson, task, user_input)

                if result.kind == TURN_IGNORE:
                    continue

                if result.kind == TURN_LEAVE:
                    question = (
                        "Are you sure you want to exit review mode?"
                        if review
                        else "Are you sure you want to exit this lesson?"
                    )
                    if questionary.confirm(question).ask():
                        if not review:
                            console.print("[bold yellow]Exited practice session.[/]")
                        return None
                    continue

                if result.kind == TURN_HINT:
                    if result.hint:
                        console.print(Panel(
                            f"[bold yellow]Hint:[/] {result.hint}",
                            border_style="yellow",
                            box=box.MINIMAL,
                        ))
                    elif review:
                        console.print("[dim yellow]No hint available.[/]")
                    else:
                        console.print("[dim yellow]No hint available for this task.[/]")
                    continue

                if not review:
                    graded.append(result)

                if result.kind == TURN_SKIPPED:
                    console.print(Panel(
                        f"[bold red]Skipped.[/]\n\n[bold white]Correct Command:[/] [bold cyan]{result.readable_command}[/]\n\n"
                        f"[bold white]Explanation:[/] {result.explanation}",
                        border_style="red",
                        title="[bold red]Task Explanation[/]",
                    ))
                    break

                if result.kind == TURN_CORRECT:
                    if review:
                        heading = review_correct_message(first_try=result.first_try)
                    else:
                        heading = "✓ Correct!"
                    console.print(Panel(
                        f"[bold green]{heading}[/]\n\n"
                        f"[bold white]Explanation:[/] {result.explanation}",
                        border_style="green",
                        box=box.ROUNDED,
                    ))
                    break

                if result.kind == TURN_INCORRECT:
                    console.print(
                        "[bold red]✗ Incorrect command. Try again, or type 'hint' / 'skip' / 'exit'.[/]"
                    )

        return graded

    def run_practice_session(
        self,
        lesson: Lesson,
        tasks_to_run: list[Task] | None = None,
    ) -> None:
        """
        Runs the interactive prompt loop for a Practice sitting.
        """
        if tasks_to_run is None:
            tasks_to_run = list(lesson.tasks)

        if not tasks_to_run:
            console.print("[yellow]No tasks to practice in this session.[/]")
            return

        self.session.mark_practice_opened(lesson)

        title_text = f"Lesson: {lesson.title}"
        if len(tasks_to_run) < len(lesson.tasks):
            title_text = f"{lesson.title} — {len(tasks_to_run)} of {len(lesson.tasks)} tasks"
        desc_text = lesson.description

        console.print("\n")
        console.print(Panel(
            f"[bold white]{desc_text}[/]\n\n"
            f"[dim green]Type 'hint' for a hint, 'skip' to see the explanation and move on, or 'exit' to quit.[/]",
            title=f"[bold yellow]{title_text}[/]",
            border_style="green",
            box=box.ROUNDED
        ))

        stats_results = self._run_sitting(
            [(lesson, task) for task in tasks_to_run],
            review=False,
        )
        if stats_results is None:
            return

        stats = practice_summary(stats_results, total_tasks=len(tasks_to_run))
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

        finished = self._run_sitting(tasks_to_review, review=True)
        if finished is None:
            return

        console.print("\n[bold green]Review Session Completed![/]\n")
        if interactive:
            questionary.press_any_key_to_continue().ask()

    def daily_review_menu(self, interactive: bool = True) -> None:
        tasks_to_review = self.session.due_review(self._lessons())
        if not tasks_to_review:
            console.print("\n[bold green]★ No tasks due for review right now. Check back later![/]\n")
            if interactive:
                questionary.press_any_key_to_continue().ask()
            return

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
        tasks_to_review = self.session.failed_queue(self._lessons())
        if not tasks_to_review:
            console.print("\n[bold green]★ Nice job! You have no failed commands to review.[/]\n")
            if interactive:
                questionary.press_any_key_to_continue().ask()
            return

        if interactive:
            console.print(
                f"\n[yellow]You have {len(tasks_to_review)} failed commands in your queue.[/]"
            )
            confirm = questionary.confirm("Start practicing all failed commands?").ask()
            if not confirm:
                return
        else:
            console.print(
                f"\n[yellow]Reviewing {len(tasks_to_review)} failed command(s) from the queue.[/]"
            )

        self._run_review_session(
            tasks_to_review,
            title="Review All Failed Commands",
            description=f"Retrying {len(tasks_to_review)} commands you previously struggled with.",
            interactive=interactive,
        )

    def view_stats(self, interactive: bool = True) -> None:
        """Displays user stats and accuracy summary."""
        stats = self.session.stats()
        console.print("\n")
        
        overview = Table(title="[bold cyan]Global Performance Overview[/]", box=box.ROUNDED, border_style="cyan")
        overview.add_column("Metric", style="cyan")
        overview.add_column("Value", style="magenta")

        overview.add_row("Completed Lessons", str(stats.completed_lessons))
        overview.add_row("Due for Review", str(stats.due_count))
        overview.add_row("Failed Commands Queue Size", str(stats.failed_queue_size))
        overview.add_row("Total Attempts Registered", str(stats.total_attempts))
        overview.add_row("First-Try Correct Commands", str(stats.correct_first_try))
        overview.add_row("Skipped Commands", str(stats.skipped))
        
        console.print(overview)

        if stats.by_platform:
            p_table = Table(title="[bold yellow]Breakdown by Platform[/]", box=box.ROUNDED, border_style="yellow")
            p_table.add_column("Platform", style="cyan")
            p_table.add_column("Attempts", style="magenta")
            p_table.add_column("First-Try Correct", style="green")
            p_table.add_column("Skipped", style="red")

            for platform, totals in stats.by_platform.items():
                p_table.add_row(
                    platform,
                    str(totals.attempts),
                    str(totals.correct_first_try),
                    str(totals.skipped),
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
            self.session.reset_all()
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
        if self.catalog.get_lesson_by_id(lesson_id):
            overwrite = questionary.confirm(f"A lesson with ID '{lesson_id}' already exists. Overwrite it?").ask()
            if not overwrite:
                return

        platform = questionary.select(
            "3. Select Platform (or type a custom one in other option):",
            choices=list(Platform.choices()),
        ).ask()

        if platform == "Other":
            platform = questionary.text("Enter custom platform name:").ask()
            if not platform:
                return

        description = questionary.text("4. Enter Lesson Description:").ask()

        default_prefix = Platform.of(platform).prefix

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

        try:
            written = self.catalog.save_lesson(new_lesson)
        except CatalogRefusal as refusal:
            console.print(f"\n[bold red]✗ {refusal.path.name}[/]")
            console.print(f"[dim]{refusal}[/]\n")
        else:
            if written:
                console.print(f"\n[bold green]✔ Success! Lesson '{title}' has been saved to the database.[/]\n")
            else:
                console.print("\n[bold red]✗ Error: Could not write the lesson to the directory.[/]\n")

        questionary.press_any_key_to_continue().ask()
