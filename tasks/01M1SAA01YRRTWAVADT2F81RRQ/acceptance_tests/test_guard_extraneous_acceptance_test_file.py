"""Приёмочные тесты AC-3, AC-6 (tasks/01M1SAA01YRRTWAVADT2F81RRQ/
SPEC.md): `scripts/guard.py`, встретив посторонний файл (критерий
допустимости — AC-1) внутри `acceptance_tests/`, называет нарушение
структуры именованной причиной «посторонний файл в каталоге планки», а
не пытается разобрать его как артефакт с frontmatter — в обоих режимах
(`--all` и `--all --artifact-branch`).

Красен до реализации: guard.py сегодня обходит `tasks/**/*.md`
(`main`, `args == ["--all"]`) и для каждого найденного `.md` зовёт
`check_content`/`_content_errors`, которые честно пытаются прочитать
frontmatter и жалуются на отсутствующие поля/неизвестный `type` — то
самое поведение, из-за которого сгенерированная карта кодовой базы 05.09
красила `guard --all` вместо понятной причины. Файла постороннего
расширения (`fixtures.json`, тест AC-3) текущий обход вообще не находит
(не `*.md`) — на нём guard сегодня молча отвечает «ок», что тоже не
совпадает с требуемым нарушением.
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402

VALID_SPEC_MD = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 4
zones: scripts/fake_zone.py
---

# SPEC: фикстура guard-теста

## Контекст

Фикстура для приёмочного теста guard.py, не имеет отношения к реальной
задаче.

## Требования

1. Требование фикстуры.

## Критерии приёмки

AC-1. Критерий фикстуры.

## Не входит

- Ничего сверх фикстуры.
"""

INCIDENT_MAP_MD = ("---\nbuilt_at_sha: 0123456789abcdef0123456789abcdef"
                   "01234567\n---\n\n# Codebase-map пульта\n\n"
                   "Автосгенерировано `scripts/codebase_map.py`.\n")

FRONTMATTER_ERROR_HINTS = (
    "нет frontmatter",
    "добавь в frontmatter",
    "неизвестный type",
    "не прочитан",
)


def run_guard(argv: list) -> tuple:
    """(код возврата, stdout) `guard.main()` с заданными аргументами."""
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["scripts/guard.py", *argv]):
        with redirect_stdout(buf):
            rc = guard.main()
    return rc, buf.getvalue()


class _GuardAllModesTmpRepoTest(unittest.TestCase):
    """Общая обвязка: `tasks/<task_id>/` во временном cwd (guard `--all`
    обходит `Path("tasks").rglob("*.md")` от cwd, git не нужен)."""

    TASK = "01FAKEGUARDEXTRABASE1"

    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp_root = Path(tmp.name)
        self.task_dir = self.tmp_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)
        (self.task_dir / "SPEC.md").write_text(
            VALID_SPEC_MD.format(task=self.TASK), encoding="utf-8")
        self._orig_cwd = Path.cwd()
        import os
        os.chdir(self.tmp_root)
        self.addCleanup(os.chdir, self._orig_cwd)

    def write(self, rel: str, content: str) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class Ac3ExtraneousFileNamedReasonTest(_GuardAllModesTmpRepoTest):
    """AC-3: файл постороннего РАСШИРЕНИЯ первого уровня `acceptance_tests/`
    (не `test_*.py`/`_sandbox.py`/`markers.py`/`__init__.py`/`*.md`/
    `*.txt`) — именованная ошибка структуры, не попытка разбора
    frontmatter, в обоих режимах."""

    TASK = "01FAKEGUARDAC3EXTRA01"

    def test_ac3_all_mode_names_the_violation_instead_of_frontmatter_parse(self):
        """Ловит мутацию: обход `--all` остаётся ограничен `*.md`
        (сегодняшний `Path("tasks").rglob("*.md")`) — тогда `fixtures.
        json` вообще не будет замечен, и guard молча ответит «ок» вместо
        нарушения."""
        self.write("acceptance_tests/fixtures.json", '{"x": 1}')

        rc, out = run_guard(["--all"])

        self.assertEqual(rc, 1, out)
        self.assertIn("посторонний файл в каталоге планки", out)
        self.assertIn("fixtures.json", out)

    def test_ac3_artifact_branch_mode_names_the_violation_instead_of_frontmatter_parse(self):
        """Тот же посторонний файл, режим `--artifact-branch`: та же
        именованная причина, не сводка «сдано/черновиков» без единого
        слова про постороннее.

        Ловит мутацию: именованная причина реализована только для
        обычного режима `--all`, а `_artifact_branch_report` продолжает
        видеть исходный необработанный список файлов без фильтрации —
        тогда режим артефактной ветки не получил бы новой причины
        вовсе."""
        self.write("acceptance_tests/fixtures.json", '{"x": 1}')

        rc, out = run_guard(["--all", "--artifact-branch"])

        self.assertEqual(rc, 1, out)
        self.assertIn("посторонний файл в каталоге планки", out)
        self.assertIn("fixtures.json", out)


class Ac6IncidentBothModesTest(_GuardAllModesTmpRepoTest):
    """AC-6: воспроизведение реального инцидента — вложенный
    `acceptance_tests/docs/codebase-map.md` с настоящей формой
    frontmatter генератора карты (`built_at_sha`, без `task`/`type`).
    Ошибка обязана быть именно именованной причиной, а не сообщением о
    разборе frontmatter (которое этот файл, имея валидный YAML-блок,
    сегодня честно проходит до заведомо иной жалобы — «неизвестный type
    ''», «добавь обязательные поля»)."""

    TASK = "01FAKEGUARDAC6INCID01"

    def test_ac6_all_mode_reports_named_reason_not_a_frontmatter_complaint(self):
        """Ловит мутацию: фильтр посторонних файлов реализован ТОЛЬКО как
        разбор расширения (что уже покрывает AC-3), без учёта вложенности
        каталога — тогда этот вложенный `.md`-файл (ровно инцидентный
        случай 05.09) остался бы виден guard'у как «почти артефакт» и
        получил бы старую жалобу на frontmatter/type вместо именованной
        причины."""
        self.write("acceptance_tests/docs/codebase-map.md", INCIDENT_MAP_MD)

        rc, out = run_guard(["--all"])

        self.assertEqual(rc, 1, out)
        self.assertIn("посторонний файл в каталоге планки", out)
        self.assertIn("codebase-map.md", out)
        map_related_lines = [line for line in out.splitlines()
                             if "codebase-map.md" in line]
        for line in map_related_lines:
            for hint in FRONTMATTER_ERROR_HINTS:
                with self.subTest(строка=line, подсказка=hint):
                    self.assertNotIn(hint, line)

    def test_ac6_artifact_branch_mode_reports_named_reason_not_a_frontmatter_complaint(self):
        """Тот же инцидентный файл, режим `--artifact-branch` — тот же
        довод, что и предыдущий тест, для второго режима, названного в
        AC-3/AC-6 явно."""
        self.write("acceptance_tests/docs/codebase-map.md", INCIDENT_MAP_MD)

        rc, out = run_guard(["--all", "--artifact-branch"])

        self.assertEqual(rc, 1, out)
        self.assertIn("посторонний файл в каталоге планки", out)
        map_related_lines = [line for line in out.splitlines()
                             if "codebase-map.md" in line]
        self.assertTrue(map_related_lines, out)
        for line in map_related_lines:
            for hint in FRONTMATTER_ERROR_HINTS:
                with self.subTest(строка=line, подсказка=hint):
                    self.assertNotIn(hint, line)


if __name__ == "__main__":
    unittest.main()
