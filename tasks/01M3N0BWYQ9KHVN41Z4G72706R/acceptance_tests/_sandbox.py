"""Тонкая надстройка `LightTransitionSandbox` (tests/sandbox.py) для планки
задачи 01M3N0BWYQ9KHVN41Z4G72706R: ВЛОЖЕННАЯ синтетическая задача-песочница
доводится до `tests_writing` с подставными файлами `acceptance_tests/` на
диске, затем зовётся настоящий `fsm.cmd_advance`, и наблюдается исход
выхода из `tests_writing` — состояние задачи и записи журнала.

`disk_backed_show`/`disk_backed_ls_tree_files`/`advance_from_in_dev` не
переопределяются — приходят готовыми с `LightTransitionSandbox`
(skills/test-authoring.md, «Лёгкая песочница переходов — не копия,
импорт»).

Почему проверки наблюдаются через `advance`, а не прямым вызовом нового
узла `scripts/guard.py`: SPEC называет место правила (`scripts/guard.py`),
но не имя функции; наблюдаемая поверхность критериев — отказ перехода
`tests_writing -> in_dev` и текст ошибки в журнале задачи. Действие
записи журнала SPEC не фиксирует (новый гейт вправе журналировать под
своим именем или вместе с трассируемостью AC), поэтому отказ здесь —
любая запись с действием «переход отклонён…», появившаяся за этот вызов
`advance`.
"""
import re
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import acceptance, config, fsm, store  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402

REFUSAL_PREFIX = "переход отклонён"

# Подсказка test_author из требования 6/AC-11 — опорные слова, между
# которыми реализация вправе вставить уточнение («исправь файл планки и
# повтори artel.py advance …»).
HINT = re.compile(r"исправь файл.*?повтори", re.S)

# Метки признаков требования 3 — дословно «в формулировке списка» SPEC.
SIGN_TASKS = "tasks/"
SIGN_GIT_MODULE = "git-модуль"
SIGN_GIT_CALL = "git-вызов"
SIGN_TASK_ID = "номер задачи"
SIGN_SYS_PATH = "sys.path"
SIGN_FOREIGN_IMPORT = "импорт вне перечня"
SIGN_PRIVATE_NAME = "закрытое имя"
SIGN_PATCH_PRIVATE = "patch закрытого"
SIGN_PRIVATE_ATTR = "закрытый атрибут"

GROUP_LONG = "долгоживущий"
GROUP_ONCE = "разовый"

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

CLAIM = "Ловит мутацию: фикстура вложенной песочницы, исполнением не запускается."
GREEN_ONLY = "Зелёный с рождения: фикстура вложенной песочницы держит пустое свойство."

# Подставной файл планки вложенной задачи. Чистый вариант (без `head`/
# `body`) не несёт ни одного признака требования 3: только стандартная
# библиотека и публичные модули `orchestrator`, ни литерала `tasks/`, ни
# идентификатора задачи, ни обращения к закрытым именам, у тестового метода
# — заявка «Ловит мутацию». Нарушение в каждом сценарии добавляется ОДНОЙ
# строкой, чтобы номер строки в тексте ошибки указывал именно на неё.
_PLANK_TEMPLATE = '''"""Фикстура файла приёмочных тестов вложенной задачи.
{group_line}
Красен до реализации: фикстура вложенной песочницы — входные данные проверки.
"""
import os  # noqa: F401
import subprocess  # noqa: F401
import sys  # noqa: F401
import unittest
from unittest import mock  # noqa: F401

from orchestrator import fsm, store  # noqa: F401
{head}


class FixtureTest(unittest.TestCase):

    def test_ac1_fixture_criterion(self):
        """Фикстурный критерий вложенной песочницы.

        {claim}
        """
{body}
        self.assertTrue(True)
'''


def plank_source(group: str | None = GROUP_LONG, head: list[str] = (),
                 body: list[str] = (), claim: str | None = CLAIM,
                 raw_group_line: str | None = None) -> str:
    """Текст подставного `test_*.py`: `group` — значение строки группы
    (`None` — строки нет вовсе), `raw_group_line` — строка группы целиком
    (для значений вне перечня), `head` — строки уровня модуля после
    импортов, `body` — строки тела тестового метода, `claim` — строка
    заявки в докстринге метода (`None` — докстринг без неё)."""
    if raw_group_line is not None:
        group_line = f"\n{raw_group_line}"
    elif group is None:
        group_line = ""
    else:
        group_line = f"\nГруппа: {group}"
    indented = "\n".join(f"        {line}" for line in body)
    return _PLANK_TEMPLATE.format(
        group_line=group_line, head="\n".join(head), body=indented,
        claim=claim or "Без заявки мутации.")


def line_of(source: str, needle: str) -> int:
    """Номер строки (с 1) первой строки `source`, совпадающей с `needle`
    без учёта отступа — ожидаемый номер в тексте ошибки."""
    for number, line in enumerate(source.splitlines(), start=1):
        if line.strip() == needle.strip():
            return number
    raise AssertionError(f"строки {needle!r} нет в тексте фикстуры")


class GroupPlankSandbox(LightTransitionSandbox):
    """Вложенная задача в `tests_writing` с подставной планкой на диске.

    `self.TASK`/`self.tdir` заводит `LightTransitionSandbox.setUp`
    (настоящий `catalog.cmd_new` во временном `config.ROOT`); здесь —
    SPEC.md вложенной задачи, файлы её `acceptance_tests/`, смена target/
    признака канарейки строкой БД и вызов `advance` с зелёным сухим
    сбором (если сценарию не нужен настоящий)."""

    def setUp(self):
        super().setUp()
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            SPEC_ONE_AC.format(task=self.TASK), encoding="utf-8")
        self.set_state("tests_writing")

    def plank_dir(self) -> Path:
        return self.tdir / "acceptance_tests"

    def write_plank(self, files: dict[str, str]) -> None:
        """Кладёт файлы планки вложенной задачи, стирая остатки прошлого
        сценария (один тест разыгрывает несколько сценариев подряд)."""
        tests_dir = self.plank_dir()
        if tests_dir.is_dir():
            for stale in tests_dir.iterdir():
                if stale.is_file():
                    stale.unlink()
        tests_dir.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (tests_dir / name).write_text(content, encoding="utf-8")

    def set_target(self, target: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET target=? WHERE id=?", (target, self.TASK))
        conn.commit()

    def set_canary(self) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET is_canary=1 WHERE id=?", (self.TASK,))
        conn.commit()

    def _last_step_id(self) -> int:
        row = store.db().execute(
            "SELECT MAX(id) AS m FROM steps WHERE task_id=?",
            (self.TASK,)).fetchone()
        return row["m"] or 0

    def advance(self, real_collect: bool = False) -> tuple[str, list[str]]:
        """(вывод, отказы) настоящего `fsm.cmd_advance` из `tests_writing`.

        `отказы` — тексты «действие detail» записей журнала с действием
        «переход отклонён…», появившихся за ЭТОТ вызов. Сухой сбор
        (`acceptance.collect`) по умолчанию замокан зелёным: исход
        зависит только от статических проверок, не от того, собирается ли
        подставная планка во временном корне (`real_collect=True` — для
        сценария, где предмет проверки и есть сухой сбор)."""
        self.set_state("tests_writing")
        before = self._last_step_id()
        if real_collect:
            out = self.capture(fsm.cmd_advance, self.TASK)
        else:
            with mock.patch.object(acceptance, "collect",
                                   return_value=(True, "1 test collected")):
                out = self.capture(fsm.cmd_advance, self.TASK)
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? AND id>? "
            "ORDER BY id", (self.TASK, before)).fetchall()
        refusals = [f"{r['action']} {r['detail'] or ''}" for r in rows
                    if (r["action"] or "").startswith(REFUSAL_PREFIX)]
        return out, refusals

    def assert_passes(self, files: dict[str, str], why: str) -> None:
        """Планка `files` проходит выход из `tests_writing`: задача в
        `in_dev`, ни одной записи отказа за вызов."""
        self.write_plank(files)
        out, refusals = self.advance()
        self.assertEqual(
            self.state(), "in_dev",
            f"{why}: переход обязан пройти; отказы: {refusals!r}; "
            f"вывод: {out!r}")
        self.assertEqual(refusals, [], why)

    def assert_refused_naming(self, files: dict[str, str], *needles: str,
                              why: str) -> list[str]:
        """Планка `files` отклоняет выход из `tests_writing`: задача
        осталась в `tests_writing`, и ОДНА из записей отказа несёт все
        `needles` (имя файла, метод, …). Возвращает записи отказа."""
        self.write_plank(files)
        out, refusals = self.advance()
        self.assertEqual(
            self.state(), "tests_writing",
            f"{why}: переход обязан быть отклонён; вывод: {out!r}")
        self.assertTrue(refusals, f"{why}: нет записи отказа; вывод: {out!r}")
        self.assertTrue(
            any(all(n in text for n in needles) for text in refusals),
            f"{why}: ни одна запись отказа не несёт {needles!r}: {refusals!r}")
        return refusals

    def assert_sign_refused(self, source: str, offending: str, sign: str,
                            file_name: str = "test_ac.py") -> None:
        """Долгоживущий файл с признаком `sign` на строке `offending`
        отклоняет переход; в тексте отказа есть фрагмент ошибки, который
        называет файл, номер этой строки и признак (требование 3)."""
        self.write_plank({file_name: source})
        out, refusals = self.advance()
        self.assertEqual(
            self.state(), "tests_writing",
            f"признак «{sign}» ({offending!r}) обязан отклонить переход; "
            f"вывод: {out!r}")
        lineno = line_of(source, offending)
        number = re.compile(rf"(?<!\d){lineno}(?!\d)")
        # Путь вложенной задачи в метке файла сам содержит `tasks/` и её
        # идентификатор — вычищается, чтобы признак `tasks/`/«номер
        # задачи» засчитывался только по тексту самой ошибки.
        path_noise = re.compile(rf"\S*tasks/{self.TASK}/", re.I)
        chunks = []
        for text in refusals:
            for chunk in re.split(r";\s|\n", text):
                if file_name in chunk:
                    chunks.append(chunk)
        matched = [c for c in chunks
                   if number.search(path_noise.sub("", c))
                   and sign in path_noise.sub("", c)]
        self.assertTrue(
            matched,
            f"нет ошибки, называющей файл {file_name}, строку {lineno} и "
            f"признак «{sign}»; отказы: {refusals!r}")


def default_target() -> str:
    return config.DEFAULT_TARGET
