"""Приёмочный тест AC-5 задачи 01M290PP4KBTG1KYS1PWKQJH6T — lease, взятый
отвязанным циклом `auto` (identity из файла сессии), и `session_id`,
который резолвит `watch --mine` той же сессии, совпадают: задача видна в
`watch --mine` без явного `--tasks`.

Разыгрывает ДВЕ identity-резолюции под РАЗНЫМИ (замоканными) `ppid` —
именно так проявляется баг из «Контекста» SPEC (`ppid-1` отвязанного
цикла не совпадает с `ppid` интерактивной сессии): первая резолюция
имитирует identity, которую видит отвязанный `auto` в момент захвата
lease, вторая (под другим `ppid`) — identity, которую резолвит `watch
--mine`, вызванный из интерактивной сессии. Обе идут БЕЗ `ARTEL_SESSION_ID`
и без явного аргумента — единственный источник совпадения между ними
после этой задачи — файл сессии в `.artel/` (AC-4).

Красен до реализации: `session.resolve_session_id` вычисляет
`ppid-{os.getppid()}` заново на каждый вызов — под разными `ppid` первая
и вторая резолюция дают РАЗНЫЕ identity, lease задачи AUTO01 записан под
identity, которую `watch --mine` не резолвит, и AUTO01 не попадает в
выборку `--mine` — ровно баг, который чинит эта задача.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import session, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WatchTestCase  # noqa: E402


def _env_without_session_var() -> dict:
    env = dict(os.environ)
    env.pop("ARTEL_SESSION_ID", None)
    return env


class DetachedAutoLeaseVisibleInWatchMineTest(WatchTestCase):

    def test_ac5_task_leased_by_detached_identity_appears_in_watch_mine(self):
        conn = store.db()
        self._insert_task("AUTO01")
        self._insert_task("OTHER01")

        with mock.patch.dict(os.environ, _env_without_session_var(),
                             clear=True):
            # Резолюция «отвязанного auto»: ppid отвязанного процесса —
            # другой, чем у интерактивной сессии ниже (та самая причина
            # прежнего бага, воспроизведённая напрямую).
            with mock.patch("os.getppid", return_value=999001):
                detached_identity = session.resolve_session_id(None)
            store.journal(conn, "AUTO01", "lease", "lease взят", "",
                         session_id=detached_identity)
            # Задача с leaseом чужой (третьей) сессии — не должна попасть
            # в выборку --mine ни при каких обстоятельствах этого теста.
            store.journal(conn, "OTHER01", "lease", "lease взят", "",
                         session_id="sess-совсем-чужая")

            # Резолюция «watch --mine, вызванный интерактивной сессией»:
            # ppid НАМЕРЕННО другой, чем у отвязанного auto выше — если
            # идентичность держится файлом сессии (AC-4), а не живым
            # ppid, обе резолюции всё равно совпадут.
            with mock.patch("os.getppid", return_value=999002):
                self._start(["--mine", "--interval", "1"])
                self._settle()

                store.journal(conn, "AUTO01", "runner", "agent run started",
                             "маркер-AUTO01-видна-в-mine")
                store.journal(conn, "OTHER01", "runner", "agent run started",
                             "маркер-OTHER01-чужая")

                self._wait_until(
                    lambda: "маркер-AUTO01-видна-в-mine"
                    in self._stream.getvalue())
                self.assertNotIn("маркер-OTHER01-чужая",
                                self._stream.getvalue())

                self._set_state("AUTO01", "done", "in_dev")
                self._set_state("OTHER01", "done", "in_dev")
                self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


if __name__ == "__main__":
    unittest.main()
