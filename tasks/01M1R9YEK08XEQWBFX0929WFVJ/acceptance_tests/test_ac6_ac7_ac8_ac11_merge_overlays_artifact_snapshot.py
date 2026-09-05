"""Красен до реализации: `orchestrator/fsm_merge_gate.py::_cmd_approve_
merge_gate` мержит кодовую ветку задачи в main ОБЫЧНЫМ `git merge
--no-ff branch` (см. код: `merge_res = gitcmd.in_repo(scratch, "merge",
"--no-ff", branch, ...)`) — что бы кодовая ветка ни несла в
`tasks/<id>/` (легаси-копия), это и попадает в main как есть. SPEC
«Критерии приёмки» AC-6/AC-7/AC-8/AC-11 требуют, чтобы попавшее в main
содержимое `tasks/<id>/` было снимком АРТЕФАКТНОЙ ветки на момент
`approve`, а расхождение с легаси-копией кодовой ветки — только
предупреждение в журнале, не отказ перехода.

Сценарий обоих тестов один и тот же (заводится в `setUp` каждого через
общий метод `_seed_divergence`): кодовая ветка несёт `tasks/<id>/
PLAN.md` с одним текстом (легаси), артефактная ветка — с другим. `git
merge` без правки принёс бы в main текст кодовой ветки; тест ловит это
через `origin_main_file_text`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import MergeGateSnapshotSandbox  # noqa: E402

CODE_BRANCH_LEGACY = "КОД-ВЕТКА-УСТАРЕВШИЙ-ТЕКСТ\n"
ARTIFACT_BRANCH_CURRENT = "АРТЕФАКТНАЯ-ВЕТКА-АКТУАЛЬНЫЙ-ТЕКСТ\n"


class MergeOverlaySandbox(MergeGateSnapshotSandbox):

    def _seed_divergence(self) -> None:
        self.commit_legacy_on_code_branch(
            {f"tasks/{self.TASK}/PLAN.md": CODE_BRANCH_LEGACY})
        self.commit_artifact(
            {f"tasks/{self.TASK}/PLAN.md": ARTIFACT_BRANCH_CURRENT})


class Ac6ArtifactSnapshotLandsInMainTest(MergeOverlaySandbox):

    def test_ac6_main_content_after_done_is_artifact_branch_snapshot(self):
        """После `merge_gate -> done` содержимое `tasks/<id>/PLAN.md` в
        main обязано быть снимком АРТЕФАКТНОЙ ветки на момент `approve`
        (SPEC AC-6), а не тем, что принёс бы обычный `git merge` из
        кодовой ветки.

        Ловит мутацию: `merge_gate` продолжает обычный `git merge --no-ff
        branch` без последующего наложения снимка артефактной ветки —
        `origin_main_file_text` вернёт легаси-текст кодовой ветки, и
        `assertEqual` здесь покраснеет.
        """
        self._seed_divergence()

        outcome = self.approve_merge_gate()

        self.assertEqual(outcome, ("done",))
        self.assertEqual(self.state(), "done")
        main_text = self.origin_main_file_text(f"tasks/{self.TASK}/PLAN.md")
        self.assertEqual(
            main_text, ARTIFACT_BRANCH_CURRENT,
            f"main обязан нести снимок артефактной ветки на момент "
            f"approve; получено: {main_text!r}")


class Ac7LegacyCodeBranchCopyIsIgnoredTest(MergeOverlaySandbox):

    def test_ac7_legacy_code_branch_copy_does_not_affect_main(self):
        """Легаси-копия `tasks/<id>/` кодовой ветки (если она есть) не
        имеет права повлиять на итоговое содержимое `tasks/<id>/` в main
        (SPEC AC-7) — main после `done` не несёт её текста.

        Ловит мутацию: наложение снимка артефактной ветки применяется не
        ко ВСЕМ файлам `tasks/<id>/`, оставляя легаси-файл кодовой ветки
        нетронутым после обычного merge — `assertNotEqual` здесь
        покраснеет, увидев легаси-текст в main.
        """
        self._seed_divergence()

        outcome = self.approve_merge_gate()

        self.assertEqual(outcome, ("done",))
        main_text = self.origin_main_file_text(f"tasks/{self.TASK}/PLAN.md")
        self.assertNotEqual(
            main_text, CODE_BRANCH_LEGACY,
            "легаси-копия tasks/<id>/ кодовой ветки не имеет права "
            "повлиять на итоговое содержимое main")


class Ac11DivergenceTestPerSpec(MergeOverlaySandbox):

    def test_ac11_divergent_copies_at_merge_time_resolve_to_artifact_branch(self):
        """Тест, дословно названный SPEC AC-11: расхождение копии
        `tasks/<id>` кодовой ветки и артефактной ветки на момент merge —
        после merge содержимое `tasks/<id>` в main соответствует
        АРТЕФАКТНОЙ ветке, не кодовой.

        Ловит мутацию: та же, что и AC-6/AC-7 выше — этот тест
        воспроизводит сценарий SPEC буквально одним прогоном, где
        `main_text` обязан совпасть с артефактным текстом и НЕ совпасть
        с легаси-текстом одновременно.
        """
        self._seed_divergence()

        outcome = self.approve_merge_gate()

        self.assertEqual(outcome, ("done",))
        main_text = self.origin_main_file_text(f"tasks/{self.TASK}/PLAN.md")
        self.assertEqual(main_text, ARTIFACT_BRANCH_CURRENT)
        self.assertNotEqual(main_text, CODE_BRANCH_LEGACY)


class Ac8DivergenceWarnsWithoutFailingTest(MergeOverlaySandbox):

    def test_ac8_divergence_between_branches_is_journaled_as_warning_not_failure(self):
        """Расхождение между легаси-копией кодовой ветки и снимком
        артефактной ветки на момент merge журналируется предупреждением
        (SPEC AC-8) — переход `merge_gate -> done` НЕ отказывает и НЕ
        эскалирует по этой причине: задача обязана дойти до `done`
        успешно, и журнал обязан нести упоминание расхождения.

        Ловит мутацию: расхождение либо отказывает переходу (например,
        `sys.exit`/эскалация вместо тихого наложения снимка) — `outcome`
        и `self.state()` здесь это поймают; либо расхождение не
        журналируется вовсе — `assertTrue` по журналу покраснеет.
        """
        self._seed_divergence()

        outcome = self.approve_merge_gate()

        self.assertEqual(
            outcome, ("done",),
            "расхождение копий tasks/<id>/ не имеет права отказать "
            "переходу merge_gate -> done")
        self.assertEqual(self.state(), "done")
        combined = "\n".join(self.journal_details()).lower()
        self.assertIn(
            "расхожд", combined,
            f"расхождение легаси-копии и артефактного снимка обязано "
            f"быть журналировано предупреждением (AC-8); журнал не "
            f"несёт упоминания расхождения: {combined}")


if __name__ == "__main__":
    unittest.main()
