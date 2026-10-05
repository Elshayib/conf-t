"""Independent firewall commands and returning-Learner progress (#31).

Command expectations follow the Ubuntu UFW/iptables and firewalld manuals.
Nothing here executes firewall commands or requires an administrative host.
"""

from dataclasses import replace
from pathlib import Path

from conf_t.acceptance import validate_input
from conf_t.engine import LessonLoader
from conf_t.models import Lesson, Task
from conf_t.session import (
    ContinueTarget,
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    ReviewEntry,
    Session,
)


def firewall_lesson() -> Lesson:
    lesson = LessonLoader().get_lesson_by_id("linux_firewall")
    assert lesson is not None
    return lesson


def task_for(action: str) -> Task:
    return next(
        task for task in firewall_lesson().tasks
        if task.id == f"linux_firewall__{action}"
    )


def test_ssh_permission_is_taught_before_ufw_activation() -> None:
    task_ids = [task.id for task in firewall_lesson().tasks]
    assert task_ids.index("linux_firewall__ufw_allow_ssh") < task_ids.index(
        "linux_firewall__ufw_enable"
    )


def test_ufw_status_reads_rules_with_required_admin_access() -> None:
    task = task_for("ufw_status")
    assert validate_input("sudo ufw status", task, "Linux")
    assert validate_input("sudo ufw status verbose", task, "Linux")
    assert not validate_input("ufw status", task, "Linux")
    assert not validate_input("sudo ufw enable", task, "Linux")


def test_ssh_rule_targets_only_incoming_tcp_port_22() -> None:
    task = task_for("ufw_allow_ssh")
    for command in (
        "sudo ufw allow ssh", "sudo ufw allow 22/tcp",
        "sudo ufw allow in 22/tcp", "sudo ufw allow OpenSSH",
    ):
        assert validate_input(command, task, "Linux")
    for command in (
        "ufw allow OpenSSH", "sudo ufw allow 22", "sudo ufw allow 22/udp",
        "sudo ufw allow out 22/tcp",
    ):
        assert not validate_input(command, task, "Linux")


def test_ufw_activation_requires_elevation_and_enables_the_firewall() -> None:
    task = task_for("ufw_enable")
    assert validate_input("sudo ufw enable", task, "Linux")
    assert validate_input("sudo ufw --force enable", task, "Linux")
    assert not validate_input("ufw enable", task, "Linux")
    assert not validate_input("sudo ufw reload", task, "Linux")
    assert not validate_input("sudo ufw --dry-run enable", task, "Linux")


def test_https_rule_has_incoming_tcp_scope() -> None:
    task = task_for("ufw_allow_port")
    assert validate_input("sudo ufw allow 443/tcp", task, "Linux")
    assert validate_input("sudo ufw allow in 443/tcp", task, "Linux")
    for command in (
        "ufw allow 443/tcp", "sudo ufw allow 443", "sudo ufw allow 443/udp",
        "sudo ufw allow out 443/tcp", "sudo ufw allow 8443/tcp",
    ):
        assert not validate_input(command, task, "Linux")


def test_source_deny_rule_rejects_wrong_address_or_direction() -> None:
    task = task_for("ufw_deny_ip")
    assert validate_input("sudo ufw deny from 192.168.1.100", task, "Linux")
    assert validate_input(
        "sudo ufw deny in from 192.168.1.100 to any", task, "Linux"
    )
    for command in (
        "ufw deny from 192.168.1.100", "sudo ufw deny from 192.168.1.10",
        "sudo ufw deny out from 192.168.1.100",
        "sudo ufw deny from 192.168.1.100 to any port 22",
    ):
        assert not validate_input(command, task, "Linux")


def test_iptables_listing_is_numeric_and_includes_line_numbers() -> None:
    task = task_for("iptables_list")
    assert validate_input("sudo iptables -L -n --line-numbers", task, "Linux")
    assert validate_input(
        "sudo iptables --list --numeric --line-numbers", task, "Linux"
    )
    assert validate_input(
        "sudo iptables -t filter -n -L --line-numbers", task, "Linux"
    )
    assert validate_input(
        "sudo iptables --table=filter -n -L --line-numbers", task, "Linux"
    )
    assert validate_input("sudo iptables -nL --line-numbers", task, "Linux")
    assert not validate_input("iptables -L -n --line-numbers", task, "Linux")
    assert not validate_input("sudo iptables -L -n", task, "Linux")
    assert not validate_input(
        "sudo iptables -L INPUT -n --line-numbers", task, "Linux"
    )
    assert not validate_input(
        "sudo iptables -Ln --line-numbers", task, "Linux"
    )
    assert not validate_input(
        "sudo iptables -L --list -n --line-numbers", task, "Linux"
    )
    assert not validate_input(
        "sudo iptables -nL -L --line-numbers", task, "Linux"
    )
    assert not validate_input(
        "sudo iptables -L -n --line-numbers -L", task, "Linux"
    )


def test_iptables_http_rule_appends_to_ipv4_input_chain() -> None:
    task = task_for("iptables_allow_port")
    assert validate_input(
        "sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT", task, "Linux"
    )
    assert validate_input(
        "sudo iptables --append INPUT --protocol tcp --dport 80 --jump ACCEPT",
        task, "Linux",
    )
    for command in (
        "iptables -A INPUT -p tcp --dport 80 -j ACCEPT",
        "sudo iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT",
        "sudo iptables -A INPUT -p udp --dport 80 -j ACCEPT",
        "sudo iptables -A INPUT -p tcp --sport 80 -j ACCEPT",
        "sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT",
    ):
        assert not validate_input(command, task, "Linux")


def test_iptables_default_policy_drops_unmatched_input() -> None:
    task = task_for("iptables_drop_all")
    assert validate_input("sudo iptables -P INPUT DROP", task, "Linux")
    assert validate_input("sudo iptables --policy INPUT DROP", task, "Linux")
    for command in (
        "iptables -P INPUT DROP", "sudo iptables -P OUTPUT DROP",
        "sudo iptables -A INPUT -j DROP", "sudo iptables -P INPUT REJECT",
    ):
        assert not validate_input(command, task, "Linux")


def test_firewalld_http_service_is_saved_without_changing_runtime() -> None:
    task = task_for("firewalld_add_service")
    assert validate_input(
        "sudo firewall-cmd --permanent --add-service=http", task, "Linux"
    )
    assert validate_input(
        "sudo firewall-cmd --add-service=http --permanent", task, "Linux"
    )
    for command in (
        "firewall-cmd --permanent --add-service=http",
        "sudo firewall-cmd --add-service=http",
        "sudo firewall-cmd --permanent --add-service=https",
        "sudo firewall-cmd --reload",
    ):
        assert not validate_input(command, task, "Linux")


def test_reload_applies_saved_configuration_and_keeps_state() -> None:
    task = task_for("firewalld_reload")
    assert validate_input("sudo firewall-cmd --reload", task, "Linux")
    for command in (
        "firewall-cmd --reload", "sudo firewall-cmd --complete-reload",
        "sudo firewall-cmd --runtime-to-permanent",
        "sudo firewall-cmd --permanent --add-service=http",
        "sudo firewall-cmd --permanent --reload",
    ):
        assert not validate_input(command, task, "Linux")


def test_authorized_read_only_firewalld_state_query() -> None:
    task = task_for("firewalld_status")
    assert validate_input("firewall-cmd --state", task, "Linux")
    assert validate_input("sudo firewall-cmd --state", task, "Linux")
    assert not validate_input("firewall-cmd --reload", task, "Linux")
    assert not validate_input("firewall-cmd --STATE", task, "Linux")


def test_reload_follows_the_saved_service_configuration() -> None:
    task_ids = [task.id for task in firewall_lesson().tasks]
    save_index = task_ids.index("linux_firewall__firewalld_add_service")
    assert task_ids[save_index + 1] == "linux_firewall__firewalld_reload"


def test_returning_learner_keeps_old_passes_and_resumes_reload(
    tmp_path: Path,
) -> None:
    repaired = firewall_lesson()
    reload_id = "linux_firewall__firewalld_reload"
    old_catalog = replace(
        repaired,
        tasks=[task for task in repaired.tasks if task.id != reload_id],
    )
    progress_path = tmp_path / "progress.json"
    previous_session = Session(progress_path=progress_path)
    for task in old_catalog.tasks:
        previous_session.record_attempt(
            old_catalog, task, correct=True, first_try=True, skipped=False
        )
    old_standing = previous_session.lesson_standing(old_catalog)
    assert old_standing.status == LESSON_STATUS_COMPLETED
    assert old_standing.passed == 10

    returning = Session(progress_path=progress_path)
    standing = returning.lesson_standing(repaired)
    assert standing.status == LESSON_STATUS_IN_PROGRESS
    assert standing.passed == 10
    assert standing.total == 11
    assert [task.id for task in returning.resume_tasks(repaired)] == [
        reload_id
    ]
    assert returning.continue_target([repaired]) == ContinueTarget(
        action="lesson", lesson_id="linux_firewall"
    )
    assert returning.due_review() == []


def test_retained_failed_task_stays_addressable_for_review(
    tmp_path: Path,
) -> None:
    repaired = firewall_lesson()
    old_catalog = replace(
        repaired,
        tasks=[
            task for task in repaired.tasks
            if task.id != "linux_firewall__firewalld_reload"
        ],
    )
    progress_path = tmp_path / "progress.json"
    previous_session = Session(progress_path=progress_path)
    failed = task_for("ufw_allow_ssh")
    previous_session.record_attempt(
        old_catalog, failed, correct=False, first_try=True, skipped=False
    )
    expected_review = [ReviewEntry("linux_firewall", failed.id)]
    assert previous_session.due_review() == expected_review

    returning = Session(progress_path=progress_path)
    assert returning.due_review() == expected_review
    assert returning.failed_queue() == expected_review
    assert failed.id in [task.id for task in returning.resume_tasks(repaired)]
    reviewed_task = next(
        task for task in repaired.tasks
        if task.id == returning.due_review()[0].task_id
    )
    assert validate_input("sudo ufw allow 22/tcp", reviewed_task, "Linux")
