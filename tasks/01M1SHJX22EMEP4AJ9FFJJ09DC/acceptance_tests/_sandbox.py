"""Общая песочница приёмочных тестов 01M1SHJX22EMEP4AJ9FFJJ09DC (SPEC:
approve без набора sha — сверка фиксации механикой; перечитывание
budget_usd на гейте SPEC).

`ApproveSandbox` переиспользует `tests.test_git_fixation.RealPultGitTest`
(настоящий git self/артели, шаблон SPEC, `enter_spec_gate`/`enter_in_dev`,
`head()`/`commit_task_dir()`) вместо копирования той же тяжёлой обвязки —
предмет проверки этой задачи (сверка sha на approve, перечитывание
бюджета) целиком строится поверх той же фиксации, что уже несёт
`test_git_fixation.py` (ADR-0003 п.15/п.17).
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

# SPEC минимальный и валидный по guard (тот же каркас, что `test_git_
# fixation.SPEC_READY`), с полем `budget_usd`, подставляемым по месту
# (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md, требования 4-5): guard на
# approve spec_gate не перезапускается (только на advance spec_writing ->
# spec_gate), поэтому содержимое, подложенное ПРЯМО в артефактную ветку
# на уже пройденном гейте, не обязано проходить полную приёмку guard —
# `_cmd_approve` читает его только `yamlmini.frontmatter`.
SPEC_WITH_BUDGET = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
budget_usd: {budget}
---

# SPEC: перечитывание бюджета на гейте

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""


class ApproveSandbox(RealPultGitTest):

    def force_state(self, state: str) -> str:
        """Ставит задачу в `state` минуя обычный advance/approve — для
        сценариев, где предмет проверки не зависит от пути входа в гейт
        (тот же приём, что `test_git_fixation.
        AutoStopHintIncludesShaOnEveryApproveNeedsShaStateTest.force_state`).
        Возвращает head фиксации ПОСЛЕ перехода (переход сам
        перефиксирует sha)."""
        conn = store.db()
        current = store.get_task(conn, self.TASK)["state"]
        store.set_state(conn, self.TASK, state, "operator",
                        expected_state=current, detail="тест: подготовка")
        return self.head()

    def approve_output_or_exit_message(self, *args) -> str:
        """Прогоняет `fsm.cmd_approve` и возвращает весь текст, который
        Оператор увидел бы — печать (stdout) либо сообщение `sys.exit`,
        смотря каким способом реализация выражает именованный отказ (SPEC
        AC-3 не предписывает механизм отказа, только его наблюдаемое
        содержимое — оба сверяемых sha и то, что состояние не изменилось).
        """
        from orchestrator import fsm
        try:
            return self.capture(fsm.cmd_approve, self.TASK, *args)
        except SystemExit as exc:
            return str(exc)

    def write_spec_budget_on_artifact_branch(self, budget_usd) -> None:
        """Кладёт SPEC.md с указанным `budget_usd` ТОЛЬКО в артефактную
        ветку пульта (не в репозиторий фиксации `task_dir()`) — симулирует
        правку Оператора на уже пройденном гейте SPEC (SPEC «Контекст»):
        approve на `spec_gate` перечитывает бюджет именно оттуда
        (`artifact_source.resolve` + `_read_branch_text_or_refuse`), а sha
        фиксации сравнивается отдельно, с репозиторием `task_dir()`."""
        self._seed_artifact_branch(
            f"tasks/{self.TASK}/SPEC.md",
            SPEC_WITH_BUDGET.format(task=self.TASK, budget=budget_usd),
            f"{self.TASK}: budget_usd -> {budget_usd}")

    def budget_journal(self, action: str) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? "
            "ORDER BY id", (self.TASK, action))]
