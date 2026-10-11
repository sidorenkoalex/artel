"""AC-5 (tasks/T075/SPEC.md): для задачи в `escalated`, чья эскалация —
исчерпание попыток агента (`config.AGENT_ATTEMPTS`), исчерпание лимита
итераций ревью или лимита отказов приёмки, конфликт подтяжки главной
ветки или инцидент целостности, `approve` работает без `ANSWER-n.md`,
как до этой задачи.

Зелёный с рождения: сегодня (HEAD этой задачи) `orchestrator/fsm.py`
(`elif state == "escalated":`, строки 1140-1150) вообще не проверяет
ANSWER-n.md ни для одного класса эскалации — approve из ЛЮБОЙ эскалации
уже проходит без него. Эти тесты фиксируют СУЩЕСТВУЮЩЕЕ поведение как
регрессионный барьер: как только разработчик добавит гейт AC-3 (ANSWER
обязателен для класса «вопрос роли»), он не имеет права расширить
требование на эти пять классов «лимит»/интеграционных эскалаций — иначе
эти тесты покраснеют. Каждый сценарий воспроизводит РЕАЛЬНОЕ условие,
при котором в проде не появляется ни QUESTIONS.md, ни `AC-n: escalate`,
ни REVIEW.md `status: escalate` (единственные сигналы класса «вопрос
роли», которые правит эта задача) — гейт AC-3, различающий класс по
факту их присутствия на ветке/диске, а не по побочному `escalated_from`
(`escalated_from` сегодня совпадает по ЗНАЧЕНИЮ, например "review", и
для эскалации-вопроса реценвьюера, и для провала агента ВО ВРЕМЯ шага
review — сам по себе он класс не различает), не имеет повода их
затребовать.

Механика самих эскалаций (когда и почему они возникают) — вне объёма
SPEC T075 («Не входит»); сценарии «конфликт подтяжки» и «инцидент
целостности» ниже не гоняют настоящий git/агента заново (это уже
доказано `tasks/T051/acceptance_tests/`, `tests/test_agent_failure.py`),
а воспроизводят их РЕЗУЛЬТИРУЮЩЕЕ состояние БД теми же вызовами и с теми
же текстами `detail`, что и сам продакшн-код (цитаты — в докстринге
каждого теста), — это тест НОВОГО гейта возврата, не старой механики
эскалации.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, fsm, runner, store  # noqa: E402
from tests.sandbox import FakeProc, seed_developer_brief_fixtures  # noqa: E402

from _sandbox import (AnswerGateTmpRootTest,  # noqa: E402
                      REVIEW_CHANGES_REQUESTED)


class AcceptRejectsLimitNeedsNoAnswerTest(AnswerGateTmpRootTest):
    """`orchestrator/fsm.py:1177-1181` (`_cmd_reject`, ветка `acceptance`):
    отказ приёмки сверх `config.LIMIT_ACCEPT_REJECTS` эскалирует, НЕ
    выставляя `escalated_from` — фолбэк `in_dev` (fsm.py:1146), как и до
    этой задачи."""

    def test_ac5_approve_without_answer_succeeds_after_accept_rejects_limit(self):
        self.set_state("acceptance", accept_rejects=config.LIMIT_ACCEPT_REJECTS)

        self.capture(fsm.cmd_reject, self.TASK, "снова не то")
        self.assertEqual(self.state(), "escalated", "подготовка сценария не удалась")

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertNotEqual(
            self.state(), "escalated",
            "approve обязан продвинуть задачу без ANSWER-n.md — "
            "эскалация класса «лимит отказов приёмки» его не требует "
            "(SPEC AC-5)")


class ReviewItersLimitNeedsNoAnswerTest(AnswerGateTmpRootTest):
    """`orchestrator/fsm.py:734-745` (ветка `changes_requested`): лимит
    `config.LIMIT_REVIEW_ITERS` эскалирует, НЕ выставляя `escalated_from`
    — фолбэк `in_dev`, как и до этой задачи."""

    def test_ac5_approve_without_answer_succeeds_after_review_iters_limit(self):
        self.set_state("review", review_iters=config.LIMIT_REVIEW_ITERS - 1)
        self.write_review(REVIEW_CHANGES_REQUESTED, iteration=1)

        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "escalated", "подготовка сценария не удалась")

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertNotEqual(
            self.state(), "escalated",
            "approve обязан продвинуть задачу без ANSWER-n.md — "
            "эскалация класса «лимит итераций ревью» его не требует "
            "(SPEC AC-5)")


class AgentAttemptsExhaustedNeedsNoAnswerTest(AnswerGateTmpRootTest):
    """`orchestrator/runner.py:294-321` (`_cmd_run`): исчерпание
    `config.AGENT_ATTEMPTS` эскалирует С `escalated_from = t["state"]`
    (значение — само состояние шага, например "in_dev", не маркер класса)
    — фолбэк на это же состояние, как и до этой задачи. Прогоняется
    настоящим `runner.cmd_run` с фейковым падающим процессом (тот же
    приём, что `tests/test_agent_failure.py`), не репликой БД: здесь это
    дешёво (без реального git/агента) и точнее воспроизводит условие,
    от которого гейт AC-3 обязан отличить класс «вопрос роли»."""

    def setUp(self):
        super().setUp()
        seed_developer_brief_fixtures(self.root)
        self.write_spec()
        self.set_state("in_dev")
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        sleep_patcher = mock.patch.object(runner.time, "sleep", lambda _: None)
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    def test_ac5_approve_without_answer_succeeds_after_agent_attempts_exhausted(self):
        procs = [FakeProc(["упал\n"], 1) for _ in range(config.AGENT_ATTEMPTS)]
        with mock.patch.object(runner, "spawn_agent", side_effect=procs):
            self.capture(runner.cmd_run, self.TASK)
        self.assertEqual(self.state(), "escalated", "подготовка сценария не удалась")

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertNotEqual(
            self.state(), "escalated",
            "approve обязан продвинуть задачу без ANSWER-n.md — "
            "эскалация класса «исчерпание попыток агента» его не "
            "требует (SPEC AC-5)")


class IntegrityIncidentNeedsNoAnswerTest(AnswerGateTmpRootTest):
    """`orchestrator/runner.py:167-180` (`_cmd_run`, `fixation.check_integrity`):
    расхождение зафиксированного и текущего sha эскалирует С
    `escalated_from = t["state"]`, `detail` содержит подстроку «инцидент
    целостности» — фолбэк на то же состояние, как и до этой задачи.
    `gitcmd.git` в этой песочнице — заглушка (`_sandbox.py`, докстринг
    модуля): `fixation.read()` всегда отдаёт пустой sha, поэтому
    ЛЮБОЙ непустой `fixed_sha` на строке задачи воспроизводит
    расхождение — тот же вырожденный случай, которым уже пользуется
    `orchestrator/fixation.py::check_integrity` (`if not current: return
    "текущее состояние артефактов не прочитано..."`)."""

    def setUp(self):
        super().setUp()
        seed_developer_brief_fixtures(self.root)
        self.set_state("in_dev", fixed_sha="f" * 40)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def test_ac5_approve_without_answer_succeeds_after_integrity_incident(self):
        self.capture(runner.cmd_run, self.TASK)
        self.assertEqual(self.state(), "escalated", "подготовка сценария не удалась")
        details = self.journal_details()
        self.assertTrue(
            any("инцидент целостности" in d for d in details),
            f"подготовка сценария не удалась — не найден инцидент "
            f"целостности в журнале: {details}")

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertNotEqual(
            self.state(), "escalated",
            "approve обязан продвинуть задачу без ANSWER-n.md — "
            "эскалация класса «инцидент целостности» его не требует "
            "(SPEC AC-5)")


class MainPullConflictNeedsNoAnswerTest(AnswerGateTmpRootTest):
    """`orchestrator/fsm.py:298-308` (`_handle_merge_conflict`, вызывается
    `_pull_main_or_escalate`): конфликт подтяжки `config.MAIN_BRANCH`
    эскалирует БЕЗ `escalated_from` — фолбэк `in_dev`, как и до этой
    задачи. Настоящий конфликтующий git воспроизведён
    `tasks/T051/acceptance_tests/` (T051, AC-2) — не дублируется здесь;
    это тест НОВОГО гейта возврата на РЕЗУЛЬТИРУЮЩЕМ состоянии БД, тем же
    вызовом (`store.set_state`) и тем же текстом `detail`, что пишет сам
    `_handle_merge_conflict`."""

    def test_ac5_approve_without_answer_succeeds_after_main_pull_conflict(self):
        self.set_state("in_dev")
        conn = store.db()
        branch = self.row()["branch"]
        store.set_state(
            conn, self.TASK, "escalated", "fsm", expected_state="in_dev",
            detail=(f"конфликт подтяжки {config.MAIN_BRANCH} в ветку "
                    f"{branch}: CONFLICT (content): Merge conflict"))

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertNotEqual(
            self.state(), "escalated",
            "approve обязан продвинуть задачу без ANSWER-n.md — "
            "эскалация класса «конфликт подтяжки главной ветки» его не "
            "требует (SPEC AC-5)")


if __name__ == "__main__":
    unittest.main()
