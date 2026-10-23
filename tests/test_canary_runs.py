"""`canary runs --since`: пустой отбор при непустой таблице (SPEC
01M5KEYG8G1WXHSR4BDKBSH6JP, требование 3) — свойство, которое не держит
долгоживущий файл задачи (он проверяет пустую таблицу, AC-7)."""
import contextlib
import io
import sys
import unittest
from unittest import mock

from orchestrator import artel, store
from tests.sandbox import InitializedTmpRootTest


class CanaryRunsEmptySinceTest(InitializedTmpRootTest):

    def test_since_after_every_run_prints_single_line(self):
        """Все прогоны начались раньше даты `--since` — одна строка «прогонов канарейки нет», код 0.

        Ловит мутацию: пустой отбор `--since` отказывает `sys.exit` или
        печатает пустой вывод вместо строки «прогонов канарейки нет» —
        код выхода либо вывод расходятся."""
        store.insert_canary_run(
            store.db(), "20300101T000000Z", "canary-a", "01AAAA", 3, 1.5, 0,
            0, "merged", None, False, False, verdict="green")
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", "canary", "runs",
                                             "--since", "2999-01-01"]), \
                contextlib.redirect_stdout(out):
            artel.main()
        lines = [line for line in out.getvalue().splitlines() if line.strip()]
        self.assertEqual(lines, ["прогонов канарейки нет"])


if __name__ == "__main__":
    unittest.main()
