"""Выход цикла `auto` из ожидания занятой зоны: парная запись выхода при каждом выходе, кроме освобождения; вывод, исход и журнал остановки — прежние (AC-1, AC-2, AC-3, AC-5, AC-6, AC-7).

Группа: долгоживущий
Красен до реализации: функции `zone_lock.wait_interrupted_action` и констант `zone_lock.AUTO_START_ACTION`/`AUTO_STOPPED_ACTION`/`CYCLE_ABORTED_ACTION` ещё нет — AC-1, AC-2 (сверка места записи выхода перед «auto остановлен») и AC-5 падают на AttributeError, а `status` после прерванного `stop` ожидания показывает «ждёт 0 мин» (AC-6); test_ac3/test_ac7 зелёные с рождения — они держат прежние запись «зона свободна через» и отказ старта, которые правка обязана сохранить.

Связка, которую держит файл: команда `auto.cmd_auto` — журнал задачи —
замок зон (`zone_lock`) — `catalog.cmd_status`. Шаг роли подменён
(`runner.cmd_run`): пока `zone_lock.refusal` отказывает, подмена журналирует
`zone_lock.REFUSAL_ACTION` и выходит `SystemExit` текстом отказа — тем же
способом, каким отказывает настоящая `cmd_run`; зона свободна — «роль
стартовала» (вызов запоминается, задача уводится в `done`, чтобы цикл
кончился). Сон между опросами подменён `TimeWithSleep` (`auto.time`), время
не идёт по-настоящему.

Команда `stop` — сигнал SIGTERM: его обработчик ставит сам `cmd_auto`, тест
зовёт тот обработчик, что стоит на SIGTERM в момент события
(`signal.getsignal`). Точка «до сна» — вызов обработчика вне сна (из отказа
`run` либо из продления lease после очередного опроса): тогда он только
помечает остановку, и цикл видит её в начале следующего опроса. Точка «во
время сна» — вызов из подменённого сна. Номер опроса, на котором приходит
событие, интервал опроса и потолок в сценарии ненулевого потолка — от зерна;
зерно печатается и входит в текст каждого провала.

Причины остановки названы здесь литералами: критерий AC-2 требует, чтобы
они остались побайтно прежними, — литерал и есть прежний текст.
"""
import contextlib
import io
import os
import random
import re
import signal
import unittest
from unittest import mock

from orchestrator import (auto, catalog, config, cycle_hint, lease, runner,
                          store, zone_lock)
from tests.sandbox import (LightTransitionSandbox, TimeWithSleep,
                           capture_new_task_id)

STOP_REASON = "штатная остановка — команда stop"
CEILING_REASON = "потолок ожидания зоны исчерпан"
LEASE_LOST_PREFIX = "lease задачи потерян во время ожидания зоны: "
ENTER_PREFIX = "ждёт зоны "
EXIT_PREFIX = "зона свободна через"
STOPPED = "auto остановлен"

# Пять выходов из ожидания без освобождения зоны (AC-1).
EXITS = ("stop до сна", "stop во время сна", "потолок 0", "потолок после опросов",
         "потеря lease")

PLAN_DRAFT = """---
task: {task}
type: plan
author_role: developer
status: draft
schema_version: 1
---

# PLAN: фикстура ожидания зоны

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

MINUTES_SUFFIX = re.compile(r"ждёт \d+ мин")


class ZoneWaitSandbox(LightTransitionSandbox):
    """Ожидающая задача на занятой зоне и цикл `auto` над ней."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.counter = 0
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        # `cmd_auto` ставит свой обработчик SIGTERM — вернуть прежний.
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)

        self.real_acquire = lease.acquire
        for target, attr, value in (
                (runner, "cmd_run", self.fake_run),
                (auto, "time", TimeWithSleep(self.fake_sleep)),
                (lease, "acquire", self.acquire)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.reset_hooks()

    # --- подмены -------------------------------------------------------------

    def reset_hooks(self) -> None:
        self.sleeps = 0
        self.on_sleep = None
        self.on_acquire = None
        self.on_refusal = None
        self.started: list[str] = []
        self.watched = None
        self.last_refusal = None

    def fake_run(self, task_id: str, session_id: str | None = None) -> None:
        t = store.get_task(self.conn, task_id)
        refusal = zone_lock.refusal(self.conn, task_id, t)
        if refusal is not None:
            store.journal(self.conn, task_id, "developer",
                          zone_lock.REFUSAL_ACTION, refusal)
            if self.on_refusal is not None:
                self.on_refusal()
            raise SystemExit(refusal)
        self.started.append(task_id)
        store.journal(self.conn, task_id, "developer", "agent run started", "")
        self.conn.execute("UPDATE tasks SET state='done' WHERE id=?", (task_id,))
        self.conn.commit()

    def fake_sleep(self, seconds) -> None:
        if seconds != config.ZONE_WAIT_POLL_SEC:
            return
        self.sleeps += 1
        if self.on_sleep is not None:
            self.on_sleep(self.sleeps)

    def acquire(self, conn, task_id, session_id, **kwargs):
        """Продление lease — и снимок отказа старта задачи на этот опрос
        (держатель мог смениться между опросами)."""
        if task_id == self.watched:
            self.last_refusal = zone_lock.refusal(
                self.conn, task_id, store.get_task(self.conn, task_id))
        if self.on_acquire is not None:
            self.on_acquire()
        return self.real_acquire(conn, task_id, session_id, **kwargs)

    @staticmethod
    def stop_signal() -> None:
        """Команда `stop`: обработчик, стоящий на SIGTERM сейчас."""
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

    # --- фикстура ------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def next_zone(self) -> str:
        self.counter += 1
        return f"zona{self.counter}/kod.py"

    def waiting_task(self, zone: str) -> str:
        _, task_id = capture_new_task_id(
            catalog.cmd_new, f"Ждёт зону {self.counter} {self.seed}")
        tdir = config.TASKS / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text(PLAN_DRAFT.format(task=task_id),
                                      encoding="utf-8")
        self.conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (task_id,))
        self.conn.commit()
        store.update_task(self.conn, task_id, zones=zone)
        return task_id

    def occupier(self, zone: str, letter: str) -> str:
        task_id = f"T9{letter}{self.counter:03d}"
        store.insert_task(self.conn, task_id, f"Держатель {task_id}", "in_dev",
                          f"task/{task_id.lower()}-fake", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task_id, zones=zone)
        store.journal(self.conn, task_id, "developer", "agent run started", "")
        return task_id

    def release(self, task_id: str) -> None:
        self.conn.execute("UPDATE tasks SET state='done' WHERE id=?", (task_id,))
        self.conn.commit()

    def rows(self, task_id: str) -> list:
        return store.task_steps(self.conn, task_id)

    def run_auto(self, task_id: str, session: str) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            auto.cmd_auto(task_id, session, True)
        return buf.getvalue()

    # --- сценарий выхода -----------------------------------------------------

    def interrupted_wait(self, variant: str) -> dict:
        """Ожидание занятой зоны, прерванное выходом `variant` из `EXITS`.

        Словарь сценария: задача, зона, первоначальный и последний
        держатель, вывод `auto`, ожидаемые причина, минуты, подсказка и
        признак алерта прежнего поведения, отказ старта на последнем
        опросе до выхода (до цикла, если опроса не было)."""
        self.reset_hooks()
        zone = self.next_zone()
        task_id = self.waiting_task(zone)
        first = self.occupier(zone, "A")
        holder = first
        session = f"sess-mine-{self.counter}"
        poll = config.ZONE_WAIT_POLL_SEC
        patches = contextlib.ExitStack()
        alert = False
        fired = {"done": False}

        def fire_once():
            if not fired["done"]:
                fired["done"] = True
                self.stop_signal()

        if variant == "stop до сна":
            polls = self.rng.randint(0, 3)
            if polls == 0:
                self.on_refusal = fire_once
            else:
                self.on_acquire = (lambda: fire_once()
                                   if self.sleeps == polls else None)
            reason, minutes = STOP_REASON, int(polls * poll // 60)
        elif variant == "stop во время сна":
            polls = self.rng.randint(1, 3)
            self.on_sleep = lambda n: self.stop_signal() if n == polls else None
            reason, minutes = STOP_REASON, int((polls - 1) * poll // 60)
        elif variant == "потолок 0":
            patches.enter_context(mock.patch.object(config, "ZONE_WAIT_MAX_SEC", 0))
            polls = 0
            reason, minutes = CEILING_REASON, 0
        elif variant == "потолок после опросов":
            poll = self.rng.choice([30, 60, 90, 120])
            polls = self.rng.randint(2, 4)
            ceiling = polls * poll
            patches.enter_context(mock.patch.object(config, "ZONE_WAIT_POLL_SEC", poll))
            patches.enter_context(mock.patch.object(config, "ZONE_WAIT_MAX_SEC",
                                                    ceiling))
            # Держатель сменяется после первого опроса: запись обязана
            # назвать последнего известного, а не первоначального.
            holder = self.occupier(zone, "B")
            self.on_sleep = lambda n: self.release(first) if n == 1 else None
            reason, minutes = CEILING_REASON, int(ceiling // 60)
        elif variant == "потеря lease":
            polls = self.rng.randint(1, 3)
            other = f"sess-other-{self.counter}"

            def hijack(n):
                if n == polls:
                    self.conn.execute(
                        "UPDATE leases SET session_id=?, pid=?, hostname=?, "
                        "heartbeat_ts=? WHERE task_id=?",
                        (other, 999, "other-host", store.now(), task_id))
                    self.conn.commit()
            self.on_sleep = hijack
            reason, minutes = None, int(polls * poll // 60)
            alert = True
        else:
            raise AssertionError(variant)

        self.watched = task_id
        self.last_refusal = zone_lock.refusal(
            self.conn, task_id, store.get_task(self.conn, task_id))
        with patches:
            out = self.run_auto(task_id, session)
            if reason == CEILING_REASON:
                hint = (f"artel.py status  (кто держит зону) — дождись "
                        f"мержа/kill занявшей задачи либо artel.py "
                        f"zone-release {task_id}, затем "
                        + cycle_hint.launch_text(self.conn, task_id, "auto"))
            elif variant == "потеря lease":
                hint = cycle_hint.launch_text(self.conn, task_id, "auto",
                                              "— перезапусти ожидание")
            else:
                hint = cycle_hint.launch_text(self.conn, task_id, "auto",
                                              "— продолжит отсюда")
        stopped = [r for r in self.rows(task_id) if r["action"] == STOPPED]
        if reason is None and len(stopped) == 1:
            detail = stopped[0]["detail"] or ""
            reason = detail.partition("in_dev: ")[2]
        return {"variant": variant, "task": task_id, "zone": zone,
                "first": first, "holder": holder, "out": out,
                "reason": reason, "minutes": minutes, "hint": hint,
                "alert": alert, "before": self.last_refusal, "session": session,
                "polls": polls}

    def scenario_note(self, s: dict) -> str:
        journal = [f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                   for r in self.rows(s["task"])]
        return self.note(f"выход «{s['variant']}», опросов {s['polls']}; "
                         f"журнал: {journal}\nвывод:\n{s['out']}")


class InterruptedWaitJournalTest(ZoneWaitSandbox):

    def test_ac1_every_non_release_exit_journals_one_interrupted_record(self):
        """Каждый выход из ожидания, кроме освобождения, — одна запись входа и одна парная запись выхода с причиной, минутами и держателем.

        Сценарий: пять выходов из ожидания занятой зоны — `stop` до сна (до
        первого опроса либо после N-го), `stop` во время N-го сна, потолок
        `ZONE_WAIT_MAX_SEC = 0`, потолок, кратный интервалу опроса и равный
        нескольким опросам (держатель сменяется после первого опроса),
        потеря lease после N-го опроса. В журнале задачи ровно одна запись
        «ждёт зоны …», ровно одна запись актора `operator`, равная
        `zone_lock.wait_interrupted_action(причина, минуты, держатель)`, —
        причина равна причине остановки, минуты — целые минуты накопленного
        ожидания, держатель — последний известный; текст содержит причину
        и держателя и не начинается ни с «зона свободна через», ни с «ждёт
        зоны»; записи «зона свободна через» нет; между записью входа и
        записью «auto остановлен» других записей `operator` нет.

        Ловит мутацию: запись выхода пишется не на всех выходах (например,
        забыта точка `stop` во время сна или потеря lease) — записи нет;
        минуты считаются не от накопленного счётчика опросов (0 вместо
        `int(ZONE_WAIT_MAX_SEC // 60)`) либо держатель берётся
        первоначальный, а не последний — текст записи не совпадает; запись
        выхода сделана текстом «зона свободна через …» — она найдена.
        """
        for variant in EXITS:
            with self.subTest(variant=variant):
                s = self.interrupted_wait(variant)
                note = self.scenario_note(s)
                rows = self.rows(s["task"])
                enters = [r for r in rows if r["action"].startswith(ENTER_PREFIX)]
                self.assertEqual(len(enters), 1, note)
                self.assertIsNotNone(s["reason"], note)
                expected = zone_lock.wait_interrupted_action(
                    s["reason"], s["minutes"], s["holder"])
                self.assertIn(s["reason"], expected, note)
                self.assertIn(s["holder"], expected, note)
                self.assertFalse(expected.startswith(EXIT_PREFIX), note)
                self.assertFalse(expected.startswith(ENTER_PREFIX.strip()), note)
                exits = [r for r in rows if r["action"] == expected]
                self.assertEqual(len(exits), 1, self.note(
                    f"ожидалась запись «{expected}»: {note}"))
                self.assertEqual(exits[0]["actor"], "operator", note)
                self.assertFalse([r for r in rows
                                  if r["action"].startswith(EXIT_PREFIX)], note)
                stop_ids = [r["id"] for r in rows if r["action"] == STOPPED]
                self.assertEqual(len(stop_ids), 1, note)
                between = [r["action"] for r in rows
                           if enters[0]["id"] < r["id"] < stop_ids[0]
                           and r["actor"] == "operator"]
                self.assertEqual(between, [expected], note)


class InterruptedWaitStopUnchangedTest(ZoneWaitSandbox):

    def test_ac2_stop_outcome_output_and_journal_unchanged(self):
        """На каждом выходе исход остановки, вывод цикла и запись «auto остановлен» — прежние; запись выхода не печатается.

        Сценарий: те же пять выходов, что в AC-1. Вывод `auto` после строки
        входа в ожидание — ровно три строки остановки прежнего вида:
        «[<id>] auto остановлен: <причина>», «  состояние: in_dev»,
        «  дальше: <подсказка>» (подсказка `stop` — «— продолжит отсюда»,
        потолка — «artel.py status  (кто держит зону) …», потери lease —
        «— перезапусти ожидание»); запись «auto остановлен» одна, её detail —
        «in_dev: <причина>», и она стоит после записи выхода; алерт
        внимания поднят только на потере lease, прежним текстом; задача
        осталась `in_dev`; текст записи выхода в выводе не встречается.

        Ловит мутацию: новая запись выхода печатается (`print` рядом с
        `store.journal`) — лишняя строка в выводе; причина `Stop` заменена
        текстом новой записи либо `alert` потери lease сброшен — detail
        «auto остановлен», строки вывода или алерт расходятся с прежними;
        запись выхода пишется после возврата в цикл — она стоит позже
        «auto остановлен».
        """
        for variant in EXITS:
            with self.subTest(variant=variant):
                s = self.interrupted_wait(variant)
                note = self.scenario_note(s)
                task_id = s["task"]
                reason = s["reason"]
                if variant == "потеря lease":
                    self.assertTrue(reason.startswith(LEASE_LOST_PREFIX)
                                    if reason else False, note)
                    self.assertIn("sess-other", reason, note)
                enter_line = (f"[{task_id}] "
                              + zone_lock.wait_enter_action(
                                  s["zone"], s["first"], "in_dev") + "\n")
                self.assertEqual(s["out"].count(enter_line), 1, note)
                tail = s["out"].split(enter_line, 1)[1]
                self.assertEqual(
                    tail,
                    f"[{task_id}] auto остановлен: {reason}\n"
                    f"  состояние: in_dev\n"
                    f"  дальше: {s['hint']}\n", note)
                rows = self.rows(task_id)
                stopped = [r for r in rows if r["action"] == STOPPED]
                self.assertEqual(len(stopped), 1, note)
                self.assertEqual(stopped[0]["detail"], f"in_dev: {reason}", note)
                expected = zone_lock.wait_interrupted_action(
                    reason, s["minutes"], s["holder"])
                exit_ids = [r["id"] for r in rows if r["action"] == expected]
                self.assertEqual(len(exit_ids), 1, note)
                self.assertLess(exit_ids[0], stopped[0]["id"], note)
                self.assertNotIn(expected, s["out"], note)
                alerts = [a["message"] for a in store.open_alerts(self.conn,
                                                                  "attention")
                          if task_id in a["message"]]
                if s["alert"]:
                    self.assertEqual(
                        alerts, [f"[{task_id}] auto остановлен: in_dev: {reason}"],
                        note)
                else:
                    self.assertEqual(alerts, [], note)
                self.assertEqual(store.task_state(self.conn, task_id), "in_dev",
                                 note)


class ReleasedZoneExitTest(ZoneWaitSandbox):

    def test_ac3_release_journals_one_old_exit_record_only(self):
        """Освобождение зоны — ровно одна прежняя запись «зона свободна через N мин, держал <id>» и никакой новой записи выхода.

        Сценарий: держатель уходит в `done` во время N-го сна (N от зерна),
        интервал опроса — боевой. В журнале ровно одна запись с началом
        «зона свободна через», её текст — прежний «зона свободна через
        <int(N·интервал // 60)> мин, держал <id>», актор `operator`; между
        записью входа и стартом роли других записей `operator` нет; строка
        выхода напечатана один раз; роль стартовала тем же вызовом.

        Ловит мутацию: запись прерванного выхода пишется и на освобождении
        (например, общим `finally` вокруг цикла) — между входом и стартом
        роли появляется вторая запись `operator`; запись освобождения
        задвоена либо сменила текст — счёт или равенство не сходятся.
        """
        zone = self.next_zone()
        task_id = self.waiting_task(zone)
        holder = self.occupier(zone, "A")
        polls = self.rng.randint(1, 3)
        self.on_sleep = lambda n: self.release(holder) if n == polls else None

        out = self.run_auto(task_id, f"sess-mine-{self.counter}")

        rows = self.rows(task_id)
        journal = [f"{r['actor']} | {r['action']}" for r in rows]
        note = self.note(f"опросов {polls}; журнал: {journal}\nвывод:\n{out}")
        minutes = int(polls * config.ZONE_WAIT_POLL_SEC // 60)
        exit_text = f"зона свободна через {minutes} мин, держал {holder}"
        exits = [r for r in rows if r["action"].startswith(EXIT_PREFIX)]
        self.assertEqual([(r["actor"], r["action"]) for r in exits],
                         [("operator", exit_text)], note)
        self.assertEqual(out.count(f"[{task_id}] {exit_text}\n"), 1, note)
        self.assertEqual(self.started, [task_id], note)
        enter_id = next(r["id"] for r in rows
                        if r["action"].startswith(ENTER_PREFIX))
        start_id = next(r["id"] for r in rows
                        if r["action"] == "agent run started"
                        and r["actor"] == "developer")
        between = [r["action"] for r in rows
                   if enter_id < r["id"] < start_id and r["actor"] == "operator"]
        self.assertEqual(between, [exit_text], note)


class CycleRecordConstantsTest(ZoneWaitSandbox):

    def test_ac5_cycle_record_constants_drive_auto_journal(self):
        """Константы записей цикла в `zone_lock` равны прежним текстам, и `auto` журналирует именно их значения.

        Сценарий: `AUTO_START_ACTION == "auto старт"`, `AUTO_STOPPED_ACTION
        == "auto остановлен"`, `CYCLE_ABORTED_ACTION == "цикл оборван"`.
        Затем каждая константа подменяется в модуле `zone_lock` строкой от
        зерна: `auto` на задаче в `done` (старт и остановка без шага роли)
        журналирует запись старта и запись остановки подменёнными
        значениями; `auto`, чей цикл обрывается исключением (роль шага
        бросает), журналирует запись обрыва подменённым значением и
        пробрасывает исключение. Прежнего литерала в журнале этих вызовов
        нет.

        Ловит мутацию: `auto.py` пишет одну из трёх записей прежним
        литералом либо значением, скопированным при импорте (`from
        zone_lock import …`), а не через `zone_lock.<имя>` в момент записи —
        подмена не доходит до журнала, в нём прежний текст.
        """
        self.assertEqual(zone_lock.AUTO_START_ACTION, "auto старт")
        self.assertEqual(zone_lock.AUTO_STOPPED_ACTION, "auto остановлен")
        self.assertEqual(zone_lock.CYCLE_ABORTED_ACTION, "цикл оборван")

        mark = self.rng.randrange(1 << 20)
        start, stopped, aborted = (f"подмена старта {mark}",
                                   f"подмена остановки {mark}",
                                   f"подмена обрыва {mark}")
        zone = self.next_zone()
        done_task = self.waiting_task(zone)
        self.release(done_task)
        with mock.patch.object(zone_lock, "AUTO_START_ACTION", start), \
                mock.patch.object(zone_lock, "AUTO_STOPPED_ACTION", stopped), \
                mock.patch.object(zone_lock, "CYCLE_ABORTED_ACTION", aborted):
            out = self.run_auto(done_task, "sess-const-1")
        actions = [r["action"] for r in self.rows(done_task)]
        note = self.note(f"журнал: {actions}\nвывод:\n{out}")
        self.assertIn(start, actions, note)
        self.assertIn(stopped, actions, note)
        self.assertNotIn("auto старт", actions, note)
        self.assertNotIn("auto остановлен", actions, note)

        broken = self.waiting_task(self.next_zone())
        failure = RuntimeError(f"обрыв фикстуры {mark}")
        with mock.patch.object(zone_lock, "CYCLE_ABORTED_ACTION", aborted), \
                mock.patch.object(runner, "step_role", side_effect=failure):
            with self.assertRaises(RuntimeError):
                self.run_auto(broken, "sess-const-2")
        actions = [r["action"] for r in self.rows(broken)]
        note = self.note(f"журнал: {actions}")
        self.assertIn(aborted, actions, note)
        self.assertNotIn("цикл оборван", actions, note)


class StatusAfterStoppedWaitTest(ZoneWaitSandbox):

    @staticmethod
    def zone_suffix(out: str, task_id: str) -> str | None:
        for line in out.splitlines():
            if task_id in line:
                found = re.search(r"  \[ждёт зоны [^\]]*\]", line)
                return found.group(0) if found else None
        return None

    def test_ac6_status_after_stop_shows_no_wait_minutes(self):
        """После ожидания, прерванного `stop`, `status` у заблокированной задачи не показывает «ждёт N мин», держатель и очередь — прежние.

        Сценарий: на занятой зоне ждут две задачи с явными позициями в
        очереди (порядок — от зерна); у первой `auto` уходит в ожидание и
        прерывается `stop` (до сна либо во время сна — от зерна). Добавка
        `status` «[ждёт зоны …]» этой задачи после выхода равна той, что
        была до вызова `auto` (держатель, «очередь i/n»), и не несёт «ждёт
        N мин»; задача по-прежнему заблокирована зоной.

        Ловит мутацию: `wait_minutes` закрывает ожидание только записью
        «зона свободна через» (новая запись выхода не распознана) — в
        добавке появляется «ждёт 0 мин».
        """
        zone = self.next_zone()
        task_id = self.waiting_task(zone)
        holder = self.occupier(zone, "A")
        other = self.waiting_task(zone)
        first_place = self.rng.choice([1, 2])
        store.update_task(self.conn, task_id, zone_queue_position=first_place)
        store.update_task(self.conn, other, zone_queue_position=3 - first_place)
        before = self.zone_suffix(self.capture(catalog.cmd_status), task_id)
        self.assertIsNotNone(before, self.note("предпосылка: нет добавки зоны"))
        self.assertIn(holder, before, self.note(before))

        if self.rng.random() < 0.5:
            variant = "до сна"
            self.on_refusal = self.stop_signal
        else:
            variant = "во время сна"
            self.on_sleep = lambda n: self.stop_signal() if n == 1 else None
        out_auto = self.run_auto(task_id, f"sess-mine-{self.counter}")

        status = self.capture(catalog.cmd_status)
        after = self.zone_suffix(status, task_id)
        note = self.note(f"stop {variant}; до: {before!r}; после: {after!r}\n"
                         f"status:\n{status}\nauto:\n{out_auto}")
        self.assertIsNotNone(zone_lock.blocking_conflict(
            self.conn, task_id, store.get_task(self.conn, task_id)), note)
        self.assertEqual(after, before, note)
        self.assertIsNone(MINUTES_SUFFIX.search(after or ""), note)


class StartRefusalAfterExitTest(ZoneWaitSandbox):

    def test_ac7_refusal_holds_after_every_exit_and_release_lets_through(self):
        """После каждого выхода из ожидания отказ старта по зоне тот же, роль не стартовала; `zone-release` пускает задачу.

        Сценарий: пять выходов AC-1. После выхода `zone_lock.refusal`
        отказывает тем же текстом, что до вызова `auto`, роль не
        стартовала ни разу. Затем `zone_lock.cmd_zone_release` (для
        потери lease — после ухода чужой сессии): отказ старта исчезает, и
        следующий `auto` стартует роль.

        Ловит мутацию: запись выхода сделана маркером, который замок зон
        читает как занятость (например, `RELEASE_ACTION` или «zone
        claimed»), — после выхода отказа нет и задача стартовала бы на
        занятой зоне; либо прерванный выход возвращает «зона свободна» и
        цикл зовёт роль.
        """
        for variant in EXITS:
            with self.subTest(variant=variant):
                s = self.interrupted_wait(variant)
                note = self.scenario_note(s)
                task_id = s["task"]
                self.assertIsNotNone(s["before"], note)
                after = zone_lock.refusal(self.conn, task_id,
                                          store.get_task(self.conn, task_id))
                self.assertEqual(after, s["before"], note)
                self.assertEqual(self.started, [], note)

                self.conn.execute("DELETE FROM leases WHERE task_id=?", (task_id,))
                self.conn.commit()
                self.capture(zone_lock.cmd_zone_release, task_id)
                self.assertIsNone(zone_lock.refusal(
                    self.conn, task_id, store.get_task(self.conn, task_id)), note)
                self.reset_hooks()
                out = self.run_auto(task_id, f"{s['session']}-again")
                self.assertEqual(self.started, [task_id],
                                 self.note(f"после zone-release:\n{out}\n{note}"))


if __name__ == "__main__":
    unittest.main()
