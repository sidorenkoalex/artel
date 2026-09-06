"""AC-7/AC-8 (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0), формулировка по ANSWER-1
(tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/ANSWER-1.md, вариант A): шаг наложения
снимка артефактной ветки поверх merge (`orchestrator/fsm_merge_gate.py`)
прогоняет guard на каталог `tasks/<id>/` в scratch-репозитории ДО `git
push` в main (AC-7); красный guard отказывает переходу именованной
причиной, задача остаётся на `merge_gate` без эскалации, `git push` в
main не выполняется, main не изменён (AC-8).

Посторонний файл сценария ниже — `.md`-копия вне белого списка AC-1
(`_head_map.md`, класс инцидента 06.09), не файл произвольного
расширения: по ANSWER-1 белый список AC-1 действует только для `.md`
первого уровня `tasks/<id>/`, вложения других расширений (например,
`.log`, использованный первым заходом этой планки до эскалации AC-9)
проходят молча и не годятся для проверки отказа гейта.

`_overlay_artifact_snapshot` (`orchestrator/fsm_merge_gate.py`)
материализует `tasks/<id>/` scratch-репозитория ИЗ ГОЛОВЫ АРТЕФАКТНОЙ
ветки, поверх результата обычного `git merge --no-ff branch` — не из
легаси-копии кодовой ветки задачи. AC-7 проверяется сценарием, где
ИМЕННО артефактная ветка несёт посторонний файл, а легаси-копия кодовой
ветки (если она вообще есть) чиста: это отличает «guard проверяет
СНИМОК АРТЕФАКТНОЙ ветки в scratch, ПОСЛЕ наложения» от гипотетической
реализации, ошибочно прогоняющей guard РАНЬШЕ наложения (на исходном
результате merge, где постороннего файла ещё нет).

Красен до реализации: `_cmd_approve_merge_gate` сегодня не зовёт guard вовсе, поэтому оба теста наблюдают продвинувшийся `origin_main_sha()`/успешный `("done",)` там, где ожидается `SystemExit`.

Подробности: `orchestrator/fsm_merge_gate.py::
_cmd_approve_merge_gate` сегодня не зовёт guard вовсе — `_publish_merge_
artifacts`/`_push_merged_main` идут безусловно после `_perform_carpentry_
merge`, посторонний файл артефактной ветки беспрепятственно доезжает до
`refs/heads/main` origin. Оба теста красные по факту продвижения
`origin_main_sha()`/успешного `("done",)` там, где ожидается отказ
`SystemExit`.

Провалидировано стабом (решение Оператора 03.09): временная вставка
`sys.exit(...)` в `_publish_merge_artifacts` (`orchestrator/
fsm_merge_gate.py`) при обнаружении файла `tasks/<id>/`, не входящего в
проверочный набор допустимых имён (тот же перечень AC-1), ДО вызова
`_push_merged_main` — с журналированием именованной причины — зеленила
оба теста ниже. Стаб убран, репозиторий не тронут.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ArtelSelfTargetSandbox  # noqa: E402

from orchestrator import artifact_branch, fsm_merge_gate, store  # noqa: E402

TASK = "01MERGEGATEGUARDBEFOREPUSH1"
STRAY_NAME = "_head_map.md"


class Ac7GuardChecksTheOverlaidArtifactSnapshotTest(ArtelSelfTargetSandbox):
    """AC-7: guard прогоняется на `tasks/<id>/` СНИМКА АРТЕФАКТНОЙ ветки
    в scratch, а не на легаси-копии кодовой ветки."""

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        # Легаси-копия tasks/<id>/ на КОДОВОЙ ветке — ЧИСТАЯ (только
        # разрешённый PLAN.md); если бы guard проверял её, а не
        # артефактную ветку, отказа не было бы вовсе.
        self.make_task_branch_in_root(
            self.branch, f"tasks/{TASK}/PLAN.md", "легаси-план\n",
            f"{TASK}: легаси-копия PLAN.md")
        self.insert_task(TASK, self.branch, "merge_gate")
        # Артефактная ветка — источник наложения (`_overlay_artifact_
        # snapshot`) — несёт тот же PLAN.md И посторонний файл.
        artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/PLAN.md": "план\n",
                  f"tasks/{TASK}/{STRAY_NAME}": "мусор\n"},
            f"{TASK}: план + мусор")
        self.green_ci()

    def approve(self):
        # SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-5..AC-7: путь "fresh" без
        # `confirmed_ci_note` возвращает ("wait", branch) сам, не опрашивая
        # CI — опрос переехал в `_wait_for_branch_ci_green` вызывающего
        # цикла. Тело вызывается напрямую (см. `tests/
        # test_fsm_merge_gate_done_snapshot.py`), поэтому `confirmed_ci_
        # note` передаём явно, как реальный внешний цикл подставил бы сюда
        # сам после зелёного CI замоканного `green_ci()`.
        t = store.get_task(store.db(), TASK)
        return fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

    def test_ac7_stray_file_only_in_the_artifact_branch_still_blocks_the_merge(self):
        """Кодовая ветка (легаси-копия `tasks/<id>/`) чиста, посторонний
        файл есть ТОЛЬКО в артефактной ветке — merge всё равно отказывает.

        Ловит мутацию: guard прогоняется на результате `git merge --no-ff`
        ДО наложения снимка артефактной ветки (`_overlay_artifact_
        snapshot`) вместо ПОСЛЕ — тогда на момент проверки `tasks/<id>/`
        ещё несёт только чистую легаси-копию, посторонний файл не виден,
        и merge пройдёт до main беспрепятственно.
        """
        before_origin_main = self.origin_main_sha()

        with self.assertRaises(SystemExit):
            self.approve()

        self.assertEqual(
            self.origin_main_sha(), before_origin_main,
            "main артели не имеет права продвинуться — guard обязан был "
            "отказать ДО git push, увидев постороннее в снимке "
            "артефактной ветки")


class Ac8RefusalMechanicsTest(ArtelSelfTargetSandbox):
    """AC-8: именованная причина, задача остаётся на `merge_gate` без
    эскалации, push не выполнен, main не изменён, отказ журналируется."""

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-y"
        self.make_task_branch_in_root(
            self.branch, "feature.txt", "код фичи\n", f"{TASK}: код фичи")
        self.insert_task(TASK, self.branch, "merge_gate")
        artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/{STRAY_NAME}": "мусор\n"},
            f"{TASK}: только мусор")
        self.green_ci()

    def approve(self):
        t = store.get_task(store.db(), TASK)
        return fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

    def journal_blob(self) -> str:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (TASK,)).fetchall()
        return "\n".join(f"{r['action']} | {r['detail']}" for r in rows)

    def test_ac8_named_refusal_no_escalation_no_push_journaled(self):
        """Посторонний файл артефактной ветки — `SystemExit` с
        распознаваемой причиной, задача остаётся `merge_gate` (не
        `escalated`, не `done`), `refs/heads/main` origin не продвинут,
        журнал несёт новую запись об отказе.

        Ловит мутацию: отказ реализован как эскалация задачи
        (`store.set_state(..., "escalated", ...)`) вместо отказа на месте
        — AC-8 прямо требует «без эскалации»; `assertEqual(state,
        "merge_gate")` ниже поймает и эскалацию, и ошибочный `"done"`.
        """
        before_origin_main = self.origin_main_sha()
        before_journal_len = len(self.journal_blob())

        with self.assertRaises(SystemExit) as exit_:
            self.approve()

        message = str(exit_.exception)
        self.assertTrue(
            STRAY_NAME in message or "guard" in message.lower()
            or "постор" in message.lower(),
            f"причина отказа не называет постороннее/guard: {message!r}")

        row = store.db().execute(
            "SELECT state FROM tasks WHERE id=?", (TASK,)).fetchone()
        self.assertEqual(row["state"], "merge_gate")

        self.assertEqual(self.origin_main_sha(), before_origin_main)

        journal_after = self.journal_blob()
        self.assertGreater(
            len(journal_after), before_journal_len,
            "отказ обязан журналироваться тем же классом записи, что "
            "прочие отказы merge_gate (CI красный, конфликт merge, push "
            "FAILED)")


if __name__ == "__main__":
    unittest.main()
