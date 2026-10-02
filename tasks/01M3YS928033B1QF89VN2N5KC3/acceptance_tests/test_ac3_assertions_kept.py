"""AC-3: проверки test_missing_cli_is_not_retried сохраняются в силе.

Группа: разовый
Зелёный с рождения: до исправления тест в базе ветки совпадает с текущим — все утверждения на месте; тест сторожит, что исправление их не удалит и не ослабит.

Сверка — по тексту метода в базе ветки задачи (`gitcmd.diff_base`) и в
коде под проверкой: каждый вызов `self.assert*(…)` базы (нормализованный
`ast.unparse`) обязан остаться в методе; подмена `spawn_agent` на
`FileNotFoundError` — тоже; метод не помечен пропуском.
"""
import ast
import unittest

from _plank import (REPO_ROOT, TARGET_CLASS, TARGET_FILE, TARGET_METHOD,
                    diff_base, show_at)


def _method(source: str):
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS:
            for sub in node.body:
                if (isinstance(sub, ast.FunctionDef)
                        and sub.name == TARGET_METHOD):
                    return sub
    return None


def _asserts(method) -> list[str]:
    found = []
    for sub in ast.walk(method):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr.startswith("assert")):
            found.append(ast.unparse(sub))
    return sorted(found)


class AssertionsKeptTest(unittest.TestCase):
    """Утверждения целевого теста не удалены и не ослаблены."""

    def setUp(self):
        base = diff_base()
        self.assertTrue(base, "база ветки задачи не вычислена")
        base_src = show_at(base, TARGET_FILE)
        self.assertIsNotNone(base_src, f"{TARGET_FILE} нет в базе {base}")
        self.base = _method(base_src)
        self.assertIsNotNone(self.base, "целевого метода нет в базе")
        path = REPO_ROOT / TARGET_FILE
        self.assertTrue(path.is_file(), f"{TARGET_FILE} нет в коде")
        self.now = _method(path.read_text(encoding="utf-8"))
        self.assertIsNotNone(
            self.now, f"{TARGET_CLASS}.{TARGET_METHOD} пропал из кода")

    def test_ac3_every_base_assertion_still_present(self):
        """Каждое утверждение метода в базе есть и в текущем методе.

        Пять свойств (один вызов, пауз нет, `in_dev`, один
        `*.prompt.txt` с ролью «разработчик», путь в выводе) держатся
        утверждениями базы; их текст сверяется побуквенно после
        нормализации.

        Ловит мутацию: исправление убрало или смягчило утверждение —
        например `assertEqual(popen.call_count, 1, …)` заменили на
        `assertLessEqual` или удалили сверку числа `*.prompt.txt` — в
        текущем методе нет утверждения базы, тест красный с его текстом.
        """
        left = _asserts(self.now)
        missing = []
        for text in _asserts(self.base):
            if text in left:
                left.remove(text)
            else:
                missing.append(text)
        self.assertEqual(missing, [], "утверждения базы пропали/изменены")

    def test_ac3_spawn_agent_still_raises_file_not_found(self):
        """Метод по-прежнему подменяет `runner.spawn_agent` на `FileNotFoundError`.

        Ловит мутацию: «починка» сменила сценарий — `spawn_agent`
        подменён на успешный вызов или иное исключение, и проверка
        «повтора при отсутствии CLI нет» перестала что-либо проверять.
        """
        texts = [ast.unparse(n) for n in ast.walk(self.now)
                 if isinstance(n, ast.Call)]
        self.assertTrue(
            any("spawn_agent" in t and "side_effect=FileNotFoundError" in t
                for t in texts),
            "подмена spawn_agent на FileNotFoundError пропала")

    def test_ac3_method_not_skipped(self):
        """Метод не помечен пропуском и не помечен ожидаемым провалом.

        Ловит мутацию: тест «стабилизировали» декоратором
        `unittest.skip`/`skipIf`/`expectedFailure` — утверждения
        формально на месте, но не исполняются.
        """
        decorators = [ast.unparse(d) for d in self.now.decorator_list]
        bad = [d for d in decorators
               if "skip" in d.lower() or "expectedfailure" in d.lower()]
        self.assertEqual(bad, [], "метод помечен пропуском")
        body = [ast.unparse(n) for n in ast.walk(self.now)
                if isinstance(n, ast.Call)]
        self.assertFalse(any("skipTest" in t for t in body),
                         "метод пропускает себя через skipTest")


if __name__ == "__main__":
    unittest.main()
