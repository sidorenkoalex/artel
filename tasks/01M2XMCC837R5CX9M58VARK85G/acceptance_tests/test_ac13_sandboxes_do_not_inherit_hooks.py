"""AC-13, вторая половина: песочницы и временные репозитории тестов
конфигурацию хуков главной копии не наследуют.

Первая половина AC-13 («полная сюита `tests/` зелёная, включая
`tests/test_gitcmd_*.py`, `tests/test_doctor.py`,
`tests/test_runner_role_model.py`») здесь не переписывается набором-копией:
её проверяет полный прогон на CI и автогейт приёмки — тот же принцип, что
для критерия «поведение не меняется» (skills/test-authoring.md). Планка
фиксирует ровно то, чего полный прогон не поймёт сам: включение хуков в
главной копии не должно протечь в песочницы.

Зелёный с рождения: хуков и `core.hooksPath` сегодня нет вовсе — тест сторожит, чтобы включение (требование 4) не оказалось глобальным.
"""
import subprocess
import unittest

from orchestrator import config
from tests.sandbox import RealGitSandbox

from _hooks import output, run_git


def git_scope_hooks_path(scope: str) -> str:
    """`core.hooksPath` из указанного слоя конфигурации git (`--global`/
    `--system`); пустая строка — в этом слое значения нет."""
    res = subprocess.run(["git", "config", scope, "--get", "core.hooksPath"],
                         capture_output=True, text=True)
    return res.stdout.strip()


class SandboxDoesNotInheritMainCopyHooksTest(RealGitSandbox):

    def test_ac13_temporary_repositories_run_without_the_main_copy_hooks(self):
        """Временный репозиторий песочницы (`tests.sandbox.RealGitSandbox`
        — основа всех тестов, которым нужен настоящий git) не видит ни
        `core.hooksPath`, ни отказа хука: коммит на его ветке main без
        маркера проходит. Ни один слой конфигурации git вне репозитория
        (`--global`, `--system`) значения `core.hooksPath` не несёт.

        Ловит мутацию: включение хуков (требование 4) сделано глобально —
        `git config --global core.hooksPath …` вместо репозиторного, или
        через `init.templateDir` — тогда КАЖДЫЙ временный репозиторий
        тестов унаследовал бы сторожа главной копии, и существующие тесты
        (`tests/test_git_fixation.py`, `tests/test_pin.py` и прочие,
        коммитящие на main песочницы) начали бы упираться в хук: сверка
        глобального слоя и коммит ниже покраснели бы.
        """
        for scope in ("--global", "--system"):
            with self.subTest(scope=scope):
                self.assertEqual(git_scope_hooks_path(scope), "",
                                 f"core.hooksPath задан в слое {scope}")

        local = subprocess.run(["git", "config", "--get", "core.hooksPath"],
                               cwd=self.root, capture_output=True, text=True)
        self.assertEqual(local.stdout.strip(), "",
                         "временный репозиторий унаследовал core.hooksPath")

        (self.root / "marker.txt").write_text("вторая строка\n",
                                              encoding="utf-8")
        run_git(self.root, "add", "marker.txt")
        res = run_git(self.root, "commit", "-q", "-m",
                      f"коммит на {config.MAIN_BRANCH} песочницы",
                      marker=False)

        self.assertEqual(res.returncode, 0, output(res))


if __name__ == "__main__":
    unittest.main()
