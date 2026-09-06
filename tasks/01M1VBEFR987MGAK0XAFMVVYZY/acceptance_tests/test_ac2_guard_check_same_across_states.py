"""AC-2 (SPEC 01M1VBEFR987MGAK0XAFMVVYZY): guard-проверка секции «##
Ответы» ANSWER-n применяется одинаково независимо от состояния задачи, в
котором файл создан (`in_dev`, `review` или `escalated`).

Смешанная краснота — по тестам, не по файлу целиком:
- `test_ac2_answer_document_is_guard_valid_from_escalated` — Зелёный с
  рождения: это ровно сегодняшнее поведение (`answer._answer_document`,
  `tests/test_answer.py::AnswerDocumentIsGuardValidTest`) — контроль,
  фиксирующий базовую линию ДО сравнения с in_dev/review ниже.
- `test_ac2_answer_document_is_guard_valid_from_in_dev_with_mandate` и
  `..._from_review_with_mandate` — Красен до реализации: до AC-1
  `answer.cmd_answer` безусловно отказывает вне `escalated`
  (`orchestrator/answer.py:82`) — вызов падает `SystemExit` до того, как
  документ вообще будет создан и закоммичен, то есть до того места, где
  этот тест сравнивает его с guard'ом. Падение по этой причине —
  корректная краснота «AC-1 ещё не реализован», а не дефект этого теста.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import answer  # noqa: E402
from scripts import guard  # noqa: E402
from _sandbox import TaskSandbox  # noqa: E402


def _answer_file(text: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False,
                                    encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


class Ac2GuardCheckSameAcrossStatesTest(TaskSandbox):

    def _committed_answer(self, n: int = 1) -> tuple:
        rel = f"tasks/{self.TASK}/ANSWER-{n}.md"
        return rel, self.artifact_branch_text(rel)

    def test_ac2_answer_document_is_guard_valid_from_escalated(self):
        """Контроль (поведение до этой задачи, не меняется этой задачей):
        ANSWER-1.md, созданный из `escalated`, проходит guard без ошибок.

        Ловит мутацию: смена шаблона документа (`_answer_document`) на
        вариант без секции `## Ответы` либо со статусом, отличным от
        `ready`, ломает guard-схему типа `answer` (`scripts/guard.py`,
        `SCHEMAS["answer"]`) — при этом контроле мутация проявилась бы
        уже здесь, до сравнения с in_dev/review ниже."""
        self.escalate()
        path = _answer_file("Ответ по вопросу эскалации.\n")
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))

        answer.cmd_answer(self.TASK, path)

        rel, text = self._committed_answer()
        self.assertEqual(guard.check_content(rel, text), [])

    def test_ac2_answer_document_is_guard_valid_from_in_dev_with_mandate(self):
        """ANSWER-1.md, созданный из `in_dev` с маркером мандата, проходит
        ТОТ ЖЕ guard без ошибок — «применяется одинаково независимо от
        состояния» дословно из AC-2.

        Ловит мутацию: реализация AC-1 вводит ВТОРОЙ, отдельный шаблон
        документа для ветки in_dev/review (например, без секции
        `## Ответы`, раз уж мандат и так разбирается по строке-маркеру) —
        guard отказал бы именно для этого состояния, хотя AC-2 требует
        совпадения поведения guard'а с escalated."""
        self.set_state("in_dev")
        path = _answer_file("Расширение зон разрешено: docs/extra_module.md\n")
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))

        answer.cmd_answer(self.TASK, path)

        rel, text = self._committed_answer()
        self.assertEqual(guard.check_content(rel, text), [])

    def test_ac2_answer_document_is_guard_valid_from_review_with_mandate(self):
        """То же (AC-2) для состояния `review`.

        Ловит мутацию: как выше, но специфично для `review` — реализация
        могла бы завести отдельную (более слабую) ветку именно для этого
        состояния, оставив `in_dev` рядом корректным."""
        self.set_state("review")
        path = _answer_file("Расширение зон разрешено: docs/extra_module.md\n")
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))

        answer.cmd_answer(self.TASK, path)

        rel, text = self._committed_answer()
        self.assertEqual(guard.check_content(rel, text), [])


if __name__ == "__main__":
    unittest.main()
