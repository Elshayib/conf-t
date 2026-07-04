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
    format_display_answer,
    get_failed_lesson_ids,
    get_lesson_status,
    get_missing_prerequisites,
    get_recommended_lesson,
    sort_lessons_by_curriculum,
    validate_input,
)

console = Console()

class ConfTCLI:
    def __init__(self):
        self.loader = LessonLoader()
        self.progress = ProgressManager()

    def run(self):
        """Main application execution loop."""
        self.show_welcome_banner()
        
        while True:
            try:
                choice = questionary.select(
                    "Select an option:",
                    choices=[
                        "1. Practice a Lesson",
                        "2. Review Failed Commands",
                        "3. View Progress & Stats",
                        "4. Reset All Progress",
                        "5. Create a Custom Lesson",
                        "6. Exit"
                    ],
                    style=questionary.Style([
                        ('pointer', 'fg:#00ffff bold'),
                        ('highlighted', 'fg:#00ffff bold'),
                        ('selected', 'fg:#00ff00'),
                    ])
                ).ask()

                if not choice:
                    break

                if "1. Practice" in choice:
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
        failed_count: int,
        prereqs_met: bool,
    ) -> str:
        icon = self._lesson_status_icon(status)
        label = f"{icon} {lesson.title} ({len(lesson.tasks)} tasks)"
        if lesson.estimated_minutes:
            label += f" · ~{lesson.estimated_minutes}m"
        if failed_count:
            label += f" · {failed_count} failed"
        if not prereqs_met:
            label += " · prereqs"
        return label

    def _confirm_lesson_start(self, lesson: Lesson, all_lessons: list[Lesson]) -> bool:
        completed = self.progress.data.get("completed_lessons", [])
        missing_ids = get_missing_prerequisites(lesson, completed)
        lesson_map = {item.id: item for item in all_lessons}

        console.print("\n")
        detail_lines = [
            f"[bold white]{lesson.description}[/]",
            "",
            f"[cyan]Difficulty:[/] {lesson.difficulty.title()}",
            f"[cyan]Tasks:[/] {len(lesson.tasks)}",
        ]
        if lesson.estimated_minutes:
            detail_lines.append(f"[cyan]Estimated time:[/] ~{lesson.estimated_minutes} minutes")
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
                status = get_lesson_status(
                    lesson.id, completed, attempted, failed_lesson_ids
                )
                label = self._format_lesson_choice_label(
                    lesson,
                    status,
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

        if self._confirm_lesson_start(selected_lesson, lessons):
            self.run_practice_session(selected_lesson)

    def run_practice_session(self, lesson: Lesson, review_mode: bool = False, review_tasks: list = None):
        """
        Runs the interactive prompt loop for a lesson or a custom set of review tasks.
        """
        tasks_to_run = review_tasks if review_mode else lesson.tasks
        if not tasks_to_run:
            console.print("[yellow]No tasks to practice in this session.[/]")
            return

        if not review_mode:
            self.progress.mark_lesson_attempted(lesson.id)

        title_text = f"Reviewing {len(tasks_to_run)} Failed Commands" if review_mode else f"Lesson: {lesson.title}"
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

        if not review_mode:
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

    def review_failed_menu(self):
        """Loads failed tasks and allows practicing them."""
        failed_entries = self.progress.get_failed_task_entries()
        if not failed_entries:
            console.print("\n[bold green]★ Nice job! You have no failed commands to review.[/]\n")
            questionary.press_any_key_to_continue().ask()
            return

        console.print(f"\n[yellow]You have {len(failed_entries)} failed commands in your queue.[/]")
        
        confirm = questionary.confirm("Start practicing failed commands?").ask()
        if not confirm:
            return

        # Group failed tasks by lesson
        all_lessons = self.loader.load_all_lessons()
        tasks_to_review = []

        for entry in failed_entries:
            lesson_id = entry["lesson_id"]
            task_id = entry["task_id"]
            
            lesson = next((l for l in all_lessons if l.id == lesson_id), None)
            if lesson:
                task = next((t for t in lesson.tasks if t.id == task_id), None)
                if task:
                    tasks_to_review.append((lesson, task))
                    
        if not tasks_to_review:
            console.print("[red]Could not load failed tasks. The source lesson files might have changed.[/]")
            return

        virtual_tasks = [item[1] for item in tasks_to_review]
        
        console.print("\n")
        console.print(Panel(
            f"[bold white]Retrying {len(virtual_tasks)} commands you previously struggled with.[/]\n\n"
            f"[dim green]Type 'hint' for a hint, 'skip' to see the explanation, or 'exit' to quit.[/]",
            title="[bold yellow]Review Mode[/]",
            border_style="yellow",
            box=box.ROUNDED
        ))

        stats = SessionStats(total_questions=len(virtual_tasks))

        for idx, (lesson, task) in enumerate(tasks_to_review, 1):
            console.print(f"\n[bold cyan]Task {idx}/{len(virtual_tasks)} [{lesson.platform}]:[/] [bold white]{task.prompt}[/]")
            
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
                    else:
                        continue

                if cleaned_input.lower() == "hint":
                    if task.hint:
                        console.print(Panel(f"[bold yellow]Hint:[/] {task.hint}", border_style="yellow", box=box.MINIMAL))
                    else:
                        console.print("[dim yellow]No hint available.[/]")
                    continue

                if cleaned_input.lower() == "skip":
                    stats.skipped_count += 1
                    stats.total_attempts += 1
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

                is_correct = validate_input(cleaned_input, task, lesson.platform)
                if is_correct:
                    stats.total_attempts += 1
                    if is_first_try:
                        stats.correct_first_try += 1
                    self.progress.record_attempt(
                        lesson_id=lesson.id,
                        platform=lesson.platform,
                        task_id=task.id,
                        is_correct=True,
                        is_first_try=is_first_try,
                        is_skipped=False
                    )
                    console.print(Panel(
                        f"[bold green]✓ Correct! (Removed from failed queue)[/]\n\n"
                        f"[bold white]Explanation:[/] {task.explanation}",
                        border_style="green",
                        box=box.ROUNDED
                    ))
                    break
                else:
                    stats.total_attempts += 1
                    is_first_try = False
                    self.progress.record_attempt(
                        lesson_id=lesson.id,
                        platform=lesson.platform,
                        task_id=task.id,
                        is_correct=False,
                        is_first_try=is_first_try,
                        is_skipped=False
                    )
                    console.print("[bold red]✗ Incorrect command. Try again, or type 'hint' / 'skip' / 'exit'.[/]")

        console.print("\n[bold green]Review Session Completed![/]\n")
        questionary.press_any_key_to_continue().ask()

    def view_stats(self):
        """Displays user stats and accuracy summary."""
        data = self.progress.data
        console.print("\n")
        
        overview = Table(title="[bold cyan]Global Performance Overview[/]", box=box.ROUNDED, border_style="cyan")
        overview.add_column("Metric", style="cyan")
        overview.add_column("Value", style="magenta")

        completed_count = len(data.get("completed_lessons", []))
        failed_count = len(data.get("failed_tasks", []))
        
        overview.add_row("Completed Lessons", str(completed_count))
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
