"""AC-1 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: разбор флага `--set`.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `canary --k <N> --set <имя>` разбирается: имя набора доезжает до
`canary.cmd_canary` отдельным параметром; без `--set` параметр несёт имя
набора по умолчанию; `--set` последним аргументом без значения — отказ с
названной причиной, без прогона.

Имя самого параметра планка не фиксирует (`_util.set_param_name` читает
его из подписи `canary.cmd_canary`) — критерий требует «отдельный
параметр», а не конкретное слово. Прогон в этом файле не стартует ни
разу: `canary.cmd_canary` подменена, проверяется только разбор argv.

Красен до реализации: у `canary.cmd_canary` нет параметра набора, а
`artel._cmd_canary` не знает флага `--set` — `_util.set_param_name`
падает именованным `AssertionError`, а отказ на `--set` без значения не
случается вовсе.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import canary  # noqa: E402


class SetFlagParsingTest(unittest.TestCase):

    def test_ac1_set_value_reaches_cmd_canary_as_its_own_parameter(self):
        """`canary --k 2 --set codex-strong`: `canary.cmd_canary` получает
        и `k=2`, и имя набора отдельным параметром своей подписи.

        Ловит мутацию: значение `--set` разобрано, но до команды не
        доезжает (флаг вырезан из `rest` и забыт, как это было бы при
        копировании разбора `--sha` без передачи значения) — параметр
        набора остался бы при своём значении по умолчанию, и вызов с
        `codex-strong` не отличался бы от вызова без флага.
        """
        arguments = _util.cli_canary_arguments(
            ["--k", "2", "--set", _util.SET_NAME])

        self.assertEqual(2, arguments.get("k"))
        self.assertEqual(_util.SET_NAME,
                         arguments.get(_util.set_param_name()),
                         f"аргументы вызова: {arguments}")

    def test_ac1_without_set_the_parameter_carries_the_default_set_name(self):
        """Без `--set` тот же параметр несёт имя набора по умолчанию —
        непустую строку, отличную от имени набора Оператора; переданное
        тем же именем явно, оно доезжает без изменений.

        Ловит мутацию: без флага в команду уходит `None` (буквальная
        копия `_sha_arg`, где отсутствие флага и есть `None`) — набором по
        умолчанию пришлось бы считать пустое значение, и вся ветка
        «прогон как пульт» (AC-14) выбиралась бы по `is None`, а не по
        имени набора, которым её ключует бейзлайн (AC-7).
        """
        default_name = _util.default_set_name()

        self.assertNotEqual(_util.SET_NAME, default_name)
        arguments = _util.cli_canary_arguments(
            ["--k", "1", "--set", default_name])
        self.assertEqual(default_name,
                         arguments.get(_util.set_param_name()))

    def test_ac1_set_without_a_value_is_a_named_refusal_without_a_run(self):
        """`canary --k 1 --set` (флаг последним аргументом): именованный
        отказ, называющий сам флаг, и ни одного вызова `cmd_canary`.

        Ловит мутацию: значение флага берётся `rest[idx + 1]` без сверки
        длины (или через `try/except IndexError` с пустым значением) —
        вместо названного отказа Оператор получил бы `IndexError` из
        глубины разбора либо прогон по набору с пустым именем.
        """
        calls = []

        with mock.patch.object(canary, "cmd_canary",
                               lambda *a, **kw: calls.append((a, kw))):
            with self.assertRaises(SystemExit) as ctx:
                _util.artel._cmd_canary(["--k", "1", "--set"])

        self.assertIn("--set", str(ctx.exception))
        self.assertEqual([], calls, "прогон стартовал на отказе разбора")


if __name__ == "__main__":
    unittest.main()
