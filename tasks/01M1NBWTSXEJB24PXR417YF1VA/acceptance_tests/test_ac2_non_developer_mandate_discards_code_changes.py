"""Приёмочный тест AC-2 — 01M1NBWTSXEJB24PXR417YF1VA: мандат
`analyst`/`test_author`/`reviewer` в WIP-чекпоинте после таймаута шага.

Источник — tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md, «Критерии приёмки»:

AC-2. При таймауте шага роли `analyst`, `test_author` или `reviewer`
WIP-чекпоинт не коммитит в кодовую ветку задачи ни одного пути worktree,
кроме `tasks/<id>/`: такие изменения откатываются командой
`git checkout -- <пути>`.

Правка — в УЖЕ ОТСЛЕЖИВАЕМЫЙ веткой файл (`CLAUDE.md`, часть исходного
коммита `RealPultGitTest.setUp`), не новый: `git checkout -- <путь>`,
названный самим критерием, откатывает именно модификацию отслеживаемого
файла — критерий проверяется буквально тем механизмом, который называет.

Красен до реализации: `checkpoint.commit_timeout_checkpoint` сегодня не
знает о роли, вызвавшей таймаут, — `git add -A` безусловно коммитит
любую правку (включая правку `analyst`/`test_author`/`reviewer` вне
`tasks/<id>/`) в кодовую ветку. Тест ниже ловит это: HEAD кодовой ветки
после чекпоинта отличался бы от `before`, и `CLAUDE.md` не вернулся бы к
исходному содержимому.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MandateCheckpointTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import checkpoint, store  # noqa: E402


class NonDeveloperMandateDiscardsCodeChangesTest(MandateCheckpointTest):

    def _assert_change_discarded(self, role: str):
        self.enter_in_dev()
        claude_md = self.wt / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            original + f"правка роли {role}, не должна попасть в код\n",
            encoding="utf-8")
        before = self.worktree_head()

        detail = checkpoint.commit_timeout_checkpoint(
            store.db(), self.TASK, role)

        self.assertEqual(
            self.worktree_head(), before,
            f"AC-2: роль {role} — ни один путь вне tasks/<id>/ не "
            f"коммитится в кодовую ветку, HEAD не сдвигается")
        self.assertEqual(
            claude_md.read_text(encoding="utf-8"), original,
            f"AC-2: правка роли {role} вне мандата обязана быть "
            f"откачена (`git checkout -- CLAUDE.md`) к исходному "
            f"содержимому")
        self.assertEqual(
            detail, "",
            f"AC-2: чекпоинту роли {role} нечего коммитить в кодовую "
            f"ветку — она не несёт ни одного пути в её мандате")

    def test_ac2_analyst_timeout_discards_non_task_change(self):
        """Таймаут шага `analyst` с правкой отслеживаемого файла кодовой
        ветки (`CLAUDE.md`) вне `tasks/<id>/` — правка откачена, HEAD
        кодовой ветки не сдвинут.

        Ловит мутацию: роль `analyst` по ошибке отнесена к мандату
        `developer` (или мандат вообще не проверяется) — тогда правка
        `CLAUDE.md` осталась бы закоммиченной в кодовую ветку.
        """
        self._assert_change_discarded("analyst")

    def test_ac2_test_author_timeout_discards_non_task_change(self):
        """Таймаут шага `test_author` с правкой отслеживаемого файла
        кодовой ветки (`CLAUDE.md`) вне `tasks/<id>/` — правка откачена,
        HEAD кодовой ветки не сдвинут.

        Ловит мутацию: роль `test_author` по ошибке отнесена к мандату
        `developer` — тот самый инцидент-источник SPEC (hotfix
        01M1KT0792125J9ZNJNZJ86E9Q, REVIEW.md R2-F1: WIP-заглушка
        реализации test_author попала в кодовую ветку).
        """
        self._assert_change_discarded("test_author")

    def test_ac2_reviewer_timeout_discards_non_task_change(self):
        """Таймаут шага `reviewer` с правкой отслеживаемого файла кодовой
        ветки (`CLAUDE.md`) вне `tasks/<id>/` — правка откачена, HEAD
        кодовой ветки не сдвинут.

        Ловит мутацию: роль `reviewer` по ошибке отнесена к мандату
        `developer` (ANSWER-1 явно относит `reviewer` к той же категории
        мандата, что `test_author`/`analyst` — «ничего в кодовую
        ветку») — тогда правка `CLAUDE.md` осталась бы закоммиченной.
        """
        self._assert_change_discarded("reviewer")


if __name__ == "__main__":
    import unittest
    unittest.main()
