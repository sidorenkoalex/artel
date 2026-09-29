"""AC-6: признаки «номер задачи» (литерал, имя, любой регистр — и в методе
класса песочницы), `sys.path`, «импорт вне перечня», «закрытое имя»,
«patch закрытого», «закрытый атрибут» и отсутствие «Ловит мутацию»
срабатывают как до задачи.

Фикстуры — текст долгоживущего файла, проверяемый публичным
`guard.long_lived_errors_from_files`; строки помечены `# @<метка>`.

Группа: разовый
Зелёный с рождения: признаки держатся нынешним `long_lived_sign_hits` — тест сторожит, что перенос `tasks/`/git на новое правило и разрешение метода песочницы их не ослабили.

Почему разовый: фикстуры несут `sys.path`, закрытые имена и номер
задачи — признаки, запрещённые долгоживущему файлу; долгоживущие тесты
признаков пишет разработчик (требование 15 SPEC).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FIXTURE_TASK_ID, LABEL, errors_of, errors_on,  # noqa: E402
                      line_of, long_lived_text)
from scripts import guard  # noqa: E402

SIGNED = long_lived_text(f'''
import sys
import unittest
from unittest import mock

import requests  # @foreign-import
from orchestrator import fsm, store
from orchestrator.fsm import _hidden  # @private-name
from tests.sandbox import RealGitSandbox

sys.path.insert(0, "/x")  # @sys-path
REF = "{FIXTURE_TASK_ID}"  # @id-upper
ref_{FIXTURE_TASK_ID.lower()} = 1  # @id-name


class CopyTest(RealGitSandbox):

    def test_ac6_copy(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        ref = "{FIXTURE_TASK_ID.lower()}"  # @id-lower-sandbox
        mock.patch("orchestrator.fsm._x")  # @patch-private
        mock.patch.object(fsm, "_x")  # @patch-object-private
        value = store._x  # @private-attr
        self.assertTrue(ref and value and requests and _hidden)


class PlainTest(unittest.TestCase):

    def test_ac6_no_claim(self):
        """Метод без заявки мутации."""
        self.assertTrue(True)
''')

EXPECTED = {
    "foreign-import": guard.SIGN_FOREIGN_IMPORT,
    "private-name": guard.SIGN_PRIVATE_NAME,
    "sys-path": guard.SIGN_SYS_PATH,
    "id-upper": guard.SIGN_TASK_ID,
    "id-name": guard.SIGN_TASK_ID,
    "id-lower-sandbox": guard.SIGN_TASK_ID,
    "patch-private": guard.SIGN_PATCH_PRIVATE,
    "patch-object-private": guard.SIGN_PATCH_PRIVATE,
    "private-attr": guard.SIGN_PRIVATE_ATTR,
}


class UnchangedSignsTest(unittest.TestCase):

    def test_ac6_other_signs_fire_as_before(self):
        """Каждая строка фикстуры с прежним признаком — ошибка с этим
        признаком на своей строке; «номер задачи» — и в методе наследника
        `RealGitSandbox`.

        Ловит мутацию: разрешение «метод класса песочницы» снимает с
        метода все признаки, а не только `tasks/`/«git-модуль» — строки
        `@id-lower-sandbox`/`@patch-private`/`@private-attr` без ошибки.
        """
        errors = errors_of(SIGNED)
        for tag, sign in EXPECTED.items():
            with self.subTest(tag=tag):
                self.assertTrue(
                    errors_on(errors, line_of(SIGNED, tag), sign),
                    f"нет признака «{sign}» на строке @{tag}: {errors!r}")

    def test_ac6_method_without_claim_is_named(self):
        """Метод долгоживущего файла без «Ловит мутацию: …» — ошибка,
        называющая файл и метод.

        Ловит мутацию: проверка заявки мутации выпала из
        `long_lived_errors_from_files` при переписывании признаков —
        ошибки с `test_ac6_no_claim` нет.
        """
        errors = errors_of(SIGNED)
        self.assertTrue(any(LABEL in e and "test_ac6_no_claim" in e
                            for e in errors), errors)

    def test_ac6_task_id_any_case_with_real_task_id(self):
        """Номер задачи, переданный проверке в нижнем регистре, находится и
        в литерале верхнего регистра.

        Ловит мутацию: сравнение номера задачи без приведения регистра —
        литерал `@id-upper` без ошибки.
        """
        errors = guard.long_lived_errors_from_files(
            [(LABEL, SIGNED)], FIXTURE_TASK_ID.lower())
        self.assertTrue(errors_on(errors, line_of(SIGNED, "id-upper"),
                                  guard.SIGN_TASK_ID), errors)


if __name__ == "__main__":
    unittest.main()
