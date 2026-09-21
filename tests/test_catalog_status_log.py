"""Юнит-тесты `orchestrator.catalog.cmd_log`/`cmd_status` (SPEC
01M1GCHKG8DDK4DCZWCE3DYKWC, требования 2, 6, AC-3/AC-11): видимость
identity сессии в журнале и держателя lease в статусе задачи.
"""
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest, TmpRootTest, _dead_pid, capture  # noqa: E402

TASK = "T001"

# Токены рядом с долларами в строке `status` (SPEC
# 01M31ZHWJWRSACYMRWTCPBC0DM, требования 1 и 5): суммарное число токенов
# задачи, прочерк вместо нуля у задачи без записей. Виды цены названы
# здесь литералами — именно ими подписана разбивка в журнале, и
# разъехаться с ней молча тест не должен.
TOKEN_KINDS = ("input", "output", "cache_write", "cache_read")
TOKENS = dict(zip(TOKEN_KINDS, (11, 13, 17, 19)))
TOKENS_TOTAL = sum(TOKENS.values())

#: Прочерк «записей токенов нет» — тот же символ, что у `retro.DASH`.
DASH = "—"


def known_cost_detail(usd: float, tokens: dict) -> str:
    """Деталь записи «agent cost KNOWN» — тем же форматом, каким её пишет
    `spend.charge_step`: разбивку по видам несут только такие записи."""
    by_kind = ", ".join(f"{kind}={tokens[kind]}" for kind in TOKEN_KINDS)
    return (f"попытка 1/1, model=alfa-model-x, provider=alfa-cli: "
            f"стоимость ${usd:.4f}, токенов {sum(tokens.values())}, "
            f"источник=факт CLI, разбивка по видам: {by_kind} | "
            f"actual_usd={usd!r}")


class CmdLogSessionIdTest(TaskSeededTmpRootTest):

    def test_log_shows_the_session_id_on_one_readable_line(self):
        store.journal(store.db(), TASK, "operator", "событие", "деталь",
                      session_id="sess-log-unit")

        out = capture(catalog.cmd_log, TASK)

        lines = [ln for ln in out.splitlines() if "sess-log-unit" in ln]
        self.assertTrue(lines, out)
        for ln in lines:
            self.assertNotIn("{'", ln)
            self.assertNotIn("Row(", ln)

    def test_log_degrades_silently_for_legacy_rows_without_session_id(self):
        """Записи, заведённые до миграции колонки, — `session_id` NULL:
        строка `log` не падает и не печатает «None»."""
        conn = store.db()
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail,"
            " session_id) VALUES (?,?,?,?,?,?,?)",
            (TASK, config.DEFAULT_TARGET, store.now(), "operator",
             "легаси-событие", "", None))
        conn.commit()

        out = capture(catalog.cmd_log, TASK)

        self.assertIn("легаси-событие", out)
        self.assertNotIn("None", out)


class CmdStatusTokensTest(TaskSeededTmpRootTest):
    """Суммарные токены задачи в строке `status` (SPEC
    01M31ZHWJWRSACYMRWTCPBC0DM, требования 1 и 5)."""

    OTHER = "T002"

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.insert_task(self.conn, self.OTHER, "Вторая", "in_dev",
                          "task/t002-vtoraya", config.DEFAULT_TARGET, 25.0)

    def charged(self, task_id: str, actor: str, usd: float,
                tokens: dict) -> None:
        store.journal(self.conn, task_id, actor, "agent cost KNOWN",
                      known_cost_detail(usd, tokens))
        store.journal(self.conn, task_id, actor, "agent run finished",
                      f"rc=0, попытка 1/1, стоимость ${usd:.4f}")

    def finished_with_total(self, task_id: str, actor: str, usd: float,
                            total: int) -> None:
        """Шаг, записанный прежним видом записи: суммарное «токенов N» в
        строке завершения, разбивки по видам в журнале нет вовсе."""
        store.journal(self.conn, task_id, actor, "agent run finished",
                      f"rc=0, попытка 1/1, стоимость ${usd:.4f}, "
                      f"токенов {total}")

    def line_for(self, task_id: str, out: str) -> str:
        lines = [ln for ln in out.splitlines() if task_id in ln]
        self.assertEqual(1, len(lines), out)
        return lines[0]

    def test_status_shows_the_total_token_count_of_the_task(self):
        """Две роли одной задачи складываются в одно число рядом с
        «$spent/budget», и задача занимает ровно одну строку.

        Ловит мутацию: показ берёт разбивку последнего шага вместо суммы
        по задаче — в строке окажется 60 вместо 120, и `assertIn`
        покраснеет; проверка «ровно одна строка» ловит встречную порчу —
        разбивку печатают дополнительной строкой на задачу.
        """
        self.charged(TASK, "developer", 1.25, TOKENS)
        self.charged(TASK, "reviewer", 2.5, TOKENS)

        line = self.line_for(TASK, capture(catalog.cmd_status))

        self.assertIn(str(TOKENS_TOTAL * 2), line)

    def test_status_shows_a_dash_for_a_task_without_token_records(self):
        """Задача, чей шаг завершился без разбивки usage, показана
        прочерком; у задачи с записями прочерка в строке нет.

        Ловит мутацию: сумма считается `sum({})` и печатается как есть —
        в строке появится «токенов 0» вместо прочерка, и обе проверки
        ниже покраснеют.
        """
        self.charged(TASK, "developer", 1.25, TOKENS)
        store.journal(self.conn, self.OTHER, "developer",
                      "agent run finished",
                      "rc=0, попытка 1/1, стоимость $4.2500")

        out = capture(catalog.cmd_status)

        self.assertIn(DASH, self.line_for(self.OTHER, out))
        self.assertNotIn(DASH, self.line_for(TASK, out))

    def test_status_counts_tokens_of_a_journal_without_a_breakdown(self):
        """Задача, чьи шаги записаны прежним видом записи (сумма в строке
        завершения, разбивки по видам нет), показана своим числом, а не
        прочерком.

        Ловит мутацию: сумма читается ТОЛЬКО из «agent cost KNOWN»/
        «PARTIAL» — задача получит прочерк «записей токенов нет» при
        известных 120 токенах в журнале (REVIEW.md итерации 1, R1-F1).
        """
        self.finished_with_total(TASK, "developer", 1.25, TOKENS_TOTAL)
        self.finished_with_total(TASK, "reviewer", 2.5, TOKENS_TOTAL)

        line = self.line_for(TASK, capture(catalog.cmd_status))

        self.assertIn(str(TOKENS_TOTAL * 2), line)
        self.assertNotIn(DASH, line)

    def test_status_counts_a_step_written_by_both_carriers_once(self):
        """Шаг, чьи токены журнал записал и разбивкой, и суммой строки
        завершения, входит в число задачи один раз.

        Ловит мутацию: оба носителя складываются подряд — в строке
        окажется 120 вместо 60, и `assertNotIn` покраснеет.
        """
        store.journal(self.conn, TASK, "developer", "agent cost KNOWN",
                      known_cost_detail(1.25, TOKENS))
        self.finished_with_total(TASK, "developer", 1.25, TOKENS_TOTAL)

        line = self.line_for(TASK, capture(catalog.cmd_status))

        self.assertIn(str(TOKENS_TOTAL), line)
        self.assertNotIn(str(TOKENS_TOTAL * 2), line)


class CmdStatusLeaseHolderTest(TaskSeededTmpRootTest):

    def test_no_lease_adds_no_holder_suffix(self):
        out = capture(catalog.cmd_status)

        self.assertNotIn("lease", out)

    def test_shows_holder_and_liveness_on_this_host(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (TASK, "sess-status-unit", os.getpid(), socket.gethostname(),
             store.now()))
        conn.commit()

        out = capture(catalog.cmd_status)

        self.assertIn("sess-status-unit", out)
        self.assertIn("жив", out)

    def insert_lease(self, pid: int, pgid=None) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts, pgid) VALUES (?,?,?,?,?,?)",
            (TASK, "sess-status-unit", pid, socket.gethostname(), store.now(),
             pgid))
        conn.commit()

    def test_dead_holder_pid_with_nonempty_agent_group_shows_alive(self):
        """SPEC 01M2B6JWGS9HMR9XZJBASXVNSY, требование 3, AC-7: pid
        держателя мёртв, но группа агента шага (`pgid`) непуста —
        суффикс называет её живой, не «мёртв».

        Ловит мутацию: если `catalog._lease_holder_suffix` не станет
        сверяться с `liveness._group_member_count(row['pgid'])` (или
        посчитает её результат и отбросит), суффикс останется «мёртв»
        несмотря на живую группу агента."""
        self.insert_lease(_dead_pid(), pgid=4242)

        with mock.patch.object(catalog.liveness, "_group_member_count",
                               return_value=2):
            out = capture(catalog.cmd_status)

        self.assertNotIn("мёртв", out)
        self.assertIn("жив (агент pgid 4242)", out)

    def test_dead_holder_pid_without_pgid_still_shows_dead(self):
        """Регресс AC-8: держатель мёртв, `pgid` в строке отсутствует
        (`NULL`) — суффикс остаётся «мёртв», как и до этой задачи.

        Ловит мутацию: если отсутствие `pgid` станет трактоваться как
        «группа есть, просто неизвестна» (например, подстановкой 0 и
        вызовом `_group_member_count(0)`), мёртвый держатель без pgid
        может ошибочно оказаться «жив»."""
        self.insert_lease(_dead_pid(), pgid=None)

        out = capture(catalog.cmd_status)

        self.assertIn("мёртв", out)

    def test_dead_holder_pid_with_empty_agent_group_still_shows_dead(self):
        """Регресс AC-8: держатель мёртв, `pgid` известен, но группа уже
        пуста (`_group_member_count` -> 0) — суффикс остаётся «мёртв».

        Ловит мутацию: если проверка забудет сравнить результат
        `_group_member_count` с нулём (будет считать «жив» по одному
        факту, что `pgid` не `NULL`), пустая группа завершившегося шага
        ошибочно покажет «жив»."""
        self.insert_lease(_dead_pid(), pgid=4242)

        with mock.patch.object(catalog.liveness, "_group_member_count",
                               return_value=0):
            out = capture(catalog.cmd_status)

        self.assertIn("мёртв", out)


class CmdStatusZoneWaitMinutesTest(TmpRootTest):
    """SPEC 01M1VBEAWZW4EBZHKMGNBBK648, требование 4, AC-6: `status`
    добавляет минуты ожидания зоны, только пока задача реально в цикле
    `auto --wait-zone` (запись входа в ожидание уже журналирована)."""

    OTHER = "T901"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        store.update_task(store.db(), TASK, zones="a/b")
        store.insert_task(store.db(), self.OTHER, "Другая", "in_dev",
                          "task/t901-fake", config.DEFAULT_TARGET, 25.0)
        store.update_task(store.db(), self.OTHER, zones="a/b")
        store.journal(store.db(), self.OTHER, "developer",
                     "agent run started", "")

    def test_status_shows_minutes_waited_once_the_wait_cycle_entered(self):
        entry = zone_lock.wait_enter_action("a/b", self.OTHER, "in_dev")
        store.journal(store.db(), TASK, "operator", entry, "")

        out = capture(catalog.cmd_status)

        self.assertIn("ждёт", out)
        self.assertIn("мин", out)

    def test_status_does_not_show_minutes_without_the_wait_cycle_entry(self):
        """Ловит мутацию: минуты появляются в строке `status` даже без
        записи входа в ожидание — задача заблокирована зоной (`run`/`auto`
        без `--wait-zone` останавливаются немедленно), но НЕ в цикле
        ожидания, показывать «ждёт N мин» тут нечего."""
        out = capture(catalog.cmd_status)

        self.assertNotIn("мин", out)


if __name__ == "__main__":
    unittest.main()
