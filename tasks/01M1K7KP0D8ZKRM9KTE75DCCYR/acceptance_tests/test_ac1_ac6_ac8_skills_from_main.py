"""AC-1, AC-6, AC-8 (tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/SPEC.md): скилы роли
(`skills/*.md`, состав из `roles.yaml`), включаемые в промпт запуска,
читаются ветко-корректным чтением через git с головы ветки `main` пульта,
а не с диска рабочей копии `config.ROOT` — и journal шага несёт
sha256-fingerprint фактически прочитанного (main-версии).

Красен до реализации: `orchestrator/runner.py::_cmd_run` (строки ~220-226
на момент написания) читает скилы буквальным `(config.ROOT / "skills" /
f"{s}.md").read_text(...)` — содержимым ДИСКА текущего чекаута `config.
ROOT`, не через `gitcmd.show(config.MAIN_BRANCH, ...)`; никакого
sha256-fingerprint скила при этом в журнал не пишется вовсе (проверено
прогоном стаб-сценария AC-1/AC-8 против сегодняшнего кода: раздел
«Красный тест до реализации» ниже).

Настоящий git (`_sandbox.TaskSandbox`), не заглушка `gitcmd.git`:
различие «диск/main» и «main на момент отведения ветки/main сейчас»
принципиально невоспроизводимо без настоящего репозитория (тот же довод,
что у `tasks/T031/acceptance_tests/test_branch_correct_reads.py::
RealGitBranchTest`).
"""
import hashlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import TaskSandbox, skill_marker  # noqa: E402
from orchestrator import config  # noqa: E402


class SkillReadFromMainTest(TaskSandbox):

    def test_ac1_skill_uncommitted_disk_edit_is_ignored(self):
        """Скил на диске `config.ROOT` правится БЕЗ коммита (та же ветка,
        `main`, остаётся чекаученной) — промпт роли обязан нести
        последнюю ЗАКОММИЧЕННУЮ в `main` версию скила, не незакоммиченную
        правку диска.

        Ловит мутацию: если реализация читает `config.ROOT / "skills" /
        f"{s}.md"` через `.read_text()` (диск текущего чекаута) вместо
        `gitcmd.show(config.MAIN_BRANCH, f"skills/{s}.md")`, промпт
        унесёт незакоммиченную правку — тест увидит маркер
        «НЕЗАКОММИЧЕНО» вместо «V1» и покраснеет.
        """
        (self.root / "skills" / "test-authoring.md").write_text(
            skill_marker("test-authoring", "НЕЗАКОММИЧЕНО"), encoding="utf-8")

        _out, popen = self.run_role("tests_writing")
        prompt = self.prompt_text_of(popen)

        self.assertIn(
            "МАРКЕР-СКИЛА-TEST-AUTHORING-V1", prompt,
            "промпт обязан нести последнюю ЗАКОММИЧЕННУЮ в main версию "
            "скила (SPEC AC-1)")
        self.assertNotIn(
            "НЕЗАКОММИЧЕНО", prompt,
            "промпт не должен нести незакоммиченную правку диска — скил "
            "читается через git, а не через диск текущего чекаута "
            "(SPEC AC-1)")

    def test_ac6_skill_changed_in_main_after_branch_cut_appears_in_prompt(self):
        """Ветка задачи отведена от `main`, когда скил был версии V1;
        ПОСЛЕ отведения ветки `main` продвинулся до V2 (коммит сделан
        через отдельный linked worktree — рабочее дерево `config.ROOT`
        при этом стоит на ветке-«обманке», замороженной на V1, имитируя
        отставшую рабочую копию из «Контекста» SPEC). Промпт роли,
        стартующей ПОСЛЕ этого, обязан нести V2, а не версию на момент
        отведения ветки.

        Ловит мутацию: чтение с диска текущего чекаута `config.ROOT`
        (стоит на V1) или кэширование скила на момент создания задачи
        дали бы V1 в промпте; только живое чтение `git show main:...` в
        момент сборки промпта отдаёт V2.
        """
        self.git("branch", "decoy-stale-checkout")
        self.checkout("decoy-stale-checkout")
        self.assertEqual(
            self.git("rev-parse", "--abbrev-ref", "HEAD").strip(),
            "decoy-stale-checkout",
            "подготовка теста: config.ROOT обязан стоять НЕ на main")

        self.advance_branch_without_checkout(
            config.MAIN_BRANCH, "skills/test-authoring.md",
            skill_marker("test-authoring", "V2"),
            "main: скил test-authoring -> V2")

        _out, popen = self.run_role("tests_writing")
        prompt = self.prompt_text_of(popen)

        self.assertIn(
            "МАРКЕР-СКИЛА-TEST-AUTHORING-V2", prompt,
            "промпт обязан нести версию скила, ДЕЙСТВУЮЩУЮ в main сейчас "
            "(SPEC AC-6), а не версию на момент отведения ветки задачи")
        self.assertNotIn(
            "МАРКЕР-СКИЛА-TEST-AUTHORING-V1", prompt,
            "старая (на момент отведения ветки) версия скила не должна "
            "оставаться в промпте после того, как main продвинулся "
            "(SPEC AC-6)")


class SkillFingerprintJournalTest(TaskSandbox):

    def test_ac8_skill_fingerprint_in_journal_matches_main_committed_content(self):
        """Скил на диске `config.ROOT` правится БЕЗ коммита (как в AC-1) —
        журнал шага обязан нести sha256 фактически прочитанной
        ЗАКОММИЧЕННОЙ в main версии скила, не sha256 незакоммиченной
        правки диска и не отсутствие фингерпринта вовсе.

        Ловит мутацию: сегодня (стаб-прогон против текущего кода) в
        журнале шага нет НИ ОДНОЙ записи с `sha256=` вовсе — скилы не
        журналируются как компонент брифа. Если реализация журналирует
        sha256 содержимого ДИСКА (или незакоммиченной правки) вместо
        содержимого, реально прочитанного из main, ожидаемый hash
        главной (main) версии не встретится в журнале.
        """
        (self.root / "skills" / "test-authoring.md").write_text(
            skill_marker("test-authoring", "НЕЗАКОММИЧЕНО"), encoding="utf-8")
        committed_main_content = skill_marker("test-authoring", "V1")
        expected_sha = hashlib.sha256(
            committed_main_content.encode("utf-8")).hexdigest()
        uncommitted_sha = hashlib.sha256(
            skill_marker("test-authoring", "НЕЗАКОММИЧЕНО")
            .encode("utf-8")).hexdigest()

        self.run_role("tests_writing")
        journal = self.journal_all()

        self.assertTrue(
            any(f"sha256={expected_sha}" in j for j in journal),
            "журнал шага обязан нести sha256 фактически прочитанной "
            "main-версии скила test-authoring.md (SPEC AC-4/AC-8); "
            f"журнал: {journal}")
        self.assertFalse(
            any(f"sha256={uncommitted_sha}" in j for j in journal),
            "журнал не должен нести sha256 незакоммиченной правки диска "
            "— fingerprint обязан отражать то, что реально ушло в "
            "промпт (main-версию), а не содержимое диска (SPEC AC-4)")


if __name__ == "__main__":
    unittest.main()
