"""AC-5: модуль `tests/test_models.py` зелёный целиком, тестовых методов в
нём не стало меньше, а дифф задачи не трогает `orchestrator/models.py`.

Зелёный с рождения: все три свойства держатся и до исправления (модуль
зелен на macOS, методов 37, диффа по `orchestrator/models.py` нет) —
критерий охраняет их от разрушения при правке затравки, а не требует
нового поведения. Красным он станет ровно тогда, когда правка уронит
или удалит соседний тест либо выйдет за зону задачи.
"""
import ast
import inspect
import io
import subprocess
import unittest

import _target

# Число тестовых методов в `tests/test_models.py` на 26.09, ДО исправления
# затравки (замер `ast` по файлу перед началом работ, тот же счёт, что
# ниже в тесте): планка стережёт «не уменьшилось», поэтому опорное число —
# снимок состояния до задачи, а не крутилка конфигурации.
BASELINE_TEST_METHODS = 37
# Файл, который правка задачи трогать не вправе: требования 1 и 3 ТЗ
# Оператор снял, из зон задачи файл ушёл (SPEC, «Не входит»).
FORBIDDEN_PATH = "orchestrator/models.py"
# Ветки, от которых считается база диффа задачи.
MAIN_REFS = ("main", "origin/main")


class Ac5ModuleGreenAndZoneTest(unittest.TestCase):
    """AC-5: модуль зелёный, методы на месте, зона не нарушена."""

    def _git(self, *args: str) -> tuple[int, str]:
        """(код возврата, stdout+stderr) команды git в корне репозитория."""
        done = subprocess.run(("git", *args),
                              cwd=_target.target_module.REPO_ROOT,
                              capture_output=True, text=True, timeout=60)
        return done.returncode, (done.stdout + done.stderr).strip()

    def test_ac5_whole_module_is_green(self):
        """Весь `tests/test_models.py` проходит целиком, а не только
        исправленный тест.

        Ловит мутацию: исправление затравки задело соседа по классу
        (`CmdModelsTest` делит `setUp` и `run_cmd`) — например закрытие
        переехало в `setUp`/`run_cmd` и сломало другой тест того же класса;
        поодиночке предметный тест при этом зелёный.
        """
        suite = unittest.defaultTestLoader.loadTestsFromModule(
            _target.target_module)
        result = unittest.TextTestRunner(stream=io.StringIO(),
                                        verbosity=0).run(suite)
        self.assertTrue(
            result.wasSuccessful(),
            f"tests/test_models.py красный целиком: "
            f"{_target.problem_reports(result)}")

    def test_ac5_test_method_count_did_not_shrink(self):
        """Тестовых методов в модуле не меньше, чем было до задачи.

        Ловит мутацию: разработчик удалил нестабильный тест целиком (или
        слил его с соседним), сочтя это исправлением нестабильности —
        падений действительно не станет, а проверка «команда чтения ничего
        не пишет» исчезнет вместе с тестом.
        """
        tree = ast.parse(inspect.getsource(_target.target_module))
        methods = [node.name for node in ast.walk(tree)
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name.startswith("test")]
        self.assertGreaterEqual(
            len(methods), BASELINE_TEST_METHODS,
            f"tests/test_models.py: тестовых методов стало {len(methods)} "
            f"против {BASELINE_TEST_METHODS} до задачи — тест удалён или "
            f"слит с другим (AC-5)")
        self.assertIn(
            _target.TARGET_METHOD, methods,
            f"tests/test_models.py: метода `{_target.TARGET_METHOD}` в файле "
            f"больше нет (AC-5)")

    def test_ac5_diff_does_not_touch_orchestrator_models(self):
        """Дифф ветки задачи против общей точки с main не содержит
        `orchestrator/models.py`.

        Ловит мутацию: разработчик всё-таки чинит команду — закрывает
        соединение внутри `cmd_models()` или заводит там `contextlib.
        closing`, — хотя Оператор снял эти требования: файл на пути
        команды БД не открывает, и правка в нём — работа вне зоны задачи.
        """
        base = None
        for ref in MAIN_REFS:
            code, out = self._git("merge-base", "HEAD", ref)
            if code == 0 and out:
                base = out.splitlines()[0]
                break
        if base is None:
            self.skipTest("ни main, ни origin/main не доступны в этой копии "
                          "репозитория — базу диффа задачи взять не от чего")

        code, out = self._git("diff", "--name-only", base)
        self.assertEqual(
            code, 0, f"git diff против {base} не выполнился: {out}")
        changed = [line.strip() for line in out.splitlines() if line.strip()]
        self.assertNotIn(
            FORBIDDEN_PATH, changed,
            f"дифф задачи трогает {FORBIDDEN_PATH} — файл вне зоны задачи "
            f"(SPEC, «Не входит»; зона — только tests/test_models.py); "
            f"изменённые файлы: {changed}")
