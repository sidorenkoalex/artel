"""AC-6 (tasks/T075/SPEC.md): роль, запущенная на задаче после `approve`
из AC-4, получает в своём брифе текст `ANSWER-n.md` этой эскалации; если
эскалация несла QUESTIONS.md, бриф включает и текст исходного вопроса.

Красен до реализации: сегодня (HEAD этой задачи) `orchestrator/brief.py`
(`developer_brief`, `analyst_map_component` — те же две функции, что
называет SPEC в разделе «Материалы» как точку добавления видимости
ANSWER) не читают ни `ANSWER-n.md`, ни `QUESTIONS.md` вовсе — оба
собирают только SPEC/карту/конвенции. Роль `test_author`
(`orchestrator/runner.py:222-241`) сегодня вообще не получает `brief_text`
(`brief_text` остаётся `None` для этой ветки `if/elif`) — промпт этой
роли не несёт НИКАКОГО текста ANSWER. Каждый тест здесь падает на
`assertIn(...)`, пока разработчик не добавит соответствующее чтение.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import brief, fsm, runner, store  # noqa: E402
from tests.sandbox import seed_developer_brief_fixtures  # noqa: E402

from _sandbox import AnswerGateTmpRootTest  # noqa: E402

ANSWER_MARKER = "МАРКЕР-ОТВЕТА-T075-ПЕСОЧНИЦЫ-1"
QUESTION_MARKER = "МАРКЕР-ВОПРОСА-T075-ПЕСОЧНИЦЫ"


class AnalystBriefIncludesAnswerAndQuestionTest(AnswerGateTmpRootTest):
    """Возврат из spec_writing-эскалации (QUESTIONS.md) — следующая роль
    analyst, брифуется `brief.analyst_map_component` (SPEC, «Материалы»)."""

    def test_ac6_analyst_brief_includes_answer_and_original_question(self):
        seed_developer_brief_fixtures(self.root)
        self.escalate_from_spec_writing_questions()
        self.write_answer(1)
        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "spec_writing", "подготовка сценария не удалась")

        text = brief.analyst_map_component(store.db(), self.TASK)

        self.assertIn(
            ANSWER_MARKER, text,
            "бриф analyst обязан нести текст ANSWER-1.md этой эскалации "
            "(SPEC AC-6)")
        self.assertIn(
            QUESTION_MARKER, text,
            "эскалация несла QUESTIONS.md — бриф обязан нести и текст "
            "исходного вопроса (SPEC AC-6)")


class DeveloperBriefIncludesAnswerTest(AnswerGateTmpRootTest):
    """Возврат из review-эскалации (REVIEW.md status: escalate) — прежняя
    адресация (AC-4) без зафиксированного escalated_from — фолбэк
    in_dev, следующая роль developer, брифуется `brief.developer_brief`
    (SPEC, «Материалы»)."""

    def test_ac6_developer_brief_includes_answer(self):
        seed_developer_brief_fixtures(self.root)
        self.write_spec()
        self.escalate_from_review_verdict()
        self.write_answer(1)
        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "in_dev", "подготовка сценария не удалась")

        text = brief.developer_brief(store.db(), self.TASK)

        self.assertIn(
            ANSWER_MARKER, text,
            "бриф developer обязан нести текст ANSWER-1.md этой "
            "эскалации (SPEC AC-6)")


class TestAuthorPromptIncludesAnswerTest(AnswerGateTmpRootTest):
    """Возврат из tests_writing-эскалации (`AC-n: escalate`) — следующая
    роль test_author; `orchestrator/runner.py` сегодня не собирает для
    неё отдельный `brief_text` — проверяется итоговый промпт шага
    (`runner.run_agent_once`, замоканный на запись своего аргумента
    `prompt`, тот же уровень наблюдения, что и у `.prompt.txt`,
    `orchestrator/runner.py:624-631`, без реального запуска процесса)."""

    def test_ac6_test_author_prompt_includes_answer(self):
        self.escalate_from_tests_writing_ac_marker()
        self.write_answer(1)
        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "tests_writing", "подготовка сценария не удалась")

        captured: dict = {}

        def fake_run_once(conn, task_id, role, prompt, attempt):
            captured["prompt"] = prompt
            return "ok", ""

        with mock.patch.object(runner, "run_agent_once", fake_run_once), \
                mock.patch("orchestrator.doctor.preflight_checks",
                          lambda role, target: []):
            self.capture(runner.cmd_run, self.TASK)

        self.assertIn(
            ANSWER_MARKER, captured.get("prompt", ""),
            "промпт шага test_author обязан нести текст ANSWER-1.md этой "
            "эскалации (SPEC AC-6)")


if __name__ == "__main__":
    unittest.main()
