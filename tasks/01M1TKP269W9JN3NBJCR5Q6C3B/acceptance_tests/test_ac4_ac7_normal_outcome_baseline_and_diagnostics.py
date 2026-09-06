"""AC-4/AC-7 (SPEC.md), с учётом ANSWER-1.md (вариант Б — «done» читается
как ФУНКЦИОНАЛЬНЫЙ «штатный» исход канарейки: kill на `merge_gate`/
`verifying`, который `canary._kill_outcome_note` отличает как «штатно»
от «не сошлась»):

AC-4. При штатном исходе БЕЗ расхождения маркера диагностика НЕ
сохраняется — каталог `.artel/canary/<run_stamp>/<task_id>/` не
заводится. Симметрично (ANSWER-1.md, правило 1): диагностика
сохраняется при штатном исходе, если маркер ожидания эскалации
разошёлся с фактом — граница «done без расхождения», а не голое
«done».

AC-7. `canary_baseline` обновляется только при штатном исходе БЕЗ
расхождения маркера; при расхождении — не обновляется, даже если исход
штатный (та же граница, что и AC-4, симметрично).

Оба класса ниже ведут задачу до `merge_gate` БЕЗ единого
`changes_requested` (`extra_review_rounds_default` не выставляется —
дефолт `SmartAgent.__init__` — 0, ревью одобряет с первого раза) и без
эскалации — единственный путь `_drive_task` до конца: `spec_gate` ->
`in_dev` -> `review` (approved) -> `acceptance` -> `merge_gate` ->
`_kill_at_merge_gate` (`_kill_outcome_note` вернёт буквально «штатно»,
не «не сошлась: ...» — в отличие от сценария `test_ac1_ac2_ac3_
diagnostics_on_inconclusive_outcome.py`/`test_ac8_killed_runs_excluded_
from_baseline_and_deviation.py`, использующих rework-гейт для «не
сошлась»). Расхождение маркера здесь — ЕДИНСТВЕННАЯ переменная:
`_sandbox.ESCALATE_TITLE_MARKER` НЕ входит в title ни одного шаблона
этого файла, поэтому фактической эскалации не бывает ни разу; маркер
`<!-- canary-expect-escalation: yes -->` в теле шаблона (когда он есть)
расходится с фактом (нет эскалации) — тот же приём, что и
`tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/test_ac8_escalation_
marker_discrepancy.py`.

Красен до реализации / Зелёный с рождения — см. маркер в докстринге
каждого тестового класса: до этой задачи код диагностики не существует
вовсе (AC-1..3 не реализованы), а бейзлайн сегодня заводится из ПЕРВОГО
прогона шаблона безусловно (`orchestrator/canary.py::_run_one_task`:
`if baseline is None: store.set_canary_baseline(...)`, без всякого
условия на исход/расхождение) — эти два факта делают ожидаемую
краснoту/зелёность разной для разных тестовых методов ниже.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox, extract_run_stamp, extract_task_ids  # noqa: E402

from orchestrator import canary as canary_mod  # noqa: E402
from orchestrator import store  # noqa: E402

TITLE_NORMAL_NO_MARKER = "shtatno-bez-markera-i-bez-bazy"
TITLE_NORMAL_MISMATCH_NO_BASE = "shtatno-s-raskhozhdeniem-bez-bazy"
TITLE_NORMAL_MISMATCH_WITH_BASE = "shtatno-s-raskhozhdeniem-est-baza"


class NormalOutcomeWithoutMismatchTest(CanarySandbox):
    """Штатный kill на `merge_gate`, маркера ожидания эскалации в
    шаблоне нет вовсе (`expected is None` -> `mismatch` всегда `False`
    независимо от факта) — ровно случай «done без расхождения» варианта
    Б ANSWER-1.md."""

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            f"{TITLE_NORMAL_NO_MARKER}.md":
                "Синтетическая тихая правка без маркера ожидания "
                "эскалации — одобряется с первого раза, без эскалаций.",
        })
        self.conn = store.db()

    def _run(self):
        out = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out, out)
        self.assertIn(
            "(штатно)", out,
            f"сценарий сломан: ожидался штатный kill на merge_gate, "
            f"вывод не несёт «(штатно)» — проверка ниже не про тот "
            f"сценарий:\n{out}")
        run_stamp = extract_run_stamp(out)
        task_ids = extract_task_ids(out)
        self.assertEqual(len(task_ids), 1, out)
        return out, task_ids[0], run_stamp

    def test_ac4_diagnostics_not_saved_on_normal_outcome_without_mismatch(self):
        """Диагностика (`.artel/canary/<run_stamp>/<task_id>/`) НЕ
        заводится для штатного kill без расхождения маркера.

        Зелёный с рождения: до этой задачи код сохранения диагностики
        (AC-1..3) не существует вовсе — каталог не заводится ни для
        какого исхода уже сегодня, эта проверка верна тривиально.
        Ловит мутацию: разработчик реализует AC-1..3 БЕЗУСЛОВНО (сохраняет
        диагностику для любого исхода, не только «не сошлась»/
        расхождение) — после такой правки каталог возник бы и здесь,
        `assertFalse(diag_dir.exists())` покраснеет.
        """
        out, task_id, run_stamp = self._run()
        diag_dir = self.root / ".artel" / "canary" / run_stamp / task_id
        self.assertFalse(
            diag_dir.exists(),
            f"диагностика заведена для штатного исхода без расхождения "
            f"маркера вопреки AC-4: {diag_dir}\n{out}")

    def test_ac7_baseline_created_on_normal_outcome_without_mismatch(self):
        """`canary_baseline` заводится (был `None`) для штатного kill без
        расхождения маркера — позитивная половина AC-7.

        Зелёный с рождения: сегодняшний код заводит бейзлайн из ПЕРВОГО
        прогона шаблона безусловно (`if baseline is None: store.
        set_canary_baseline(...)`) — в этом сценарии (штатно, без
        расхождения) бейзлайн и должен завестись, поведение уже верно.
        Ловит мутацию: разработчик, закрывая AC-7 (не заводить бейзлайн
        для «не сошлась»/расхождения), перепутает условие и ПЕРЕСТАНЕТ
        заводить его и для штатного случая тоже (например, использует
        буквальный `t["state"] == "done"`, недостижимый для канарейки
        вообще, см. ANSWER-1.md/markers.py) — `store.canary_baseline`
        останется `None`.
        """
        self.assertIsNone(
            store.canary_baseline(self.conn, TITLE_NORMAL_NO_MARKER))
        self._run()
        self.assertIsNotNone(
            store.canary_baseline(self.conn, TITLE_NORMAL_NO_MARKER),
            "бейзлайн не заведён для штатного исхода без расхождения "
            "маркера вопреки AC-7")


class NormalOutcomeWithMarkerMismatchNoBaselineTest(CanarySandbox):
    """Штатный kill на `merge_gate`, но шаблон несёт
    `<!-- canary-expect-escalation: yes -->`, а фактической эскалации
    НЕ было (title без `ESCALATE_TITLE_MARKER`) — `mismatch=True` при
    штатном исходе: «done» ЕСТЬ, «без расхождения» — НЕТ."""

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            f"{TITLE_NORMAL_MISMATCH_NO_BASE}.md":
                f"{canary_mod.MARK_EXPECT_ESCALATION_YES}\n"
                "Синтетическая тихая правка — маркер ошибочно обещает "
                "эскалацию, которой не будет; одобряется с первого раза.",
        })
        self.conn = store.db()

    def _run(self):
        out = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out, out)
        self.assertIn(
            "(штатно)", out,
            f"сценарий сломан: ожидался штатный kill на merge_gate:\n{out}")
        self.assertIn(
            "РАСХОЖДЕНИЕ", out,
            f"сценарий сломан: ожидалось расхождение маркер/факт "
            f"(marker=yes, факт=no эскалации):\n{out}")
        run_stamp = extract_run_stamp(out)
        task_ids = extract_task_ids(out)
        self.assertEqual(len(task_ids), 1, out)
        return out, task_ids[0], run_stamp

    def test_ac4_diagnostics_saved_on_normal_outcome_with_marker_mismatch(self):
        """Диагностика заводится для штатного kill, ЕСЛИ маркер ожидания
        эскалации разошёлся с фактом — «done» само по себе не
        освобождает от сохранения диагностики (ANSWER-1.md, правило 1).

        Красен до реализации: код сохранения диагностики (AC-1..3) не
        написан вовсе — каталог не существует ни для одного исхода.
        Ловит мутацию: разработчик условием сохранения диагностики берёт
        ТОЛЬКО `outcome != "штатно"` (`_kill_outcome_note`), забывая
        учесть `mismatch` — для этого сценария (штатно + расхождение)
        каталог не завёлся бы, хотя AC-4 требует обратного.
        """
        out, task_id, run_stamp = self._run()
        diag_dir = self.root / ".artel" / "canary" / run_stamp / task_id
        self.assertTrue(
            diag_dir.is_dir(),
            f"диагностика не заведена для штатного исхода С расхождением "
            f"маркера вопреки AC-4/ANSWER-1.md: {diag_dir}\n{out}")

    def test_ac7_baseline_not_created_on_normal_outcome_with_marker_mismatch(self):
        """`canary_baseline` НЕ заводится (остаётся `None`) для штатного
        kill, если маркер ожидания эскалации разошёлся с фактом —
        негативная половина AC-7 («без расхождения» — обязательное
        условие, не факультативное уточнение).

        Красен до реализации: сегодняшний код заводит бейзлайн из
        ПЕРВОГО прогона шаблона безусловно, не глядя на `mismatch` — тот
        же `if baseline is None: store.set_canary_baseline(...)`
        сработал бы и здесь.
        Ловит мутацию: разработчик проверяет для AC-7 только
        `_kill_outcome_note(...) == "штатно"`, забывая про `mismatch` —
        бейзлайн завёлся бы в этом сценарии, хотя AC-7 требует «штатно
        И без расхождения».
        """
        self.assertIsNone(
            store.canary_baseline(self.conn, TITLE_NORMAL_MISMATCH_NO_BASE))
        self._run()
        self.assertIsNone(
            store.canary_baseline(self.conn, TITLE_NORMAL_MISMATCH_NO_BASE),
            "бейзлайн заведён для штатного исхода С расхождением маркера "
            "вопреки AC-7")


class NormalOutcomeWithMarkerMismatchAndPriorBaselineTest(CanarySandbox):
    """Тот же штатный kill + расхождение маркера, но бейзлайн для этого
    шаблона УЖЕ существует (заведён заранее, заведомо маленькие
    значения) — проверяет вторую половину AC-8 применительно к
    расхождению маркера (не только к «не сошлась», уже покрытому
    `test_ac8_killed_runs_excluded_from_baseline_and_deviation.py`):
    расхождение при штатном исходе исключает прогон из СРАВНЕНИЯ с
    бейзлайном ровно так же, как исход «не сошлась»."""

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            f"{TITLE_NORMAL_MISMATCH_WITH_BASE}.md":
                f"{canary_mod.MARK_EXPECT_ESCALATION_YES}\n"
                "Синтетическая тихая правка — маркер ошибочно обещает "
                "эскалацию, которой не будет; одобряется с первого раза.",
        })
        self.conn = store.db()
        store.set_canary_baseline(self.conn, TITLE_NORMAL_MISMATCH_WITH_BASE,
                                  steps=1, cost_usd=0.01,
                                  review_iterations=0)
        self.baseline_before = dict(
            store.canary_baseline(self.conn, TITLE_NORMAL_MISMATCH_WITH_BASE))
        self.alerts_before_ids = {a["id"] for a in store.open_alerts(self.conn)}

    def test_ac8_normal_outcome_with_marker_mismatch_does_not_raise_deviation_alert(self):
        """Штатный исход С расхождением маркера не сравнивается с уже
        существующим бейзлайном, несмотря на заведомо огромное
        отклонение реальных метрик (много шагов, `cost_usd=0`) от
        заведомо маленького бейзлайна (`steps=1, cost_usd=0.01`) —
        ни нового алерта отклонения, ни строки «[ВНИМАНИЕ», ни правки
        самого бейзлайна.

        Красен до реализации: `_run_one_task` сегодня сравнивает метрики
        с бейзлайном БЕЗУСЛОВНО (`else: warnings = _task_deviation_
        warnings(...)`), не глядя на `mismatch` — алерт `kind=threshold,
        source=canary` появится, и в выводе — «[ВНИМАНИЕ».
        Ловит мутацию: разработчик закрывает AC-8 только для исхода «не
        сошлась» (`_kill_outcome_note(...) != "штатно"`), забывая про
        `mismatch` при штатном исходе — сравнение здесь по-прежнему
        сработает.
        """
        out = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out, out)
        self.assertIn("(штатно)", out, out)
        self.assertIn("РАСХОЖДЕНИЕ", out, out)

        alerts_after = store.open_alerts(self.conn)
        new_alerts = [a for a in alerts_after
                     if a["id"] not in self.alerts_before_ids]
        canary_deviation_alerts = [
            a for a in new_alerts
            if a["source"] == "canary"
            and TITLE_NORMAL_MISMATCH_WITH_BASE in a["message"]]
        self.assertEqual(
            canary_deviation_alerts, [],
            f"штатный исход с расхождением маркера завёл алерт "
            f"отклонения от бейзлайна вопреки AC-8: "
            f"{canary_deviation_alerts}")
        self.assertNotIn(
            "[ВНИМАНИЕ", out,
            f"вывод команды несёт предупреждение об отклонении для "
            f"штатного исхода с расхождением маркера:\n{out}")

        baseline_after = dict(
            store.canary_baseline(self.conn, TITLE_NORMAL_MISMATCH_WITH_BASE))
        self.assertEqual(
            baseline_after["steps"], self.baseline_before["steps"],
            f"штатный исход с расхождением маркера переписал бейзлайн "
            f"по шагам: было {self.baseline_before}, стало "
            f"{baseline_after}")


if __name__ == "__main__":
    unittest.main()
