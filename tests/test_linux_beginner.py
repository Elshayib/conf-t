"""Beginner Linux commands through loaded Lessons and the grader (#25).

Command literals follow GNU manuals and Ubuntu's APT documentation; no shell
commands are executed. Scenarios and teaching prose are reviewed separately.
"""

from __future__ import annotations

import pytest

from conf_t.catalog import Catalog
from conf_t.acceptance import format_display_answer, validate_input
from conf_t.models import Lesson, Task


def _lesson(lesson_id: str) -> Lesson:
    lesson = Catalog().get_lesson_by_id(lesson_id)
    assert lesson is not None
    return lesson


def _task(task_id: str) -> Task:
    lesson = _lesson(task_id.split("__")[0])
    return next(task for task in lesson.tasks if task.id == task_id)


def test_cut_selects_colon_fields_with_separate_arguments() -> None:
    task = _task("linux_text_processing__cut_fields")
    for command in (
        "cut -d: -f1,3 /etc/passwd",
        "cut -d ':' -f 1,3 /etc/passwd",
        "cut -f 1,3 -d : /etc/passwd",
        "cut --delimiter=: --fields=1,3 /etc/passwd",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "cut -d:-f1,3 /etc/passwd",
        "cut -d: -f1,2 /etc/passwd",
        "cut -d, -f1,3 /etc/passwd",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_awk_reads_comma_fields_without_bash_expansion() -> None:
    task = _task("linux_text_processing__awk_print_column")
    for command in (
        "awk -F, '{print $3}' users.csv",
        "awk -F ',' '{ print $3 }' users.csv",
        'awk -F, "{print \\$3}" users.csv',
        "awk -v FS=, '{print $3}' users.csv",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'awk "{print $3}" users.csv',
        'awk -F, "{print $3}" users.csv',
        "awk '{print $3}' users.csv",
        "awk -F, '{print $2}' users.csv",
        "awk -F: '{print $3}' users.csv",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_pwd_prints_the_current_absolute_path() -> None:
    task = _task('linux_basic__pwd')
    for command in (
        'pwd',
        'pwd -P',
        'pwd -L',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'PWD',
        'cd /home/user',
        'pwd /home/user',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_ls_lists_all_entries_in_long_format() -> None:
    task = _task('linux_basic__ls_la')
    for command in (
        'ls -la',
        'ls -al',
        'ls -l -a',
        'ls -a -l',
        'ls -l --all',
        'ls --all -l .',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'ls -l',
        'ls -a',
        'ls -lA',
        'ls -ld',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_mkdir_creates_the_named_subdirectory() -> None:
    task = _task('linux_basic__mkdir')
    for command in (
        'mkdir backups',
        'mkdir -- backups',
        "mkdir 'backups'",
        'mkdir ./backups',
        'mkdir -p backups',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'mkdir backup',
        'rmdir backups',
        'mkdir /backups',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_cd_changes_this_shell_to_the_absolute_log_directory() -> None:
    task = _task('linux_basic__cd_var_log')
    for command in (
        'cd /var/log',
        'cd -- /var/log',
        "cd '/var/log'",
        'cd -P /var/log',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'cd var/log',
        'pwd /var/log',
        'sudo cd /var/log',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_cat_prints_the_complete_log_without_pagination() -> None:
    task = _task('linux_basic__cat_syslog')
    for command in (
        'cat syslog',
        'cat -- syslog',
        'cat ./syslog',
        'cat /var/log/syslog',
        "cat 'syslog'",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'less syslog',
        'more syslog',
        'cat -n syslog',
        'cat messages',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_rm_removes_the_disposable_directory_without_confirmation() -> None:
    task = _task('linux_basic__rm_rf_temp')
    for command in (
        'rm -rf temp',
        'rm -fr temp',
        'rm -r -f temp',
        'rm --recursive --force temp',
        'rm -f -R ./temp',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'rm temp',
        'rm -r temp',
        'rm -rf backups',
        'rmdir temp',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_grep_matches_the_case_sensitive_substring() -> None:
    task = _task('linux_text_processing__grep_error')
    for command in (
        'grep ERROR app.log',
        "grep 'ERROR' app.log",
        'grep -F ERROR app.log',
        'grep -e ERROR app.log',
        'grep --regexp=ERROR app.log',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'grep -i ERROR app.log',
        'grep -v ERROR app.log',
        'grep error app.log',
        'grep -w ERROR app.log',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_head_then_tail_read_the_same_original_file() -> None:
    task = _task('linux_text_processing__head_tail')
    for command in (
        'head -n 10 server.log; tail -n 5 server.log',
        'head -10 server.log; tail -5 server.log',
        'head server.log; tail --lines=5 server.log',
        '{ head -n10 server.log; tail -n5 server.log; }',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'head -n 5 server.log; tail -n 10 server.log',
        'head -n 10 server.log | tail -n 5',
        'head -n 10 server.log; tail server.log',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_sed_replaces_only_the_first_match_without_editing_the_file() -> None:
    task = _task('linux_text_processing__sed_substitute')
    for command in (
        "sed 's/localhost/127.0.0.1/' hosts.txt",
        'sed "s/localhost/127.0.0.1/" hosts.txt',
        "sed -e 's/localhost/127.0.0.1/' hosts.txt",
        "sed 's#localhost#127.0.0.1#' hosts.txt",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        "sed -i 's/localhost/127.0.0.1/' hosts.txt",
        "sed 's/localhost/127.0.0.1/g' hosts.txt",
        "sed -n 's/localhost/127.0.0.1/' hosts.txt",
    ):
        assert not validate_input(command, task, "Linux"), command


def test_sort_preserves_duplicates_in_descending_numeric_order() -> None:
    task = _task('linux_text_processing__sort_numeric')
    for command in (
        'sort -rn scores.txt',
        'sort -nr scores.txt',
        'sort -n -r scores.txt',
        'sort --reverse --numeric-sort scores.txt',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'sort -r scores.txt',
        'sort -n scores.txt',
        'sort -u scores.txt',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_uniq_counts_adjacent_case_sensitive_duplicates() -> None:
    task = _task('linux_text_processing__uniq_count')
    for command in (
        'uniq -c access.log',
        'uniq --count access.log',
        'uniq -c < access.log',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'uniq access.log',
        'uniq -d access.log',
        'uniq -c -i access.log',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_wc_counts_newlines_instead_of_words_or_bytes() -> None:
    task = _task('linux_text_processing__wc_lines')
    for command in (
        'wc -l document.txt',
        'wc --lines document.txt',
        'wc -l < document.txt',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'wc -w document.txt',
        'wc -c document.txt',
        'wc document.txt',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_cp_copies_the_file_into_the_existing_directory() -> None:
    task = _task('linux_file_operations__cp_file')
    for command in (
        'cp report.txt /home/user/backups/',
        'cp -- report.txt /home/user/backups',
        'cp report.txt /home/user/backups/report.txt',
        'cp -t /home/user/backups report.txt',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'mv report.txt /home/user/backups/',
        'cp report.txt /home/user/',
        'cp /home/user/backups/report.txt report.txt',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_mv_renames_without_leaving_a_copy() -> None:
    task = _task('linux_file_operations__mv_rename')
    for command in (
        'mv draft.txt final.txt',
        'mv -- draft.txt final.txt',
        "mv 'draft.txt' 'final.txt'",
        'mv -T draft.txt final.txt',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'cp draft.txt final.txt',
        'mv final.txt draft.txt',
        'mv draft.txt /final.txt',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_touch_creates_or_updates_both_timestamps() -> None:
    task = _task('linux_file_operations__touch_file')
    for command in (
        'touch notes.txt',
        'touch -- notes.txt',
        "touch 'notes.txt'",
        'touch ./notes.txt',
        'touch -am notes.txt',
        'touch -a -m notes.txt',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'touch -c notes.txt',
        'touch -a notes.txt',
        'touch -m notes.txt',
        'mkdir notes.txt',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_ln_creates_a_symbolic_link_to_the_specified_target() -> None:
    task = _task('linux_file_operations__ln_symlink')
    for command in (
        'ln -s /etc/nginx/nginx.conf config_link',
        'ln --symbolic /etc/nginx/nginx.conf config_link',
        "ln -s '/etc/nginx/nginx.conf' 'config_link'",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'ln /etc/nginx/nginx.conf config_link',
        'ln -s config_link /etc/nginx/nginx.conf',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_find_matches_only_regular_files_with_the_exact_name() -> None:
    task = _task('linux_file_operations__find_name')
    for command in (
        "find /var -type f -name 'error.log'",
        'find /var -name error.log -type f',
        'find /var -type f -name "error.log" -print',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'find /var -name error.log',
        'find /var -type d -name error.log',
        'find /var -type f -iname error.log',
        'find /var -type f -name "*.log"',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_tar_creates_a_gzip_compressed_archive() -> None:
    task = _task('linux_file_operations__tar_create')
    for command in (
        'tar -czf project.tar.gz project',
        'tar czf project.tar.gz project',
        'tar -zcf project.tar.gz project',
        'tar --create --gzip --file=project.tar.gz project',
        'tar -c -z -f project.tar.gz project',
        'tar -caf project.tar.gz project',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'tar -cf project.tar.gz project',
        'tar -xzf project.tar.gz project',
        'tar -cjf project.tar.gz project',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_gzip_replaces_the_original_with_compressed_output() -> None:
    task = _task('linux_file_operations__gzip_file')
    for command in (
        'gzip data.csv',
        'gzip -- data.csv',
        'gzip -9 data.csv',
        'gzip --best data.csv',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'gzip -c data.csv',
        'gzip -k data.csv',
        'gzip -d data.csv',
        'gzip -l data.csv',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_rsync_copies_contents_and_keeps_destination_only_files() -> None:
    task = _task('linux_file_operations__rsync_copy')
    for command in (
        'rsync -a src/ dest/',
        'rsync --archive src/ dest/',
        'rsync -av src/ dest/',
        'rsync -rltpgoD src/ dest/',
        'rsync -a src/ dest',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'rsync -a src dest/',
        'rsync -r src/ dest/',
        'rsync -a --delete src/ dest/',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_apt_refreshes_the_index_with_elevation() -> None:
    task = _task('linux_package_management__apt_update')
    for command in (
        'sudo apt update',
        'sudo -- apt update',
        'sudo -u root apt update',
        'sudo apt -q update',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'apt update',
        'sudo apt upgrade',
        'sudo apt-get update',
        'sudo -u user apt update',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_apt_upgrades_without_package_removal() -> None:
    task = _task('linux_package_management__apt_upgrade')
    for command in (
        'sudo apt upgrade',
        'sudo apt -y upgrade',
        'sudo apt upgrade --assume-yes',
        'sudo -u root apt upgrade',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'apt upgrade',
        'sudo apt update',
        'sudo apt full-upgrade',
        'sudo apt --simulate upgrade',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_apt_installs_the_named_package_with_elevation() -> None:
    task = _task('linux_package_management__apt_install')
    for command in (
        'sudo apt install htop',
        'sudo apt -y install htop',
        'sudo apt install -y htop',
        'sudo apt install htop --yes',
        "sudo apt install 'htop'",
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'apt install htop',
        'sudo apt remove htop',
        'sudo apt download htop',
        'sudo apt --simulate install htop',
        'sudo apt install htop-',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_apt_removes_the_package_while_retaining_configuration() -> None:
    task = _task('linux_package_management__apt_remove')
    for command in (
        'sudo apt remove apache2',
        "sudo apt remove 'apache2'",
        'sudo apt remove -y apache2',
        'sudo apt -y remove apache2',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'apt remove apache2',
        'sudo apt purge apache2',
        'sudo apt remove --purge apache2',
        'sudo apt install apache2',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_apt_purges_the_package_and_packaged_configuration() -> None:
    task = _task('linux_package_management__apt_purge')
    for command in (
        'sudo apt purge apache2',
        'sudo apt purge -y apache2',
        'sudo apt remove --purge apache2',
        'sudo apt --purge remove apache2',
        'sudo apt remove apache2 --purge',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'apt purge apache2',
        'sudo apt remove apache2',
        'sudo apt clean',
        'sudo apt autoremove',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_apt_searches_names_and_descriptions_read_only() -> None:
    task = _task('linux_package_management__apt_search')
    for command in (
        'apt search nginx',
        "apt search 'nginx'",
        'sudo apt search nginx',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'apt show nginx',
        'apt install nginx',
        'apt search --names-only nginx',
        'apt-cache search nginx',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_apt_displays_package_metadata_without_changing_packages() -> None:
    task = _task('linux_package_management__apt_show')
    for command in (
        'apt show curl',
        "apt show 'curl'",
        'sudo apt show curl',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'apt search curl',
        'apt list curl',
        'apt install curl',
        'apt-cache show curl',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_apt_removes_unused_dependencies_with_elevation() -> None:
    task = _task('linux_package_management__apt_autoremove')
    for command in (
        'sudo apt autoremove',
        'sudo apt -y autoremove',
        'sudo apt autoremove --yes',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'apt autoremove',
        'sudo apt clean',
        'sudo apt remove',
        'sudo apt autoremove --purge',
        'sudo apt --simulate autoremove',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_copy_destination_file_does_not_accept_a_directory_suffix() -> None:
    task = _task("linux_file_operations__cp_file")
    assert not validate_input(
        "cp report.txt /home/user/backups/report.txt/", task, "Linux"
    )


def test_symlink_points_to_the_exact_regular_file_path() -> None:
    task = _task("linux_file_operations__ln_symlink")
    assert not validate_input(
        "ln -s /etc/nginx/nginx.conf/ config_link", task, "Linux"
    )


@pytest.mark.parametrize(
    ("task_id", "command"),
    [
        ("linux_basic__pwd", "pwd"),
        ("linux_basic__ls_la", "ls -la"),
        ("linux_basic__mkdir", "mkdir backups"),
        ("linux_basic__cd_var_log", "cd /var/log"),
        ("linux_basic__cat_syslog", "cat syslog"),
        ("linux_basic__rm_rf_temp", "rm -rf temp"),
        (
            "linux_file_operations__cp_file",
            "cp report.txt /home/user/backups/",
        ),
        ("linux_file_operations__mv_rename", "mv draft.txt final.txt"),
        ("linux_file_operations__touch_file", "touch notes.txt"),
        (
            "linux_file_operations__ln_symlink",
            "ln -s /etc/nginx/nginx.conf config_link",
        ),
        (
            "linux_file_operations__find_name",
            "find /var -type f -name 'error.log'",
        ),
        (
            "linux_file_operations__tar_create",
            "tar -czf project.tar.gz project",
        ),
        ("linux_file_operations__gzip_file", "gzip data.csv"),
        ("linux_file_operations__rsync_copy", "rsync -a src/ dest/"),
        ("linux_text_processing__grep_error", "grep ERROR app.log"),
        (
            "linux_text_processing__head_tail",
            "head -n 10 server.log; tail -n 5 server.log",
        ),
        (
            "linux_text_processing__sed_substitute",
            "sed 's/localhost/127.0.0.1/' hosts.txt",
        ),
        (
            "linux_text_processing__awk_print_column",
            "awk -F, '{print $3}' users.csv",
        ),
        (
            "linux_text_processing__cut_fields",
            "cut -d: -f1,3 /etc/passwd",
        ),
        ("linux_text_processing__sort_numeric", "sort -rn scores.txt"),
        ("linux_text_processing__uniq_count", "uniq -c access.log"),
        ("linux_text_processing__wc_lines", "wc -l document.txt"),
        ("linux_package_management__apt_update", "sudo apt update"),
        ("linux_package_management__apt_upgrade", "sudo apt upgrade"),
        (
            "linux_package_management__apt_install",
            "sudo apt install htop",
        ),
        (
            "linux_package_management__apt_remove",
            "sudo apt remove apache2",
        ),
        (
            "linux_package_management__apt_purge",
            "sudo apt purge apache2",
        ),
        ("linux_package_management__apt_search", "apt search nginx"),
        ("linux_package_management__apt_show", "apt show curl"),
        (
            "linux_package_management__apt_autoremove",
            "sudo apt autoremove",
        ),
    ],
)
def test_skip_reveals_a_concrete_accepted_command(
    task_id: str, command: str
) -> None:
    task = _task(task_id)
    displayed = format_display_answer(task, "Linux")
    assert displayed == command
    assert validate_input(displayed, task, "Linux")


@pytest.mark.parametrize(
    ("task_id", "command"),
    [
        ("linux_basic__mkdir", "mkdir /home/user/backups"),
        (
            "linux_file_operations__cp_file",
            "cp /home/user/report.txt /home/user/backups/",
        ),
        (
            "linux_text_processing__awk_print_column",
            "awk -F, '{print $3}' /home/user/users.csv",
        ),
    ],
)
def test_absolute_paths_identify_the_same_scenario_target(
    task_id: str, command: str
) -> None:
    assert validate_input(command, _task(task_id), "Linux")
