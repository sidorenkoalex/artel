"""AC-1, AC-7 (SPEC 01M1VBEFR987MGAK0XAFMVVYZY): `answer <id> <файл>`
принимает задачу в состояниях `in_dev` и `review`, если файл несёт
маркер «Расширение зон разрешено:», — коммитит ANSWER-n в артефактную
ветку тем же кодом, что и для `escalated`, без смены состояния задачи, и
журналирует запись «ANSWER создан (мандат на расширение зон: <пути>)».
Без маркера в этих состояниях — прежний отказ («answer доступна только
для состояния escalated»). AC-7 — тот же прежний отказ, явно
сформулированный SPEC как тест на мутацию: «снятие этой проверки (приём
любого файла в in_dev) красит тест».

Смешанная краснота — по классам, не по файлу целиком:
- `Ac1MarkerAcceptedInInDevAndReviewTest` — Красен до реализации:
  `orchestrator/answer.py:82` сегодня отказывает БЕЗУСЛОВНО любому
  состоянию, кроме `escalated` — маркер мандата вовсе не читается, коммит
  ANSWER-n в `in_dev`/`review` и отдельная запись журнала о мандате
  сегодня недостижимы.
- `Ac1MissingMarkerStillRefusesTest` и `Ac7MutationMissingMarkerNeverAcceptedTest`
  — Зелёный с рождения: это ровно СЕГОДНЯШНЕЕ поведение (`answer.py:82-84`)
  — задача вне `escalated` отказывает уже сейчас, независимо от маркера;
  тесты фиксируют это поведение как планку, которую реализация AC-1 не
  имеет права ослабить (расширение исключения не должно превратиться в
  «состояние in_dev — можно отвечать чем угодно»).
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import answer  # noqa: E402
from _sandbox import TaskSandbox  # noqa: E402

MANDATE_MARKER = "Расширение зон разрешено:"


def _answer_file(text: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False,
                                    encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


class Ac1MarkerAcceptedInInDevAndReviewTest(TaskSandbox):

    def test_ac1_marker_in_in_dev_commits_answer_without_changing_state(self):
        """Задача в `in_dev`, файл ответа несёт строку «Расширение зон
        разрешено: docs/extra_module.md» — `answer` обязана закоммитить
        ANSWER-1.md в артефактную ветку, оставить задачу в `in_dev` и
        записать в журнал «ANSWER создан (мандат на расширение зон:
        docs/extra_module.md)».

        Ловит мутацию: проверка состояния в `_cmd_answer` не расширена
        веткой исключения для `in_dev`/`review` с маркером (осталось
        буквально `if t["state"] != "escalated": sys.exit(...)`) — вызов
        отказал бы, как и до этой задачи, хотя файл несёт валидный мандат
        Оператора."""
        self.set_state("in_dev")
        path = _answer_file(f"{MANDATE_MARKER} docs/extra_module.md\n")
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))

        answer.cmd_answer(self.TASK, path)

        self.assertEqual(self.state(), "in_dev",
                         "мандат на расширение зон не меняет состояние задачи")
        self.assertIn(f"tasks/{self.TASK}/ANSWER-1.md",
                      self.artifact_branch_files())
        self.assertTrue(
            any("ANSWER создан (мандат на расширение зон: "
               "docs/extra_module.md)" in d for d in self.journal_details()),
            f"журнал не несёт записи о мандате: {self.journal_details()}")

    def test_ac1_marker_in_review_commits_answer_without_changing_state(self):
        """То же самое (AC-1) для состояния `review` — второе из двух
        названных SPEC состояний, не только `in_dev`.

        Ловит мутацию: ветка исключения подключена только для `in_dev`
        буквальным сравнением строки, без `review` — задача в `review`
        отказывала бы, хотя AC-1 явно называет оба состояния через
        перечисление «in_dev и review»."""
        self.set_state("review")
        path = _answer_file(f"{MANDATE_MARKER} docs/extra_module.md\n")
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))

        answer.cmd_answer(self.TASK, path)

        self.assertEqual(self.state(), "review")
        self.assertIn(f"tasks/{self.TASK}/ANSWER-1.md",
                      self.artifact_branch_files())
        self.assertTrue(
            any("ANSWER создан (мандат на расширение зон: "
               "docs/extra_module.md)" in d for d in self.journal_details()))


class Ac1MissingMarkerStillRefusesTest(TaskSandbox):

    def test_ac1_without_marker_in_in_dev_refuses_with_prior_message(self):
        """Задача в `in_dev`, файл ответа НЕ несёт маркера мандата — AC-1
        требует «прежний отказ» дословно: то же сообщение, что и раньше
        («answer доступна только для состояния escalated»), ANSWER-n.md
        не коммитится.

        Ловит мутацию: исключение AC-1 расширено до «состояние in_dev/
        review — коммитить всегда», без сверки маркера — обычный ответ
        без мандата, адресованный совсем другому вопросу, ошибочно
        принимался бы, легализуя работу мимо эскалации."""
        self.set_state("in_dev")
        path = _answer_file("Обычный ответ без мандата.\n")
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))

        with self.assertRaises(SystemExit) as ctx:
            answer.cmd_answer(self.TASK, path)

        self.assertIn("escalated", str(ctx.exception))
        self.assertNotIn(f"tasks/{self.TASK}/ANSWER-1.md",
                         self.artifact_branch_files())


class Ac7MutationMissingMarkerNeverAcceptedTest(TaskSandbox):
    """AC-7 дословно: тест на мутацию, снимающую проверку маркера в
    `in_dev`/`review` (приём ЛЮБОГО файла ответа)."""

    def test_ac7_missing_marker_still_refuses_even_with_a_substantive_answer(self):
        """Файл ответа синтаксически валиден (непустой, обычный текст) и
        по существу адресован реальному вопросу задачи — но БЕЗ маркера
        «Расширение зон разрешено:» — задача в `in_dev` обязана отказать
        тем же сообщением, что и до этой задачи; ANSWER-1.md не
        появляется на артефактной ветке.

        Ловит мутацию: снятая проверка наличия маркера (например,
        `if raw: ...` вместо `if MANDATE_MARKER in raw: ...`) превращает
        исключение AC-1 в «состояние in_dev — можно отвечать чем угодно»
        — именно эта мутация («приём любого файла в in_dev») красит тест
        по формулировке AC-7."""
        self.set_state("in_dev")
        path = _answer_file(
            "Ответ по существу вопроса, без единого слова про зоны.\n")
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))

        with self.assertRaises(SystemExit) as ctx:
            answer.cmd_answer(self.TASK, path)

        self.assertIn("escalated", str(ctx.exception))
        self.assertNotIn(f"tasks/{self.TASK}/ANSWER-1.md",
                         self.artifact_branch_files())


if __name__ == "__main__":
    unittest.main()
