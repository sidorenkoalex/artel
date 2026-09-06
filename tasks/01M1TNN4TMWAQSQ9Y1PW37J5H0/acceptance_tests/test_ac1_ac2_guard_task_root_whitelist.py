"""AC-1/AC-2 (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0): `scripts/guard.py` несёт
единый белый список допустимых имён ПЕРВОГО уровня `tasks/<id>/` (не
только внутри `acceptance_tests/`, как уже делает существующий
`ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL`/`is_extraneous_acceptance_test_file`
для SPEC 01M1SAA01YRRTWAVADT2F81RRQ) — `SPEC.md`, `PLAN.md`, `REVIEW.md`,
`TEST_REPORT.md`, `QUESTIONS.md`, `TZ.md`, `ANSWER-<n>.md`, каталог
`acceptance_tests/`, приложения `*.patch`. Файл вне списка — именованная
ошибка «посторонний файл в каталоге задачи» в обоих режимах `--all`, не
попытка разбора его как артефакт с frontmatter; на полном штатном наборе
имён guard молчит (AC-2).

Сегодня `guard.py --all` обходит только `Path("tasks").rglob("*.md")` и
честно пытается разобрать КАЖДЫЙ найденный `.md`-файл как артефакт с
frontmatter (`check`/`_content_errors`); файл первого уровня `tasks/<id>/`
вне будущего белого списка (например, `notes.txt`, скопированная
сгенерированная карта кодовой базы — инцидент 06.09 из «Контекста» SPEC)
либо проходит незамеченным (не `.md` — молчаливое «ок», не нарушение),
либо получил бы жалобу на frontmatter вместо именованной причины. Правила
белого списка ПЕРВОГО уровня `tasks/<id>/` в guard.py сегодня нет вовсе.

Красен до реализации: три теста (оба test_ac2_..._stray_file_... и test_ac1_..._is_flagged) падают потому, что `notes.txt` не `.md` и обход `--all` его вообще не видит — код возврата 0 вместо ожидаемого 1 с именованной причиной.

Подробности по тестам: `Ac1WhitelistCoversAllEnumeratedNamesTest::
test_ac1_all_enumerated_names_are_recognized_while_a_real_stray_file_is_flagged`,
`Ac2NamedReasonNotFrontmatterParseTest::
test_ac2_all_mode_names_stray_file_without_frontmatter_parse_attempt` и
`Ac2NamedReasonNotFrontmatterParseTest::
test_ac2_artifact_branch_mode_names_stray_file_the_same_way` — все три
падают сегодня потому, что `notes.txt` не `.md` и обход `--all` его вообще
не видит: код возврата 0 («GUARD: ок»/«сдано N / … / нарушений 0») вместо
ожидаемого 1 с именованной причиной, ни одной строки «посторонний файл в
каталоге задачи» в выводе.

Зелёный с рождения: полный набор фактически валидных артефактов уже проходит существующие правила содержания сегодня без нового правила белого списка — регресс-контроль на будущее.

Подробности: `Ac2NamedReasonNotFrontmatterParseTest::
test_ac2_all_mode_is_silent_on_the_full_named_allowlist` и `::
test_ac2_artifact_branch_mode_is_silent_on_the_full_named_allowlist` —
полный набор ФАКТИЧЕСКИ валидных артефактов уже проходит существующие
(независимые от этой SPEC) правила содержания сегодня, без какого-либо
нового правила белого списка (его пока нет, поэтому и ломать он ничего
не может). Оба теста — регресс-контроль на будущее: как только правило
появится, оно не имеет права начать ошибочно помечать эти легитимные
штатные имена посторонними или как-то иначе красить `--all`.

Стаб для самопроверки (решение Оператора 03.09) прогонялся локально:
временная реализация — общий top-level scan по образцу
`scan_extraneous_acceptance_files`, применённый к `tasks/<id>/*` (не
`acceptance_tests/*`), с перечнем имён из AC-1, встроенная в `main()`
`--all` рядом с существующим фильтром — зеленила все пять тестов этого
файла; следом убрана, репозиторий не тронут.
"""
import io
import sys
import tempfile
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

VALID_PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: фикстура

## Подход
Фикстура.

## Шаги
1. Фикстура.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Фикстура.
"""

VALID_REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: draft
schema_version: 1
---

# REVIEW: фикстура

## Соответствие SPEC
Фикстура.

## Замечания
Фикстура.

## Вердикт
Фикстура.
"""

VALID_TEST_REPORT_MD = """---
task: {task}
type: test_report
author_role: test_author
status: passed
schema_version: 4
---

# TEST_REPORT: фикстура

## Матрица критериев
Фикстура.

## Вердикт
Фикстура.
"""

VALID_QUESTIONS_MD = """---
task: {task}
type: questions
author_role: analyst
status: ready
schema_version: 4
---

# QUESTIONS: фикстура

## Вопросы
Фикстура.
"""

VALID_TZ_MD = """---
task: {task}
type: tz
author_role: operator
status: ready
schema_version: 4
---

# TZ: фикстура

Свободный текст ТЗ.
"""

VALID_ANSWER_MD = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 4
---

# ANSWER-7: фикстура

## Ответы
Фикстура.
"""

FRONTMATTER_ERROR_HINTS = (
    "нет frontmatter",
    "добавь в frontmatter",
    "неизвестный type",
    "не прочитан",
)

STRAY_REASON = "посторонний файл в каталоге задачи"


def run_guard(argv: list) -> tuple:
    """(код возврата, stdout) `guard.main()` с заданными аргументами —
    тот же приём, что `tasks/01M1SAA01YRRTWAVADT2F81RRQ/acceptance_tests/
    test_guard_extraneous_acceptance_test_file.py::run_guard`."""
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["scripts/guard.py", *argv]):
        with redirect_stdout(buf):
            rc = guard.main()
    return rc, buf.getvalue()


class _GuardAllModesTmpRepoTest(unittest.TestCase):
    """Общая обвязка: `tasks/<task_id>/` во временном cwd (guard `--all`
    обходит `Path("tasks")` от cwd, git не нужен)."""

    TASK = "01FAKEGUARDTASKROOT01"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp_root = Path(tmp.name)
        self.task_dir = self.tmp_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)
        self._orig_cwd = Path.cwd()
        import os
        os.chdir(self.tmp_root)
        self.addCleanup(os.chdir, self._orig_cwd)

    def write(self, rel: str, content: str) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_full_allowed_set_placeholder_content(self) -> None:
        """Полный перечень AC-1, представленный ОДНОВРЕМЕННО в одном
        каталоге — содержимое НЕ обязано быть содержательно валидным
        (AC-1 — про распознавание ИМЕНИ как непостороннего, не про
        существующие правила содержания; те правила покрыты отдельно, не
        этой планкой)."""
        self.write("SPEC.md", "---\ntask: x\ntype: spec\nstatus: draft\n---\n# x\n")
        self.write("PLAN.md", "---\ntask: x\ntype: plan\nstatus: draft\n---\n# x\n")
        self.write("REVIEW.md", "---\ntask: x\ntype: review\nstatus: draft\n---\n# x\n")
        self.write("TEST_REPORT.md",
                   "---\ntask: x\ntype: test_report\nstatus: draft\n---\n# x\n")
        self.write("QUESTIONS.md",
                   "---\ntask: x\ntype: questions\nstatus: draft\n---\n# x\n")
        self.write("TZ.md", "---\ntask: x\ntype: tz\nstatus: draft\n---\n# x\n")
        self.write("ANSWER-7.md",
                   "---\ntask: x\ntype: answer\nstatus: ready\n---\n# x\n")
        self.write("acceptance_tests/test_x.py", "# фикстура\n")
        self.write("x.patch", "диф фикстуры\n")

    def write_full_allowed_set_valid_content(self) -> None:
        """Тот же перечень, но КАЖДЫЙ файл честно проходит существующие
        (независимые от этой SPEC) правила содержания — нужен там, где
        тест требует буквального «guard молчит» (AC-2), не только
        отсутствия именованной причины «постороннее» (AC-1)."""
        self.write("SPEC.md", VALID_SPEC_MD.format(task=self.TASK))
        self.write("PLAN.md", VALID_PLAN_MD.format(task=self.TASK))
        self.write("REVIEW.md", VALID_REVIEW_MD.format(task=self.TASK))
        self.write("TEST_REPORT.md", VALID_TEST_REPORT_MD.format(task=self.TASK))
        self.write("QUESTIONS.md", VALID_QUESTIONS_MD.format(task=self.TASK))
        self.write("TZ.md", VALID_TZ_MD.format(task=self.TASK))
        self.write("ANSWER-7.md", VALID_ANSWER_MD.format(task=self.TASK))
        self.write("acceptance_tests/test_x.py", "# фикстура\n")
        self.write("x.patch", "диф фикстуры\n")

    def stray_lines(self, out: str) -> list:
        return [line for line in out.splitlines() if STRAY_REASON in line]


class Ac1WhitelistCoversAllEnumeratedNamesTest(_GuardAllModesTmpRepoTest):
    """AC-1: белый список — ОДНО место в guard.py, распознающее ВЕСЬ
    перечисленный набор имён/расширений одновременно как непосторонние —
    проверяется В ПРИСУТСТВИИ настоящего постороннего файла, иначе
    отсутствие жалоб ничего не доказывало бы (guard молчал бы одинаково
    и с реализованным, и с отсутствующим правилом)."""

    def test_ac1_all_enumerated_names_are_recognized_while_a_real_stray_file_is_flagged(self):
        """Полный перечень имён AC-1 — ни одно не названо посторонним, но
        добавленный рядом `notes.txt` — назван; единственная строка с
        причиной «посторонний файл в каталоге задачи» относится именно к
        `notes.txt`.

        Ловит мутацию: из белого списка выпадает одно из перечисленных
        имён/шаблонов (например, `TZ.md`, `ANSWER-<n>.md` или `*.patch`)
        — тогда рядом с `notes.txt` в выводе появится вторая строка с той
        же причиной для выпавшего имени, и проверка «ровно одна строка,
        она про notes.txt» упадёт.
        """
        self.write_full_allowed_set_placeholder_content()
        self.write("notes.txt", "черновая заметка ревьювера\n")

        rc, out = run_guard(["--all"])

        self.assertEqual(rc, 1, out)
        stray = self.stray_lines(out)
        self.assertEqual(len(stray), 1, out)
        self.assertIn("notes.txt", stray[0])


class Ac2NamedReasonNotFrontmatterParseTest(_GuardAllModesTmpRepoTest):
    """AC-2: файл первого уровня `tasks/<id>/` вне белого списка AC-1 —
    именованная ошибка «посторонний файл в каталоге задачи» в ОБОИХ
    режимах, не попытка разбора его как артефакта с frontmatter; на
    полном штатном наборе имён guard молчит целиком."""

    def test_ac2_all_mode_names_stray_file_without_frontmatter_parse_attempt(self):
        """Посторонний `notes.txt` первого уровня рядом с валидным
        `SPEC.md` получает именно именованную причину, а не молчаливое
        «ок» (сегодня `notes.txt` не `.md` — обход `--all` его вообще не
        находит) и не жалобу на frontmatter.

        Ловит мутацию: обход `--all` остаётся ограничен `*.md` — тогда
        `notes.txt` не будет замечен вовсе, и guard молча ответит «ок»
        вместо именованного нарушения.
        """
        self.write("SPEC.md", VALID_SPEC_MD.format(task=self.TASK))
        self.write("notes.txt", "черновая заметка ревьювера\n")

        rc, out = run_guard(["--all"])

        self.assertEqual(rc, 1, out)
        self.assertIn(STRAY_REASON, out)
        self.assertIn("notes.txt", out)
        for line in self.stray_lines(out):
            for hint in FRONTMATTER_ERROR_HINTS:
                with self.subTest(строка=line, подсказка=hint):
                    self.assertNotIn(hint, line)

    def test_ac2_artifact_branch_mode_names_stray_file_the_same_way(self):
        """Тот же посторонний файл, режим `--artifact-branch`: та же
        именованная причина, не сводка «сдано/черновиков» без единого
        слова про постороннее.

        Ловит мутацию: именованная причина реализована только для
        обычного режима `--all` — `_artifact_branch_report` продолжает
        видеть необработанный список файлов, и режим артефактной ветки
        не получает нового нарушения вовсе (AC-2 явно требует обоих
        режимов).
        """
        self.write("SPEC.md", VALID_SPEC_MD.format(task=self.TASK))
        self.write("notes.txt", "черновая заметка ревьювера\n")

        rc, out = run_guard(["--all", "--artifact-branch"])

        self.assertEqual(rc, 1, out)
        self.assertIn(STRAY_REASON, out)
        self.assertIn("notes.txt", out)

    def test_ac2_all_mode_is_silent_on_the_full_named_allowlist(self):
        """Полный штатный набор имён (включая `ANSWER-7.md` и `x.patch`),
        каждый файл содержательно валиден, — guard молчит буквально: код
        возврата 0, ни строки вывода.

        Ловит мутацию: правило белого списка реализовано, но случайно
        задевает и содержательно корректный штатный файл (например,
        неверно определяет границу имени `ANSWER-<n>.md` регэкспом,
        ловящим только `ANSWER-1.md`) — тогда `guard --all` вернёт 1 и
        напечатает нарушение по легитимному файлу набора.
        """
        self.write_full_allowed_set_valid_content()

        rc, out = run_guard(["--all"])

        self.assertEqual(rc, 0, out)
        self.assertEqual(out.strip(), "GUARD: ок (7 файлов)")

    def test_ac2_artifact_branch_mode_is_silent_on_the_full_named_allowlist(self):
        """Тот же полный штатный набор, режим `--artifact-branch`: сводка
        «сдано/черновиков» без единого нарушения/предупреждения.

        Ловит мутацию: правило белого списка учтено только в обычном
        режиме `--all`, а `_artifact_branch_report` продолжает получать
        на вход НЕотфильтрованный список файлов — штатное имя (например,
        `TZ.md`, для которого раньше не было отдельного типа) получит
        нарушение и в этом режиме тоже.
        """
        self.write_full_allowed_set_valid_content()

        rc, out = run_guard(["--all", "--artifact-branch"])

        self.assertEqual(rc, 0, out)
        self.assertNotIn(STRAY_REASON, out)
        self.assertNotIn("GUARD: нарушения", out)
        self.assertNotIn("GUARD: предупреждения", out)


if __name__ == "__main__":
    unittest.main()
