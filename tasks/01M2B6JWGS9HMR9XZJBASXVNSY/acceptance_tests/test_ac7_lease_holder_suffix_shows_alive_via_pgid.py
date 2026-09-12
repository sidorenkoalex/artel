"""Приёмочный тест 01M2B6JWGS9HMR9XZJBASXVNSY — AC-7.

AC-7. `catalog._lease_holder_suffix`: pid держателя мёртв, но
`liveness._group_member_count(row["pgid"]) > 0` — суффикс строки
`status` показывает «жив (агент pgid N)» вместо «мёртв».

Красен до реализации: `catalog._lease_holder_suffix`
(`orchestrator/catalog.py:343-362`) сегодня решает «жив/мёртв» ТОЛЬКО
по `liveness._pid_alive(row["pid"])` — `row["pgid"]` не читается вовсе,
поэтому мёртвый pid держателя всегда даёт «мёртв», независимо от
группы агента.
"""
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTmpRootTest, insert_lease_row  # noqa: E402
from tests.sandbox import _dead_pid  # noqa: E402


class LeaseHolderSuffixShowsAliveViaPgidTest(LeaseTmpRootTest):

    def test_ac7_dead_holder_pid_with_nonempty_agent_pgid_shows_alive(self):
        """Pid держателя мёртв, но группа его pgid (агент шага) непуста —
        суффикс обязан назвать её живой, а не заявить «мёртв» о живом
        цикле (ровно инцидент из «Контекст» SPEC).

        Ловит мутацию: если проверка `_group_member_count(row["pgid"])
        > 0` не будет добавлена (либо будет добавлена, но не влияющей на
        текст — например, посчитана и отброшена), суффикс останется
        «мёртв» несмотря на живую группу агента.
        """
        conn = store.db()
        dead_pid = _dead_pid()
        agent_pgid = 4242
        insert_lease_row(conn, self.TASK, "sess-holder", dead_pid,
                         socket.gethostname(), store.now(), pgid=agent_pgid)

        with mock.patch.object(catalog.liveness, "_group_member_count",
                               return_value=3) as group_count:
            suffix = catalog._lease_holder_suffix(conn, self.TASK)

        group_count.assert_called_with(agent_pgid)
        self.assertNotIn("мёртв", suffix)
        self.assertIn(f"жив (агент pgid {agent_pgid})", suffix)


if __name__ == "__main__":
    unittest.main()
