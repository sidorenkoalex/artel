"""Юнит-тесты узла двух групп приёмочных тестов в `scripts/guard.py`
(SPEC 01M3N0BWYQ9KHVN41Z4G72706R, требования 1, 3, 4; ADR-0020):
строка группы (`plank_file_group`/`group_line_errors_from_files`/
`plank_has_group_lines`) и проверки долгоживущего файла
(`long_lived_sign_hits`/`long_lived_errors_from_files`).

Каждый признак требования 3 — отдельный метод: чистая фикстура `source()`
(ни одного признака) плюс ОДНА строка с признаком; ожидаемая строка
ошибки считается по тексту фикстуры.
"""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import guard  # noqa: E402

TASK_ID = "01ABCDEFGHJKMNPQRSTVWXYZ00"

CLAIM = "Ловит мутацию: фикстура узла групп, исполнением не запускается."

_TEMPLATE = '''"""Фикстура файла планки.
{group_line}
"""
import os  # noqa: F401
import subprocess  # noqa: F401
import sys  # noqa: F401
import unittest
from unittest import mock  # noqa: F401

from orchestrator import fsm, store  # noqa: F401
{head}


class FixtureTest(unittest.TestCase):

    def test_fixture(self):
        """Фикстурный метод.

        {claim}
        """
{body}
        self.assertTrue(True)
'''


def source(group: str | None = guard.GROUP_LONG_LIVED, head: list = (),
           body: list = (), claim: str = CLAIM) -> str:
    group_line = "" if group is None else f"Группа: {group}"
    return _TEMPLATE.format(
        group_line=group_line, head="\n".join(head), claim=claim,
        body="\n".join(f"        {line}" for line in body))


def line_of(text: str, needle: str) -> int:
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip() == needle.strip():
            return number
    raise AssertionError(f"строки {needle!r} нет в фикстуре")


class GroupLineTest(unittest.TestCase):

    def test_both_values_are_recognised(self):
        """`Группа: долгоживущий` и `Группа: разовый` — распознанная группа
        без ошибки.

        Ловит мутацию: значение сравнивается с «долгоживущии»/без «ё» или
        перечень несёт одно значение — одна из групп даёт ошибку.
        """
        for group in guard.GROUP_VALUES:
            with self.subTest(group=group):
                self.assertEqual(guard.plank_file_group(source(group)),
                                 (group, None))

    def test_missing_line_is_an_error_naming_the_file(self):
        """Докстринг модуля без строки группы — ошибка с меткой файла.

        Ловит мутацию: отсутствие строки трактуется как «разовый» по
        умолчанию — ошибок нет.
        """
        errors = guard.group_line_errors_from_files(
            [("acceptance_tests/test_x.py", source(None))])
        self.assertEqual(len(errors), 1)
        self.assertIn("acceptance_tests/test_x.py", errors[0])

    def test_unknown_value_is_an_error_naming_value(self):
        """`Группа: временный` — ошибка с файлом и неизвестным значением.

        Ловит мутацию: выражение принимает любое слово после «Группа:»
        без сверки с перечнем — ошибок нет.
        """
        errors = guard.group_line_errors_from_files(
            [("test_x.py", source("временный"))])
        self.assertEqual(len(errors), 1)
        self.assertIn("test_x.py", errors[0])
        self.assertIn("временный", errors[0])

    def test_line_must_stand_alone_in_module_docstring(self):
        """«Группа:» внутри фразы и строка группы в докстринге метода (не
        модуля) строкой группы не считаются.

        Ловит мутацию: выражение без якоря начала строки или поиск по
        всему тексту файла — фраза «строка Группа: разовый» засчитана.
        """
        prose = source(None).replace(
            "Фикстура файла планки.", "Фикстура: строка Группа: разовый.")
        self.assertIsNone(guard.plank_file_group(prose)[0])
        in_method = source(None, claim=CLAIM + "\n        Группа: разовый")
        self.assertIsNone(guard.plank_file_group(in_method)[0])

    def test_two_different_values_are_an_error(self):
        """Две строки группы с разными значениями — ошибка.

        Ловит мутацию: берётся первое совпадение — файл засчитан
        долгоживущим, ошибки нет.
        """
        text = source(guard.GROUP_LONG_LIVED).replace(
            "Группа: долгоживущий", "Группа: долгоживущий\nГруппа: разовый")
        self.assertEqual(len(guard.group_line_errors_from_files(
            [("test_x.py", text)])), 1)

    def test_single_group_pattern_in_guard(self):
        """Правило разбора строки группы — одно выражение модуля `guard`.

        Ловит мутацию: рядом завели второе выражение строки группы
        (копию правила) — выражений два.
        """
        import re
        patterns = [name for name, value in vars(guard).items()
                    if isinstance(value, re.Pattern) and "Группа" in value.pattern]
        self.assertEqual(patterns, ["GROUP_LINE"])

    def test_plank_has_group_lines_only_with_recognised_line(self):
        """Планка «после правила» — хоть один файл несёт распознанную
        строку группы; планка без строк (или с неизвестным значением) —
        «до правила».

        Ловит мутацию: функция возвращает `True` для любой непустой
        планки — старая планка без строк группы начинает проверяться.
        """
        self.assertFalse(guard.plank_has_group_lines([("t.py", source(None))]))
        self.assertFalse(guard.plank_has_group_lines(
            [("t.py", source("временный"))]))
        self.assertTrue(guard.plank_has_group_lines(
            [("a.py", source(None)), ("b.py", source(guard.GROUP_ONE_OFF))]))


class LongLivedSignTest(unittest.TestCase):

    def assert_sign(self, sign: str, head: list = (), body: list = ()) -> None:
        text = source(head=head, body=body)
        offending = (list(head) + list(body))[-1]
        lineno = line_of(text, offending)
        errors = guard.long_lived_errors_from_files([("test_x.py", text)], TASK_ID)
        self.assertTrue(
            any(e.startswith(f"test_x.py:{lineno}: ") and f"«{sign}»" in e
                for e in errors),
            f"нет ошибки «{sign}» на строке {lineno}: {errors!r}")

    def test_clean_fixture_has_no_errors(self):
        """Чистая фикстура — ни одной ошибки (база остальных методов).

        Ловит мутацию: признак срабатывает на стандартный импорт
        `from unittest import mock` или на `self.assertTrue` — чистый файл
        получает ошибку.
        """
        self.assertEqual(
            guard.long_lived_errors_from_files([("test_x.py", source())], TASK_ID),
            [])

    def test_sign_tasks_literal(self):
        """Литерал, содержащий `tasks/` не в начале, — признак `tasks/`.

        Ловит мутацию: проверка признака `tasks/` снята (или ищет только
        литерал, начинающийся с `tasks/`).
        """
        self.assert_sign(guard.SIGN_TASKS, head=['NOTE = "каталог tasks/ пульта"'])

    def test_sign_git_module(self):
        """Три формы импорта `gitcmd`/`artifact_branch` — признак
        `git-модуль`.

        Ловит мутацию: проверка признака «git-модуль» снята (или смотрит
        только на `import …`, не на `from orchestrator import gitcmd`).
        """
        for line in ("from orchestrator import gitcmd",
                     "import orchestrator.artifact_branch",
                     "from orchestrator.gitcmd import show"):
            with self.subTest(line=line):
                self.assert_sign(guard.SIGN_GIT_MODULE, head=[line])

    def test_sign_git_call(self):
        """`subprocess` со списком `["git", …]`, строкой `"git …"`,
        `os.system("git …")` и `run` из `from subprocess import run` —
        признак `git-вызов`; вызов не-git команды — нет.

        Ловит мутацию: проверка признака «git-вызов» снята (или узнаёт
        только список аргументов).
        """
        for line in ('subprocess.run(["git", "status"])',
                     'subprocess.check_output("git log -1", shell=True)',
                     'os.system("git status")'):
            with self.subTest(line=line):
                self.assert_sign(guard.SIGN_GIT_CALL, body=[line])
        self.assert_sign(guard.SIGN_GIT_CALL,
                         head=["from subprocess import run"],
                         body=['run(args=["git", "log"])'])
        text = source(body=['subprocess.run(["ls", "git"])'])
        self.assertEqual(guard.long_lived_errors_from_files(
            [("test_x.py", text)], TASK_ID), [])

    def test_sign_task_id_any_case(self):
        """Идентификатор задачи в литерале (любой регистр) и в имени —
        признак «номер задачи».

        Ловит мутацию: проверка признака «номер задачи» снята (или
        сравнивает без приведения регистра).
        """
        for line in (f'REF = "{TASK_ID}"', f'REF = "{TASK_ID.lower()}"',
                     f"ref_{TASK_ID.lower()} = 1"):
            with self.subTest(line=line):
                self.assert_sign(guard.SIGN_TASK_ID, head=[line])

    def test_sign_sys_path(self):
        """`insert`/`append`/`extend` и присваивание в `sys.path` (целиком,
        по индексу, по срезу, `+=`) — признак `sys.path`.

        Ловит мутацию: проверка признака `sys.path` снята (или ловит
        только `sys.path.insert`).
        """
        for line in ('sys.path.insert(0, "/x")', 'sys.path.append("/x")',
                     'sys.path.extend(["/x"])', 'sys.path = ["/x"]',
                     'sys.path[0] = "/x"', 'sys.path[0:0] = ["/x"]',
                     'sys.path += ["/x"]'):
            with self.subTest(line=line):
                self.assert_sign(guard.SIGN_SYS_PATH, head=[line])

    def test_sign_import_outside_list(self):
        """Помощник по голому имени, сторонний пакет, относительный импорт
        — признак «импорт вне перечня»; `tests.sandbox` и `pytest` —
        нет.

        Ловит мутацию: проверка признака «импорт вне перечня» снята (или
        относительный импорт с пустым `module` пропускается).
        """
        for line in ("import _sandbox", "from _util import helper",
                     "import requests", "from . import neighbour",
                     "from .neighbour import thing"):
            with self.subTest(line=line):
                self.assert_sign(guard.SIGN_FOREIGN_IMPORT, head=[line])
        text = source(head=["from tests import sandbox", "import pytest"])
        self.assertEqual(guard.long_lived_errors_from_files(
            [("test_x.py", text)], TASK_ID), [])

    def test_sign_private_name_import(self):
        """Имя или сегмент пути модуля с подчёркиванием в импорте из
        `orchestrator`/`scripts` — признак «закрытое имя»; из `tests` —
        нет.

        Ловит мутацию: проверка признака «закрытое имя» снята (или смотрит
        только на импортируемые имена, не на сегменты пути модуля).
        """
        for line in ("from orchestrator.fsm import _x",
                     "import orchestrator.advance_gates._base",
                     "from scripts.guard import _dotted_name"):
            with self.subTest(line=line):
                self.assert_sign(guard.SIGN_PRIVATE_NAME, head=[line])
        text = source(head=["from tests.sandbox import _REPO_ROOT"])
        self.assertEqual(guard.long_lived_errors_from_files(
            [("test_x.py", text)], TASK_ID), [])

    def test_sign_patch_private(self):
        """`patch`/`mock.patch`/`unittest.mock.patch` со строкой, чей
        сегмент закрыт, и `patch.object(obj, "_x")` — признак «patch
        закрытого»; `patch` публичного имени — нет.

        Ловит мутацию: проверка признака «patch закрытого» снята (или не
        разбирает второй аргумент `patch.object`).
        """
        for line in ('mock.patch("orchestrator.fsm._x")',
                     'mock.patch.object(fsm, "_x")',
                     'unittest.mock.patch("orchestrator.fsm._x")',
                     'mock.patch.object(fsm, attribute="_x")'):
            with self.subTest(line=line):
                self.assert_sign(guard.SIGN_PATCH_PRIVATE, body=[line])
        self.assert_sign(guard.SIGN_PATCH_PRIVATE,
                         head=["from unittest.mock import patch"],
                         body=['patch("orchestrator.fsm._x")'])
        text = source(body=['mock.patch("orchestrator.fsm.cmd_advance")',
                            'mock.patch.object(fsm, "cmd_advance")'])
        self.assertEqual(guard.long_lived_errors_from_files(
            [("test_x.py", text)], TASK_ID), [])

    def test_sign_private_attribute(self):
        """`store._x`, `fsm._x` и `obj._x` локального имени — признак
        «закрытый атрибут»; `self._x`, `super()._x`, `os._exit` и имя из
        `tests` — нет.

        Ловит мутацию: проверка признака «закрытый атрибут» снята (или
        исключение «корень — self/cls» расширено на любое имя).
        """
        for line in ("value = store._x", "value = fsm._y.z",
                     "value = object()._x"):
            with self.subTest(line=line):
                self.assert_sign(guard.SIGN_PRIVATE_ATTR, body=[line])
        text = source(head=["from tests import sandbox as sandbox_mod"],
                      body=["self._value = 1", "super()._cleanup",
                            "value = os._exit", "root = sandbox_mod._REPO_ROOT",
                            "name = self.__class__"])
        self.assertEqual(guard.long_lived_errors_from_files(
            [("test_x.py", text)], TASK_ID), [])


class LongLivedScopeTest(unittest.TestCase):

    def test_one_off_file_is_not_checked(self):
        """Разовый файл со всеми признаками и методом без заявки — ни
        одной ошибки; тот же файл долгоживущим — ошибки есть.

        Ловит мутацию: проверки долгоживущего файла применяются без учёта
        группы — разовый файл получает ошибки.
        """
        head = ['NOTE = "tasks/"', "from orchestrator import gitcmd",
                'sys.path.insert(0, "/x")', "import _sandbox"]
        body = ["value = store._x"]
        once = source(guard.GROUP_ONE_OFF, head, body, claim="Без заявки.")
        self.assertEqual(guard.long_lived_errors_from_files(
            [("test_x.py", once)], TASK_ID), [])
        long = source(guard.GROUP_LONG_LIVED, head, body, claim="Без заявки.")
        self.assertTrue(guard.long_lived_errors_from_files(
            [("test_x.py", long)], TASK_ID))

    def test_method_without_claim_is_named(self):
        """Метод долгоживущего файла без «Ловит мутацию» и метод только с
        «Зелёный с рождения» — ошибка с файлом и методом.

        Ловит мутацию: проверка заявки у долгоживущего файла снята (или
        «Зелёный с рождения» засчитан заявкой).
        """
        for claim in ("Без заявки.", "Зелёный с рождения: держит пустое."):
            with self.subTest(claim=claim):
                errors = guard.long_lived_errors_from_files(
                    [("test_x.py", source(claim=claim))], TASK_ID)
                self.assertTrue(any("test_x.py" in e and "test_fixture" in e
                                    for e in errors), errors)

    def test_signs_on_random_lines(self):
        """Признак, вставленный на случайную по счёту строку тела метода
        (зерно печатается), — ошибка называет именно её номер.

        Ловит мутацию: номер строки ошибки берётся от узла-родителя
        (функции/класса), а не от узла признака — номер не совпадает.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        filler = [f"x{i} = {i}" for i in range(rng.randrange(1, 15))]
        position = rng.randrange(len(filler) + 1)
        body = filler[:position] + ["value = store._x"] + filler[position:]
        text = source(body=body)
        lineno = line_of(text, "value = store._x")
        errors = guard.long_lived_errors_from_files([("t.py", text)], TASK_ID)
        self.assertEqual(
            errors, [f"t.py:{lineno}: признак «{guard.SIGN_PRIVATE_ATTR}» — "
                     f"только публичный интерфейс кода"], f"зерно {seed}")


if __name__ == "__main__":
    unittest.main()
