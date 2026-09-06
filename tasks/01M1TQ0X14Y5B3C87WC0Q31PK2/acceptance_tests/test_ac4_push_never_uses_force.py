"""Приёмочный тест AC-4 задачи 01M1TQ0X14Y5B3C87WC0Q31PK2: push
артефактной ветки не вызывается с `--force` ни при каком отказе, включая
non-fast-forward.

Зелёный с рождения: сегодняшний `artifact_branch.push`
(`orchestrator/artifact_branch.py:130-137`) — голый `git push -q origin
refs/heads/<branch>:refs/heads/<branch>` без единого условного пути к
`--force`/`-f`; настоящий git на non-fast-forward честно отказывает сам,
ничего не перезаписывая. Требование 2/AC-4 запрещает добавлять силовой
путь ПОЗЖЕ, в рамках этой же задачи (повтор push на следующем
автокоммите, AC-3) — тест ловит именно такую регрессию, а не текущее
поведение, поэтому уже сейчас проходит и обязан продолжать проходить
после реализации AC-1..AC-3/AC-5 тем же файлом, без правки ассертов.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import gitcmd  # noqa: E402
from _sandbox import DivergedArtifactBranchSandbox  # noqa: E402


class NonFastForwardNeverForcesTest(DivergedArtifactBranchSandbox):

    def test_ac4_push_never_passes_force_even_on_non_fast_forward(self):
        """Локальный автокоммит следующего шага роли расходится с origin
        (внешний коммит Оператора уже там, локальный ref о нём не знает)
        — push этого автокоммита обязан быть отклонён БЕЗ `--force`/`-f`/
        `--force-with-lease`, а origin обязан остаться НЕТРОНУТЫМ.

        Ловит мутацию: реализация повтора push (AC-3) «чинит»
        non-fast-forward добавлением `--force` (или `-f`) к аргументам
        push при отказе — тогда либо `assertNotIn` находит флаг силы среди
        записанных вызовов `gitcmd.git`, либо (если бы мутация ещё и
        обошла эту точку записи) origin сменил бы sha на локальный, и
        вторая проверка поймала бы это через `origin_branch_sha`.
        """
        real_git = gitcmd.git
        recorded = []

        def spy(*args):
            recorded.append(args)
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=spy):
            self.run_reviewer_autocommit()

        push_calls = [c for c in recorded if c and c[0] == "push"]
        self.assertTrue(push_calls, "AC-4: push обязан быть вызван")
        for call in push_calls:
            self.assertNotIn("--force", call)
            self.assertNotIn("-f", call)
            self.assertNotIn("--force-with-lease", call)

        self.assertEqual(
            self.origin_branch_sha(self.branch), self.origin_sha_before,
            "AC-4: без --force отклонённый push не имеет права изменить "
            "origin")


if __name__ == "__main__":
    unittest.main()
