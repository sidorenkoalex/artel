"""AC-23 — канарейка проходит аудит SPEC и автогейт SPEC после него; при третьем fail задача снимается как неоконченная, исход прогона красный.

Вождение задачи — настоящее `canary._drive_task` (тот же цикл `auto`, что
в прогоне канарейки, и тот же автогейт `canary._pass_spec_gate`); шаги ролей
— штатный `runner.cmd_run` с подменённым запуском агента в песочнице
долгоживущего файла задачи (`SpecAuditSandbox`, настоящий git, ссылка
документов, автокоммит пульта): подменённый агент по состоянию задачи
пишет SPEC (аналитик, каждый визит — новая метка) или `SPEC-AUDIT.md` с
очередным вердиктом сценария (аудитор, `spec_sha` — sha содержимого SPEC
в ссылке); шаг test_author (после гейта SPEC) прерывает вождение — дальше
гейта SPEC предмет критерия не идёт. Исход прогона — вердикт строки
прогона тем же расчётом, что `canary._run_task_in_ephemeral_clone`:
`canary._kill_outcome_note` -> штатный ли исход -> `canary._run_verdict`.

Провалидирован временным стабом реализации (`plank-run`): оба метода
зелёные; мутация «`_pass_spec_gate` не смотрит вердикт аудита» красила
сценарий третьего fail; стаб удалён, код не тронут.

Группа: разовый
Красен до реализации: состояния spec_audit нет — задача с ТЗ уходит из spec_writing сразу на гейт SPEC, канарейка проходит его без аудита (записи state -> spec_audit нет), а шага spec_auditor и вердикта fail, снимающего задачу, не существует.
"""
import contextlib
import io
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT  # noqa: E402

if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from orchestrator import canary, catalog, runner, store  # noqa: E402
from tests.sandbox import FakeProc, capture_new_task_id, is_claude_call  # noqa: E402
from tests.test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow import (  # noqa: E402
    AUDIT, AUDIT_FILE, AUDITOR, FLAG, RESULT, SpecAuditSandbox, word)


class StopDrive(BaseException):
    """Вождение дошло до шага, который предмету критерия не нужен."""


class CanaryAuditTest(SpecAuditSandbox):

    def canary_task(self) -> str:
        path = self.scratch / f"tz-{word(self.rng)}.txt"
        path.write_text(f"Канареечное ТЗ {word(self.rng)}.\n", encoding="utf-8")
        _, task = capture_new_task_id(lambda: catalog.cmd_new(
            f"Канарейка {word(self.rng)}", str(path), canary=True))
        return task

    def drive(self, task: str, verdicts: list) -> str:
        """`canary._drive_task` до конца либо до шага вне аналитика/аудитора;
        возврат — где вождение прервано (пусто — `_drive_task` вернулся сам)."""
        queue = list(verdicts)

        def spawn(cmd, *args, **kwargs):
            if not is_claude_call(cmd):
                return subprocess.Popen(cmd, *args, **kwargs)
            state = store.get_task(store.db(), task)["state"]
            if state == "spec_writing":
                files = {"SPEC.md": self.spec(task)}
            elif state == AUDIT:
                if not queue:
                    raise StopDrive("вердикты сценария кончились")
                files = {AUDIT_FILE: self.audit_text(
                    task, queue.pop(0), self.ref_file_sha(task),
                    deviation=self.deviation())}
            else:
                raise StopDrive(state)
            for name, text in files.items():
                path = self.docs_dir(task) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            return FakeProc([RESULT])

        out = io.StringIO()
        stopped = ""
        with mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                canary._drive_task(store.db(), task)
            except StopDrive as exc:
                stopped = str(exc)
        self.last_output = out.getvalue()
        return stopped

    def context(self, task: str, stopped: str) -> str:
        return self.msg(f"прервано: {stopped!r}\nвывод:\n{self.last_output[-4000:]}\n"
                        f"журнал:\n{self.journal(task)}")

    def test_ac23_canary_passes_audit_then_spec_gate_on_pass_or_concerns(self):
        """Прогон канарейки с задачей с ТЗ проходит spec_audit и автогейт SPEC после него при pass и concerns.

        Сценарий: на каждый из вердиктов `pass`/`concerns` (порядок
        случаен) — канареечная задача с ТЗ; `canary._drive_task`: шаг
        аналитика, вход в `spec_audit`, шаг аудитора с вердиктом, гейт
        SPEC, затем вождение доходит до шага test_author. В журнале вход в
        `spec_audit` раньше входа в `spec_gate`, переход с гейта в
        `tests_writing` сделан актором канарейки.

        Ловит мутацию: канарейка ведёт задачу мимо аудита (цикл не знает
        агентского состояния `spec_audit` и останавливается/снимает задачу);
        автогейт канарейки отвергает и `concerns`.
        """
        verdicts = ["pass", "concerns"]
        self.rng.shuffle(verdicts)
        for verdict in verdicts:
            with self.subTest(вердикт=verdict):
                task = self.canary_task()
                stopped = self.drive(task, [verdict])
                context = self.context(task, stopped)
                entries = self.state_entries(task)
                self.assertEqual(stopped, "tests_writing", context)
                self.assertIn(AUDIT, entries, context)
                self.assertIn("spec_gate", entries, context)
                self.assertLess(entries.index(AUDIT), entries.index("spec_gate"),
                                context)
                gate_pass = [r for r in self.steps(task)
                             if r["action"] == "state -> tests_writing"]
                self.assertEqual(len(gate_pass), 1, context)
                self.assertEqual(gate_pass[0]["actor"], canary.CANARY_MARK_ACTOR,
                                 context)

    def test_ac23_canary_third_fail_kills_task_red_without_accepting_fail(self):
        """Третий fail аудита на канарейке: автогейт SPEC не проходит, задача снята, исход прогона красный, принятия fail нет.

        Сценарий: канареечная задача с ТЗ, аудитор трижды отдаёт `fail`
        (аналитик каждый раз переписывает SPEC). После третьего `fail`
        задача на `spec_gate` — `canary._drive_task` снимает её: состояние
        `killed`, перехода в `tests_writing`/`in_dev` нет; исход по
        `canary._kill_outcome_note` не штатный, `canary._run_verdict` —
        `red`; в журнале задачи есть запись с вердиктом `fail` (не шага
        аудитора), записи о принятии `fail` (флаг `--accept-audit-fail`,
        «принят… fail») нет.

        Ловит мутацию: `_pass_spec_gate` не смотрит вердикт аудита —
        канарейка сама проводит `fail` через гейт в `tests_writing`;
        задача снята путём «штатно» — прогон зелёный; снятие не
        журналирует вердикт.
        """
        task = self.canary_task()
        stopped = self.drive(task, ["fail", "fail", "fail"])
        context = self.context(task, stopped)
        self.assertEqual(stopped, "", context)
        self.assertEqual(self.state(task), "killed", context)
        entries = self.state_entries(task)
        self.assertEqual(entries.count(AUDIT), 3, context)
        self.assertNotIn("tests_writing", entries, context)
        self.assertNotIn("in_dev", entries, context)
        steps = self.steps(task)
        note = canary._kill_outcome_note(store.db(), task, steps)
        normal = note in ("штатно", "поделена")
        verdict = canary._run_verdict(normal, False, canary._ceiling_exhausted(steps))
        self.assertEqual(verdict, "red", self.msg(f"исход: {note}\n{context}"))
        lines = [f"{r['action']} | {r['detail'] or ''}" for r in steps
                 if r["actor"] != AUDITOR]
        self.assertTrue(any(re.search(r"\bfail\b", line) for line in lines), context)
        for line in lines:
            self.assertNotIn(FLAG, line, context)
            self.assertIsNone(re.search(r"принят\w*[^|]*\bfail\b", line, re.I),
                              context)


if __name__ == "__main__":
    unittest.main()
