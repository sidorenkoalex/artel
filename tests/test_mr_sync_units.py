"""Юнит-тесты сверки MR `mr-sync` (SPEC 01M6AB4VE2R0Q2V5D4MMJGNGH7): свойства вне долгоживущих файлов задачи.

Сквозные сценарии (таблица итогов, `--confirm`, инциденты, опрос надзора)
держит `tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py`. Здесь — узлы в
изоляции: принятая голова ветки только при возврате из эскалации «чужой
коммит» (ANSWER-1 п. 6, отрицательная половина), срок опроса надзора,
показ итога в модели доски только у задачи в `awaiting_human`, признаки
(б)/(в) на правке не в UTF-8 и отказ `approve` без точки ответвления.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import board, mr_sync, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402
from tests.test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery import stand  # noqa: E402,F401  (фикстура стенда доставки)

SERVER_HEAD = "f" * 40


class AcceptServerHeadTest(TaskSeededTmpRootTest):

    def escalate(self, detail: str) -> None:
        conn = store.db()
        store.update_task(conn, self.TASK, state="escalated")
        store.journal(conn, self.TASK, "fsm", "state -> escalated", detail)

    def accept(self) -> list:
        with mock.patch.object(mr_sync.gitcmd, "remote_branch_sha",
                               lambda branch, repo=None: SERVER_HEAD):
            mr_sync.accept_server_head(store.db(), self.TASK)
        return [r for r in store.task_steps(store.db(), self.TASK)
                if r["action"] == mr_sync.ACCEPTED_HEAD_ACTION]

    def test_other_escalation_does_not_accept_head(self):
        """Иная эскалация (например MR влит до `awaiting_human`) голову сервера не принимает.

        Ловит мутацию: голова принимается при возврате из любой эскалации —
        чужой коммит, положенный после неё, стал бы своим без решения
        Оператора по нему.
        """
        self.escalate(f"{mr_sync.MR_DONE_EARLY_DETAIL}: MR !7 merged")
        self.assertEqual(self.accept(), [])
        self.assertEqual(mr_sync.expected_server_head(store.db(), self.TASK), "")


class NonUtf8DiffTest(unittest.TestCase):
    """Правка задачи с файлом в cp1251: признаки (б) и (в) считаются по
    байтам, без исключения декодирования (REVIEW R1-F1)."""

    def git(self, *args: str) -> str:
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_COMMITTER_NAME": "t",
               "GIT_AUTHOR_EMAIL": "t@example.invalid",
               "GIT_COMMITTER_EMAIL": "t@example.invalid",
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        return subprocess.run(["git", "-C", self.repo, *args], env=env,
                              check=True, capture_output=True).stdout.decode()

    def commit(self, rel: str, data: bytes, message: str) -> str:
        with open(os.path.join(self.repo, rel), "wb") as fh:
            fh.write(data)
        self.git("add", rel)
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = tmp.name
        self.git("init", "-q", "-b", "base")
        self.fork = self.commit("readme.txt", b"start\n", "fork")
        self.git("checkout", "-q", "-b", "task")
        self.head = self.commit("legacy.txt", "Привет\n".encode("cp1251"),
                                "task")
        self.git("checkout", "-q", "base")
        self.commit("other.txt", b"other\n", "other")
        self.git("cherry-pick", self.head)
        self.base = self.git("rev-parse", "HEAD").strip()

    def test_signs_on_cp1251_file(self):
        """Коммит задачи с файлом в cp1251, перенесённый в базу: (б) находит его, (в) проходит с доказательством по файлу.

        Ловит мутацию: вывод git снова декодируется строгим UTF-8
        (`text=True` в `_git`/`_out_bytes`, патч строкой в `git apply`) —
        `UnicodeDecodeError` вылетает мимо `GitFailure`, сверка падает
        трассировкой вместо итога.
        """
        commits, found, closing = mr_sync._commits_sign(
            self.repo, self.base, self.fork, self.head)
        self.assertEqual(found, commits)
        self.assertEqual(closing, self.base)
        passes, lines = mr_sync._diff_sign(self.repo, self.base, self.fork,
                                           self.head)
        self.assertTrue(passes, lines)
        self.assertIn("legacy.txt: обратное наложение — проходит", lines[0])


class DueTest(unittest.TestCase):

    def test_interval_counts_minutes_since_last_sync(self):
        """Сверка надзора — не раньше `interval` минут после прошлой; первой сверки ничто не держит.

        Ловит мутацию: интервал читается в секундах (сверка через 61 с при
        N = 2 — «пора») или прошлая сверка не учитывается.
        """
        now = "2031-07-05 12:10:00Z"
        with mock.patch.object(mr_sync.store, "now", lambda: now):
            self.assertTrue(mr_sync.due({"mr_sync_at": None}, 2))
            self.assertFalse(mr_sync.due({"mr_sync_at": "2031-07-05 12:08:59Z"}, 2))
            self.assertTrue(mr_sync.due({"mr_sync_at": "2031-07-05 12:08:00Z"}, 2))


class FirstSyncNotifiesTest(TaskSeededTmpRootTest):

    def changes(self, outcome: str) -> list:
        with mock.patch.object(mr_sync, "evaluate",
                               lambda conn, task_id: mr_sync.Sync(outcome)):
            mr_sync.sync_task(store.db(), self.TASK)
        return [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                if r["action"] == mr_sync.OUTCOME_CHANGED_ACTION]

    def test_first_sync_is_a_change_repeat_is_not(self):
        """Первая сверка задачи даёт запись смены итога (уведомление `watch`), повтор того же итога — нет (ANSWER-2 п. 3).

        Ловит мутацию: смена считается только относительно прошлого итога —
        первая сверка (например сразу «влит этим MR») без записи смены;
        либо каждая сверка пишется сменой.
        """
        self.assertEqual(self.changes(mr_sync.MERGED_THIS),
                         [f"{mr_sync.FIRST_SYNC} → {mr_sync.MERGED_THIS}"])
        self.assertEqual(len(self.changes(mr_sync.MERGED_THIS)), 1)


class BoardMrSyncTest(unittest.TestCase):

    @staticmethod
    def row(state: str) -> dict:
        class Row(dict):
            def keys(self):
                return list(super().keys())
        return Row(state=state, mr_sync_outcome=mr_sync.MERGED_THIS,
                   mr_sync_at="2031-07-05 12:10:00Z")

    def test_shown_only_while_awaiting_human(self):
        """Итог `mr-sync` показан у задачи в `awaiting_human` и не показан после закрытия.

        Ловит мутацию: итог показывается в любом состоянии — у закрытой
        `done` задачи доска несёт устаревшую сверку.
        """
        shown = board.mr_sync_shown(self.row("awaiting_human"))
        self.assertEqual(shown, {"outcome": mr_sync.MERGED_THIS,
                                 "at": "2031-07-05 12:10:00Z"})
        self.assertIsNone(board.mr_sync_shown(self.row("done")))


def test_gate_refuses_when_mr_status_unread(stand):
    """Отказ `forge.mr_status` на `approve` гейта мержа задачи с `mr_iid` — отказ `approve`, задача на гейте (ANSWER-2 п. 2).

    Сценарий: стенд доставки Б2.1б, запись `target-human`, ссылка на MR в
    БД, подделка хостинга отвечает на `mr_status` отказом. `approve`:
    задача в `merge_gate`, причина хостинга в выводе, `undraft_mr` и
    `assign_mr` не званы.

    Ловит мутацию: сбой чтения статуса MR пропускает проверку инцидента —
    гейт снимает черновик, назначает исполнителя и переводит задачу в
    `awaiting_human`.
    """
    stand.record(mr_assignee='"42"')
    task = stand.new_task(state="merge_gate", published=True)
    iid = stand.rng.randrange(100, 10 ** 6)
    store.update_task(stand.conn, task, mr_iid=iid,
                      mr_url=f"https://localhost/mr/{iid}")
    reason = f"GitLab ответил кодом 503 на GET merge_requests/{iid}"
    stand.fake.fail["mr_status"] = reason
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == "merge_gate", where
    assert reason in out, where
    assert stand.fake.named("undraft_mr") == [], where
    assert stand.fake.named("assign_mr") == [], where


def test_gate_refuses_without_fork_point(stand):
    """Точка ответвления не вычислена на `approve` гейта мержа — отказ `approve` до MR, задача на гейте (REVIEW R1-F3).

    Сценарий: стенд доставки Б2.1б, запись `target-human`, ссылка на MR в
    БД, `git merge-base` не отвечает. `approve`: задача в `merge_gate`,
    причина в выводе, точки ответвления в БД нет, `undraft_mr`/`assign_mr`
    не званы.

    Ловит мутацию: несчитанная точка не останавливает гейт — задача уходит
    в `awaiting_human` без точки, где каждая сверка — «неизвестно» и выход
    только `kill`; либо отказ идёт после снятия черновика MR.
    """
    stand.record(mr_assignee='"42"')
    task = stand.new_task(state="merge_gate", published=True)
    iid = stand.rng.randrange(100, 10 ** 6)
    store.update_task(stand.conn, task, mr_iid=iid,
                      mr_url=f"https://localhost/mr/{iid}")
    real_out = mr_sync._out

    def out(repo, *args, **kwargs):
        if args and args[0] == "merge-base":
            return None
        return real_out(repo, *args, **kwargs)

    with mock.patch.object(mr_sync, "_out", out):
        out_text = stand.approve(task)
    where = stand.context(task, out_text)
    assert stand.state(task) == "merge_gate", where
    assert "точка ответвления не вычислена" in out_text, where
    assert not store.get_task(stand.conn, task)["fork_point"], where
    assert stand.fake.named("undraft_mr") == [], where
    assert stand.fake.named("assign_mr") == [], where


if __name__ == "__main__":
    unittest.main()
