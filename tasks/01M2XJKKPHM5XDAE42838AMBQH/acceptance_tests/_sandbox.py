"""Тонкая надстройка `LightTransitionSandbox` (tests/sandbox.py) для планки
задачи 01M2XJKKPHM5XDAE42838AMBQH: сценарий один на все файлы — ВЛОЖЕННАЯ
синтетическая задача-песочница доводится до состояния `tests_writing` с
подставной планкой на диске, после чего зовётся настоящий
`fsm.cmd_advance`, и наблюдается исход выхода из `tests_writing`.

`disk_backed_show`/`disk_backed_ls_tree_files`/`advance_from_in_dev` здесь
не переопределяются — импортируются готовыми вместе с
`LightTransitionSandbox` (skills/test-authoring.md, «Лёгкая песочница
переходов — не копия, импорт»).

Почему проверка требований 1-3 SPEC наблюдается через `advance`, а не
прямым вызовом новой функции `scripts/guard.py`: SPEC называет функцию
(«отдельная функция, принимающая `*.py` каталога `acceptance_tests/`»),
но не даёт ей имени, а единственный её санкционированный вызов —
гейт выхода `tests_writing` (требование 4 прямо запрещает второй,
из `check()`/`main()`). Наблюдаемая поверхность отказа («переход
отклонён: планка читает артефакты с диска» + текст ошибок в detail,
AC-6) поэтому и есть поверхность, на которой критерии AC-1..AC-5
проверяемы без угадывания имени.
"""
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import acceptance, fsm, store  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402

# Действие журнала отказа (SPEC, требование 5 и AC-6) — дословно.
REFUSAL_ACTION = "переход отклонён: планка читает артефакты с диска"

# Рецепт из текста ошибки (SPEC, требование 3 и AC-1). Проверяются две
# опорные части формулировки: вводная («читай из артефактной ветки») и
# сам вызов; `"tasks/<id>/PLAN.md"` последним аргументом намеренно не
# фиксируется дословно — реализация вправе подставить настоящий id
# задачи и настоящее имя артефакта вместо плейсхолдера.
RECIPE_HEAD = "читай из артефактной ветки"
RECIPE_CALL = "gitcmd.show(artifact_branch.branch_name(TASK_ID)"

# Имена артефактов задачи из требования 1/AC-5. `ANSWER-` — префикс, в
# выражении он встречается именем файла целиком.
ARTIFACT_NAMES = ("PLAN.md", "SPEC.md", "REVIEW.md", "TZ.md",
                  "QUESTIONS.md", "TEST_REPORT.md", "ANSWER-1.md")

SPEC_ONE_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: вложенная песочница одного критерия

## Критерии приёмки

AC-1. Единственный критерий вложенной песочницы, покрытый тестом.
"""

# Шаблон подставной планки вложенной задачи: тело тестового метода —
# строки сценария (чтение артефакта тем или иным способом). Импорты
# `gitcmd`/`artifact_branch` стоят в КАЖДОЙ фикстуре, включая
# нарушающие: «файл вообще-то знает про артефактную ветку» не имеет
# права служить индульгенцией чтению с диска в том же файле.
_PLANK_TEMPLATE = '''"""Фикстура планки вложенной синтетической задачи.{extra}

Зелёный с рождения: это не планка задачи 01M2XJKKPHM5XDAE42838AMBQH, а
входные данные её проверки — исполнением не запускается.
"""
import os  # noqa: F401
import subprocess  # noqa: F401
import unittest
from pathlib import Path  # noqa: F401

from orchestrator import artifact_branch, gitcmd  # noqa: F401

TASK = "01FIXTURETASK"
TASK_DIR = Path(__file__).resolve().parents[1]


class FixturePlankTest(unittest.TestCase):

    def test_ac1_fixture_criterion(self):
        """Фикстурный критерий вложенной песочницы."""
{body}
        self.assertIsNotNone(TASK_DIR)


# AC-1 вложенной песочницы покрыт методом выше.
'''

# Планка вложенной задачи без единого обращения к артефактам — контроль
# «переход проходит, когда читать с диска нечего».
CLEAN_BODY = ['data = TASK_DIR.name']

# Каноническое нарушение — тот самый образец, на котором класс сработал
# 12.09 (AC-8 задачи 01M2B6K3EM). Один на все файлы планки: контроль
# «механизм существует и срабатывает» обязан быть везде одинаковым,
# иначе файлы разъедутся при первой же правке.
DISK_READ_LINE = 'plan = (Path(__file__).resolve().parents[1] / "PLAN.md")'


def plank_source(body: list[str], extra: str = "") -> str:
    """Текст файла подставной планки: строки `body` — тело тестового
    метода (отступ проставляется здесь), `extra` — добавка в докстринг
    модуля."""
    indented = "\n".join(f"        {line}" for line in body)
    return _PLANK_TEMPLATE.format(body=indented, extra=extra)


def line_of(source: str, needle: str) -> int:
    """Номер строки (1-based) первой строки `source`, совпадающей с
    `needle` без учёта отступа — ожидаемый номер в тексте ошибки."""
    for number, line in enumerate(source.splitlines(), start=1):
        if line.strip() == needle.strip():
            return number
    raise AssertionError(f"строки {needle!r} нет в тексте планки")


class ArtifactSourcePlankSandbox(LightTransitionSandbox):
    """Вложенная задача в `tests_writing` с подставной планкой на диске.

    `self.TASK`/`self.tdir` заводит `LightTransitionSandbox.setUp`
    (настоящий `catalog.cmd_new` во временном `config.ROOT`); здесь —
    только SPEC.md вложенной задачи, файлы её `acceptance_tests/` и
    вызов `advance` с зелёным сухим сбором."""

    def enter_tests_writing(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            SPEC_ONE_AC.format(task=self.TASK), encoding="utf-8")
        self.set_state("tests_writing")

    def plank_dir(self) -> Path:
        return self.tdir / "acceptance_tests"

    def write_plank(self, content: str, name: str = "test_ac.py") -> None:
        """Кладёт файл планки вложенной задачи, стирая каталог от файлов
        предыдущего сценария (один тест разыгрывает несколько сценариев
        подряд — остатки прошлого сделали бы исход неоднозначным)."""
        tests_dir = self.plank_dir()
        if tests_dir.is_dir():
            for stale in tests_dir.iterdir():
                if stale.is_file():
                    stale.unlink()
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def add_plank_file(self, content: str, name: str) -> None:
        """Добавляет файл к уже написанной планке, не стирая каталог."""
        (self.plank_dir() / name).write_text(content, encoding="utf-8")

    def advance(self) -> str:
        """Вызов настоящего `fsm.cmd_advance` с зелёным сухим сбором:
        `acceptance.collect` замокан, чтобы исход зависел только от
        проверки источника артефактов, а не от того, собирается ли
        подставная планка в этой временной песочнице (и чтобы тест не
        зависел от порядка двух соседних гейтов одного состояния)."""
        self.set_state("tests_writing")
        with mock.patch.object(acceptance, "collect",
                               return_value=(True, "1 test collected")):
            return self.capture(fsm.cmd_advance, self.TASK)

    def control_refuses(self) -> None:
        """Контроль отрицательных сценариев: механизм проверки
        существует и срабатывает — планка с каноническим чтением
        `PLAN.md` с диска отклоняет выход из `tests_writing`. Без него
        «ошибок нет» доказывало бы лишь отсутствие проверки, и файл
        остался бы зелёным независимо от реализации."""
        source = plank_source([DISK_READ_LINE])
        self.write_plank(source)
        out = self.advance()
        self.assert_disk_read_refused(out, source, DISK_READ_LINE)

    def refusal_details(self) -> list[str]:
        return [row["detail"] or "" for row in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, REFUSAL_ACTION))]

    def assert_disk_read_refused(self, out: str, source: str, offending: str,
                                 file_name: str = "test_ac.py") -> str:
        """Общая проверка положительного исхода: переход отклонён, и в
        тексте отказа есть имя файла планки и номер строки нарушения
        (AC-1). Возвращает detail последнего такого отказа."""
        self.assertEqual(
            self.state(), "tests_writing",
            f"чтение артефакта с диска ({offending}) обязано отклонить "
            f"переход; вывод advance: {out!r}")
        details = self.refusal_details()
        self.assertTrue(
            details,
            f"нет записи журнала «{REFUSAL_ACTION}» для {offending}; "
            f"вывод advance: {out!r}")
        detail = details[-1]
        lineno = line_of(source, offending)
        mentions = [chunk for chunk in detail.replace("; ", "\n").splitlines()
                    if file_name in chunk]
        self.assertTrue(
            mentions,
            f"текст отказа не называет файл планки {file_name}: {detail!r}")
        self.assertTrue(
            any(str(lineno) in chunk for chunk in mentions),
            f"текст отказа не называет номер строки {lineno} "
            f"(строка {offending!r}): {detail!r}")
        return detail
