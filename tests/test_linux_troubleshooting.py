"""Troubleshooting answers at the real-Lesson command-grader seam (#32).

Command examples follow procps, iproute2, GNU, systemd, util-linux, BIND,
curl, and Ubuntu tool manuals. No diagnostic command is actually executed.
"""

from pathlib import Path

import pytest

from conf_t.acceptance import format_display_answer, validate_input
from conf_t.engine import LessonLoader
from conf_t.models import Task


LESSONS_DIR = Path(__file__).parent.parent / "conf_t" / "lessons"
LESSON_ID = "linux_troubleshooting_lab"


def load_task(action: str) -> Task:
    lesson = LessonLoader(LESSONS_DIR).get_lesson_by_id(LESSON_ID)
    assert lesson is not None
    return next(task for task in lesson.tasks
                if task.id == f"{LESSON_ID}__{action}")


def test_cpu_snapshot_is_sorted_highest_first() -> None:
    task = load_task("ps_high_cpu")
    assert not validate_input("ps aux", task, "Linux")
    for command in (
        "ps aux --sort=-%cpu",
        "ps aux --sort=-pcpu",
        "ps --sort=-%cpu aux",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "ps aux --sort=%cpu", "ps aux --sort=-%mem", "top", "ps auxf",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_route_trace_uses_installed_tool_and_exact_destination() -> None:
    task = load_task("traceroute_external")
    for command in ("traceroute 8.8.8.8", "traceroute -n 8.8.8.8",
                    "traceroute -4 8.8.8.8"):
        assert validate_input(command, task, "Linux"), command
    for command in ("traceroute 8.8.8.80", "tracepath 8.8.8.8",
                    "traceroute -I 8.8.8.8"):
        assert not validate_input(command, task, "Linux"), command


def test_log_follow_reads_protected_file_as_it_grows() -> None:
    task = load_task("tail_app_log")
    for command in ("sudo tail -f /var/log/app.log",
                    "sudo tail --follow=descriptor /var/log/app.log"):
        assert validate_input(command, task, "Linux"), command
    for command in ("tail -f /var/log/app.log", "sudo tail /var/log/app.log",
                    "sudo tail -f /var/log/other.log"):
        assert not validate_input(command, task, "Linux"), command


def test_error_search_reads_case_sensitive_matches_in_protected_log() -> None:
    task = load_task("grep_errors")
    for command in ("sudo grep FATAL /var/log/app.log",
                    "sudo grep -F 'FATAL' /var/log/app.log"):
        assert validate_input(command, task, "Linux"), command
    for command in ("grep FATAL /var/log/app.log",
                    "sudo grep -i FATAL /var/log/app.log",
                    "sudo grep ERROR /var/log/app.log",
                    "sudo grep FATAL /var/log/other.log"):
        assert not validate_input(command, task, "Linux"), command


def test_service_journal_has_required_access_unit_and_time_window() -> None:
    task = load_task("journalctl_service")
    for command in ('sudo journalctl -u nginx --since "1 hour ago"',
                    "sudo journalctl -u nginx.service -S '1 hour ago'",
                    'sudo journalctl --unit=nginx --since "1 hour ago"',
                    'sudo journalctl --since "1 hour ago" -u nginx',
                    'sudo journalctl -u nginx --since "-1h"',
                    'sudo journalctl -u nginx --since "60 minutes ago"',
                    "sudo journalctl -u nginx --since=-1h",
                    "sudo journalctl --since=-1h -u nginx"):
        assert validate_input(command, task, "Linux"), command
    for command in ('journalctl -u nginx --since "1 hour ago"',
                    'sudo journalctl -u mysql --since "1 hour ago"',
                    "sudo journalctl -u nginx -n 50",
                    'sudo journalctl -u nginx --since "2 hours ago"',
                    'sudo journalctl --user -u nginx --since "1 hour ago"'):
        assert not validate_input(command, task, "Linux"), command


def test_status_inspects_the_system_service_without_changing_it() -> None:
    task = load_task("systemctl_status")
    for command in ("systemctl status mysql", "systemctl status mysql.service",
                    "systemctl --system status mysql",
                    "sudo systemctl status mysql"):
        assert validate_input(command, task, "Linux"), command
    for command in ("systemctl --user status mysql", "systemctl restart mysql",
                    "systemctl is-active mysql", "systemctl status nginx"):
        assert not validate_input(command, task, "Linux"), command


def test_kernel_inspection_reads_last_twenty_current_buffer_lines() -> None:
    task = load_task("dmesg_kernel")
    for command in ("sudo dmesg | tail -n 20", "sudo dmesg | tail -20",
                    "sudo dmesg | tail -n20"):
        assert validate_input(command, task, "Linux"), command
    for command in ("dmesg | tail -20", "sudo dmesg", "journalctl -k",
                    "sudo dmesg | tail -n 200", "sudo dmesg -c | tail -20"):
        assert not validate_input(command, task, "Linux"), command


def test_capstone_requires_the_lessons_whose_tools_it_reuses() -> None:
    lesson = LessonLoader(LESSONS_DIR).get_lesson_by_id(LESSON_ID)
    assert lesson is not None
    assert {
        "linux_networking", "linux_process_management", "linux_systemd",
        "linux_lvm_storage", "linux_file_operations", "linux_text_processing",
    }.issubset(lesson.prerequisites)


def test_uptime_includes_load_and_elapsed_uptime() -> None:
    task = load_task("uptime_load")
    assert validate_input("uptime", task, "Linux")
    for command in ("uptime -p", "uptime -s", "hostname"):
        assert not validate_input(command, task, "Linux"), command


@pytest.mark.parametrize("action, answer", [
    ("uptime_load", "uptime"),
    ("free_memory", "free -h"),
    ("df_disk_full", "df -h"),
    ("du_find_large", "sudo du -sh /var"),
    ("find_large_logs", "sudo find /var/log -type f -size +100M"),
    ("ps_high_cpu", "ps aux --sort=-%cpu"),
    ("pgrep_stuck", "pgrep -x backup"),
    ("kill_stuck", "kill 8842"),
    ("ss_web_port", "ss -tln 'sport = :80'"),
    ("lsof_port", "sudo lsof -nP -iTCP:8080 -sTCP:LISTEN"),
    ("curl_localhost", "curl -I http://localhost"),
    ("ping_gateway", "ping -c 4 192.168.1.1"),
    ("dig_dns_fail", "dig api.example.com A"),
    ("ip_addr_check", "ip addr show"),
    ("traceroute_external", "traceroute 8.8.8.8"),
    ("tail_app_log", "sudo tail -f /var/log/app.log"),
    ("grep_errors", "sudo grep FATAL /var/log/app.log"),
    ("journalctl_service", 'sudo journalctl -u nginx --since "1 hour ago"'),
    ("systemctl_status", "systemctl status mysql"),
    ("dmesg_kernel", "sudo dmesg | tail -n 20"),
])
def test_skip_reveals_a_concrete_complete_correct_command(
    action: str, answer: str
) -> None:
    task = load_task(action)
    assert format_display_answer(task, "Linux") == answer
    assert validate_input(answer, task, "Linux")


def test_gateway_probe_has_the_requested_target_and_count() -> None:
    task = load_task("ping_gateway")
    for command in (
        "ping -c 4 192.168.1.1", "ping 192.168.1.1 -c 4",
        "ping -c4 192.168.1.1", "ping -4 -c 4 192.168.1.1",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "ping 192.168.1.1", "ping -c 40 192.168.1.1",
        "ping -c 4 8.8.8.8", "ping -c 4 192.168.1.10",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_interface_inspection_shows_addresses_without_changes() -> None:
    task = load_task("ip_addr_check")
    for command in (
        "ip addr show", "ip address show", "ip a", "ip addr",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "ip link show", "ip route show", "ip addr flush dev ens3",
        "ip addr add 192.168.1.10/24 dev ens3",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_dns_probe_queries_a_record_using_configured_resolver() -> None:
    task = load_task("dig_dns_fail")
    for command in (
        "dig api.example.com A", "dig api.example.com",
        "dig api.example.com -t A", "dig -t A api.example.com.",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "dig api.example.com AAAA", "dig example.com A",
        "dig @8.8.8.8 api.example.com A", "nslookup api.example.com",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_local_http_probe_uses_the_stated_host_protocol_and_port() -> None:
    task = load_task("curl_localhost")
    for command in (
        "curl -I http://localhost", "curl http://localhost",
        "curl --head http://localhost:80/", "curl -I http://localhost/",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "curl -I https://localhost", "curl -I http://localhost:8080",
        "curl -I http://example.com", "curl -X POST http://localhost",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_sigterm_targets_only_the_stated_learner_owned_process() -> None:
    task = load_task("kill_stuck")
    for command in (
        "kill 8842", "kill -15 8842", "kill -TERM 8842",
        "kill -s SIGTERM 8842", "kill -n 15 8842",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "kill 15 8842", "kill -9 8842", "kill 8843", "kill 8842 8843",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_stuck_process_lookup_matches_the_exact_visible_name() -> None:
    task = load_task("pgrep_stuck")
    for command in ("pgrep -x backup", "pgrep --exact backup"):
        assert validate_input(command, task, "Linux"), command
    for command in ("pgrep backup", "pgrep -f backup", "pkill -x backup"):
        assert not validate_input(command, task, "Linux"), command


@pytest.mark.parametrize("action, canonical, equivalent, wrong", [
    ("free_memory", "free -h", "free --human", "free -b"),
    ("df_disk_full", "df -h", "df --human-readable", "df -i"),
])
def test_system_capacity_is_reported_in_human_readable_units(
    action: str, canonical: str, equivalent: str, wrong: str
) -> None:
    task = load_task(action)
    assert validate_input(canonical, task, "Linux")
    assert validate_input(equivalent, task, "Linux")
    assert not validate_input(wrong, task, "Linux")


def test_large_log_search_selects_regular_files_over_one_hundred_mib() -> None:
    task = load_task("find_large_logs")
    for command in (
        "sudo find /var/log -type f -size +100M",
        "sudo find /var/log -size +100M -type f",
        "sudo find /var/log -type f -size +104857600c",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "find /var/log -type f -size +100M",
        "sudo find /var/log -size +100M",
        "sudo find /var/log -type d -size +100M",
        "sudo find /var/log -type f -size 100M",
        "sudo find /var/log -type f -size +100000000c",
        "sudo find /var/log -type f -size +100M -delete",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_directory_usage_can_traverse_protected_subdirectories() -> None:
    task = load_task("du_find_large")
    for command in (
        "sudo du -sh /var", "sudo du -hs /var",
        "sudo du -h -s /var",
        "sudo du --summarize --human-readable /var",
        "sudo du --human-readable --summarize /var",
        "sudo du -s --human-readable /var",
        "sudo du --human-readable -s /var",
        "sudo du --summarize -h /var",
        "sudo du -h --summarize /var",
        "sudo du -h --max-depth=0 /var",
        "sudo du --max-depth=0 -h /var",
        "sudo du -d 0 -h /var",
        "sudo du -h -d 0 /var",
        "sudo du -d0 -h /var",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "du -sh /var", "sudo du -h /var", "sudo du -sh /var/log",
        "sudo du -sb /var",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_lsof_identifies_tcp_listener_owners_with_elevation() -> None:
    task = load_task("lsof_port")
    for command in (
        "sudo lsof -nP -iTCP:8080 -sTCP:LISTEN",
        "sudo lsof -iTCP:8080 -sTCP:LISTEN",
        "sudo lsof -i TCP:8080 -sTCP:LISTEN",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "lsof -iTCP:8080 -sTCP:LISTEN",
        "sudo lsof -i :8080",
        "sudo lsof -iTCP:8080",
        "sudo lsof -iUDP:8080",
        "sudo lsof -iTCP:8080 -sTCP:ESTABLISHED",
        "sudo lsof -iTCP:80 -sTCP:LISTEN",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_web_socket_check_filters_exact_local_tcp_listening_port() -> None:
    task = load_task("ss_web_port")
    assert not validate_input("ss -tlnp | grep :80", task, "Linux")
    for command in (
        "ss -tln 'sport = :80'",
        'ss -ltn "sport = :80"',
        "ss -tn state listening 'sport = :80'",
        "ss -tln sport = :80",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "ss -tln 'sport = :8080'",
        "ss -tln 'dport = :80'",
        "ss -tn 'sport = :80'",
        "ss -uln 'sport = :80'",
        "ss -tln",
        "netstat -tlnp | grep :80",
    ):
        assert not validate_input(command, task, "Linux"), command
