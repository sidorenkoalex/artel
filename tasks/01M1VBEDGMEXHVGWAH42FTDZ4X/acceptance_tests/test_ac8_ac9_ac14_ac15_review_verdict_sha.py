"""Приёмочные тесты 01M1VBEDGMEXHVGWAH42FTDZ4X — AC-8, AC-9, AC-14, AC-15:
эскалация по бюджету, наступившая во время шага reviewer с уже вынесенным
approved-вердиктом REVIEW.md, — возврат в `review` пропускает новый прогон
ревьювера, только если sha кодовой ветки задачи не менялся с момента
вердикта (требование 3).

Сценарий у всех четырёх тестов один и тот же: reviewer пишет approved
REVIEW.md, БЮДЖЕТ эскалирует задачу СРАЗУ после (`enforce_budget` внутри
`orchestrator/runner.py::_cmd_run` — до того, как хоть один `advance`
успел прочитать вердикт, см. `orchestrator/budget.py::enforce_budget`) —
`reviewed_iter` остаётся НЕ обновлённым, вердикт лежит «непрочитанным».
`gitcmd.branch_head_sha` подменена контролируемым значением (в лёгкой
песочнице `fake_git` он всегда пуст — не годится для сверки двух разных
sha, см. докстринг соседнего файла про ту же деградацию для времени
коммитов): AC-8/AC-14 держат его неизменным между вердиктом и возвратом,
AC-9/AC-15 — меняют, симулируя посторонний коммit на кодовой ветке, пока
задача стояла эскалированной.

Красен до реализации: сегодня `review()` (orchestrator/fsm_advance.py)
не сравнивает sha вовсе — свежесть держит только `reviewed_iter`
(итерация REVIEW.md), который в этом сценарии ещё не тронут ни при каком
исходе сверки. AC-9/AC-15 покраснеют: возврат пройдёт прямиком в
`acceptance` даже при сменившемся sha (проверено прогоном на
немодифицированном коде — см. журнал разработки этой планки). AC-8/AC-14
уже сегодня проходят (сверка sha ещё не введена — блокировать ей нечего)
— зелёные с рождения, они фиксируют, что requirement 3 не должен
испортить и без того рабочий путь.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AutoCycleTest, agent_run_finished_actors,  # noqa: E402
                      journal_agent_run_finished)
from orchestrator import budget, fsm, gitcmd, store  # noqa: E402


class _ReviewSandbox(AutoCycleTest):
    """Общая обвязка сценария: approved REVIEW.md, эскалация по бюджету
    ДО первого прочтения вердикта, управляемый sha кодовой ветки."""

    def escalate_with_approved_verdict(self, sha: str) -> dict:
        self.write_plan("ready")
        self.set_state("review", budget_usd=25.0, spent_usd=1.0)
        t = store.get_task(store.db(), self.TASK)
        branch = t["branch"]
        sha_box = {"sha": sha}

        def fake_branch_head_sha(b: str) -> str:
            return sha_box["sha"] if b == branch else ""

        self.patch_object(gitcmd, "branch_head_sha", fake_branch_head_sha)

        self.write_review("approved", 1)
        conn = store.db()
        journal_agent_run_finished(conn, self.TASK)
        store.update_task(conn, self.TASK, spent_usd=26.0)
        escalated = budget.enforce_budget(conn, self.TASK, "review")
        assert escalated and self.state() == "escalated", (
            "сценарий не воспроизведён: эскалация по бюджету не сработала")
        return sha_box


class UnchangedShaSkipsANewReviewerRunTest(_ReviewSandbox):
    """AC-8: код не менялся с момента вердикта — возврат в `review`
    переходит в `acceptance` без нового прогона ревьювера."""

    def test_ac8_manual_advance_reaches_verifying_on_unchanged_sha(self):
        """sha кодовой ветки в момент возврата совпадает со sha на момент
        вердикта — ручной `advance` после `budget` обязан довести задачу
        до `acceptance`.

        Ловит мутацию: сверка sha реализована «наоборот» (блокирует
        РАВЕНСТВО вместо различия) — переход не случится, задача
        останется в `review` даже без единого изменения кода.
        """
        self.escalate_with_approved_verdict("a" * 40)

        self.capture(budget.cmd_budget, self.TASK, "50")
        self.assertEqual(self.state(), "review")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "acceptance")


class ChangedShaBlocksTheTransitionTest(_ReviewSandbox):
    """AC-9: код сменился ПОСЛЕ вердикта — возврат в `review` не переходит
    в `acceptance` без нового вердикта ревьювера."""

    def test_ac9_manual_advance_does_not_reach_verifying_on_changed_sha(self):
        """sha кодовой ветки на момент возврата ОТЛИЧАЕТСЯ от sha на
        момент вердикта — ручной `advance` обязан отказать переходу в
        `acceptance`, несмотря на статус `approved` в REVIEW.md.

        Ловит мутацию: требование 3 не реализовано вовсе (сегодняшнее
        поведение) — advance доведёт задачу до `acceptance` по старому
        вердикту, написанному для уже неактуального кода.
        """
        sha_box = self.escalate_with_approved_verdict("a" * 40)
        sha_box["sha"] = "b" * 40  # посторонний коммит, пока задача стояла escalated

        self.capture(budget.cmd_budget, self.TASK, "50")
        self.assertEqual(self.state(), "review")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "review",
            "переход в acceptance не должен был случиться — гейт обязан отказать")


class UnchangedShaAutoCycleSkipsTheReviewerTest(_ReviewSandbox):
    """AC-14: интеграционный дубль AC-8 через `auto` — ревьювер не
    получает второго шага."""

    def test_ac14_auto_reaches_verifying_without_a_second_reviewer_step(self):
        """`auto` после подъёма потолка обязан довести задачу до
        `acceptance`, не потратив ни одного нового шага ревьювера.

        Ловит мутацию: пред-advance `auto` (или сама сверка sha) требует
        нового прогона ревьювера даже при неизменном коде — `agent.calls`
        перестанет быть пустым, а `reviewer` появится в
        `agent_run_finished_actors` второй раз.
        """
        self.escalate_with_approved_verdict("a" * 40)
        conn = store.db()

        self.capture(budget.cmd_budget, self.TASK, "50")

        self.agent.script = [lambda: None]
        self.auto()

        self.assertEqual(self.state(), "acceptance")
        reviewer_steps = [a for a in agent_run_finished_actors(conn, self.TASK)
                         if a == "reviewer"]
        self.assertEqual(len(reviewer_steps), 1)


class ChangedShaAutoCycleForcesANewReviewerStepTest(_ReviewSandbox):
    """AC-15: интеграционный дубль AC-9 через `auto` — код сменился,
    ревьювер обязан получить новый шаг, раз старый вердикт больше не
    учитывается."""

    def test_ac15_auto_calls_the_reviewer_again_on_changed_sha(self):
        """sha сменился, пока задача стояла эскалированной — `auto`
        обязан позвать ревьювера заново, а не продвинуть задачу по
        устаревшему вердикту.

        Ловит мутацию: требование 3 не реализовано — `auto` доводит
        задачу прямиком до `acceptance` (проверено прогоном на
        немодифицированном коде), ни разу не вызвав ревьювера повторно;
        `self.agent.calls` останется пустым.
        """
        sha_box = self.escalate_with_approved_verdict("a" * 40)
        sha_box["sha"] = "b" * 40

        self.capture(budget.cmd_budget, self.TASK, "50")

        self.agent.script = [lambda: None]
        self.auto()

        self.assertTrue(
            self.agent.calls,
            "auto не позвал ревьювера заново, несмотря на сменившийся "
            "sha кода после вердикта")


if __name__ == "__main__":
    import unittest
    unittest.main()
