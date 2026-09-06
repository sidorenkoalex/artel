"""AC-1/AC-2 (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0), формулировка по
ANSWER-1 (tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/ANSWER-1.md, вариант A):
`scripts/guard.py` несёт единый белый список допустимых `*.md` имён
ПЕРВОГО уровня `tasks/<id>/` — `SPEC.md`, `PLAN.md`, `REVIEW.md`,
`TEST_REPORT.md`, `QUESTIONS.md`, `TZ.md`, `ANSWER-<n>.md`. Любой ДРУГОЙ
`*.md` первого уровня — «посторонний файл в каталоге задачи» (класс
инцидента 06.09: копии карты кодовой базы `_head_map.md` и подобные).
Файлы ЛЮБОГО другого расширения (`*.patch`, `*.png`, `*.bin`, `*.html`,
`*.txt` и прочие) — вложения: допускаются БЕЗ ограничений имени (ровно
это разрешило конфликт с уже залоченными `tests/
test_checkpoint_external_step_artifacts.py::test_binary_file_is_not_lost`
и `::test_all_files_binary_still_commits_and_clears_the_dir`, из-за
которого предыдущий заход test_author эскалировал AC-9). Скрытые файлы
и каталоги (`.`-префикс) и `__pycache__/` — посторонние независимо от
расширения. `acceptance_tests/` — по собственным правилам (SPEC
01M1SAA01YRRTWAVADT2F81RRQ), этим правилом не задета.

Сегодня `guard.py --all` обходит только `Path("tasks").rglob("*.md")` и
честно пытается разобрать КАЖДЫЙ найденный `.md`-файл как артефакт с
frontmatter (`check`/`_content_errors`) — правила белого списка ПЕРВОГО
уровня `tasks/<id>/` в guard.py сегодня нет вовсе, ни для `.md`, ни для
скрытых файлов/`__pycache__` (обход `*.md` их и не находит, поскольку
это не сегодняшняя проверка расширения, а полное отсутствие правила).

Красен до реализации: тесты test_ac1_all_enumerated_md_names_recognized_while_stray_md_copy_is_flagged, test_ac1_hidden_file_at_task_root_is_flagged_as_stray, test_ac1_pycache_directory_contents_are_flagged_as_stray и оба test_ac2_..._stray_md_file_... падают, потому что правила белого списка первого уровня нет вовсе — код возврата 0 вместо ожидаемого 1 с именованной причиной.

Подробности по красноте: `_head_map.md` (посторонняя копия карты
кодовой базы), `.DS_Store` (скрытый файл) и `__pycache__/junk.pyc`
сегодня не проверяются НИКАКИМ правилом белого списка — `--all` либо не
находит их в обходе `*.md` вовсе (`.DS_Store`, `__pycache__/junk.pyc` —
не `.md`), либо (`_head_map.md`) находит и пытается разобрать как
артефакт вместо именованной причины. Во всех случаях код возврата
сегодня 0 («GUARD: ок») вместо ожидаемого 1 с строкой «посторонний файл
в каталоге задачи».

Зелёный с рождения: test_ac1_arbitrary_extension_attachments_are_not_flagged_regardless_of_name и оба test_ac2_..._is_silent_on_the_full_named_allowlist проходят уже сегодня, поскольку обход `--all` ограничен `*.md` и никакое правило пока не может ошибочно зацепить не-`.md` вложение или содержательно валидный штатный `.md` — регресс-контроль на будущее правило, не тавтология: как только правило появится, ему запрещено расширяться на вложения или задевать штатные имена.

Стаб для самопроверки (решение Оператора 03.09) прогонялся локально:
временная реализация — top-level scan `tasks/<id>/*`, различающий
`.md`-имена (сверка с перечнем AC-1), скрытые имена (`.`-префикс) и
`__pycache__/` как посторонние, вложения любого другого расширения —
пропуская молча; встроена в `main()` `--all` рядом с существующим
фильтром `acceptance_tests/`. Зеленила все тесты этого файла. Следом
убрана, репозиторий не тронут.
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

# Посторонняя копия карты кодовой базы — буквально сценарий инцидента
# 06.09 из «Контекста» SPEC и из курируемого HOME (docs/reference/
# role-home/claude/CLAUDE.md): `.md`-файл первого уровня `tasks/<id>/`,
# не входящий в перечень AC-1.
STRAY_MD_NAME = "_head_map.md"


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

    def write(self, rel: str, content: str = "содержимое\n") -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_full_allowed_set_placeholder_content(self) -> None:
        """Полный перечень `.md`-имён AC-1, представленный ОДНОВРЕМЕННО
        в одном каталоге — содержимое НЕ обязано быть содержательно
        валидным (AC-1 — про распознавание ИМЕНИ как непостороннего, не
        про существующие правила содержания; те правила покрыты
        отдельно, не этой планкой)."""
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
    перечисленный набор `.md`-имён одновременно как непосторонние —
    проверяется В ПРИСУТСТВИИ настоящего постороннего `.md`-файла, иначе
    отсутствие жалоб ничего не доказывало бы (guard молчал бы одинаково
    и с реализованным, и с отсутствующим правилом)."""

    def test_ac1_all_enumerated_md_names_recognized_while_stray_md_copy_is_flagged(self):
        """Полный перечень `.md`-имён AC-1 — ни одно не названо
        посторонним, но добавленная рядом посторонняя копия карты
        кодовой базы `_head_map.md` — названа; единственная строка с
        причиной «посторонний файл в каталоге задачи» относится именно к
        `_head_map.md`.

        Ловит мутацию: из белого списка `.md`-имён выпадает одно из
        перечисленных (например, `TZ.md` или регэксп `ANSWER-<n>.md`
        ловит только `ANSWER-1.md`) — тогда рядом с `_head_map.md` в
        выводе появится вторая строка с той же причиной для выпавшего
        имени, и проверка «ровно одна строка, она про _head_map.md»
        упадёт.
        """
        self.write_full_allowed_set_placeholder_content()
        self.write(STRAY_MD_NAME, "черновая копия карты кодовой базы\n")

        rc, out = run_guard(["--all"])

        self.assertEqual(rc, 1, out)
        stray = self.stray_lines(out)
        self.assertEqual(len(stray), 1, out)
        self.assertIn(STRAY_MD_NAME, stray[0])

    def test_ac1_arbitrary_extension_attachments_are_not_flagged_regardless_of_name(self):
        """Вложения ЛЮБОГО расширения, кроме `.md`, — `screenshot.png`,
        `blob.bin`, файл вовсе без расширения — лежащие рядом с валидным
        `PLAN.md`, не получают именованную причину «постороннее»,
        независимо от того, насколько странно их имя (ANSWER-1: белый
        список AC-1 действует только для `.md`, вложения других
        расширений допускаются без ограничений имени — это разрешило
        конфликт с уже залоченными `tests/
        test_checkpoint_external_step_artifacts.py::test_binary_file_is_not_lost`
        и `::test_all_files_binary_still_commits_and_clears_the_dir`).

        Ловит мутацию: разработчик реализует буквальный белый список
        AC-1 ДО правки ANSWER-1 (единый список имён/расширений без
        различия «.md» / «прочее», как в первоначальной формулировке
        требования 1 SPEC) — тогда `screenshot.png`/`blob.bin`/
        `weird_no_ext` получат именованную причину наравне с
        `_head_map.md`, и `assertEqual(rc, 0)` ниже упадёт.
        """
        self.write("PLAN.md", VALID_PLAN_MD.format(task=self.TASK))
        self.write("screenshot.png", "не настоящий png, но не суть\n")
        self.write("blob.bin", "бинарная фикстура\n")
        self.write("weird_no_ext", "вложение без расширения\n")

        rc, out = run_guard(["--all"])

        self.assertEqual(rc, 0, out)
        self.assertNotIn(STRAY_REASON, out)


class Ac1HiddenAndPycacheAreStrayTest(_GuardAllModesTmpRepoTest):
    """AC-1: скрытые файлы/каталоги (`.`-префикс) и `__pycache__/` —
    посторонние НЕЗАВИСИМО от расширения (ANSWER-1) — в отличие от
    обычных вложений выше, для которых расширение вне `.md` само по себе
    легально."""

    def test_ac1_hidden_file_at_task_root_is_flagged_as_stray(self):
        """Скрытый файл `.DS_Store` первого уровня `tasks/<id>/`, рядом с
        валидным `PLAN.md`, получает именованную причину «посторонний
        файл в каталоге задачи», хотя расширения `.md` не несёт вовсе.

        Ловит мутацию: правило постороннего ограничено ТОЛЬКО
        `.md`-именами (реализация буквально следует за «белый список
        `.md`» и не заводит отдельную проверку скрытых имён) — тогда
        `.DS_Store` пройдёт как обычное неограниченное вложение, и
        `assertEqual(rc, 1)` ниже упадёт.
        """
        self.write("PLAN.md", VALID_PLAN_MD.format(task=self.TASK))
        self.write(".DS_Store", "мусор macOS\n")

        rc, out = run_guard(["--all"])

        self.assertEqual(rc, 1, out)
        stray = self.stray_lines(out)
        self.assertEqual(len(stray), 1, out)
        self.assertIn(".DS_Store", stray[0])

    def test_ac1_pycache_directory_contents_are_flagged_as_stray(self):
        """Каталог `__pycache__/` первого уровня `tasks/<id>/` (не внутри
        `acceptance_tests/` — та расположена по собственным правилам
        01M1SAA01YRRTWAVADT2F81RRQ) с посторонним содержимым получает
        именованную причину «постороннее».

        Ловит мутацию: `__pycache__/` первого уровня `tasks/<id>/`
        обрабатывается так же, как обычное вложение произвольного
        расширения (правило постороннего проверяет только сами
        `.md`-имена, игнорируя каталоги целиком) — тогда содержимое
        `__pycache__/` пройдёт молча, и `assertEqual(rc, 1)` ниже
        упадёт.
        """
        self.write("PLAN.md", VALID_PLAN_MD.format(task=self.TASK))
        self.write("__pycache__/junk.pyc", "байткод фикстуры\n")

        rc, out = run_guard(["--all"])

        self.assertEqual(rc, 1, out)
        self.assertIn(STRAY_REASON, out)
        self.assertIn("__pycache__", out)


class Ac2NamedReasonNotFrontmatterParseTest(_GuardAllModesTmpRepoTest):
    """AC-2: `.md`-файл первого уровня `tasks/<id>/` вне белого списка
    AC-1 — именованная ошибка «посторонний файл в каталоге задачи» в
    ОБОИХ режимах, не попытка разбора его как артефакта с frontmatter;
    на полном штатном наборе имён guard молчит целиком."""

    def test_ac2_all_mode_names_stray_md_file_without_frontmatter_parse_attempt(self):
        """Посторонняя `.md`-копия `_head_map.md` первого уровня рядом с
        валидным `SPEC.md` получает именно именованную причину, а не
        молчаливое «ок» и не жалобу на frontmatter.

        Ловит мутацию: белый список AC-1 не реализован вовсе (сегодняшнее
        поведение) — `_head_map.md` получит жалобу на отсутствие
        frontmatter (найден обходом `*.md`, разобран как артефакт) вместо
        именованной причины «постороннее», и цикл `assertNotIn` ниже
        поймает подсказку frontmatter-ошибки в той же строке.
        """
        self.write("SPEC.md", VALID_SPEC_MD.format(task=self.TASK))
        self.write(STRAY_MD_NAME, "черновая копия карты кодовой базы\n")

        rc, out = run_guard(["--all"])

        self.assertEqual(rc, 1, out)
        self.assertIn(STRAY_REASON, out)
        self.assertIn(STRAY_MD_NAME, out)
        for line in self.stray_lines(out):
            for hint in FRONTMATTER_ERROR_HINTS:
                with self.subTest(строка=line, подсказка=hint):
                    self.assertNotIn(hint, line)

    def test_ac2_artifact_branch_mode_names_stray_md_file_the_same_way(self):
        """Тот же посторонний `.md`-файл, режим `--artifact-branch`: та
        же именованная причина, не сводка «сдано/черновиков» без единого
        слова про постороннее.

        Ловит мутацию: именованная причина реализована только для
        обычного режима `--all` — `_artifact_branch_report` продолжает
        видеть необработанный список файлов, и режим артефактной ветки
        не получает нового нарушения вовсе (AC-2 явно требует обоих
        режимов).
        """
        self.write("SPEC.md", VALID_SPEC_MD.format(task=self.TASK))
        self.write(STRAY_MD_NAME, "черновая копия карты кодовой базы\n")

        rc, out = run_guard(["--all", "--artifact-branch"])

        self.assertEqual(rc, 1, out)
        self.assertIn(STRAY_REASON, out)
        self.assertIn(STRAY_MD_NAME, out)

    def test_ac2_all_mode_is_silent_on_the_full_named_allowlist(self):
        """Полный штатный набор `.md`-имён (включая `ANSWER-7.md`) плюс
        `x.patch`/`acceptance_tests/`, каждый файл содержательно валиден,
        — guard молчит буквально: код возврата 0, ни строки вывода.

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
