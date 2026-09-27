"""AC-2 (SPEC 01M3H3K73XBMJMD0EPXZX6HYY9): офлайн-сверка окружений и
команд шагов Codex и Claude — `python3`, `pytest`, `git` и `gh` после
оболочки входа резолвятся в одинаковые пути, а PATH шага Codex
соответствует PATH, собранному `role_env`.

Красен до реализации: `python3` после оболочки входа шага Codex
резолвится в системный `/usr/bin/python3` (его ставит первым
`path_helper` из `/etc/zprofile`), а в шаге Claude — в интерпретатор
пульта из PATH `role_env`; PATH шага Codex после оболочки входа
начинается системными каталогами, а каталоги `role_env` уезжают в хвост
(воспроизведено этим же прогоном до реализации).

Чтение критерия, зафиксированное планкой: «резолвятся в одинаковые пути»
— одинаковые с тем, что видит шаг Claude, то есть с резолвом по PATH,
который собрал `role_env` (требование 2 SPEC теми же словами: «резолвятся
в те же пути, что в шаге Claude», и заголовок SPEC — «как у шага
Claude»). Поэтому эталон снимается резолвом по PATH окружения шага
Claude, а испытуемое — тем, что отвечает голый вызов инструмента ПОСЛЕ
оболочки входа в окружении шага Codex. Требовать сверх этого, чтобы
оболочка входа в окружении шага Claude тоже отдавала тот же путь, планка
не вправе: решение задачи может быть провайдерским (ключ окружения или
файл дома роли Codex), и такое требование запрещало бы его без всякого
основания в критерии.
"""
import os
import shutil
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import providers  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402

from _step_env import PARITY_TOOLS, ProviderStepEnvSandbox  # noqa: E402


class CodexClaudeStepEnvParityTest(ProviderStepEnvSandbox):

    def test_ac2_declared_tools_resolve_to_the_same_paths_as_in_a_claude_step(self):
        """Собраны окружения и команды обоих шагов; каждый из четырёх
        инструментов критерия после оболочки входа шага Codex резолвится
        ровно в тот путь, в который его резолвит PATH шага Claude.

        Ловит мутацию: паритет сделан только для интерпретатора (например
        PATH дописан одним каталогом venv), а остальные объявленные
        инструменты по-прежнему берутся из системных каталогов, которые
        оболочка входа ставит первыми — сверка по `pytest`/`git`/`gh`
        откажет, назвав инструмент.
        """
        codex_env = self.step_env(codex_provider.CLI_NAME)
        claude_env = self.step_env(providers.DEFAULT_PROVIDER)

        # Команды обоих шагов тоже собираются: критерий говорит «собирает
        # окружения И команды», и несобираемая команда означала бы, что
        # сверять нечего.
        for name in (codex_provider.CLI_NAME, providers.DEFAULT_PROVIDER):
            cmd = self.step_command(name)
            self.assertTrue(cmd and Path(cmd[0]).is_absolute(),
                            f"команда шага {name} не собралась: {cmd}")

        for tool in PARITY_TOOLS:
            with self.subTest(tool=tool):
                expected = shutil.which(tool, path=claude_env["PATH"])
                self.assertIsNotNone(
                    expected,
                    f"{tool} не резолвится PATH шага Claude — предпосылка "
                    f"критерия не воспроизведена")
                self.assertEqual(
                    expected, self.resolved_after_login_shell(codex_env, tool),
                    f"PATH после оболочки входа: "
                    f"{self.path_after_login_shell(codex_env)}")

    def test_ac2_path_after_the_login_shell_matches_the_one_role_env_built(self):
        """PATH, который видит команда шага Codex после оболочки входа,
        начинается ровно каталогами PATH, собранного `role_env`, — в том
        же порядке и без вставок перед ними.

        Ловит мутацию: каталоги роли лишь ДОПИСАНЫ к PATH оболочки входа
        (`PATH=$PATH:<каталоги роли>` вместо устранения самой перезаписи) —
        порядок каталогов не совпадёт: первыми останутся системные, и
        сравнение префикса откажет.
        """
        codex_env = self.step_env(codex_provider.CLI_NAME)

        role_entries = codex_env["PATH"].split(os.pathsep)
        observed = self.path_after_login_shell(codex_env).split(os.pathsep)

        self.assertEqual(role_entries, observed[:len(role_entries)],
                         f"PATH роли: {codex_env['PATH']!r}; после оболочки "
                         f"входа: {os.pathsep.join(observed)!r}")


if __name__ == "__main__":
    unittest.main()
