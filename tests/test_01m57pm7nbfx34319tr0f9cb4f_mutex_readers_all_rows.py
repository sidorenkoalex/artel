"""Читатели мьютекса мержа вне `merge_lock` смотрят все его строки: окно
тишины `note` и проверка `doctor check_merge_lock` с автоподтверждением
инцидента.

Группа: долгоживущий
Красен до реализации: окно тишины и `doctor check_merge_lock` читают одну «первую» строку `merge_locks` — при строке внешнего проекта первой окно не открывается (AC-13), мёртвый держатель за живой строкой не виден, а его инцидент закрывается живой строкой другого проекта (AC-14); в порядке «нужная строка первой» сценарии зелены и до правки.

Связки: окно тишины — публичная команда `notes.cmd_note` на настоящем
bare `origin` (`RealGitSandbox`): решение окна наблюдается по тому,
удержана ли запись с текстом «заметка удержана: <причина>; отправка — …»;
doctor — `doctor.check_merge_lock` и таблица алертов на БД песочницы.
Строки мьютекса двух проектов сеются прямой вставкой в `merge_locks`
(схема несёт несколько строк без ключа). Живой держатель артели — этот
процесс на этом host; живой держатель внешнего проекта — чужой host со
свежим heartbeat либо этот процесс; мёртвый — неживой pid на этом host.

Идентификаторы задач, сессий и имя внешнего проекта случайны на каждый
запуск; зерно печатается и входит в текст провала.
"""
import os
import random
import shutil
import socket
import tempfile
import unittest
from unittest import mock

from orchestrator import alerts, catalog, config, doctor, notes, store
from tests.sandbox import (RealGitSandbox, TmpRootTest, _dead_pid, capture,
                           declare_target, init_bare_origin)

BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое наблюдение | orchestrator/x.py |
"""

HELD_PREFIX = "заметка удержана: "
HELD_SUFFIX = "; отправка"
OTHER_HOST = "other-host.invalid"
MERGE_LOCK_SOURCE = "doctor.merge_lock"

# Состояния вне окна тишины — у задач держателей, чтобы держатель был
# единственным триггером окна. Фильтр по набору окна динамический.
OUTSIDE_WINDOW = tuple(s for s in ("done", "killed", "escalated", "merge_gate")
                       if s not in config.NOTE_SILENCE_WINDOW_STATES)

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class _RandomIds:

    def init_rng(self) -> None:
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def token(self, n: int = 10) -> str:
        return "".join(self.rng.choice(_ALPHABET) for _ in range(n))

    def new_task(self, target, state: str) -> str:
        tid = "T" + self.token(12)
        conn = store.db()
        store.insert_task(conn, tid, "читатели мьютекса", state,
                          f"task/{tid.lower()}", config.DEFAULT_TARGET, 10.0)
        if target != config.DEFAULT_TARGET:
            store.update_task(conn, tid, target=target)
        return tid

    def session(self) -> str:
        return "s-" + self.token(8).lower()

    def seed_lock(self, task_id: str, session_id: str, pid: int,
                  hostname: str) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO merge_locks (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (task_id, session_id, pid, hostname, store.now()))
        conn.commit()

    def clear_locks(self) -> None:
        conn = store.db()
        conn.execute("DELETE FROM merge_locks")
        conn.commit()

    def msg(self, ctx: str) -> str:
        return f"{ctx}; зерно {self.seed}"


class SilenceWindowAllRowsTest(_RandomIds, RealGitSandbox):
    """Стенд: bare `origin` с `docs/backlog.md`, внешний проект объявлен в
    `config.TARGETS` песочницы."""

    def setUp(self):
        super().setUp()
        self.init_rng()
        role_patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role_patcher.start()
        self.addCleanup(role_patcher.stop)
        self.origin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        init_bare_origin(self.origin, self.git)
        self.git("remote", "add", "origin", self.origin)
        docs = self.root / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "backlog.md").write_text(BACKLOG_TEXT, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "backlog")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.external = "ext" + self.token(6).lower()
        declare_target(self.external)
        self.calls = 0

    def note(self) -> tuple:
        """Одна запись копилки; (уникальный текст, вывод команды)."""
        self.calls += 1
        marker = f"запись{self.calls}-{self.token(8)}"
        text = f"2 | 18.10 | {marker} | orchestrator/n.py"
        out = self.capture(notes.cmd_note, ["копилка", "--text", text])
        return marker, out

    def origin_backlog(self) -> str:
        return self.git("--git-dir", self.origin, "show",
                        f"{config.MAIN_BRANCH}:docs/backlog.md")

    def test_ac13_artel_holder_opens_window_beside_external_holder(self):
        """Строки живого держателя внешнего проекта и живого
        держателя-задачи артели, оба порядка вставки; задачи держателей
        вне состояний окна. `note` удержан с причиной «держатель
        merge-окна жив (сессия <sid>, задача <id>)» держателя артели.

        Ловит мутацию: окно тишины читает одну «первую» строку мьютекса
        (прежний `merge_lock_row`) — при строке внешнего держателя первой
        она пропускается как внешняя, держатель артели не виден, и запись
        уходит в `origin` без удержания."""
        for external_first in (True, False):
            with self.subTest(external_first=external_first):
                self.clear_locks()
                art = self.new_task(config.DEFAULT_TARGET,
                                    self.rng.choice(OUTSIDE_WINDOW))
                ext = self.new_task(self.external,
                                    self.rng.choice(OUTSIDE_WINDOW))
                art_sid, ext_sid = self.session(), self.session()
                seeds = [lambda: self.seed_lock(ext, ext_sid,
                                                self.rng.randrange(100000, 4000000),
                                                OTHER_HOST),
                         lambda: self.seed_lock(art, art_sid, os.getpid(),
                                                socket.gethostname())]
                for seed in (seeds if external_first else seeds[::-1]):
                    seed()
                marker, out = self.note()
                ctx = self.msg(f"артель {art}/{art_sid}, внешний {ext}; "
                               f"вывод {out!r}")

                self.assertIn(HELD_PREFIX, out, ctx)
                self.assertNotIn(marker, self.origin_backlog(), ctx)
                reason = out.split(HELD_PREFIX, 1)[1].split(HELD_SUFFIX, 1)[0]
                self.assertEqual(
                    reason,
                    f"держатель merge-окна жив (сессия {art_sid}, задача {art})",
                    ctx)


class DoctorMergeLockAllRowsTest(_RandomIds, TmpRootTest):
    """Стенд: инициализированный пульт, внешний проект объявлен."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.init_rng()
        self.external = "ext" + self.token(6).lower()
        declare_target(self.external)

    def merge_lock_incidents(self, task_id: str) -> list:
        return [a for a in alerts.open_alerts(store.db(), "incident")
                if a["source"] == MERGE_LOCK_SOURCE
                and a["message"].startswith(f"{task_id}:")]

    def test_ac14_dead_holder_beside_live_one_is_flagged_until_removed(self):
        """Строка мёртвого держателя проекта P (этот host, неживой pid) и
        живого держателя проекта Q, оба порядка вставки. `check_merge_lock`
        даёт fail и incident `doctor.merge_lock` с задачей P; повторный
        прогон инцидент не закрывает; после снятия строки P — закрывает.

        Ловит мутацию: проверка смотрит одну «первую» строку — при живой
        строке Q первой fail и инцидента нет; либо автоподтверждение
        сверяет инцидент с одной строкой — живая строка Q закроет инцидент
        P на повторном прогоне, `assertIsNone(ack_ts)` покраснеет."""
        pairs = ((config.DEFAULT_TARGET, self.external),
                 (self.external, config.DEFAULT_TARGET))
        for p_target, q_target in pairs:
            for dead_first in (True, False):
                with self.subTest(p=p_target, q=q_target,
                                  dead_first=dead_first):
                    self.clear_locks()
                    conn = store.db()
                    p_task = self.new_task(p_target, "merge_gate")
                    q_task = self.new_task(q_target, "merge_gate")
                    p_sid, p_pid = self.session(), _dead_pid()
                    seeds = [lambda: self.seed_lock(p_task, p_sid, p_pid,
                                                    socket.gethostname()),
                             lambda: self.seed_lock(q_task, self.session(),
                                                    os.getpid(),
                                                    socket.gethostname())]
                    for seed in (seeds if dead_first else seeds[::-1]):
                        seed()
                    ctx = self.msg(f"мёртв P {p_task} ({p_target}), жив Q "
                                   f"{q_task} ({q_target})")

                    checks = doctor.check_merge_lock(conn)

                    self.assertTrue(any(c.status == "fail" for c in checks),
                                    f"{ctx}; {checks}")
                    incidents = self.merge_lock_incidents(p_task)
                    self.assertEqual(len(incidents), 1, ctx)
                    alert_id = incidents[0]["id"]

                    doctor.check_merge_lock(conn)

                    self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"],
                                      ctx)

                    store.release_merge_lock(conn, p_sid, p_pid)
                    doctor.check_merge_lock(conn)

                    self.assertIsNotNone(
                        store.get_alert(conn, alert_id)["ack_ts"], ctx)


if __name__ == "__main__":
    unittest.main()
