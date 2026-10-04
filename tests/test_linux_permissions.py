"""Permissions and accounts through the real Lesson command grader (#26).

Command literals come from GNU, Bash, Ubuntu and systemd manuals, rather
than the catalog's answer patterns. Commands are validated, never executed.
"""

import pytest

from conf_t.engine import LessonLoader, validate_input
from conf_t.models import Task


def task_for(lesson_id: str, action: str) -> Task:
    lesson = LessonLoader().get_lesson_by_id(lesson_id)
    assert lesson is not None
    return next(
        task for task in lesson.tasks
        if task.id == f"{lesson_id}__{action}"
    )


def test_ownership_change_requires_elevation() -> None:
    task = task_for("linux_advanced", "chown_owner")
    assert validate_input("sudo chown root:root file.txt", task, "Linux")
    assert not validate_input("chown root:root file.txt", task, "Linux")
    assert not validate_input("sudo chown root file.txt", task, "Linux")


def test_owner_only_change_preserves_group() -> None:
    task = task_for("linux_permissions_deep", "chown_user")
    assert validate_input("sudo chown www-data app.log", task, "Linux")
    assert not validate_input("chown www-data app.log", task, "Linux")
    assert not validate_input("sudo chown www-data: app.log", task, "Linux")


def test_group_change_reaches_root_owned_descendants() -> None:
    task = task_for("linux_permissions_deep", "chgrp_change")
    assert validate_input("sudo chgrp -R developers shared_dir", task, "Linux")
    assert validate_input(
        "sudo chgrp --recursive developers shared_dir", task, "Linux"
    )
    assert not validate_input("chgrp -R developers shared_dir", task, "Linux")
    assert not validate_input(
        "sudo chgrp developers shared_dir", task, "Linux"
    )


def test_system_journal_is_followed_with_admin_access() -> None:
    task = task_for("linux_advanced", "journalctl_logs")
    assert validate_input("sudo journalctl -f", task, "Linux")
    assert validate_input("sudo journalctl --follow", task, "Linux")
    assert not validate_input("journalctl -f", task, "Linux")
    assert not validate_input("tail -f /var/log/syslog", task, "Linux")
    assert not validate_input("sudo journalctl", task, "Linux")


def test_root_owned_executable_needs_sudo_for_suid() -> None:
    task = task_for("linux_permissions_deep", "chmod_suid")
    assert validate_input(
        "sudo chmod 4755 /usr/local/bin/backup_tool", task, "Linux"
    )
    assert not validate_input(
        "chmod 4755 /usr/local/bin/backup_tool", task, "Linux"
    )
    assert not validate_input(
        "sudo chmod 2755 /usr/local/bin/backup_tool", task, "Linux"
    )


def test_root_owned_shared_directory_needs_sudo_for_sticky_mode() -> None:
    task = task_for("linux_permissions_deep", "chmod_sticky")
    assert validate_input("sudo chmod 1777 /tmp/shared", task, "Linux")
    assert not validate_input("chmod 1777 /tmp/shared", task, "Linux")
    assert not validate_input("sudo chmod 777 /tmp/shared", task, "Linux")


@pytest.mark.parametrize(
    "action, command",
    [
        ("useradd_create", "useradd -m -s /bin/bash jsmith"),
        ("usermod_groups", "usermod -a -G docker jsmith"),
        ("userdel_remove", "userdel -r tempuser"),
        ("passwd_set", "passwd jsmith"),
        ("groupadd_create", "groupadd -g 1500 developers"),
        ("groupmod_name", "groupmod --new-name newteam oldteam"),
    ],
)
def test_account_administration_rejects_unprivileged_aliases(
    action: str, command: str,
) -> None:
    task = task_for("linux_users_groups", action)
    assert not validate_input(command, task, "Linux")
    assert validate_input(f"sudo {command}", task, "Linux")


def test_process_snapshot_uses_ps_not_an_interactive_monitor() -> None:
    task = task_for("linux_advanced", "ps_aux")
    assert validate_input("ps aux", task, "Linux")
    assert validate_input("ps -ef", task, "Linux")
    assert not validate_input("top", task, "Linux")
    assert not validate_input("htop", task, "Linux")
    assert not validate_input("ps", task, "Linux")


def test_force_kill_accepts_bash_signal_spellings_for_owned_process() -> None:
    task = task_for("linux_advanced", "kill_process")
    for command in ("kill -9 1234", "kill -KILL 1234", "kill -s SIGKILL 1234"):
        assert validate_input(command, task, "Linux")
    for command in ("kill 9 1234", "kill 1234", "kill -15 1234"):
        assert not validate_input(command, task, "Linux")


def test_named_user_acl_accepts_equivalent_permission_spellings() -> None:
    task = task_for("linux_permissions_deep", "setfacl_user")
    assert validate_input("setfacl -m u:alice:rw project.txt", task, "Linux")
    assert validate_input(
        "setfacl --modify user:alice:rw- project.txt", task, "Linux"
    )
    assert not validate_input(
        "setfacl -m u:alice:rwx project.txt", task, "Linux"
    )
    assert not validate_input(
        "setfacl -m g:alice:rw project.txt", task, "Linux"
    )


@pytest.mark.parametrize(
    "lesson_id, action, accepted, rejected",
    [
        (
            "linux_advanced", "chmod_permissions",
            "chmod 755 script.sh", "chmod 775 script.sh",
        ),
        ("linux_advanced", "ping_test", "ping -c 4 8.8.8.8", "ping 8.8.8.8"),
        (
            "linux_permissions_deep", "chmod_symbolic_add",
            "chmod g+x deploy.sh", "chmod +x deploy.sh",
        ),
        (
            "linux_permissions_deep", "chmod_symbolic_remove",
            "chmod o-w secret.conf", "chmod a-w secret.conf",
        ),
        (
            "linux_permissions_deep", "chmod_octal_640",
            "chmod 640 database.conf", "chmod 644 database.conf",
        ),
        ("linux_permissions_deep", "umask_value", "umask", "umask 022"),
        (
            "linux_permissions_deep", "getfacl_view",
            "getfacl project.txt", "getfacl other.txt",
        ),
        ("linux_users_groups", "id_user", "id jsmith", "id"),
        ("linux_users_groups", "groups_list", "groups", "groups jsmith"),
    ],
)
def test_independent_permission_and_identity_targets(
    lesson_id: str, action: str, accepted: str, rejected: str,
) -> None:
    task = task_for(lesson_id, action)
    assert validate_input(accepted, task, "Linux")
    assert not validate_input(rejected, task, "Linux")
    assert not validate_input(accepted.upper(), task, "Linux")


def test_group_append_does_not_replace_existing_memberships() -> None:
    task = task_for("linux_users_groups", "usermod_groups")
    assert validate_input(
        "sudo usermod --append --groups docker jsmith", task, "Linux"
    )
    assert not validate_input("sudo usermod -G docker jsmith", task, "Linux")
    assert not validate_input("sudo usermod -g docker jsmith", task, "Linux")


def test_bash_signal_names_are_case_insensitive_but_command_is_not() -> None:
    task = task_for("linux_advanced", "kill_process")
    assert validate_input("kill -s sigkill 1234", task, "Linux")
    assert not validate_input("KILL -s SIGKILL 1234", task, "Linux")
