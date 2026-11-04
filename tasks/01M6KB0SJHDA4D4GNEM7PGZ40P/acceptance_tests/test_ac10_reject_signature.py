"""Сигнатура `fsm.cmd_reject` и неизменность тестов обвязки lease (AC-10).

Группа: разовый
Красен до реализации: у `fsm.cmd_reject` нет именованного параметра `decision_file` — сверка сигнатуры падает; прогон названных SPEC тестов обвязки и их неизменность в диффе задачи зелёны с рождения.

Сверка сигнатуры — `inspect.signature`. Существующие тесты, которые AC-10
требует держать зелёными без правки, исполняются в этом же процессе
загрузчиком unittest (без порождения процессов): строки
`tests/test_lease_run_task_command.py:133–157` —
`CommandsLintTest::test_commands_delegate_to_run_task_command`, `:177–182` —
`CommandsReachBodyTest::test_each_command_reaches_body_with_full_id`,
`tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py:225–257` —
`CommandsDelegateTest::test_ac4_commands_delegate_wrapping_to_run_task_command`.
«Без правки» — их файлов нет среди путей задачи помощника пульта
`changed_paths()`.
"""
import inspect
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, changed_paths  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))

from orchestrator import fsm  # noqa: E402

WRAPPER_TESTS = (
    "tests.test_lease_run_task_command.CommandsLintTest."
    "test_commands_delegate_to_run_task_command",
    "tests.test_lease_run_task_command.CommandsReachBodyTest."
    "test_each_command_reaches_body_with_full_id",
    "tests.test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.CommandsDelegateTest."
    "test_ac4_commands_delegate_wrapping_to_run_task_command",
)
WRAPPER_FILES = ("tests/test_lease_run_task_command.py",
                 "tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py")


def test_ac10_cmd_reject_positional_head_and_keyword_only_decision_file():
    """`fsm.cmd_reject(task_id, reason, session_id)` — позиционные как сегодня, `decision_file` — только именованный после `session_id`, по умолчанию `None`.

    Ловит мутацию: `decision_file` добавлен позиционным параметром (или
    перед `session_id`) — вызов `cmd_reject(PREFIX, "причина", "sess-g")`
    отдал бы сессию в `decision_file`; параметр без умолчания `None` —
    прежний вызов без него падает `TypeError`.
    """
    params = list(inspect.signature(fsm.cmd_reject).parameters.values())
    head = [(p.name, p.kind) for p in params[:3]]
    assert head == [("task_id", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                    ("reason", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                    ("session_id", inspect.Parameter.POSITIONAL_OR_KEYWORD)], head
    assert params[2].default is None, params[2]
    names = [p.name for p in params]
    assert "decision_file" in names, names
    decision = params[names.index("decision_file")]
    assert decision.kind is inspect.Parameter.KEYWORD_ONLY, decision
    assert decision.default is None, decision
    assert names.index("decision_file") > names.index("session_id"), names


def test_ac10_wrapper_tests_green_and_unedited():
    """Названные SPEC тесты обвязки lease зелёны и их файлы не правлены задачей.

    Сценарий: три теста загружаются по имени и исполняются раннером
    unittest в этом процессе; пути задачи (`changed_paths()`) не содержат
    их файлов.

    Ловит мутацию: `cmd_reject` при `decision_file=None` зовёт тело
    `_cmd_reject(conn, tid, reason, decision_file=None)` — у
    `test_each_command_reaches_body_with_full_id` `kwargs != {}`, прогон
    красный; второй вызов `lease.run_task_command` под ветвление по
    `decision_file` или `store.db()` в теле — красны AST-линтеры обвязки;
    правка этих тестов под код — их файлы в путях задачи.
    """
    suite = unittest.defaultTestLoader.loadTestsFromNames(WRAPPER_TESTS)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    assert result.testsRun == len(WRAPPER_TESTS), stream.getvalue()
    assert result.wasSuccessful(), stream.getvalue()
    touched = [p for p in changed_paths() if p in WRAPPER_FILES]
    assert touched == [], touched
