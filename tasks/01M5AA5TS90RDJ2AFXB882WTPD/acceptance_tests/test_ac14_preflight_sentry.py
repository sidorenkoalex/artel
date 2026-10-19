"""Сторож предпроверки зелёный без правки своего файла.

Группа: разовый
Зелёный с рождения: сторож `test_ac9_transition_guard_calls_equal_preflight_and_not_checked` зелёный на базе ветки, а файл сторожа не тронут; краснеет, если задача добавит вызов новой функции `guard` в тело перехода без вызова в `orchestrator/preflight.py` либо поправит файл сторожа.

Факт задачи: дифф ветки (`changed_paths()` помощника пульта) не несёт файла
сторожа, а сам метод сторожа, загруженный из рабочей копии кода задачи,
проходит. Метод исполняется в процессе тем же `unittest`, что и полный
набор, — без подмены и без копии его логики.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, changed_paths  # noqa: E402

SENTRY_FILE = "tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py"
SENTRY_NAME = ("tests.test_01m4p4zp37wv81410ytzhkqc8d_preflight.SentryTest."
               "test_ac9_transition_guard_calls_equal_preflight_and_not_checked")


class Ac14PreflightSentryTest(unittest.TestCase):

    def test_ac14_sentry_green_and_file_untouched(self):
        """Файл сторожа вне диффа задачи, метод сторожа из рабочей копии кода проходит.

        Сценарий: путь `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`
        ищется среди путей задачи (`changed_paths()`); затем метод
        `SentryTest.test_ac9_transition_guard_calls_equal_preflight_and_not_checked`
        загружается по имени из корня рабочей копии кода и исполняется:
        ни провала, ни ошибки, ни пропуска.

        Ловит мутацию: новая функция `guard` (строка группы файла с меткой,
        статика долгоживущего файла с меткой) вызвана в
        `advance_gates/tests_writing.py` или `fsm.py`, но не в
        `orchestrator/preflight.py` — сторож падает; сторож «починен»
        правкой своего файла — путь появляется в диффе задачи.
        """
        paths = changed_paths()
        self.assertNotIn(SENTRY_FILE, paths,
                         f"файл сторожа правлен задачей: {paths}")
        root = str(Path(CODE_ROOT).resolve()) if CODE_ROOT else str(Path.cwd())
        if root not in sys.path:
            sys.path.insert(0, root)
        suite = unittest.defaultTestLoader.loadTestsFromName(SENTRY_NAME)
        self.assertEqual(suite.countTestCases(), 1, SENTRY_NAME)
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        self.assertEqual(result.testsRun, 1, stream.getvalue())
        self.assertFalse(result.skipped, stream.getvalue())
        self.assertTrue(result.wasSuccessful(), stream.getvalue())
