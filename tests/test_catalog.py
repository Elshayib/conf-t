"""Catalog seam: one read of a lessons directory (#36)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conf_t.catalog import Catalog, CatalogRefusal
from conf_t.models import Lesson, Task


def _write(directory: Path, filename: str, body: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(json.dumps(body), encoding="utf-8")


def _lesson(
    lesson_id: str,
    *,
    title: str,
    platform: str,
    tasks: list[dict] | None = None,
    difficulty: str = "beginner",
    tags: list[str] | None = None,
    prerequisites: list[str] | None = None,
) -> dict:
    return {
        "id": lesson_id,
        "title": title,
        "platform": platform,
        "description": f"{title} description",
        "difficulty": difficulty,
        "tags": tags or [],
        "prerequisites": prerequisites or [],
        "tasks": tasks
        or [
            {
                "id": f"{lesson_id}__one",
                "prompt": "Run it",
                "prefix": "$",
                "expected": "^true$",
            }
        ],
    }


def test_linux_and_Linux_are_the_same_platform(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "alpha.json",
        _lesson("alpha", title="Alpha", platform="linux"),
    )
    _write(
        tmp_path,
        "beta.json",
        _lesson("beta", title="Beta", platform="Linux"),
    )
    _write(
        tmp_path,
        "git.json",
        _lesson("git_one", title="Git One", platform="git"),
    )
    _write(
        tmp_path,
        "cisco.json",
        _lesson("cisco_one", title="Cisco One", platform="CISCO"),
    )
    _write(
        tmp_path,
        "ps.json",
        _lesson("ps_one", title="PS One", platform="powershell"),
    )
    _write(
        tmp_path,
        "docker.json",
        _lesson("docker_one", title="Docker One", platform="DOCKER"),
    )

    catalog = Catalog(tmp_path)
    lower = [lesson.id for lesson in catalog.lessons(platform="linux")]
    upper = [lesson.id for lesson in catalog.lessons(platform="Linux")]

    assert lower == ["alpha", "beta"]
    assert upper == ["alpha", "beta"]
    assert catalog.platforms() == [
        "Cisco",
        "Docker",
        "Git",
        "Linux",
        "PowerShell",
    ]


def test_lessons_stay_ordered_by_difficulty_then_title(tmp_path: Path) -> None:
    _write(tmp_path, "z.json", _lesson("zebra", title="Zebra", platform="Linux", difficulty="advanced"))
    _write(tmp_path, "b.json", _lesson("banana", title="Banana", platform="Linux"))
    _write(tmp_path, "a.json", _lesson("apple", title="Apple", platform="Linux"))
    _write(
        tmp_path,
        "m.json",
        _lesson("middle", title="Middle", platform="Linux", difficulty="intermediate"),
    )

    assert [lesson.id for lesson in Catalog(tmp_path).lessons()] == [
        "apple",
        "banana",
        "middle",
        "zebra",
    ]


def test_topic_tags_narrow_the_same_set(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "vlan.json",
        _lesson("vlan", title="VLAN", platform="Cisco", tags=["vlan", "switching"]),
    )
    _write(
        tmp_path,
        "ospf.json",
        _lesson("ospf", title="OSPF", platform="Cisco", tags=["ospf", "routing"]),
    )

    catalog = Catalog(tmp_path)
    assert [lesson.id for lesson in catalog.lessons(tags=["vlan"])] == ["vlan"]
    assert [lesson.id for lesson in catalog.lessons(tags=["VLAN"])] == ["vlan"]
    assert [lesson.id for lesson in catalog.lessons(tags=["routing"])] == ["ospf"]
    assert catalog.lessons(tags=["vlan", "switching"])[0].id == "vlan"
    assert catalog.lessons(tags=["vlan", "routing"]) == []


def test_shipped_curriculum_loads() -> None:
    lessons = Catalog().lessons()
    ids = {lesson.id for lesson in lessons}
    assert {"linux_basic", "cisco_basic", "powershell_basic", "git_basic", "docker_basic"} <= ids


def test_unparsed_lesson_file_names_the_file(tmp_path: Path) -> None:
    from conf_t.catalog import CatalogRefusal

    _write(tmp_path, "good.json", _lesson("good", title="Good", platform="Linux"))
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")

    with pytest.raises(CatalogRefusal) as exc:
        Catalog(tmp_path).lessons()
    assert exc.value.path.name == "broken.json"


def test_lesson_missing_required_fields_names_the_file(tmp_path: Path) -> None:
    from conf_t.catalog import CatalogRefusal

    (tmp_path / "partial.json").write_text('{"title": "Only a title"}', encoding="utf-8")

    with pytest.raises(CatalogRefusal) as exc:
        Catalog(tmp_path).lessons()
    assert exc.value.path.name == "partial.json"


def test_duplicate_task_id_names_the_later_file(tmp_path: Path) -> None:
    from conf_t.catalog import CatalogRefusal

    shared = {
        "id": "shared__one",
        "prompt": "Run it",
        "prefix": "$",
        "expected": "^true$",
    }
    _write(
        tmp_path,
        "a.json",
        _lesson("alpha", title="Alpha", platform="Linux", tasks=[shared]),
    )
    _write(
        tmp_path,
        "b.json",
        _lesson("beta", title="Beta", platform="Linux", tasks=[shared]),
    )

    with pytest.raises(CatalogRefusal) as exc:
        Catalog(tmp_path).lessons()
    assert exc.value.path.name == "b.json"


def test_expected_regex_that_does_not_compile_names_the_file(tmp_path: Path) -> None:
    from conf_t.catalog import CatalogRefusal

    _write(tmp_path, "good.json", _lesson("good", title="Good", platform="Linux"))
    _write(
        tmp_path,
        "bad.json",
        _lesson(
            "bad",
            title="Bad",
            platform="Linux",
            tasks=[
                {
                    "id": "bad__one",
                    "prompt": "Run it",
                    "prefix": "$",
                    "expected": "[unterminated",
                }
            ],
        ),
    )

    with pytest.raises(CatalogRefusal) as exc:
        Catalog(tmp_path).lessons()
    assert exc.value.path.name == "bad.json"


def test_curriculum_shape_problems_do_not_refuse_the_read(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "shape.json",
        _lesson(
            "shape",
            title="Shape",
            platform="Linux",
            difficulty="expert",
            prerequisites=["missing_lesson"],
            tasks=[
                {
                    "id": "Not-A-Slug",
                    "prompt": "Run it",
                    "prefix": "$",
                    "expected": "^echo$",
                },
                {
                    "id": "Also Bad",
                    "prompt": "Run it again",
                    "prefix": "$",
                    "expected": "^echo$",
                },
            ],
        ),
    )

    lessons = Catalog(tmp_path).lessons()
    assert [lesson.id for lesson in lessons] == ["shape"]
    assert lessons[0].difficulty == "expert"
    assert lessons[0].prerequisites == ["missing_lesson"]
    assert [task.expected for task in lessons[0].tasks] == ["^echo$", "^echo$"]
    assert [task.id for task in lessons[0].tasks] == ["Not-A-Slug", "Also Bad"]


def _model(
    lesson_id: str,
    tasks: list[Task],
    *,
    difficulty: str = "beginner",
    prerequisites: list[str] | None = None,
) -> Lesson:
    return Lesson(
        id=lesson_id,
        title=lesson_id.title(),
        platform="Linux",
        description="Desc",
        tasks=tasks,
        difficulty=difficulty,
        prerequisites=prerequisites or [],
    )


def _command(task_id: str, expected: str = "^true$") -> Task:
    return Task(id=task_id, prompt="Run it", prefix="$", expected=expected)


def _shared_task(task_id: str = "shared__one") -> dict:
    return {
        "id": task_id,
        "prompt": "Run it",
        "prefix": "$",
        "expected": "^true$",
    }


def test_save_refuses_a_regex_that_does_not_compile(tmp_path: Path) -> None:
    oracle = tmp_path / "oracle"
    _write(
        oracle,
        "custom.json",
        _lesson(
            "custom",
            title="Custom",
            platform="Linux",
            tasks=[
                {
                    "id": "custom__one",
                    "prompt": "Run it",
                    "prefix": "$",
                    "expected": "[unterminated",
                }
            ],
        ),
    )
    with pytest.raises(CatalogRefusal) as read_exc:
        Catalog(oracle).lessons()

    catalog = Catalog(tmp_path)
    lesson = _model("custom", [_command("custom__one", "[unterminated")])
    with pytest.raises(CatalogRefusal) as save_exc:
        catalog.save_lesson(lesson)

    assert str(save_exc.value) == "custom.json: expected regex does not compile"
    assert str(save_exc.value) == str(read_exc.value)
    assert save_exc.value.path.name == "custom.json"
    assert list(tmp_path.glob("*.json")) == []
    assert catalog.lessons() == []


def test_save_refuses_a_reused_task_id(tmp_path: Path) -> None:
    catalog = Catalog(tmp_path)
    assert catalog.save_lesson(_model("first", [_command("shared__one")])) is True

    oracle = tmp_path / "oracle"
    _write(
        oracle,
        "first.json",
        _lesson("first", title="First", platform="Linux", tasks=[_shared_task()]),
    )
    _write(
        oracle,
        "second.json",
        _lesson(
            "second",
            title="Second",
            platform="Linux",
            tasks=[_shared_task(), _shared_task("second__other")],
        ),
    )
    with pytest.raises(CatalogRefusal) as read_exc:
        Catalog(oracle).lessons()

    reused = _model(
        "second",
        [_command("shared__one"), _command("second__other")],
    )
    with pytest.raises(CatalogRefusal) as save_exc:
        catalog.save_lesson(reused)

    assert str(save_exc.value) == (
        "second.json: duplicate task id 'shared__one' is also in first.json"
    )
    assert str(save_exc.value) == str(read_exc.value)
    assert catalog.get_lesson_by_id("second") is None
    assert [lesson.id for lesson in catalog.lessons()] == ["first"]


def test_save_refuses_a_reused_task_id_when_the_new_file_sorts_first(
    tmp_path: Path,
) -> None:
    catalog = Catalog(tmp_path)
    assert catalog.save_lesson(_model("zzz", [_command("shared__one")])) is True

    oracle = tmp_path / "oracle"
    _write(
        oracle,
        "aaa.json",
        _lesson("aaa", title="Aaa", platform="Linux", tasks=[_shared_task()]),
    )
    _write(
        oracle,
        "zzz.json",
        _lesson("zzz", title="Zzz", platform="Linux", tasks=[_shared_task()]),
    )
    with pytest.raises(CatalogRefusal) as read_exc:
        Catalog(oracle).lessons()

    with pytest.raises(CatalogRefusal) as save_exc:
        catalog.save_lesson(_model("aaa", [_command("shared__one")]))

    assert str(save_exc.value) == (
        "zzz.json: duplicate task id 'shared__one' is also in aaa.json"
    )
    assert str(save_exc.value) == str(read_exc.value)
    assert catalog.get_lesson_by_id("aaa") is None
    assert [lesson.id for lesson in catalog.lessons()] == ["zzz"]


def test_save_refuses_duplicate_task_ids_inside_the_lesson(tmp_path: Path) -> None:
    oracle = tmp_path / "oracle"
    _write(
        oracle,
        "custom.json",
        _lesson(
            "custom",
            title="Custom",
            platform="Linux",
            tasks=[_shared_task("custom__one"), _shared_task("custom__one")],
        ),
    )
    with pytest.raises(CatalogRefusal) as read_exc:
        Catalog(oracle).lessons()

    catalog = Catalog(tmp_path)
    lesson = _model("custom", [_command("custom__one"), _command("custom__one")])
    with pytest.raises(CatalogRefusal) as save_exc:
        catalog.save_lesson(lesson)

    assert str(save_exc.value) == "custom.json: duplicate task id 'custom__one'"
    assert str(save_exc.value) == str(read_exc.value)
    assert list(tmp_path.glob("*.json")) == []
    assert catalog.lessons() == []


def test_save_refuses_a_lesson_that_will_not_parse(tmp_path: Path) -> None:
    class Unparsed(Lesson):
        def to_dict(self) -> dict:
            return {"title": "Only a title"}

    oracle = tmp_path / "oracle"
    (oracle / "custom.json").parent.mkdir()
    (oracle / "custom.json").write_text('{"title": "Only a title"}', encoding="utf-8")
    with pytest.raises(CatalogRefusal) as read_exc:
        Catalog(oracle).lessons()

    catalog = Catalog(tmp_path)
    lesson = Unparsed(
        id="custom",
        title="Custom",
        platform="Linux",
        description="Desc",
        tasks=[_command("custom__one")],
    )
    with pytest.raises(CatalogRefusal) as save_exc:
        catalog.save_lesson(lesson)

    assert str(save_exc.value) == "custom.json: file does not parse as a Lesson"
    assert str(save_exc.value) == str(read_exc.value)
    assert list(tmp_path.glob("*.json")) == []


def test_save_reports_a_disk_failure_without_a_refusal(tmp_path: Path) -> None:
    blocked = tmp_path / "lessons"
    blocked.write_text("not a directory", encoding="utf-8")
    catalog = Catalog(blocked)
    lesson = _model("custom", [_command("custom__one")])

    assert catalog.save_lesson(lesson) is False
    assert blocked.read_text(encoding="utf-8") == "not a directory"


def test_save_keeps_a_lesson_that_passes_and_lists_it(tmp_path: Path) -> None:
    catalog = Catalog(tmp_path)
    lesson = _model("custom", [_command("custom__one", "^pwd$")])

    assert catalog.save_lesson(lesson) is True
    loaded = catalog.lessons()
    assert [item.id for item in loaded] == ["custom"]
    assert loaded[0].tasks[0].expected == "^pwd$"


def test_save_accepts_shape_problems_that_do_not_refuse_startup(tmp_path: Path) -> None:
    catalog = Catalog(tmp_path)
    lesson = _model(
        "shape",
        [_command("Not-A-Slug", "^echo$"), _command("Also-Bad", "^echo$")],
        difficulty="expert",
        prerequisites=["missing_lesson"],
    )

    assert catalog.save_lesson(lesson) is True
    loaded = catalog.lessons()
    assert loaded[0].difficulty == "expert"
    assert loaded[0].prerequisites == ["missing_lesson"]
    assert [task.expected for task in loaded[0].tasks] == ["^echo$", "^echo$"]

