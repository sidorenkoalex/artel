"""Файл результата отвязанной канарейки при отказе ведения."""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import artel, canary, runner
from tests.sandbox import TmpRootTest


class CanaryDetachResultTest(TmpRootTest):
    def test_failed_child_writes_result_file(self):
        """Ловит мутацию: при ошибке дочерний вход CLI оставляет файл результата пустым."""
        result = self.root / ".artel" / "logs" / "canary" / "failed.json"
        with mock.patch.object(runner, "in_role_environment", return_value=False), \
             mock.patch.object(sys, "argv", ["artel.py", "canary", "--k", "1",
                                            "--result-file", str(result)]), \
             mock.patch.object(canary, "cmd_canary", side_effect=RuntimeError("drive")):
            with pytest.raises(RuntimeError, match="drive"):
                artel.main()
        assert result.is_file()
        assert json.loads(result.read_text(encoding="utf-8"))["status"] == "failed"
