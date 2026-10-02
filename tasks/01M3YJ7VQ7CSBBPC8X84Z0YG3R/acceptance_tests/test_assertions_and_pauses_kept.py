"""AC-2, AC-4 — утверждения тестов гейта мержа на часы и паузы самого
пульта остаются прежними.

Группа: разовый
Зелёный с рождения: до реализации файлы равны базе ветки — методы, утверждения на часы и паузы пульта совпадают сами с собой, а `tests/test_merge_gate_ci_wait.py` зелёный; тесты сторожат, что перевод часов их не снимет и не ослабит.

Сверка идёт с базой ветки задачи (точка расхождения с `origin/<основная
ветка>`, `gitcmd.diff_base`) по нормализованному тексту (`ast.unparse`) —
переформатирование строк не мешает, изменение ожидаемого значения видно.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

PAUSE_FUNCS = ("_wait_for_branch_ci_green", "_await_main_ci",
               "_cmd_approve_merge_gate_cycle")


def _pauses(source: str, func: str) -> list[str] | None:
    """Аргументы вызовов паузы (`…sleep(…)`) функции `func` в порядке
    исходника; `None` — функции нет."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == func:
            calls = []
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                name = (sub.func.attr if isinstance(sub.func, ast.Attribute)
                        else getattr(sub.func, "id", ""))
                if "sleep" in name.lower():
                    calls.append((sub.lineno, sub.col_offset,
                                  ", ".join(ast.unparse(a) for a in sub.args)))
            return [args for _l, _c, args in sorted(calls)]
    return None


class AssertionsKeptTest(unittest.TestCase):

    def test_ac2_ci_wait_methods_and_clock_assertions_kept(self):
        """Тестовые методы `tests/test_merge_gate_ci_wait.py` из базы ветки
        на месте, и каждое их утверждение на `sleep_calls`/`clock.value`/
        `monotonic` присутствует с прежним текстом и ожидаемым значением.

        Ловит мутацию: после перевода часов «неудобный» ассерт
        `assertEqual(self.clock.sleep_calls, [config.
        MERGE_GATE_CI_WAIT_POLL_SEC])` ослаблен до `assertIn(…)`/снят, или
        метод `test_wait_path_does_not_get_the_moved_pause` удалён — метод
        и утверждение в тексте провала.
        """
        base = _util.base_source(self, _util.CI_WAIT_FILE)
        now = _util.current_source(self, _util.CI_WAIT_FILE)
        missing_methods = sorted(set(_util.test_methods(base))
                                 - set(_util.test_methods(now)))
        self.assertEqual(missing_methods, [], "пропали тестовые методы")
        before = _util.clock_assertions(base)
        self.assertTrue(any(before.values()),
                        "в базе не найдено ни одного утверждения на часы — "
                        "сверка ничего не сторожит")
        self.assertEqual(_util.missing_clock_assertions(base, now), [],
                         "утверждения на часы сняты или изменены")

    def test_ac2_ci_wait_file_green(self):
        """Файл `tests/test_merge_gate_ci_wait.py` кода под проверкой
        зелёный отдельным прогоном pytest.

        Ловит мутацию: объект, подставленный вместо `fsm_merge_gate.time`,
        отдаёт часы теста только для `sleep`, а `monotonic` — настоящий
        `time.monotonic` — пауза пульта не двигает его часы, потолок не
        наступает, число push в
        `test_persistently_moved_main_exits_by_ceiling_with_real_wait_loop`
        превысит `PUSH_CAP`, и файл не зелёный.
        """
        _util.run_pytest_file(self, _util.CI_WAIT_FILE)


class PultPausesKeptTest(unittest.TestCase):

    def test_ac4_pult_pauses_same_durations_and_order(self):
        """В `_wait_for_branch_ci_green`, `_await_main_ci` и
        `_cmd_approve_merge_gate_cycle` кода под проверкой паузы идут с
        теми же длительностями и в том же порядке, что в базе ветки; тесты
        на эти паузы проверяют `test_ac2_ci_wait_file_green` и
        `test_ac3_kind_gate_methods_and_assertions_kept_and_green`.

        Ловит мутацию: при замене способа вызова паузы в
        `orchestrator/fsm_merge_gate.py` в `_await_main_ci` взята
        `config.MERGE_GATE_CI_WAIT_POLL_SEC` вместо
        `config.VERIFYING_POLL_INTERVAL_SEC` (или пауза цикла выпала) —
        список длительностей функции разойдётся с базой.
        """
        base = _util.base_source(self, _util.PULT_FILE)
        now = _util.current_source(self, _util.PULT_FILE)
        diverged = []
        for func in PAUSE_FUNCS:
            before = _pauses(base, func)
            self.assertTrue(before, f"в базе у {func} не найдено пауз")
            after = _pauses(now, func)
            if after != before:
                diverged.append(f"{func}: было {before}, стало {after}")
        self.assertEqual(diverged, [], "паузы пульта изменились")


if __name__ == "__main__":
    unittest.main()
