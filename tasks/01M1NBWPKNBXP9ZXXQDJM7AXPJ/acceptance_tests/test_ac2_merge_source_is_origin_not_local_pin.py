"""AC-2 (tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md): Merge внутри
`_pull_main_or_escalate` (подтяжка ветки задачи в её worktree)
выполняется из того же источника, что и сверка в AC-1 —
`FETCH_HEAD`/`origin/<MAIN_BRANCH>` — не из локального
`config.MAIN_BRANCH`.

Источник — tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md, «Критерии
приёмки», AC-2.

Красен до реализации: сегодня сверка (AC-1) вообще не доходит до этой
ветки задачи в сценарии теста — она форкнута до расхождения, поэтому
`commits_behind` против локального `config.MAIN_BRANCH` считает её не
отставшей, и `_pull_main_or_escalate` возвращает `"fresh"` ДО того, как
worktree заводится и merge вызывается хоть раз. Проверено прогоном на
немодифицированном коде: `outcome == "fresh"`, ноль вызовов
`git merge`, файл, существующий только в origin, в worktree не
появляется (worktree не заводится вовсе).
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import OriginDivergedSandbox, UPSTREAM_MARKER_REL  # noqa: E402
from orchestrator import config, gitcmd  # noqa: E402


class Ac2MergeSourceIsOriginNotLocalPinTest(OriginDivergedSandbox):

    def test_ac2_merge_uses_origin_ref_and_pulls_origin_only_content(self):
        """Origin ушёл вперёд локального пина; ветка задачи совпадает с
        пином (тот же сценарий, что AC-1). Merge, реально исполненный
        `_pull_main_or_escalate`, обязан (а) не называть локальный
        `config.MAIN_BRANCH` буквальным аргументом и (б) реально внести
        в worktree файл, существующий ТОЛЬКО в main артели на origin —
        второе доказывает первое по содержимому, не только по аргументу
        вызова.

        Ловит мутацию: код, оставляющий `config.MAIN_BRANCH` буквальным
        аргументом merge (сегодняшний код, если бы до него дошло
        исполнение) — сольётся не сдвинутый локальный пин, апстрим-файл
        в worktree не появится, а аргумент совпадёт с именем локальной
        ветки один-в-один.
        """
        self.advance_origin_only()
        merge_calls = []
        real_in_repo = gitcmd.in_repo

        def spying_in_repo(repo, *args):
            if args and args[0] == "merge" and "--no-ff" in args:
                merge_calls.append(args)
            return real_in_repo(repo, *args)

        with mock.patch.object(gitcmd, "in_repo", spying_in_repo):
            outcome = self.pull()

        self.assertEqual(
            outcome, "pulled",
            "предпосылка теста: подтяжка обязана состояться (AC-4)")
        self.assertEqual(
            len(merge_calls), 1,
            f"ожидался ровно один git merge --no-ff, получено: {merge_calls}")
        merge_source = merge_calls[0][2]  # ("merge", "--no-ff", <source>, ...)
        self.assertNotEqual(
            merge_source, config.MAIN_BRANCH,
            f"merge обязан идти НЕ из локального config.MAIN_BRANCH "
            f"({config.MAIN_BRANCH!r}) — аргумент merge: {merge_source!r}")
        merged_file = self.worktree_file(UPSTREAM_MARKER_REL)
        self.assertTrue(
            merged_file.exists(),
            "результат merge обязан нести файл, существующий ТОЛЬКО в "
            "main артели на origin — его отсутствие значит, что слился "
            "локальный (не сдвинутый) пин")


if __name__ == "__main__":
    import unittest
    unittest.main()
