"""Приёмочные тесты AC-1/AC-2/AC-3 задачи 01M287TPG0HAVXS8CHBCY679WN:
`answer <id> <файл>` для задачи в `in_dev`/`review`, если текст файла
несёт строку маркера «Расширение зон разрешено:» (SPEC, требование 1).

Красен до реализации: `orchestrator/answer.py::_cmd_answer` сегодня
безусловно отказывает при `t["state"] != "escalated"` (answer.py:82) —
маркер «Расширение зон разрешено:» вообще не разбирается. Красны
`test_ac1_in_dev_with_marker_commits_answer_without_changing_state`,
`test_ac1_review_state_with_marker_is_also_accepted` (мандат для
`in_dev`/`review` не принимается — команда отказывает раньше, чем
успевает прочитать маркер) и
`test_ac3_mandate_commit_passes_the_same_answer_section_guard` (тот же
ранний отказ — ANSWER-файл не коммитится, гейт guard проверять нечего).
`test_ac2_in_dev_without_marker_refuses_same_as_before` УЖЕ зелёный на
текущем коде — контроль, не молчаливый пропуск: критерий требует
ИМЕННО сегодняшнего поведения (отказ вне `escalated`), которое эта
задача не меняет для файла без маркера.

Настоящий git (`RealGitSandbox`) — `answer.cmd_answer` коммитит
`ANSWER-n.md` плотницки в артефактную ветку пульта (`artifact_branch.
commit_files`), тот же приём, что уже проверяет `tests/test_answer.py`
(`_ArtifactBranchAnswerTest`, `RealPultGitTest`) для пути `escalated` —
здесь та же механика, но без полного флоу эскалации: состояние задачи
для `in_dev`/`review` выставляется напрямую (`store.update_task`), это
единственное, что различает предусловие двух путей `_cmd_answer`.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock  # noqa: F401  (доступен тестам, не используется напрямую здесь)

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import answer, artifact_branch, catalog, gitcmd, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import RealGitSandbox, capture, capture_new_task_id  # noqa: E402

# Маркер + текст мандата в одном файле ответа — тот же формат, что
# производит будущая команда `zones-extend` (AC-4 той же задачи), но
# здесь собран руками: `answer` для in_dev/review обязан распознать
# ЛЮБОЙ файл Оператора с этой строкой, не только выход `zones-extend`.
MANDATE_ANSWER_TEXT = (
    "Расширение зон разрешено: docs/extra_module.md\n\n"
    "мандат Оператора: docs/extra_module.md\n"
)

PLAIN_ANSWER_TEXT = "Обычный ответ Оператора, без маркера мандата.\n"


class _AnswerMandateSandbox(RealGitSandbox):
    """Задача заведена (`spec_writing`), артефактная ветка пульта уже
    существует и пуста от ANSWER-файлов — состояние `in_dev`/`review`
    выставляется тестом напрямую, минуя полный флоу FSM (предмет этих
    трёх критериев — разбор маркера в `_cmd_answer`, не сама FSM)."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "answer в in_dev/review, мандат зон")
        self.conn = store.db()
        self.branch = artifact_branch.branch_name(self.TASK)

    def row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def set_state(self, state: str) -> None:
        store.update_task(self.conn, self.TASK, state=state)

    def artifact_branch_files(self) -> list:
        return gitcmd.ls_tree_files(self.branch, f"tasks/{self.TASK}") or []

    def artifact_text(self, rel: str) -> str | None:
        text, _reason = gitcmd.show(self.branch, rel)
        return text

    def journal_texts(self) -> list:
        return [f"{s['action']} {s['detail']}"
               for s in store.task_steps(self.conn, self.TASK)]

    def answer_file(self, text: str) -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8")
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        f.write(text)
        f.close()
        return f.name


class Ac1AnswerInDevOrReviewWithMandateMarkerTest(_AnswerMandateSandbox):
    """AC-1."""

    def test_ac1_in_dev_with_marker_commits_answer_without_changing_state(self):
        """Задача в `in_dev`, файл ответа несёт строку «Расширение зон
        разрешено: ...» — `answer` коммитит `ANSWER-1.md` в артефактную
        ветку тем же путём, что для `escalated` (состояние не меняется),
        и журналирует запись «ANSWER создан (мандат на расширение зон:
        <пути>)» с путями из строки маркера.

        Ловит мутацию: гейт состояния `_cmd_answer` по-прежнему проверяет
        только `state == "escalated"`, без чтения файла на маркер —
        вызов для `in_dev` отказывает всегда, коммит не создаётся вовсе.
        """
        self.set_state("in_dev")

        answer.cmd_answer(self.TASK, self.answer_file(MANDATE_ANSWER_TEXT))

        self.assertEqual(
            self.row()["state"], "in_dev",
            "маршрут мандата не имеет права менять состояние задачи")
        self.assertIn(f"tasks/{self.TASK}/ANSWER-1.md",
                      self.artifact_branch_files())
        texts = self.journal_texts()
        matched = [t for t in texts
                  if "ANSWER создан" in t and "мандат на расширение зон" in t]
        self.assertTrue(matched, f"нет записи мандата в журнале: {texts}")
        self.assertIn("docs/extra_module.md", matched[-1])

    def test_ac1_review_state_with_marker_is_also_accepted(self):
        """Тот же сценарий для состояния `review` — критерий буквально
        называет оба состояния («in_dev либо review»).

        Ловит мутацию: разбор состояния сужен до буквального `"in_dev"`
        (например `if t["state"] != "in_dev" and marker not in raw`) —
        `review` с маркером отказывает так же, как раньше любое
        состояние вне `escalated`.
        """
        self.set_state("review")

        answer.cmd_answer(self.TASK, self.answer_file(MANDATE_ANSWER_TEXT))

        self.assertEqual(self.row()["state"], "review")
        self.assertIn(f"tasks/{self.TASK}/ANSWER-1.md",
                      self.artifact_branch_files())
        texts = self.journal_texts()
        self.assertTrue(
            any("ANSWER создан" in t and "мандат на расширение зон" in t
                for t in texts),
            f"нет записи мандата в журнале: {texts}")


class Ac2AnswerInDevWithoutMandateMarkerStillRefusesTest(_AnswerMandateSandbox):
    """AC-2."""

    def test_ac2_in_dev_without_marker_refuses_same_as_before(self):
        """Задача в `in_dev`, файл ответа НЕ несёт строку маркера —
        `answer` отказывает так же, как до этой задачи (задача остаётся
        в `in_dev`, коммит в артефактную ветку не создаётся).

        Ловит мутацию: разбор маркера ослаблен настолько, что срабатывает
        на ЛЮБОМ тексте файла (например проверка `if raw` вместо поиска
        конкретной строки-префикса) — обычный ответ без маркера тоже
        коммитился бы в in_dev.
        """
        self.set_state("in_dev")

        with self.assertRaises(SystemExit) as ctx:
            answer.cmd_answer(self.TASK, self.answer_file(PLAIN_ANSWER_TEXT))

        self.assertIn("escalated", str(ctx.exception))
        self.assertEqual(self.row()["state"], "in_dev")
        self.assertNotIn(f"tasks/{self.TASK}/ANSWER-1.md",
                         self.artifact_branch_files())


class Ac3AnswerMandateGuardSectionTest(_AnswerMandateSandbox):
    """AC-3."""

    def test_ac3_mandate_commit_passes_the_same_answer_section_guard(self):
        """`ANSWER-n.md`, созданный по маркеру в `in_dev`, несёт
        обязательную секцию «## Ответы» и проходит ту же guard-проверку
        (`scripts.guard.check_content`), что и `ANSWER-n.md`, создаваемый
        для `escalated`.

        Ловит мутацию: новая ветка кода для in_dev/review строит документ
        иначе (например пропускает заголовок «## Ответы» или частями
        шаблона `_answer_document`) — guard находит ошибку структуры
        там, где путь `escalated` её не находит.
        """
        self.set_state("in_dev")

        answer.cmd_answer(self.TASK, self.answer_file(MANDATE_ANSWER_TEXT))

        rel = f"tasks/{self.TASK}/ANSWER-1.md"
        text = self.artifact_text(rel)
        self.assertIsNotNone(text, f"{rel} не прочитан с артефактной ветки")
        self.assertIn("## Ответы", text)
        errors = guard.check_content(rel, text)
        self.assertEqual(errors, [], f"guard нашёл ошибки в {rel}: {errors}")


if __name__ == "__main__":
    unittest.main()
