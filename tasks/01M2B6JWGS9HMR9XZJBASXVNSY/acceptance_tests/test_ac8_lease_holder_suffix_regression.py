"""Приёмочный тест 01M2B6JWGS9HMR9XZJBASXVNSY — AC-8.

AC-8. `catalog._lease_holder_suffix`: pid держателя жив — суффикс
«жив», как и до этой задачи; pid держателя мёртв и группа pgid пуста
(pgid отсутствует либо `_group_member_count` вернул 0) — суффикс
«мёртв», как и до этой задачи.

Зелёный с рождения: сегодняшний `_lease_holder_suffix` решает
«жив/мёртв» ровно по `liveness._pid_alive(row["pid"])`, без pgid —
оба сценария этого AC уже дают ожидаемый текст. Тест — регресс-щит на
реализацию AC-7 (добавление проверки pgid): она не имеет права
подменить существующий текст «жив» новым «жив (агент pgid N)» для
живого pid, ни ослабить условие «мёртв» так, чтобы пустая группа тоже
считалась живой.
"""
import os
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


class LeaseHolderSuffixRegressionTest(LeaseTmpRootTest):

    def test_ac8_live_holder_pid_shows_plain_alive(self):
        """Держатель на своём host, pid жив (сам процесс теста) — суффикс
        «жив» без добавки про pgid, как и до этой задачи.

        Ловит мутацию: если реализация AC-7 начнёт безусловно добавлять
        «(агент pgid N)» к «жив» независимо от того, мёртв ли pid
        держателя, формат суффикса для уже живого держателя поменяется —
        регресс формата, который эта задача не должна затрагивать.
        """
        conn = store.db()
        insert_lease_row(conn, self.TASK, "sess-holder", os.getpid(),
                         socket.gethostname(), store.now())

        suffix = catalog._lease_holder_suffix(conn, self.TASK)

        self.assertIn("жив", suffix)
        self.assertNotIn("мёртв", suffix)
        self.assertNotIn("агент pgid", suffix)

    def test_ac8_dead_holder_without_pgid_still_shows_dead(self):
        """Держатель мёртв, `pgid` в строке отсутствует (`NULL`, как у
        lease, никогда не видевшего `store.update_lease_pgid`) —
        суффикс остаётся «мёртв».

        Ловит мутацию: если реализация AC-7 трактует `pgid IS NULL` как
        «группа есть, просто неизвестна» (например, подставит 0 и
        всё равно позовёт `_group_member_count(0)`, которая на некоторых
        системах отвечает > 0 для группы вызывающего теста), мёртвый
        держатель без pgid ошибочно окажется «жив».
        """
        conn = store.db()
        dead_pid = _dead_pid()
        insert_lease_row(conn, self.TASK, "sess-holder", dead_pid,
                         socket.gethostname(), store.now(), pgid=None)

        suffix = catalog._lease_holder_suffix(conn, self.TASK)

        self.assertIn("мёртв", suffix)

    def test_ac8_dead_holder_with_empty_pgid_group_still_shows_dead(self):
        """Держатель мёртв, `pgid` известен, но группа агента уже пуста
        (`_group_member_count` -> 0, шаг реально завершился) — суффикс
        остаётся «мёртв».

        Ловит мутацию: если проверка AC-7 забудет сравнить результат
        `_group_member_count` с нулём (`> 0`) и будет считать «жив» уже
        по самому факту, что `pgid` в строке не `NULL`, пустая группа
        (шаг давно закончился) ошибочно покажет «жив».
        """
        conn = store.db()
        dead_pid = _dead_pid()
        insert_lease_row(conn, self.TASK, "sess-holder", dead_pid,
                         socket.gethostname(), store.now(), pgid=4242)

        with mock.patch.object(catalog.liveness, "_group_member_count",
                               return_value=0):
            suffix = catalog._lease_holder_suffix(conn, self.TASK)

        self.assertIn("мёртв", suffix)


if __name__ == "__main__":
    unittest.main()
