"""Сводка и запись приёмки канарейки по результату процесса клона.
Группа: долгоживущий
Красен до реализации: пульт ещё не сохраняет способ приёмки и причину отказа автогейта.
"""
import json
import random
import re
import subprocess
import sys
from pathlib import Path
from unittest import mock

from orchestrator import canary, catalog, config, store
from tests.sandbox import RealGitSandbox, capture


class CanaryAcceptanceResultTest(RealGitSandbox):
    """Локальный клон отдаёт пульту результат без новых JSON-полей."""

    def setUp(self):
        super().setUp()
        entry = self.root / "orchestrator" / "canary_drive.py"
        entry.parent.mkdir(parents=True)
        entry.write_text("# вход учебного клона\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "clone entry")
        self.target = self.git("rev-parse", "HEAD").strip()
        self.home = self.root / "fixture-home"
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir(parents=True)
        self.template = pool / "fixture.md"
        self.template.write_text("# Учебная задача\n", encoding="utf-8")
        self.steps = []
        self.kill_note = "штатно"
        self.real_popen = subprocess.Popen

    def _step(self, action, detail="", actor="fsm"):
        return {"ts": "2026-09-30T12:00:00Z", "actor": actor,
                "action": action, "detail": detail}

    def _result(self):
        return {
            "task_id": "01FIXTURE", "head": self.target, "outcome": "killed",
            "escalated": False,
            "metrics": {
                "steps": 3, "cost_usd": 0.0, "review_iterations": 0,
                "escalations": [], "dev_retries": 0, "outcome": "killed",
                "kill_note": self.kill_note, "test_author_visited": False,
                "ceiling_exhausted": False, "ceiling_raise": None,
            },
            "steps": self.steps,
        }

    def _popen(self, argv, *args, **kwargs):
        if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
            return self.real_popen(argv, *args, **kwargs)
        result_path = Path(argv[argv.index("--result") + 1])
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(self._result(), ensure_ascii=False),
                               encoding="utf-8")
        kwargs["stdout"].write("учебный процесс завершён\n")

        class FinishedProcess:
            def wait(self, timeout=None):
                return 0

        return FinishedProcess()

    def _run(self, steps, *, kill_note="штатно"):
        self.steps = steps
        self.kill_note = kill_note
        with mock.patch.object(Path, "home", return_value=self.home), \
                mock.patch.object(catalog, "cmd_init"), \
                mock.patch.object(subprocess, "Popen", self._popen):
            output = capture(lambda: canary.cmd_canary(
                k=1, sha=self.target, templates=[self.template.stem]))
        conn = store.db()
        row = conn.execute("SELECT * FROM canary_runs ORDER BY id DESC LIMIT 1").fetchone()
        return output, row

    def _manual_steps(self, reason):
        return [self._step("state -> acceptance"),
                self._step("автогейт acceptance не пройден", reason),
                self._step("state -> merge_gate", actor="canary")]

    def test_ac1_refusal_reason_is_bounded_and_journaled(self):
        """Длинная многострочная причина отказа до ручной приёмки видна в сводке и выдержке.

        Ловит мутацию: отказ вырезан из выдержки или причина в строке итога
        потеряна, не свёрнута либо печатается без ограничения длины.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        tail_size = rng.randint(310, 410)
        reason = f"причина  {'A' * 310}\n  {'B' * tail_size}"
        output, _ = self._run(self._manual_steps(reason))
        summary = next((line for line in output.splitlines()
                        if "причина" in line
                        and "fsm: автогейт acceptance не пройден" not in line),
                       "")
        self.assertTrue(summary, f"зерно: {seed}\n{output}")
        self.assertRegex(summary, r"A{310} B+", f"зерно: {seed}\n{summary}")
        self.assertLessEqual(sum(len(s) for s in re.findall(r"[AB]+", summary)),
                             492, f"зерно: {seed}\n{summary}")
        self.assertTrue(any("fsm: автогейт acceptance не пройден" in line
                            for line in output.splitlines()),
                        f"зерно: {seed}\n{output}")

    def test_ac2_not_started_and_self_passed_are_distinct(self):
        """Достижение приёмки без запуска автогейта названо, а самостоятельный проход не несёт отказа.

        Ловит мутацию: отсутствие записи отказа всегда считается успешным
        автогейтом либо строка успеха повторяет чужую причину отказа.
        """
        not_started, _ = self._run([
            self._step("state -> acceptance"),
            self._step("state -> merge_gate", actor="canary")])
        self.assertIn("автогейт не запускался", not_started)
        passed, _ = self._run([
            self._step("state -> acceptance"),
            self._step("state -> merge_gate", actor="autogate")])
        summary = next(line for line in passed.splitlines() if "исход=" in line)
        self.assertNotIn("причина отказа", summary)
        self.assertNotIn("автогейт не запускался", summary)

    def test_ac3_database_records_acceptance_route_and_refusal(self):
        """Три исхода результата клона сохраняют в БД самостоятельную, ручную и отсутствующую приёмку.

        Ловит мутацию: способ приёмки пишется только в печатную сводку,
        теряется на пути в БД или отказ оставляет в строке пустую причину.
        """
        _, auto = self._run([
            self._step("state -> acceptance"),
            self._step("state -> merge_gate", actor="autogate")])
        reason = "нет зелёной приёмочной планки"
        _, manual = self._run(self._manual_steps(reason))
        _, absent = self._run([self._step("state -> in_dev")],
                              kill_note="не сошлась")
        route_keys = [key for key in auto.keys()
                      if auto[key] == "autogate" and manual[key] == "manual"]
        self.assertTrue(route_keys, dict(auto))
        self.assertIn(absent[route_keys[0]], (None, ""))
        reason_keys = [key for key in manual.keys() if manual[key] == reason]
        self.assertTrue(reason_keys, dict(manual))
        self.assertIn(auto[reason_keys[0]], (None, ""))
        self.assertIn(absent[reason_keys[0]], (None, ""))

    def test_ac4_legacy_row_and_legacy_json_remain_usable(self):
        """Старая таблица с прежней строкой мигрирует при обработке прежнего JSON результата.

        Ловит мутацию: миграция забывает старые строки либо пульт требует
        новое JSON-поле от уже выпущенного процесса клона и красит прогон.
        """
        conn = store.db()
        conn.execute("CREATE TABLE canary_runs ("
                     "id INTEGER PRIMARY KEY AUTOINCREMENT, run_stamp TEXT, "
                     "title TEXT, task_id TEXT, steps INTEGER, cost_usd REAL, "
                     "review_iterations INTEGER, escalations INTEGER, "
                     "outcome TEXT, expected_escalation TEXT, "
                     "actual_escalation INTEGER, marker_mismatch INTEGER, "
                     "created_at TEXT, main_sha TEXT, verdict TEXT, "
                     "set_name TEXT, models_summary TEXT)")
        conn.execute("INSERT INTO canary_runs "
                     "(run_stamp, title, task_id, verdict, set_name) "
                     "VALUES (?, ?, ?, ?, ?)",
                     ("old", "old fixture", "01OLD", "green",
                      config.CANARY_DEFAULT_SET))
        conn.commit()
        reason = "старый JSON сохранил отказ"
        _, current = self._run(self._manual_steps(reason))
        old = conn.execute("SELECT * FROM canary_runs WHERE run_stamp='old'").fetchone()
        self.assertEqual(old["task_id"], "01OLD")
        self.assertEqual(old["title"], "old fixture")
        self.assertEqual(current["verdict"], "green")
        self.assertIn(reason, dict(current).values())

    def test_ac5_diagnostics_are_saved_for_normal_manual_pass_only(self):
        """Штатный ручной проход после отказа оставляет диагностику, самостоятельный проход обходится без неё.

        Ловит мутацию: сохранение диагностики привязано только к красному
        вердикту, поэтому зелёный ручной прогон теряет след отказа.
        """
        reason = "нет допуска автогейта"
        manual_output, manual_row = self._run(self._manual_steps(reason))
        self.assertEqual(manual_row["verdict"], "green")
        diagnostic = next((line.split("диагностика: ", 1)[1].strip()
                           for line in manual_output.splitlines()
                           if "диагностика: " in line), None)
        self.assertIsNotNone(diagnostic, manual_output)
        self.assertTrue(Path(diagnostic).is_dir(), manual_output)
        auto_output, _ = self._run([
            self._step("state -> acceptance"),
            self._step("state -> merge_gate", actor="autogate")])
        self.assertNotIn("диагностика:", auto_output)

    def test_ac6_manual_acceptance_keeps_green_pin_input_and_names_reason(self):
        """Ручная приёмка после отказа остаётся зелёной для входа сдвига пина и названа в итоге.

        Ловит мутацию: ручной проход принудительно красится или не попадает
        в выборку зелёных прогонов, хотя прежний штатный исход зелёный.
        """
        reason = "ручной допуск после отказа"
        output, row = self._run(self._manual_steps(reason))
        self.assertEqual(row["verdict"], "green")
        self.assertIn(row["id"], [item["id"] for item in
                                  store.green_canary_runs(store.db())])
        summary = next(line for line in output.splitlines() if "исход=" in line)
        self.assertIn(f"приёмка вручную: {reason}", summary)
        self.assertNotIn("допуск моделей", summary)
