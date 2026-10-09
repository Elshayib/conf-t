"""Complete Bash Tasks through the real Lesson grader (#29).

Commands follow the GNU Bash manual. The tests never execute shell commands.
"""

from conf_t.acceptance import validate_input
from conf_t.catalog import Catalog
from conf_t.models import Task


def task_for(action: str) -> Task:
    lesson = Catalog().get_lesson_by_id("linux_shell_scripting")
    assert lesson is not None
    return next(
        task for task in lesson.tasks
        if task.id == f"linux_shell_scripting__{action}"
    )


def test_shebang_is_written_by_a_complete_command() -> None:
    task = task_for("shebang_line")
    assert validate_input(
        "printf '%s\\n' '#!/bin/bash' > deploy.sh", task, "Linux"
    )
    assert validate_input(
        "printf '%s\\n' '#!/usr/bin/env bash' > deploy.sh", task, "Linux"
    )
    for command in (
        "#!/bin/bash", "#!/usr/bin/env bash",
        "printf '%s\\n' '#!/bin/bash' >> deploy.sh",
        "printf '%s\\n' '#!/bin/sh' > deploy.sh",
    ):
        assert not validate_input(command, task, "Linux")


def test_execute_permission_changes_only_owner_bits() -> None:
    task = task_for("chmod_executable")
    assert validate_input("chmod u+x deploy.sh", task, "Linux")
    for command in (
        "chmod +x deploy.sh", "chmod a+x deploy.sh", "chmod 755 deploy.sh",
    ):
        assert not validate_input(command, task, "Linux")


def test_for_loop_prints_each_matching_filename_as_one_line() -> None:
    task = task_for("for_loop")
    assert validate_input(
        'for file in *.log; do printf \'%s\\n\' "$file"; done', task, "Linux"
    )
    assert validate_input(
        'for file in *.log; do printf "%s\\n" "${file}"; done', task, "Linux"
    )
    for command in (
        "for file in *.log; do",
        'for file in "*.log"; do printf \'%s\\n\' "$file"; done',
        "for file in *.log; do printf '%s\\n' $file; done",
        'for file in *.log; do rm "$file"; done',
    ):
        assert not validate_input(command, task, "Linux")


def test_read_loop_preserves_lines_and_redirects_the_completed_loop() -> None:
    task = task_for("while_read")
    assert validate_input(
        'while IFS= read -r line; do printf \'%s\\n\' "$line"; done < app.log',
        task, "Linux",
    )
    assert validate_input(
        'while IFS="" read -r line; do printf "%s\\n" "${line}"; done<app.log',
        task, "Linux",
    )
    for command in (
        "while read line; do < app.log",
        'while read -r line; do printf \'%s\\n\' "$line"; done < app.log',
        'while IFS= read line; do printf \'%s\\n\' "$line"; done < app.log',
        "while IFS= read -r line; do printf '%s\\n' $line; done < app.log",
        'while IFS= read -r line; do printf \'%s\\n\' "$line" < app.log; done',
        'while IFS= read -r line; do printf \'%s\\n\' "$line"; done',
    ):
        assert not validate_input(command, task, "Linux")


def test_function_definition_includes_the_requested_body_and_closure() -> None:
    task = task_for("function_define")
    assert validate_input(
        "greet() { printf '%s\\n' 'Hello'; }", task, "Linux"
    )
    assert validate_input(
        'function greet { printf "%s\\n" "Hello"; }', task, "Linux"
    )
    for command in (
        "greet() {", "function greet {",
        "greet() { printf '%s\\n' 'Goodbye'; }", "greet() { :; }",
        "greet() { printf '%s\\n' 'Hello' }",
    ):
        assert not validate_input(command, task, "Linux")


def test_case_statement_includes_both_requested_branches() -> None:
    task = task_for("case_statement")
    assert validate_input(
        'case "$ACTION" in start) printf \'%s\\n\' \'Starting\';; '
        '*) printf \'%s\\n\' \'Unknown\';; esac', task, "Linux",
    )
    assert validate_input(
        'case ${ACTION} in start) printf "%s\\n" "Starting";; '
        '*) printf "%s\\n" "Unknown";; esac', task, "Linux",
    )
    for command in (
        "case $ACTION in",
        'case "$ACTION" in start) :;; *) :;; esac',
        'case "$ACTION" in start) printf \'%s\\n\' \'Starting\';; esac',
        'case "$ACTION" in start) printf \'%s\\n\' \'Unknown\';; '
        '*) printf \'%s\\n\' \'Starting\';; esac',
        'case "$ACTION" in start) printf \'%s\\n\' \'Starting\';; '
        '*) printf \'%s\\n\' \'Unknown\';;',
    ):
        assert not validate_input(command, task, "Linux")


def test_variable_output_preserves_the_whole_value() -> None:
    task = task_for("echo_variable")
    assert validate_input('echo "$HOSTNAME"', task, "Linux")
    assert validate_input('echo "${HOSTNAME}"', task, "Linux")
    assert not validate_input("echo $HOSTNAME", task, "Linux")
    assert not validate_input("echo '$HOSTNAME'", task, "Linux")


def test_shell_assignment_accepts_literal_quote_variants() -> None:
    task = task_for("variable_assign")
    for command in ("ENV=production", "ENV='production'", 'ENV="production"'):
        assert validate_input(command, task, "Linux")
    for command in ("ENV = production", "ENV=staging", "sudo ENV=production"):
        assert not validate_input(command, task, "Linux")


def test_file_test_checks_regular_file_without_exiting_shell() -> None:
    task = task_for("if_test")
    for command in (
        "test -f config.yml", 'test -f "config.yml"', "[ -f config.yml ]",
    ):
        assert validate_input(command, task, "Linux")
    for command in (
        "test -e config.yml", "test -d config.yml", "test -f other.yml",
        "[ -f config.yml]",
    ):
        assert not validate_input(command, task, "Linux")


def test_interpreter_can_read_script_without_execute_permission() -> None:
    task = task_for("bash_script")
    assert validate_input("bash deploy.sh", task, "Linux")
    assert validate_input("bash ./deploy.sh", task, "Linux")
    assert not validate_input("./deploy.sh", task, "Linux")
    assert not validate_input("sh deploy.sh", task, "Linux")


def test_direct_execution_names_the_current_directory_script() -> None:
    task = task_for("run_script")
    assert validate_input("./deploy.sh", task, "Linux")
    assert not validate_input("deploy.sh", task, "Linux")
    assert not validate_input("./Deploy.sh", task, "Linux")
    assert not validate_input("bash deploy.sh", task, "Linux")


def test_script_exit_reports_failure_to_its_caller() -> None:
    task = task_for("exit_code")
    assert validate_input("exit 1", task, "Linux")
    assert not validate_input("exit 0", task, "Linux")
    assert not validate_input("return 1", task, "Linux")
    assert not validate_input("EXIT 1", task, "Linux")
