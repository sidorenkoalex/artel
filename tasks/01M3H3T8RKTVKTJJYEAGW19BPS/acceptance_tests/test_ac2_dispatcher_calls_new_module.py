"""AC-2 — 01M3H3T8RKTVKTJJYEAGW19BPS: диспетчер `orchestrator/artel.py`
вызывает `ci_rerun.cmd_ci_rerun`; справка `ci-rerun` и разбор её
аргументов не изменены.

Справка команды — строки модульного докстринга `artel.py` (его печатает
`main()` без аргументов); разбор аргументов — выражение записи
`"ci-rerun"` в таблице команд плюс тело `_reason_arg`. Всё трое
сверяется с версией «до» из git (`_util.base_source`).

Красен до реализации: запись таблицы сегодня вызывает
`fsm.cmd_ci_rerun`, модуля `orchestrator/ci_rerun.py` ещё нет — и
статическая сверка записи, и прогон диспетчера со шпионом на
`ci_rerun.cmd_ci_rerun` падают на этом. Два других метода (справка и
разбор аргументов) зелены с рождения и такими обязаны остаться: они
сверяют ветку с её же версией «до», то есть фиксируют то, что перенос
менять не вправе.
"""
import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

COMMAND_KEY = "ci-rerun"
TASK_ARG = "01M3H3T8RKTVKTJJYEAGW19BPS"
REASON_ARG = "флейк сети на шаге pip install"


def _command_entry(source: str):
    """Узел-значение записи `"ci-rerun"` таблицы команд `main()`."""
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == COMMAND_KEY:
                return value
    return None


def _help_lines(source: str) -> list:
    """Строки справки (модульного докстринга `artel.py`), называющие
    команду `ci-rerun`."""
    doc = ast.get_docstring(ast.parse(source)) or ""
    return [line for line in doc.splitlines() if COMMAND_KEY in line]


class DispatcherRoutesCiRerunToNewModuleTest(unittest.TestCase):

    def test_ac2_command_table_entry_calls_ci_rerun_module(self):
        """Запись `"ci-rerun"` таблицы команд вызывает именно
        `ci_rerun.cmd_ci_rerun`, а имя `ci_rerun` доступно диспетчеру как
        модуль пакета.

        Ловит мутацию: команда переехала в новый модуль, а диспетчер
        оставлен на алиасе `fsm.cmd_ci_rerun` (перенос «наполовину»:
        снятие алиаса следующей волной молча оторвёт команду от CLI) —
        получатель вызова в записи таблицы останется `fsm`, и сверка
        покраснеет.
        """
        entry = _command_entry(_util.current_source(_util.ARTEL_REL))
        self.assertIsNotNone(
            entry, f"в {_util.ARTEL_REL} нет записи {COMMAND_KEY!r} таблицы "
                   f"команд")
        self.assertIsInstance(entry, ast.Lambda)
        call = entry.body
        self.assertIsInstance(
            call, ast.Call,
            f"запись {COMMAND_KEY!r} перестала быть одним вызовом команды")
        self.assertIsInstance(call.func, ast.Attribute)
        self.assertEqual("cmd_ci_rerun", call.func.attr)
        self.assertEqual(
            "ci_rerun", getattr(call.func.value, "id", None),
            f"запись {COMMAND_KEY!r} вызывает "
            f"{ast.dump(call.func)} вместо ci_rerun.cmd_ci_rerun (AC-2)")

        from orchestrator import artel, ci_rerun

        self.assertIs(
            ci_rerun, getattr(artel, "ci_rerun", None),
            "имя ci_rerun в orchestrator/artel.py — не модуль "
            "orchestrator.ci_rerun")

    def test_ac2_argument_parsing_of_the_command_is_unchanged(self):
        """Аргументы, с которыми диспетчер зовёт команду, и тело
        `_reason_arg` — те же, что до переноса (меняется только
        получатель вызова).

        Ловит мутацию: вместе с переносом «причесали» разбор — например,
        `_reason_arg(rest)` заменили на `rest[1] if len(rest) > 1 else
        None`, и `ci-rerun <id> "<основание>"` без флага начал
        приниматься; исходник аргументов записи разойдётся с версией
        «до».
        """
        base_src = _util.base_source(_util.ARTEL_REL)
        cur_src = _util.current_source(_util.ARTEL_REL)

        base_entry = _command_entry(base_src)
        cur_entry = _command_entry(cur_src)
        self.assertIsNotNone(cur_entry)
        base_args = [ast.get_source_segment(base_src, a)
                     for a in base_entry.body.args]
        cur_args = [ast.get_source_segment(cur_src, a)
                    for a in cur_entry.body.args]
        self.assertEqual(
            base_args, cur_args,
            f"аргументы записи {COMMAND_KEY!r} изменились — AC-2 требует "
            f"оставить разбор аргументов прежним")

        base_reason = _util.functions(base_src)["_reason_arg"]
        cur_reason = _util.functions(cur_src).get("_reason_arg")
        self.assertIsNotNone(cur_reason,
                             f"{_util.ARTEL_REL} потерял _reason_arg")
        self.assertEqual(
            _util.normalized_function_source(base_src, base_reason),
            _util.normalized_function_source(cur_src, cur_reason),
            "тело _reason_arg изменилось — разбор `--reason` команды "
            "ci-rerun обязан остаться прежним (AC-2)")

    def test_ac2_help_text_of_the_command_is_unchanged(self):
        """Строки справки `artel.py`, называющие `ci-rerun`, совпадают с
        дорефакторинговыми посимвольно и в прежнем порядке.

        Ловит мутацию: заодно с переносом подправлена строка справки
        (например, из перечня команд выпал флаг `--reason` или абзац
        описания переписан) — набор строк разойдётся с версией «до».
        """
        self.assertEqual(
            _help_lines(_util.base_source(_util.ARTEL_REL)),
            _help_lines(_util.current_source(_util.ARTEL_REL)),
            "справка ci-rerun изменилась — AC-2 требует оставить её без "
            "изменений")

    def test_ac2_cli_invocation_reaches_the_new_module(self):
        """Прогон `main()` с argv `ci-rerun <id> --reason "<основание>"`
        доходит до подменённого `ci_rerun.cmd_ci_rerun` ровно одним
        вызовом с разобранными id и основанием.

        Инвариант T056 (`_refuse_if_worktree`) снят подменой: планка
        исполняется в worktree задачи, где настоящий `main()` отказал бы
        до таблицы команд — к разбору `ci-rerun` этот отказ отношения не
        имеет.

        Ловит мутацию: таблица команд зовёт новый модуль, но имя внутри
        неё берётся из `fsm` (или запись потеряла `_reason_arg`) —
        шпион не получит вызова вовсе либо получит основание `None`.
        """
        from orchestrator import artel, ci_rerun

        spy = mock.Mock(return_value=None)
        argv = ["artel.py", COMMAND_KEY, TASK_ARG, "--reason", REASON_ARG]
        with mock.patch.object(artel, "_refuse_if_worktree", lambda: None), \
                mock.patch.object(ci_rerun, "cmd_ci_rerun", spy), \
                mock.patch.object(sys, "argv", argv):
            artel.main()

        self.assertEqual(1, spy.call_count,
                         "диспетчер не позвал ci_rerun.cmd_ci_rerun")
        self.assertEqual((TASK_ARG, REASON_ARG), spy.call_args.args)


if __name__ == "__main__":
    unittest.main()
