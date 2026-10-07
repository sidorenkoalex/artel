"""Extra safety coverage for notification arguments and terminal output."""

import subprocess
import sys
from unittest import mock

from orchestrator import watch


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
