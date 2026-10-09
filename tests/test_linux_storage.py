"""Storage Task behavior through loaded Lessons; no disk commands execute.

Command literals follow Ubuntu manuals for LVM2, e2fsprogs, util-linux and GNU
coreutils. Session with temporary progress verifies compatibility only (#30).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conf_t.catalog import Catalog
from conf_t.acceptance import format_display_answer, validate_input
from conf_t.models import Lesson, Task
from conf_t.session import (
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    Session,
    TURN_CORRECT,
    TaskResult,
)

NEW_TASK_ID = "linux_lvm_storage__mkfs_ext4_create"
OLD_ACTIONS = (
    "lsblk_list", "df_human", "du_summary", "pvcreate_init",
    "vgcreate_pool", "lvcreate_logical", "lvextend_grow",
    "resize2fs_grow", "mount_device", "pvs_display",
)


def _lesson() -> Lesson:
    lesson = Catalog().get_lesson_by_id("linux_lvm_storage")
    assert lesson is not None
    return lesson


def _task(action: str) -> Task:
    return next(
        task for task in _lesson().tasks
        if task.id == f"linux_lvm_storage__{action}"
    )


def test_completed_old_lesson_resumes_only_new_filesystem_task(
    tmp_path: Path,
) -> None:
    updated = _lesson()
    old_data = updated.to_dict()
    old_ids = {f"linux_lvm_storage__{action}" for action in OLD_ACTIONS}
    old_data["tasks"] = [
        task.to_dict() for task in updated.tasks if task.id in old_ids
    ]
    old = Lesson.from_dict(old_data)
    assert len(old.tasks) == 10
    progress_path = tmp_path / "progress.json"
    session = Session(progress_path=progress_path)
    session.mark_practice_opened(old)
    for task in old.tasks:
        session.record_attempt(
            old, task, TaskResult.FIRST_TRY_PASS,
        )
    assert session.lesson_standing(old).status == LESSON_STATUS_COMPLETED
    assert session.stats().completed_lessons == 1

    # Reload the real updated catalog without touching the progress file.
    updated = _lesson()
    returning = Session(progress_path=progress_path)
    assert returning.stats().completed_lessons == 1
    standing = returning.lesson_standing(updated)
    assert standing.status == LESSON_STATUS_IN_PROGRESS
    assert standing.passed == 10
    assert standing.total == 11
    resumed = returning.resume_tasks(updated)
    assert [task.id for task in resumed] == [NEW_TASK_ID]
    target = returning.continue_target([updated])
    assert target is not None
    assert target.action == "lesson"
    assert target.lesson_id == updated.id
    result = returning.submit(
        updated, resumed[0], "sudo mkfs.ext4 /dev/vg_data/lv_apps"
    )
    assert result.kind == TURN_CORRECT
    assert result.first_try
    assert returning.lesson_standing(updated).passed == 11
    final_standing = returning.lesson_standing(updated)
    assert final_standing.status == LESSON_STATUS_COMPLETED
    assert returning.resume_tasks(updated) == []


def test_lsblk_lists_devices_and_partitions_as_a_tree() -> None:
    task = _task('lsblk_list')
    for command in (
        'lsblk',
        'lsblk -f',
        'lsblk --fs',
        'lsblk --tree',
        'lsblk -o NAME,SIZE,TYPE,MOUNTPOINTS',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'lsblk -l',
        'lsblk -d',
        'lsblk /dev/sdb',
        'lsblk -t',
        'lsblk -o SIZE,TYPE',
        'LSBLK',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_df_reports_human_readable_filesystem_space() -> None:
    task = _task('df_human')
    for command in (
        'df -h',
        'df --human-readable',
        'df -hT',
        'df -Th',
        'df -h -T',
        'df --human-readable --print-type',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'df',
        'df -H',
        'df --si',
        'df -i',
        'du -sh /var/log',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_du_summarizes_all_log_contents_with_required_access() -> None:
    task = _task('du_summary')
    for command in (
        'sudo du -sh /var/log',
        'sudo du -hs /var/log/',
        'sudo du -s -h "/var/log"',
        'sudo du --human-readable --summarize /var/log',
        'sudo du -h --max-depth=0 /var/log',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'du -sh /var/log',
        'sudo du -h /var/log',
        'sudo du -sh /var/lib',
        'sudo du -Sh /var/log',
        'sudo du -sb /var/log',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_mkfs_creates_ext4_on_the_empty_logical_volume() -> None:
    task = _task('mkfs_ext4_create')
    for command in (
        'sudo mkfs.ext4 /dev/vg_data/lv_apps',
        'sudo mkfs.ext4 /dev/mapper/vg_data-lv_apps',
        'sudo mke2fs -t ext4 /dev/vg_data/lv_apps',
        'sudo mke2fs -text4 "/dev/vg_data/lv_apps"',
        'sudo -- mkfs.ext4 -q /dev/vg_data/lv_apps',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'mkfs.ext4 /dev/vg_data/lv_apps',
        'sudo mkfs.ext3 /dev/vg_data/lv_apps',
        'sudo mke2fs -t ext3 /dev/vg_data/lv_apps',
        'sudo mkfs.ext4 -n /dev/vg_data/lv_apps',
        'sudo mkfs.ext4 /dev/vg_data/lv_other',
        'sudo lvcreate -L 10G -n lv_apps vg_data',
        'sudo mount /dev/vg_data/lv_apps /mnt/apps',
        'sudo resize2fs /dev/vg_data/lv_apps',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_pvcreate_initializes_only_the_empty_target_disk() -> None:
    task = _task('pvcreate_init')
    for command in (
        'sudo pvcreate /dev/sdb',
        'sudo -- pvcreate "/dev/sdb"',
        'sudo -u root pvcreate /dev/sdb',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'pvcreate /dev/sdb',
        'sudo pvcreate /dev/sdc',
        'sudo pvcreate /dev/sdb1',
        'sudo pvcreate -t /dev/sdb',
        'sudo mkfs.ext4 /dev/sdb',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_vgcreate_forms_the_named_pool_from_the_existing_pv() -> None:
    task = _task('vgcreate_pool')
    for command in (
        'sudo vgcreate vg_data /dev/sdb',
        'sudo -- vgcreate "vg_data" "/dev/sdb"',
        'sudo --user=root vgcreate vg_data /dev/sdb',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'vgcreate vg_data /dev/sdb',
        'sudo vgcreate vg_other /dev/sdb',
        'sudo vgcreate vg_data /dev/sdc',
        'sudo vgextend vg_data /dev/sdb',
        'sudo vgcreate -t vg_data /dev/sdb',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_lvcreate_allocates_exactly_ten_gib_under_the_named_lv() -> None:
    task = _task('lvcreate_logical')
    for command in (
        'sudo lvcreate -L 10G -n lv_apps vg_data',
        'sudo lvcreate -n lv_apps -L 10G vg_data',
        'sudo lvcreate --size=10g --name=lv_apps vg_data',
        'sudo lvcreate vg_data -n lv_apps -L10240M',
        'sudo lvcreate -l2560 -nlv_apps vg_data',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'lvcreate -n lv_apps -L 10G vg_data',
        'sudo lvcreate -L 10M -n lv_apps vg_data',
        'sudo lvcreate -L 5G -n lv_apps vg_data',
        'sudo lvcreate -L 10G -n lv_other vg_data',
        'sudo lvcreate -L 10G -n lv_apps vg_other',
        'sudo lvcreate -t -L 10G -n lv_apps vg_data',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_lvextend_adds_five_gib_without_resizing_the_filesystem() -> None:
    task = _task('lvextend_grow')
    for command in (
        'sudo lvextend -L +5G /dev/vg_data/lv_apps',
        'sudo lvextend --size=+5g vg_data/lv_apps',
        'sudo lvextend /dev/vg_data/lv_apps -L+5120M',
        'sudo lvextend -L 15G /dev/vg_data/lv_apps',
        'sudo lvextend -l+1280 /dev/mapper/vg_data-lv_apps',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'lvextend -L +5G /dev/vg_data/lv_apps',
        'sudo lvextend -L 5G /dev/vg_data/lv_apps',
        'sudo lvextend -L +15G /dev/vg_data/lv_apps',
        'sudo lvextend -L +5G /dev/vg_data/lv_other',
        'sudo lvextend -r -L +5G /dev/vg_data/lv_apps',
        'sudo resize2fs /dev/vg_data/lv_apps',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_resize2fs_grows_existing_ext4_to_the_larger_device() -> None:
    task = _task('resize2fs_grow')
    for command in (
        'sudo resize2fs /dev/vg_data/lv_apps',
        'sudo resize2fs /dev/mapper/vg_data-lv_apps',
        'sudo resize2fs "/dev/vg_data/lv_apps" 15G',
        'sudo resize2fs /dev/vg_data/lv_apps 15360M',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'resize2fs /dev/vg_data/lv_apps',
        'sudo resize2fs /dev/vg_data/lv_apps 10G',
        'sudo resize2fs /dev/vg_data/lv_other',
        'sudo resize2fs -P /dev/vg_data/lv_apps',
        'sudo mkfs.ext4 /dev/vg_data/lv_apps',
        'sudo lvextend -L +5G /dev/vg_data/lv_apps',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_mount_attaches_existing_ext4_at_the_exact_directory() -> None:
    task = _task('mount_device')
    for command in (
        'sudo mount /dev/vg_data/lv_apps /mnt/apps',
        'sudo mount -t ext4 /dev/vg_data/lv_apps /mnt/apps',
        'sudo mount --types=ext4 -o rw /dev/mapper/vg_data-lv_apps /mnt/apps/',
        'sudo mount /dev/vg_data/lv_apps /mnt/apps -t ext4',
        'sudo mount --source /dev/vg_data/lv_apps --target /mnt/apps',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'mount /dev/vg_data/lv_apps /mnt/apps',
        'sudo mount /dev/vg_data/lv_other /mnt/apps',
        'sudo mount /dev/vg_data/lv_apps /mnt/other',
        'sudo mount -t xfs /dev/vg_data/lv_apps /mnt/apps',
        'sudo mount -r /dev/vg_data/lv_apps /mnt/apps',
        'sudo mount -f /dev/vg_data/lv_apps /mnt/apps',
        'sudo mount /mnt/apps',
    ):
        assert not validate_input(command, task, "Linux"), command


def test_pvs_reports_all_initialized_volumes_with_device_access() -> None:
    task = _task('pvs_display')
    for command in (
        'sudo pvs',
        'sudo -- pvs',
        'sudo pvs --readonly',
        'sudo pvs -o pv_name,vg_name,pv_size,pv_free',
        'sudo -u root pvs --units g',
    ):
        assert validate_input(command, task, "Linux"), command
    for command in (
        'pvs',
        'sudo pvs /dev/sdb',
        'sudo pvs --select vg_name=vg_data',
        'sudo pvs -a',
        'sudo vgs',
        'sudo lvs',
    ):
        assert not validate_input(command, task, "Linux"), command


@pytest.mark.parametrize(
    ("action", "command"),
    (
        ("lsblk_list", "lsblk"),
        ("df_human", "df -h"),
        ("du_summary", "sudo du -sh /var/log"),
        ("pvcreate_init", "sudo pvcreate /dev/sdb"),
        ("vgcreate_pool", "sudo vgcreate vg_data /dev/sdb"),
        (
            "lvcreate_logical",
            "sudo lvcreate -L 10G -n lv_apps vg_data",
        ),
        ("mkfs_ext4_create", "sudo mkfs.ext4 /dev/vg_data/lv_apps"),
        ("lvextend_grow", "sudo lvextend -L +5G /dev/vg_data/lv_apps"),
        ("resize2fs_grow", "sudo resize2fs /dev/vg_data/lv_apps"),
        ("mount_device", "sudo mount /dev/vg_data/lv_apps /mnt/apps"),
        ("pvs_display", "sudo pvs"),
    ),
)
def test_reveal_is_a_concrete_accepted_storage_command(
    action: str, command: str,
) -> None:
    task = _task(action)
    assert format_display_answer(task, "Linux") == command
    assert validate_input(command, task, "Linux")


def test_filesystem_creation_is_taught_between_lv_creation_and_use() -> None:
    actions = [task.id.split("__")[1] for task in _lesson().tasks]
    assert len(actions) == 11
    assert actions.index("mkfs_ext4_create") == (
        actions.index("lvcreate_logical") + 1
    )
    for action in ("lvextend_grow", "resize2fs_grow", "mount_device"):
        assert actions.index("mkfs_ext4_create") < actions.index(action)



def test_mount_is_taught_before_later_volume_and_filesystem_growth() -> None:
    actions = [task.id.split("__")[1] for task in _lesson().tasks]
    assert actions.index("mount_device") == (
        actions.index("mkfs_ext4_create") + 1
    )
    assert actions.index("mount_device") < actions.index("lvextend_grow")
    assert actions.index("lvextend_grow") < actions.index("resize2fs_grow")
