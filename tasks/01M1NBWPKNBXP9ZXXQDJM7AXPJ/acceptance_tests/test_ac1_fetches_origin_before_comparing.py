"""AC-1 (tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md): `fsm._pull_main_or_
escalate` перед вызовом `gitcmd.commits_behind` делает `git fetch origin
<MAIN_BRANCH>` и сравнивает отставание ветки задачи относительно
`FETCH_HEAD`/`origin/<MAIN_BRANCH>`, а не относительно локального
`config.MAIN_BRANCH`.

Источник — tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md, «Критерии
приёмки», AC-1.

Красен до реализации: сегодня `_pull_main_or_escalate` зовёт
`gitcmd.commits_behind(branch)` без предварительного `fetch` и без
`base` — сравнение идёт с ЛОКАЛЬНЫМ `config.MAIN_BRANCH` (пином,
который не двигается между мержами, SPEC «Контекст»). В сценарии этого
теста (ветка задачи форкнута ДО расхождения, origin ушёл вперёд,
локальный пин остался на месте) это значит: ни разу `git fetch origin
...` не вызывается, а исход — `"fresh"`, не `"pulled"`. Проверено
прогоном на немодифицированном коде при подготовке файла: список
перехваченных вызовов `gitcmd.git` не содержит `fetch`, `outcome ==
"fresh"`.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import OriginDivergedSandbox  # noqa: E402
from orchestrator import config, gitcmd  # noqa: E402


class Ac1FetchesOriginBeforeComparingTest(OriginDivergedSandbox):

    def test_ac1_fetch_origin_precedes_and_drives_freshness_decision(self):
        """Origin ушёл вперёд локального пина; ветка задачи форкнута ДО
        расхождения (совпадает с пином). Среди РЕАЛЬНЫХ git-вызовов,
        сделанных `_pull_main_or_escalate`, обязан найтись `git fetch
        ... origin <MAIN_BRANCH>`, и итог сверки — `"pulled"`, а не
        `"fresh"` (иначе fetch случился впустую — сверка всё равно
        читала бы старое состояние, не его результат).

        Ловит мутацию: разработчик полагается на уже существующий
        (возможно устаревший) remote-tracking `origin/<MAIN_BRANCH>` без
        собственного `fetch` перед сверкой — тест не увидит вызова
        `fetch` среди перехваченных команд и покраснеет по этой причине
        отдельно от исхода сверки.
        """
        self.advance_origin_only()
        real_git = gitcmd.git
        calls = []

        def spying_git(*args):
            calls.append(args)
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", spying_git):
            outcome = self.pull()

        fetch_calls = [c for c in calls
                      if c and c[0] == "fetch" and "origin" in c
                      and config.MAIN_BRANCH in c]
        self.assertTrue(
            fetch_calls,
            f"ожидался git fetch origin {config.MAIN_BRANCH} среди "
            f"вызовов gitcmd.git, получено: {calls}")
        self.assertEqual(
            outcome, "pulled",
            "fetch без использования его результата в сверке — не то же "
            "самое, что сверка от origin (AC-1 требует и то, и другое)")


if __name__ == "__main__":
    import unittest
    unittest.main()
