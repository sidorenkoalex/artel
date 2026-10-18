"""AC-8: у базы с задачами только артели тексты `status`, `report` и
`watch` совпадают с выводом до правки.

Группа: разовый
Зелёный с рождения: эталон `_ac8_golden.py` снят на коде до правки (база ветки задачи, 18.10.2026) — тест держит прежний вывод и краснеет, только если правка задачи изменила текст артели сверх строк алертов с `target` NULL в дозоре наблюдения.

Эталон — литералы модуля `_ac8_golden.py` рядом с тестом; тест не строит
его тем же кодом при прогоне. Нормализация времени: текущий момент
`report` зафиксирован (`report.datetime.now` и аргумент `now` рендера —
`FROZEN`), метки времени журнала и алертов фикстуры — литералы. Прочие
части HTML сравниваются без нормализации.
"""
import contextlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ac8_golden as golden  # noqa: E402

from orchestrator import agent_log, artel, catalog, config, report, store, watch  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest, capture, patch_sleep  # noqa: E402

FROZEN = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
NULL_MESSAGE = "ac8-null-alert-of-pult"
NULL_WATCH_MESSAGES = ("ac8-null-in-observation", "ac8-null-in-plain-watch")


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN if tz is not None else FROZEN.replace(tzinfo=None)


class ArtelOnlyOutputs(TaskSeededTmpRootTest):
    """Фикстура: задачи только артели — `target` = артель и `target`
    NULL — в разных состояниях; журнал гейтов, operator, test_author и
    трения; алерты артели, NULL, id задачи и триггеры."""

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "CODEX_SANDBOX": "",
                                           "CODEX_SANDBOX_NETWORK_DISABLED": ""})
        env.start()
        self.addCleanup(env.stop)
        self.conn = store.db()
        c = self.conn
        store.insert_task(c, "T002", "Гейт приёмки", "acceptance", "task/t002",
                          config.DEFAULT_TARGET, 25.0)
        store.insert_task(c, "T003", "Без проекта", "done", "task/t003",
                          config.DEFAULT_TARGET, 25.0)
        store.update_task(c, "T003", target=None, spent_usd=4.0,
                          spent_estimate_usd=0.3)
        store.insert_task(c, "T004", "Закрытая", "done", "task/t004",
                          config.DEFAULT_TARGET, 25.0)
        store.update_task(c, "T004", spent_usd=1.0)
        store.insert_task(c, "T005", "Гейт SPEC", "spec_gate", "task/t005",
                          config.DEFAULT_TARGET, 25.0)
        store.update_task(c, "T002", spent_usd=2.5)
        for task_id, actor in (("T003", "autogate"), ("T004", "operator"),
                               ("T003", "operator")):
            store.journal(c, task_id, actor, report.GATE_TRANSITION_ACTION)
        store.journal(c, "T005", "operator", "approve", "spec_gate")
        # Запуск test_author — у задачи вне наблюдения и вне `watch --tasks`:
        # живой шаг в наборе дал бы строку хода шага с текущим временем.
        store.journal(c, "T005", report.TEST_AUTHOR_ROLE,
                      report.STEP_STARTED_ACTION, "старт шага")
        store.journal(c, "T004", "developer", agent_log.FRICTION_JOURNAL_ACTION,
                      "0.25")
        store.insert_alert(c, config.DEFAULT_TARGET, "incident", "ac8", "ac8-artel")
        store.insert_alert(c, None, "warning", "ac8", NULL_MESSAGE)
        store.insert_alert(c, "T002", "attention", "ac8", "ac8-task")
        store.insert_alert(c, config.DEFAULT_TARGET, "trigger", "ac8", "ac8-trig")
        store.insert_alert(c, None, "trigger", "ac8", "ac8-trig-null")
        self.freeze_ts()

    def freeze_ts(self) -> None:
        """Метки времени журнала и алертов — литералы по порядку записи."""
        c = self.conn
        for table in ("steps", "alerts"):
            ids = [r[0] for r in c.execute(f"SELECT id FROM {table} ORDER BY id")]
            for i, row_id in enumerate(ids):
                ts = f"2026-10-{12 + i % 4:02d} 09:{i % 60:02d}:00Z"
                c.execute(f"UPDATE {table} SET ts=? WHERE id=?", (ts, row_id))
        c.commit()

    def cli(self, *argv) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            return capture(artel.main)

    def status_text(self) -> str:
        return capture(catalog.cmd_status)

    def report_html(self) -> str:
        with mock.patch.object(report, "datetime", FrozenDatetime):
            capture(report.cmd_report)
        return (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")

    def run_watch(self, argv: list, between) -> str:
        """Две итерации дозора: `between` — события между ними."""
        calls = []

        def sleep(_seconds):
            calls.append(1)
            if len(calls) > 1:
                raise RuntimeError("watch ended")
            between()

        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", "watch", *argv]), \
                patch_sleep(watch, sleep), contextlib.redirect_stdout(out):
            try:
                artel.main()
            except RuntimeError as exc:
                if str(exc) != "watch ended":
                    raise
        return out.getvalue()

    def watch_observation_text(self) -> str:
        observation_id = json.loads(self.cli("observe", "register", "--tasks",
                                             f"{self.TASK},T002"))["id"]
        c = self.conn
        store.journal(c, self.TASK, "fsm", "state -> review", "ac8-step-obs")
        store.insert_alert(c, config.DEFAULT_TARGET, "incident", "ac8", "ac8-obs-artel")
        store.insert_alert(c, "T002", "attention", "ac8", "ac8-obs-task")
        store.insert_alert(c, None, "incident", "ac8", NULL_WATCH_MESSAGES[0])
        self.freeze_ts()
        return self.run_watch(["--observation", observation_id], lambda: None)

    def watch_plain_text(self) -> str:
        def between():
            c = self.conn
            store.journal(c, self.TASK, "fsm", "state -> review", "ac8-step-plain")
            store.insert_alert(c, self.TASK, "attention", "ac8", "ac8-plain-task")
            store.insert_alert(c, None, "incident", "ac8", NULL_WATCH_MESSAGES[1])
            self.freeze_ts()
        return self.run_watch(["--tasks", self.TASK], between)

    def outputs(self) -> dict:
        return {"status": self.status_text(), "report": self.report_html(),
                "watch_observation": self.watch_observation_text(),
                "watch_plain": self.watch_plain_text()}


def without_null_lines(text: str) -> str:
    return "".join(line for line in text.splitlines(keepends=True)
                   if not any(m in line for m in NULL_WATCH_MESSAGES))


class ArtelOnlyUnchangedTest(ArtelOnlyOutputs):

    def test_ac8_status_report_watch_match_pre_change_golden(self):
        """Тексты `status`, HTML `report`, дозора наблюдения и обычного
        `watch` у базы только артели — ровно эталон до правки; из дозора
        наблюдения исключены только строки алертов с `target` NULL.

        Ловит мутацию: метка проекта ставится задаче артели или задаче с
        `target` NULL (`[artel]`/`[None]` в `status`/`report`); блоки
        «Экономика»/доли acceptance разбиваются при одном проекте (NULL
        считается отдельным проектом); правка доставки NULL-алертов
        задела обычный `watch` или строки прочих алертов дозора.
        """
        got = self.outputs()
        got["watch_observation"] = without_null_lines(got["watch_observation"])
        expected = {"status": golden.STATUS, "report": golden.REPORT_HTML,
                    "watch_observation": without_null_lines(golden.WATCH_OBSERVATION),
                    "watch_plain": golden.WATCH_PLAIN}
        for name in expected:
            with self.subTest(output=name):
                self.assertEqual(got[name], expected[name])
