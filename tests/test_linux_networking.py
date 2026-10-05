"""Networking commands via real Lessons and the grader (#28).

Literal commands follow Ubuntu/iproute2, curl, ISC BIND and iputils manuals.
No networking command is executed; teaching scenarios are reviewed separately.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conf_t.engine import format_display_answer, validate_input
from conf_t.models import Lesson, Task

LESSON_PATH = (
    Path(__file__).parent.parent / "conf_t/lessons/linux_networking.json"
)


def _task(action: str) -> Task:
    lesson = Lesson.from_dict(
        json.loads(LESSON_PATH.read_text(encoding="utf-8"))
    )
    return next(
        task for task in lesson.tasks
        if task.id == f"linux_networking__{action}"
    )


def test_ip_displays_addresses_for_every_interface() -> None:
    task = _task('ip_addr_show')
    for command in (
        'ip addr show',
        'ip address show',
        'ip address',
        'ip a',
        'ip addr list',
        'ip -br address show',
        'ip -o addr',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'ip link show',
        'ip addr show dev eth0',
        'ip -4 addr show',
        'IP addr show',
        'ip addr flush dev eth0',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_ip_enables_the_exact_interface_with_elevation() -> None:
    task = _task('ip_link_up')
    for command in (
        'sudo ip link set eth0 up',
        'sudo ip link set dev eth0 up',
        'sudo -u root ip link set eth0 up',
        'sudo -- ip link set dev "eth0" up',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'ip link set eth0 up',
        'sudo ip link set eth1 up',
        'sudo ip link set eth0 down',
        'sudo -u nobody ip link set eth0 up',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_ip_lists_the_ipv4_main_routing_table() -> None:
    task = _task('ip_route_show')
    for command in (
        'ip route show',
        'ip route',
        'ip -4 route show',
        'ip route list table main',
        'ip route show table 254',
        'ip -family inet route show table main',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'route -n',
        'ip -6 route show',
        'ip route show table local',
        'ip route get 8.8.8.8',
        'ip route show dev eth0',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_ss_lists_tcp_listeners_and_other_users_processes() -> None:
    task = _task('ss_listening')
    for command in (
        'sudo ss -tlnp',
        'sudo ss -plnt',
        'sudo ss -t -l -n -p',
        'sudo ss --tcp --listening --numeric --processes',
        'sudo --user=root ss -n --processes -lt',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'ss -tlnp',
        'sudo ss -ulnp',
        'sudo ss -tnp',
        'sudo ss -tln',
        'sudo ss -tlnp sport = :22',
        'sudo ss -tlnp -6',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_netstat_lists_only_numeric_tcp_listeners() -> None:
    task = _task('netstat_listening')
    for command in (
        'netstat -tln',
        'netstat -nlt',
        'netstat -t -l -n',
        'netstat --tcp --listening --numeric',
        'netstat --numeric -lt',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'netstat -uln',
        'netstat -tn',
        'netstat -tl',
        'netstat -tlan',
        'ss -tln',
        'netstat -tln -6',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_curl_fetches_headers_using_head_for_exact_https_url() -> None:
    task = _task('curl_headers')
    for command in (
        'curl -I https://example.com',
        'curl --head https://example.com',
        'curl https://example.com -I',
        'curl -I "https://example.com/"',
        'curl --head --url https://example.com',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'curl https://example.com',
        'curl -i https://example.com',
        'curl -X HEAD https://example.com',
        'curl -I http://example.com',
        'curl -I https://example.net',
        'curl -I https://example.com/path',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_curl_downloads_the_exact_archive_to_requested_file() -> None:
    task = _task('curl_download')
    for command in (
        'curl -o app.tar.gz https://releases.example.com/app.tar.gz',
        'curl https://releases.example.com/app.tar.gz --output=app.tar.gz',
        'curl --output ./app.tar.gz "https://releases.example.com/app.tar.gz"',
        'curl -o/home/user/app.tar.gz https://releases.example.com/app.tar.gz',
        'curl -O https://releases.example.com/app.tar.gz',
        'curl https://releases.example.com/app.tar.gz > app.tar.gz',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'curl https://releases.example.com/app.tar.gz',
        'curl -o other.tar.gz https://releases.example.com/app.tar.gz',
        'curl -o app.tar.gz https://releases.example.com/other.tar.gz',
        'curl -o app.tar.gz http://releases.example.com/app.tar.gz',
        'curl -I -o app.tar.gz https://releases.example.com/app.tar.gz',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_dig_queries_mx_for_the_exact_domain() -> None:
    task = _task('dig_mx')
    for command in (
        'dig example.com MX',
        'dig MX example.com',
        'dig -t MX example.com',
        'dig example.com -t MX',
        'dig -q example.com -t MX',
        'dig "example.com." mx',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'dig example.com A',
        'dig example.com',
        'dig example.net MX',
        'dig -x example.com',
        'host -t MX example.com',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_dig_shows_short_a_answers_for_the_exact_domain() -> None:
    task = _task('dig_short')
    for command in (
        'dig +short google.com',
        'dig +short google.com A',
        'dig google.com A +short',
        'dig google.com +short',
        'dig -t A google.com +short',
        'dig +short -q "google.com." -t A',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'dig google.com A',
        'dig +short google.com AAAA',
        'dig +short example.com A',
        'dig +short google.com MX',
        'dig +short google.com +noshort',
        'dig +short google.com example.com',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_traceroute_uses_default_udp_probes_for_exact_ipv4_host() -> None:
    task = _task('traceroute_host')
    for command in (
        'traceroute 8.8.8.8',
        'traceroute -4 8.8.8.8',
        'traceroute -n 8.8.8.8',
        'traceroute -4n "8.8.8.8"',
        'traceroute -M default 8.8.8.8',
        'traceroute --module=default -n 8.8.8.8',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'tracepath 8.8.8.8',
        'traceroute 8.8.4.4',
        'traceroute -6 8.8.8.8',
        'traceroute -I 8.8.8.8',
        'traceroute -T 8.8.8.8',
        'traceroute -U 8.8.8.8',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_hostname_displays_the_resolver_canonical_fqdn() -> None:
    task = _task('hostname_fqdn')
    for command in (
        'hostname -f',
        'hostname --fqdn',
        'hostname --long',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'hostname',
        'hostname -s',
        'hostname -d',
        'hostname -A',
        'hostname -F /etc/hostname',
        'HOSTNAME -f',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_ping_limits_exact_ipv4_target_to_three_echo_requests() -> None:
    task = _task('ping_count')
    for command in (
        'ping -c 3 1.1.1.1',
        'ping 1.1.1.1 -c 3',
        'ping -c3 1.1.1.1',
        'ping -4 -n -c 3 "1.1.1.1"',
        'ping -n 1.1.1.1 -c3',
        'ping -nc3 1.1.1.1',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'ping -c 4 1.1.1.1',
        'ping -c 30 1.1.1.1',
        'ping -c 3 1.0.0.1',
        'ping 1.1.1.1',
        'ping -6 -c 3 1.1.1.1',
        'ping -c 3 -w 1 1.1.1.1',
        'ping -c 3 1.1.1.1 8.8.8.8',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_ss_can_select_listeners_with_a_state_filter() -> None:
    task = _task('ss_listening')
    for command in (
        'sudo ss -tnp state listening',
        'sudo ss --processes --numeric --tcp state listening',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'sudo ss -tnp state established',
        'sudo ss -tnp state all',
        'sudo ss -unp state listening',
        'sudo ss -tn state listening',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_dig_accepts_explicit_name_and_mx_type_in_either_order() -> None:
    task = _task('dig_mx')
    for command in (
        'dig -t MX -q example.com',
        'dig -q example.com -tMX',
        'dig -tMX -q "example.com."',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'dig -t A -q example.com',
        'dig -t MX -q example.net',
        'dig -t MX -q example.com -p 5353',
    ):
        assert not validate_input(command, task, "Linux"), command


@pytest.mark.parametrize(
    ("action", "command"),
    (
        ("ip_addr_show", "ip addr show"),
        ("ip_link_up", "sudo ip link set eth0 up"),
        ("ip_route_show", "ip route show"),
        ("ss_listening", "sudo ss -tlnp"),
        ("netstat_listening", "netstat -tln"),
        ("curl_headers", "curl -I https://example.com"),
        (
            "curl_download",
            "curl -o app.tar.gz https://releases.example.com/app.tar.gz",
        ),
        ("dig_mx", "dig example.com MX"),
        ("dig_short", "dig +short google.com A"),
        ("traceroute_host", "traceroute 8.8.8.8"),
        ("hostname_fqdn", "hostname -f"),
        ("ping_count", "ping -c 3 1.1.1.1"),
    ),
)
def test_reveal_is_a_concrete_accepted_command(
    action: str, command: str
) -> None:
    task = _task(action)
    assert format_display_answer(task, "Linux") == command
    assert validate_input(command, task, "Linux")
