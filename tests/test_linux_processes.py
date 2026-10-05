"""Process, service, and scheduling commands through real Lessons (#27).

Expected command behavior comes from Bash, GNU Coreutils, Ubuntu procps,
systemd, util-linux, cron, at, and anacron manuals, not Lesson patterns.
"""

from pathlib import Path

import pytest

from conf_t.acceptance import format_display_answer, validate_input
from conf_t.engine import LessonLoader
from conf_t.models import Task


LESSONS_DIR = Path(__file__).parent.parent / "conf_t" / "lessons"


def load_task(lesson_id: str, action: str) -> Task:
    lesson = LessonLoader(LESSONS_DIR).get_lesson_by_id(lesson_id)
    assert lesson is not None
    return next(
        task for task in lesson.tasks if task.id == f"{lesson_id}__{action}"
    )


def test_timer_curriculum_builds_on_system_service_management() -> None:
    loader = LessonLoader(LESSONS_DIR)
    scheduling = loader.get_lesson_by_id("linux_cron_scheduling")
    systemd = loader.get_lesson_by_id("linux_systemd")
    assert scheduling is not None and systemd is not None
    assert systemd.id in scheduling.prerequisites


def test_sigterm_targets_only_the_requested_learner_owned_pid() -> None:
    task = load_task("linux_process_management", "kill_sigterm")
    for command in (
        "kill 5678",
        "kill -15 5678",
        "kill -TERM 5678",
        "kill -SIGTERM 5678",
        "kill -s TERM 5678",
        "kill -s SIGTERM 5678",
        "kill -s 15 5678",
        "kill -n 15 5678",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "kill 15 5678",
        "kill -9 5678",
        "kill -TERM 15 5678",
        "kill -TERM 5679",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_anacron_inspection_reads_the_existing_timestamp_file() -> None:
    task = load_task("linux_cron_scheduling", "anacron_status")
    for command in (
        "cat /var/spool/anacron/cron.daily",
        "cat -- /var/spool/anacron/cron.daily",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "cat /var/spool/anacron/cron.weekly",
        "anacron -u",
        "cat /etc/anacrontab",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_system_timer_listing_does_not_include_inactive_timers() -> None:
    task = load_task("linux_cron_scheduling", "systemctl_list_timers")
    assert not validate_input("systemctl list-timers --all", task, "Linux")
    for command in (
        "systemctl list-timers",
        "systemctl --system list-timers",
        "systemctl list-timers --state=active",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "systemctl --user list-timers",
        "systemctl list-units",
        "systemctl list-timers --state=inactive",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_at_submits_the_supplied_job_file_for_today_in_one_command() -> None:
    task = load_task("linux_cron_scheduling", "at_schedule")
    for command in (
        "at -f /home/user/backup-job.sh 14:30 today",
        "at -f /home/user/backup-job.sh 14:30",
        "at 14:30 today < /home/user/backup-job.sh",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "at 14:30",
        "at 14:30 today",
        "at -f /home/user/backup-job.sh 14:30 tomorrow",
        "at -f /home/user/other-job.sh 14:30 today",
        "sudo at -f /home/user/backup-job.sh 14:30 today",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_backup_crontab_requires_sudo_and_identifies_the_account() -> None:
    task = load_task("linux_cron_scheduling", "crontab_user")
    assert not validate_input("crontab -l -u backup", task, "Linux")
    for command in (
        "sudo crontab -l -u backup",
        "sudo crontab -u backup -l",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "sudo crontab -l",
        "crontab -l",
        "sudo crontab -e -u backup",
        "sudo crontab -l -u root",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_service_status_reads_the_system_unit_without_requiring_sudo() -> None:
    task = load_task("linux_systemd", "status_service")
    for command in (
        "systemctl status ssh",
        "systemctl status ssh.service",
        "systemctl --system status ssh.service",
        "sudo systemctl status ssh",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "systemctl --user status ssh",
        "systemctl is-active ssh",
        "systemctl status apache2",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_nginx_journal_since_local_midnight_requires_elevation() -> None:
    task = load_task("linux_systemd", "journalctl_unit")
    assert not validate_input(
        "journalctl -u nginx --since today", task, "Linux"
    )
    for command in (
        "sudo journalctl -u nginx --since today",
        "sudo journalctl -u nginx.service --since=today",
        "sudo journalctl --unit=nginx.service --since 'today'",
        'sudo journalctl --since "today" -u nginx',
        "sudo journalctl -S today --unit nginx.service",
        "sudo journalctl --since today -u nginx.service",
        "sudo journalctl --since today --unit nginx.service",
        "sudo journalctl -S today -u nginx.service",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "sudo journalctl -u nginx",
        "sudo journalctl --since today",
        "sudo journalctl -u apache2 --since today",
        "sudo journalctl -u nginx --since yesterday",
        "sudo journalctl --user -u nginx --since today",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_following_the_local_journal_requires_access_to_system_logs() -> None:
    task = load_task("linux_systemd", "journalctl_follow")
    assert not validate_input("journalctl -f", task, "Linux")
    for command in (
        "sudo journalctl -f",
        "sudo journalctl --follow",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "sudo journalctl",
        "sudo journalctl --user -f",
        "sudo journalctl -f -u nginx",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_daemon_reload_requires_system_manager_elevation() -> None:
    task = load_task("linux_systemd", "daemon_reload")
    assert not validate_input("systemctl daemon-reload", task, "Linux")
    for command in (
        "sudo systemctl daemon-reload",
        "sudo systemctl --system daemon-reload",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "sudo systemctl --user daemon-reload",
        "sudo systemctl reload nginx",
    ):
        assert not validate_input(command, task, "Linux"), command


@pytest.mark.parametrize("action, unit", [
    ("start", "nginx"), ("stop", "apache2"),
    ("restart", "mysql"), ("enable", "docker"),
])
def test_system_service_changes_require_elevation(
    action: str, unit: str
) -> None:
    task = load_task("linux_systemd", f"{action}_service")
    for command in (
        f"sudo systemctl {action} {unit}",
        f"sudo systemctl {action} {unit}.service",
        f"sudo systemctl --system {action} {unit}.service",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        f"systemctl {action} {unit}",
        f"sudo systemctl --user {action} {unit}",
        f"sudo systemctl {action} other.service",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_ps_forest_includes_parent_child_relationships() -> None:
    task = load_task("linux_process_management", "ps_tree")
    for command in (
        "ps auxf",
        "ps aux f",
        "ps aux --forest",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "ps aux",
        "ps",
        "PS auxf",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_renice_sets_the_existing_learner_owned_process_to_five() -> None:
    task = load_task("linux_process_management", "renice_pid")
    for command in (
        "renice 5 -p 4321",
        "renice 5 --pid 4321",
        "renice 5 4321",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "renice -5 -p 4321",
        "renice 5 -g 4321",
        "renice 5 -p 4322",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_nice_starts_the_available_script_with_adjustment_ten() -> None:
    task = load_task("linux_process_management", "nice_priority")
    for command in (
        "nice -n 10 backup.sh",
        "nice -n10 backup.sh",
        "nice --adjustment=10 backup.sh",
        "nice backup.sh",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "nice -n -10 backup.sh",
        "nice -n 5 backup.sh",
        "nice -n 10",
        "renice 10 backup.sh",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_pgrep_lists_only_exact_nginx_process_names() -> None:
    task = load_task("linux_process_management", "pgrep_name")
    for command in (
        "pgrep -x nginx",
        "pgrep --exact nginx",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "pgrep nginx",
        "pgrep -f nginx",
        "pkill -x nginx",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_pkill_sends_sigterm_to_exactly_named_learner_owned_workers() -> None:
    task = load_task("linux_process_management", "pkill_signal")
    for command in (
        "pkill -x stale_worker",
        "pkill --exact stale_worker",
        "pkill -TERM -x stale_worker",
        "pkill -15 -x stale_worker",
        "pkill --signal TERM --exact stale_worker",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "pkill stale_worker",
        "pkill -9 -x stale_worker",
        "pgrep -x stale_worker",
        "pkill -f stale_worker",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_sigkill_of_another_users_process_requires_sudo() -> None:
    task = load_task("linux_process_management", "kill_sigkill")
    for command in (
        "sudo kill -9 9999",
        "sudo kill -KILL 9999",
        "sudo kill -SIGKILL 9999",
        "sudo kill -s KILL 9999",
        "sudo kill -s SIGKILL 9999",
        "sudo kill -s 9 9999",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "kill -9 9999",
        "kill -SIGKILL 9999",
        "sudo kill 9 9999",
        "sudo kill 9999",
        "sudo kill -TERM 9999",
    ):
        assert not validate_input(command, task, "Linux"), command


@pytest.mark.parametrize("action, accepted, rejected", [
    ("jobs_list", ("jobs", "jobs -l"), ("sudo jobs", "jobs -r")),
    ("fg_resume", ("fg %1", "fg 1"), ("sudo fg %1", "fg %2", "bg %1")),
    ("nohup_run", ("nohup long_task.sh", "nohup long_task.sh &"),
     ("long_task.sh &", "nohup other.sh", "nohup long_task.sh > other.log")),
])
def test_process_shell_commands_fit_the_stated_job_scenario(
    action: str, accepted: tuple[str, ...], rejected: tuple[str, ...]
) -> None:
    task = load_task("linux_process_management", action)
    for command in accepted:
        assert validate_input(command, task, "Linux"), command
    for command in rejected:
        assert not validate_input(command, task, "Linux"), command


@pytest.mark.parametrize("action, command", [
    ("crontab_list", "crontab -l"),
    ("crontab_edit", "crontab -e"),
    ("crontab_remove", "crontab -r"),
    ("at_list", "atq"),
])
def test_user_scheduling_operations_do_not_select_roots_jobs(
    action: str, command: str
) -> None:
    task = load_task("linux_cron_scheduling", action)
    assert validate_input(command, task, "Linux")
    assert not validate_input(f"sudo {command}", task, "Linux")


@pytest.mark.parametrize("lesson_id, action, answer", [
    ("linux_process_management", "ps_tree", "ps auxf"),
    ("linux_process_management", "pgrep_name", "pgrep -x nginx"),
    ("linux_process_management", "pkill_signal", "pkill -x stale_worker"),
    ("linux_process_management", "kill_sigterm", "kill -15 5678"),
    ("linux_process_management", "kill_sigkill", "sudo kill -9 9999"),
    ("linux_process_management", "nice_priority", "nice -n 10 backup.sh"),
    ("linux_process_management", "renice_pid", "renice 5 -p 4321"),
    ("linux_process_management", "jobs_list", "jobs"),
    ("linux_process_management", "fg_resume", "fg %1"),
    ("linux_process_management", "nohup_run", "nohup long_task.sh"),
    ("linux_systemd", "start_service", "sudo systemctl start nginx"),
    ("linux_systemd", "stop_service", "sudo systemctl stop apache2"),
    ("linux_systemd", "restart_service", "sudo systemctl restart mysql"),
    ("linux_systemd", "enable_service", "sudo systemctl enable docker"),
    ("linux_systemd", "status_service", "systemctl status ssh"),
    ("linux_systemd", "daemon_reload", "sudo systemctl daemon-reload"),
    ("linux_systemd", "journalctl_follow", "sudo journalctl -f"),
    ("linux_systemd", "journalctl_unit",
     "sudo journalctl -u nginx --since today"),
    ("linux_cron_scheduling", "crontab_list", "crontab -l"),
    ("linux_cron_scheduling", "crontab_edit", "crontab -e"),
    ("linux_cron_scheduling", "crontab_remove", "crontab -r"),
    ("linux_cron_scheduling", "crontab_user", "sudo crontab -l -u backup"),
    ("linux_cron_scheduling", "at_schedule",
     "at -f /home/user/backup-job.sh 14:30 today"),
    ("linux_cron_scheduling", "at_list", "atq"),
    ("linux_cron_scheduling", "systemctl_list_timers",
     "systemctl list-timers"),
    ("linux_cron_scheduling", "anacron_status",
     "cat /var/spool/anacron/cron.daily"),
])
def test_skip_reveals_a_concrete_command_for_every_task(
    lesson_id: str, action: str, answer: str
) -> None:
    task = load_task(lesson_id, action)
    displayed = format_display_answer(task, "Linux")
    assert displayed == answer
    assert validate_input(displayed, task, "Linux")
