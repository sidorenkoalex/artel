"""AC-7: признак «пропуск» у долгоживущего файла — `skipTest`, `skipIf`,
`skipUnless`, `unittest.skip`, `pytest.skip`, `pytest.mark.skip*` на
строке употребления; разовый файл с теми же формами ошибки не получает.

Фикстуры — текст файла тестов, проверяемый публичным
`guard.long_lived_errors_from_files`; строки помечены `# @<метка>`.

Группа: разовый
Красен до реализации: признака «пропуск» в `long_lived_sign_hits` нет — ни одна строка с пропуском ошибки не получает.

Почему разовый: предмет — признак, которого до задачи нет; долгоживущие
тесты признаков пишет разработчик (требование 15 SPEC).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (SIGN_SKIP, errors_of, errors_on, line_of,  # noqa: E402
                      long_lived_text)
from scripts import guard  # noqa: E402

BODY = '''
import unittest

import pytest

pytestmark = pytest.mark.skip(reason="фикстура")  # @pytestmark


@unittest.skip("фикстура")  # @class-skip
class SkippedClassTest(unittest.TestCase):

    def test_ac7_in_class(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        self.assertTrue(True)


class SkipFormsTest(unittest.TestCase):

    @unittest.skipIf(True, "фикстура")  # @skip-if
    def test_ac7_skip_if(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        self.assertTrue(True)

    @unittest.skipUnless(False, "фикстура")  # @skip-unless
    def test_ac7_skip_unless(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        self.assertTrue(True)

    @unittest.skip("фикстура")  # @method-skip
    def test_ac7_method_skip(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        self.assertTrue(True)

    @pytest.mark.skip(reason="фикстура")  # @mark-skip
    def test_ac7_mark_skip(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        self.assertTrue(True)

    @pytest.mark.skipif(True, reason="фикстура")  # @mark-skipif
    def test_ac7_mark_skipif(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        self.assertTrue(True)

    def test_ac7_calls(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        self.skipTest("фикстура")  # @skip-test
        pytest.skip("фикстура")  # @pytest-skip
'''

LONG_LIVED = long_lived_text(BODY)
ONE_OFF = long_lived_text(BODY, group=guard.GROUP_ONE_OFF)

TAGS = ("pytestmark", "class-skip", "skip-if", "skip-unless", "method-skip",
        "mark-skip", "mark-skipif", "skip-test", "pytest-skip")


class SkipSignTest(unittest.TestCase):

    def test_ac7_long_lived_skip_forms_get_sign(self):
        """Каждая форма пропуска в долгоживущем файле — ошибка с признаком
        «пропуск» на строке употребления (декоратор — на строке
        декоратора).

        Ловит мутацию: признак узнаёт только вызов `skipTest` (или только
        декораторы `unittest`) — строка `@mark-skipif`/`@pytestmark`/
        `@pytest-skip` без ошибки.
        """
        errors = errors_of(LONG_LIVED)
        for tag in TAGS:
            with self.subTest(tag=tag):
                self.assertTrue(
                    errors_on(errors, line_of(LONG_LIVED, tag), SIGN_SKIP),
                    f"нет признака «{SIGN_SKIP}» на строке @{tag}: {errors!r}")

    def test_ac7_one_off_file_with_skips_has_no_errors(self):
        """Тот же текст с «Группа: разовый» — ни одной ошибки.

        Ловит мутацию: признак «пропуск» проверяется вне фильтра группы —
        разовый файл планки с `skipTest` получает отказ.
        """
        self.assertEqual(errors_of(ONE_OFF), [])


if __name__ == "__main__":
    unittest.main()
