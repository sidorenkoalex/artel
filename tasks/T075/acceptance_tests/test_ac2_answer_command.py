"""AC-2 (tasks/T075/SPEC.md): «Команда `artel.py answer <id>
<файл-с-ответом>`, вызванная Оператором на задаче в состоянии
`escalated`, создаёт `tasks/<id>/ANSWER-n.md` в worktree задачи,
коммитит его в ветку задачи с авторством Оператора и оставляет запись в
журнале задачи.»

Имя и сигнатура команды больше не эскалированы: SPEC (требование 2, AC-2)
фиксирует решение Оператора 31.08 — `answer <id> <файл-с-ответом>`,
диспетчеризация той же таблицей `orchestrator/artel.py`, что остальные
команды (по образцу `new "<название>" --tz <файл>`).

Песочница — `RealPultGitTest` (tests/test_git_fixation.py), не лёгкая
`AnswerGateTmpRootTest` этого каталога: та специально работает с
заглушкой `gitcmd.git` и читает артефакты с диска, не с ветки (докстринг
`_sandbox.py`) — авторство КОММИТА эта заглушка не воспроизводит вовсе
(тот же довод, что `tests/test_step_autocommit.py`, докстринг: «заглушкой
`gitcmd.git` эту механику не проверить»). Здесь ветка/worktree задачи —
настоящий git.

Проверка «авторством Оператора» — НЕ равенство конкретному имени/почте:
`git` разрешает identity коммита переменными окружения
`GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL` ПОВЕРХ конфига, включая `-c
user.name=...` (та же механика, что описывает `orchestrator/runner.py:
11-18`, `GIT_IDENTITY`, экспериментально проверено при написании этого
теста: `-c user.name=X` не перебивает уже выставленный `GIT_AUTHOR_NAME`
процесса) — конкретное имя автора коммита этой команды зависит от
окружения, в котором Оператор её вызвал (его личный `~/.gitconfig` или
экспортированные `GIT_AUTHOR_*`), а не от кода `answer`. Тест здесь
проверяет единственный воспроизводимый в любом окружении инвариант:
коммит НЕ должен уходить под служебную identity оркестратора
(`fixation.FIXATION_AUTHOR_NAME`/`FIXATION_AUTHOR_EMAIL` — той же, что
`catalog.cmd_new` явно проставляет `-c user.name=.../-c user.email=...`
коммиту ТЗ/SPEC, `orchestrator/catalog.py:166-169`, T025) — это и есть
разница между «коммит от имени Оператора» (эта задача) и «коммит от
служебного имени оркестратора», доступная тесту без предположений о
конкретной identity машины, на которой он запущен.

Красен до реализации: на HEAD этой задачи `orchestrator/artel.py`
(таблица команд, строки 209-236) не несёт ключа `"answer"` — `artel.
main()` с `argv=["artel.py", "answer", ...]` попадает в `sys.exit(f"
Неизвестная команда {cmd}...")` (`artel.py:236`), тест ловит это как
`ERROR` (`SystemExit`, не `assertRaises` — эта ветка не входит в
контракт критерия, она лишь показывает, что команды сегодня нет).
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artel, fixation, fsm, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

QUESTIONS_TEXT = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: батч AC-2

## Вопросы

1. **Какой вариант выбрать?** — варианты: A) первый; B) второй — дефолт: A.
"""

ANSWER_MARKER = "МАРКЕР-ОТВЕТА-AC2-ac2ans"


class AnswerCommandCreatesCommitsAndJournalsTest(RealPultGitTest):

    def _escalate(self) -> None:
        (self.task_dir() / "QUESTIONS.md").write_text(
            QUESTIONS_TEXT.format(task=self.TASK), encoding="utf-8")
        self.commit_task_dir("батч вопросов")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "escalated",
            "подготовка сценария не удалась")

    def test_ac2_answer_creates_answer_file_commits_and_journals(self):
        self._escalate()
        head_before = self.head()
        steps_before = len(store.task_steps(store.db(), self.TASK))

        answer_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8")
        self.addCleanup(lambda: Path(answer_file.name).unlink(missing_ok=True))
        answer_file.write(f"Ответ Оператора: вариант A.\n\n{ANSWER_MARKER}\n")
        answer_file.close()

        with mock.patch.object(
                sys, "argv",
                ["artel.py", "answer", self.TASK, answer_file.name]):
            artel.main()

        answer_path = self.task_dir() / "ANSWER-1.md"
        self.assertTrue(
            answer_path.exists(),
            "answer обязан создать tasks/<id>/ANSWER-1.md в worktree "
            "задачи (SPEC AC-2)")
        self.assertIn(
            ANSWER_MARKER, answer_path.read_text(encoding="utf-8"),
            "ANSWER-1.md обязан нести текст, прочитанный из файла ответа "
            "(SPEC AC-2)")

        head_after = self.head()
        self.assertNotEqual(
            head_before, head_after,
            "answer обязан закоммитить ANSWER-1.md в ветку задачи "
            "(SPEC AC-2)")

        author = self.git_in_worktree(
            "log", "-1", "--format=%an%x1f%ae", head_after).strip()
        author_name, _, author_email = author.partition("\x1f")
        self.assertNotEqual(
            (author_name, author_email),
            (fixation.FIXATION_AUTHOR_NAME, fixation.FIXATION_AUTHOR_EMAIL),
            "коммит ANSWER-1.md не должен уходить под служебную identity "
            "оркестратора (fixation) — это не авторство Оператора (SPEC "
            "AC-2)")

        steps_after = len(store.task_steps(store.db(), self.TASK))
        self.assertGreater(
            steps_after, steps_before,
            "answer обязан оставить запись в журнале задачи (SPEC AC-2)")


if __name__ == "__main__":
    unittest.main()
