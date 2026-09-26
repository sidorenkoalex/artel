"""Приёмочные тесты 01M3EM7A84KE0W690M02VWPNXF — AC-4: метки требования 1
не подводят задачу под стоп-кран серии меток конфликта подтяжки
(`auto._pull_conflict_marker_streak`/`_pre_advance_step`), и файл
`orchestrator/auto.py` задачей не изменён.

Красен до реализации: сценарий «конфликт на гейте мержа -> возврат -> шаг
developer -> повторная подтяжка без конфликта» сегодня до повторной
подтяжки не доходит — без метки для `merge_gate` рубеж переделки не держит
предварительный advance, тот повторяет подтяжку РАНЬШЕ шага developer (шаг
и не отдаётся), конфликт всё ещё на месте, задача уходит в `escalated`, и
записи `state -> verifying` в журнале не появляется: первый тест падает на
ней. Второй тест файла (`orchestrator/auto.py` не изменён) зелёный с
рождения — это лок раздела «Не входит» SPEC, а не ожидание кода: пустой
дифф файла проверен на диске в момент написания планки.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (PullConflictSandbox, REPO_ROOT,  # noqa: E402
                      ROLE_STEP_ACTION, STREAK_STOP_PHRASE)
from orchestrator import config  # noqa: E402

AUTO_REL = "orchestrator/auto.py"


class ResolvedConflictPassesWithoutTheStreakStopTest(PullConflictSandbox):
    """AC-4: серия меток остаётся единичной и гасится переходом в
    следующее состояние — сценарий «конфликт подтяжки на гейте мержа ->
    возврат из эскалации -> шаг developer -> повторная подтяжка без
    конфликта» проходит цикл без остановки стоп-краном."""

    def test_ac4_developer_step_then_clean_pull_is_not_stopped_by_the_streak(self):
        """Шаг developer разрешает конфликт (следующая подтяжка чистая) —
        `auto` обязан продвинуть задачу дальше `in_dev` и не остановиться
        стоп-краном серии меток; на весь сценарий приходится РОВНО одна
        запись метки (один конфликт — одна метка), поэтому серия и не
        может дорасти до порога стоп-крана.

        Ловит мутацию: метка для трёх состояний записана вторым блоком
        `store.journal` рядом с прежним `if state == "in_dev"` (старая
        ветка не убрана) — один конфликт оставляет ДВЕ записи метки,
        серия сразу достигает порога, и первый же последующий
        предварительный advance, упёршийся в конфликт, останавливает цикл
        именованной причиной вместо того, чтобы дать роли шаг:
        `assertEqual(len(marker_rows), 1)` это поймает, а `assertNotIn`
        по тексту стоп-крана и `assertIn` по `state -> verifying` — его
        последствие в этом сценарии.
        """
        self.write_plan_ready()
        self.write_acceptance_plank()

        self.escalate_via_merge_gate()
        self.assertEqual(self.state(), "escalated")
        self.approve()
        self.assertEqual(self.state(), "in_dev")

        # Шаг developer: конфликт разрешён, подтяжка после него чистая.
        self.agent.script = [self.clear_conflict]
        out = self.auto()

        self.assertNotIn(
            STREAK_STOP_PHRASE, out,
            "цикл остановлен стоп-краном серии меток конфликта подтяжки, "
            "хотя повторная подтяжка прошла без конфликта")
        rows = self.journal_rows()
        actions = [r["action"] for r in rows]
        self.assertTrue(
            any(r["action"] == ROLE_STEP_ACTION and r["actor"] == "developer"
                for r in rows),
            "шаг developer не был отдан — сценарий AC-4 не воспроизведён")
        self.assertIn(
            "state -> verifying", actions,
            "задача не продвинулась дальше in_dev по чистой повторной "
            "подтяжке — цикл остановился раньше")
        self.assertEqual(
            len(self.marker_rows()), 1,
            "на один конфликт подтяжки пришлось не одно вхождение метки — "
            "серия стоп-крана растёт без второго конфликта")


class AutoPyIsNotTouchedByThisTaskTest(unittest.TestCase):
    """AC-4, вторая половина: `orchestrator/auto.py` — «Не входит» SPEC
    (стоп-кран и перечень меток рубежа переделки не правятся), требование
    4 выполняется без единой правки этого файла."""

    def test_ac4_auto_py_has_no_diff_since_the_last_main_merge(self):
        """Дифф `orchestrator/auto.py` между последним смерженным в ветку
        задачи `main` и текущим `HEAD` пуст.

        Ловит мутацию: разработчик добивается сценария AC-4 правкой
        стоп-крана (`_pull_conflict_marker_streak`, порог `streak >= 2`)
        или перечня `_ROLE_STEP_REQUIRED_MARKERS` вместо правки условия
        записи метки в `orchestrator/pull.py` — дифф файла перестанет
        быть пустым, и `assertEqual` ниже это поймает.
        """
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", config.MAIN_BRANCH],
            cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(merge_base.returncode, 0, merge_base.stderr)
        base_sha = merge_base.stdout.strip()

        diff = subprocess.run(
            ["git", "diff", "--stat", base_sha, "HEAD", "--", AUTO_REL],
            cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(diff.returncode, 0, diff.stderr)
        self.assertEqual(
            diff.stdout.strip(), "",
            f"{AUTO_REL} изменён относительно последнего слияния "
            f"{config.MAIN_BRANCH}: {diff.stdout}")


if __name__ == "__main__":
    unittest.main()
