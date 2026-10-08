"""Extra safety coverage for notification arguments and terminal output."""

import os
import subprocess
import sys
from unittest import mock

import pytest

from orchestrator import artel, store, watch


def test_notification_treats_leading_dash_and_nul_as_data():
    """Ловит мутацию: текст уведомления попадает в AppleScript либо NUL в argv."""
    message = '-"quoted"\x00tail'
    with mock.patch.object(sys, "platform", "darwin"), \
         mock.patch.object(subprocess, "run") as run:
        watch._notify(message)
    argv = run.call_args.args[0]
    assert argv[0] == "osascript"
    assert message not in argv[2]
    assert argv[-1].startswith("x-")
    assert "\x00" not in argv[-1]
    assert '"quoted"' in argv[-1]


def test_terminal_control_bytes_are_rendered_inert():
    """Ловит мутацию: OSC 52 или новая строка проходят в терминал без экранирования."""
    escaped = watch.safe_text("a\x1b]52;c;copy\x07\n")
    assert "\x1b" not in escaped
    assert "\x07" not in escaped
    assert "\n" not in escaped
    assert "\\x1b" in escaped


@pytest.mark.parametrize("command", ("run", "auto"))
def test_seatbelt_sandbox_refuses_cycle_before_launch(command):
    """Ловит мутацию: значение seatbelt обходит запрет цикла Codex без сети."""
    env = {"CODEX_SANDBOX": "seatbelt", "CODEX_SANDBOX_NETWORK_DISABLED": "1"}
    launch = artel._cmd_run_or_detach if command == "run" else artel._cmd_auto_or_detach
    with mock.patch.dict(os.environ, env), \
         mock.patch.object(artel.runner if command == "run" else artel.auto,
                           "cmd_run_and_advance" if command == "run" else "cmd_auto") as start, \
         pytest.raises(SystemExit, match="песочница Codex"):
        launch(["any", "--attach"])
    start.assert_not_called()


@pytest.mark.parametrize("ending", (("--once",), ("--exit-on", "steps"),
                                      ("--until", "done")))
def test_observation_rejects_ignored_ending_flags_before_database(ending):
    """Ловит мутацию: завершающий флаг дозора игнорируется и цикл зависает."""
    with mock.patch.object(store, "db") as db, \
         pytest.raises(SystemExit, match="несовместимые флаги") as refusal:
        watch.cmd_watch(["--observation", "any", *ending])
    assert ending[0] in str(refusal.value)
    db.assert_not_called()
