"""Приёмочные тесты 01M297HFSKV3GVZJ9YF20FZEZE (AC-1..AC-3): база НОВОЙ
ветки задачи в `workspace.ensure` — `origin/<config.MAIN_BRANCH>` после
`git fetch origin`, не локальный `config.MAIN_BRANCH`.

Красен до реализации: test_ac1_new_branch_starts_from_origin_main_not_local_main
и test_ac3_fetch_failure_is_a_named_reason_with_no_fallback — сегодняшний
`orchestrator/workspace.py::ensure` заводит свежую ветку задачи командой
`git worktree add -b <branch> <wt_path> <config.MAIN_BRANCH>` — без
единого `git fetch origin` где-либо в функции (см. тело `ensure`, ветка
`else` при отсутствующей в git ветке задачи): AC-1 требует базы
`origin/main` после fetch (тест видит базу — локальный main), AC-3 —
именованного отказа без отката на локальный main при отказе fetch (тест
видит `error is None` и заведённую ветку — сегодня `ensure` вообще не
делает fetch, значит не может на нём отказать).

Зелёный с рождения: test_ac2_existing_branch_is_reused_without_needing_origin
— критерий явно требует «путь без изменений», уже реализованное
поведение `ensure` для существующей в git ветки (ветка `if
gitcmd.branch_exists(branch)`) не трогает базу вовсе.

Настоящий git (`_RealGitWorkspaceTest`, тот же приём, что
`tests/test_workspace.py::RealGitWorkspaceTest`): предмет проверки —
результат РЕАЛЬНОГО `git fetch`/`merge-base` относительно РЕАЛЬНОГО
`origin`, заглушкой `gitcmd.git` это не изобразить.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd, workspace  # noqa: E402
from tests.sandbox import resilient_tmp_cleanup  # noqa: E402


class _RealGitWorkspaceTest(unittest.TestCase):
    """`config.ROOT` — настоящий git-репозиторий с одним коммитом на
    `config.MAIN_BRANCH`; ветка задачи ещё не заведена в git."""

    TASK = "T900ORIGINBASE"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        (self.root / "marker.txt").write_text("main\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.wt_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wt_root, ignore_errors=True)

        for attr, value in (("ROOT", self.root), ("WORKTREES", self.wt_root)):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.branch = f"task/{self.TASK.lower()}-origin-base"

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, cwd=None,
           check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    def worktree_list(self) -> str:
        return self.git("worktree", "list", "--porcelain").stdout

    def wt_path(self) -> Path:
        return config.WORKTREES / self.TASK

    def add_real_origin(self) -> None:
        self.origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(self.origin))
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin",
                f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def push_extra_commit_to_origin_only(self) -> str:
        """Коммит, которого нет в локальном `config.MAIN_BRANCH` этого
        `config.ROOT` — попадает в `origin` через ОТДЕЛЬНЫЙ клон, тем же
        приёмом, каким Оператор мог бы запушить документный коммит прямо
        в origin в обход локального пина (инцидент 11.09 из «Контекста»
        SPEC). Возвращает sha головы origin после пуша."""
        clone_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, clone_dir, ignore_errors=True)
        self.git("clone", "-q", str(self.origin), str(clone_dir))
        self.git("config", "user.email", "artel-tests@example.invalid",
                 cwd=clone_dir)
        self.git("config", "user.name", "artel tests", cwd=clone_dir)
        (clone_dir / "origin-only.txt").write_text("y\n", encoding="utf-8")
        self.git("add", "-A", cwd=clone_dir)
        self.git("commit", "-q", "-m", "прямой коммит в origin", cwd=clone_dir)
        self.git("push", "-q", "origin", config.MAIN_BRANCH, cwd=clone_dir)
        return self.git("rev-parse", "HEAD", cwd=clone_dir).stdout.strip()


class EnsureNewBranchOriginBaseTest(_RealGitWorkspaceTest):

    def setUp(self):
        super().setUp()
        self.add_real_origin()

    def test_ac1_new_branch_starts_from_origin_main_not_local_main(self):
        """Локальный `config.MAIN_BRANCH` отстал от `origin/<MAIN_BRANCH>`
        (коммит попал в origin в обход локального пина) — новая ветка
        задачи обязана стартовать от актуального `origin`, не от
        устаревшего локального main.

        Ловит мутацию: база `config.MAIN_BRANCH` без предшествующего `git
        fetch origin <MAIN_BRANCH>` (сегодняшнее поведение `ensure`) —
        новая ветка тогда стартует от устаревшего локального main, и
        `rev-parse HEAD` в свежесозданной ветке не совпадёт с головой
        `origin`, зафиксированной в этом тесте ДО вызова `ensure`.
        """
        origin_sha = self.push_extra_commit_to_origin_only()
        local_main_sha = self.git("rev-parse",
                                  config.MAIN_BRANCH).stdout.strip()
        self.assertNotEqual(
            origin_sha, local_main_sha,
            "предпосылка теста: origin обязан уйти вперёд локального main")

        path, error = workspace.ensure(self.TASK, self.branch)

        self.assertIsNone(error)
        branch_sha = self.git("-C", str(path), "rev-parse",
                              "HEAD").stdout.strip()
        self.assertEqual(
            branch_sha, origin_sha,
            "новая ветка задачи обязана стартовать от origin/"
            f"{config.MAIN_BRANCH}, а не от отставшего локального "
            f"{config.MAIN_BRANCH}")


class EnsureExistingBranchSkipsFetchTest(_RealGitWorkspaceTest):

    def test_ac2_existing_branch_is_reused_without_needing_origin(self):
        """Ветка задачи уже существует в git (например, шаг роли уже
        закоммитил в неё раньше) — `ensure` заводит worktree НА неё, путь
        не должен обращаться к базе вовсе: в этом тесте `origin` не
        настроен совсем, поведение остаётся прежним (AC-2, «без изменений»).

        Ловит мутацию: `ensure` начинает БЕЗУСЛОВНО звать `git fetch
        origin <MAIN_BRANCH>` перед проверкой существования ветки — без
        настроенного `origin` fetch отказывает, и функция либо вернула бы
        именованную ошибку, либо (что тоже неверно) откатилась на базу,
        которой требование 1 для этого пути не предусматривает, — обе
        ветки исхода нарушают «путь без изменений».
        """
        self.git("branch", self.branch, config.MAIN_BRANCH)

        path, error = workspace.ensure(self.TASK, self.branch)

        self.assertIsNone(error)
        branch_res = self.git("-C", str(path), "rev-parse",
                              "--abbrev-ref", "HEAD")
        self.assertEqual(branch_res.stdout.strip(), self.branch)


class EnsureFetchFailureTest(_RealGitWorkspaceTest):

    def setUp(self):
        super().setUp()
        # origin настроен, но указывает в никуда — `git fetch` отказывает
        # по-настоящему, не заглушкой.
        self.git("remote", "add", "origin",
                str(self.root / "no-such-origin-here"))

    def test_ac3_fetch_failure_is_a_named_reason_with_no_fallback(self):
        """`git fetch origin <MAIN_BRANCH>` отказывает (origin недоступен)
        — `ensure` обязана вернуть именованную причину «база ветки
        недоступна: fetch origin не удался» (или содержащую эту
        формулировку) и НЕ создать ни worktree, ни ветку — в частности,
        НЕ откатиться молча на локальный `config.MAIN_BRANCH`.

        Ловит мутацию: отказ `git fetch origin` молча деградирует до
        прежнего поведения (заведение от локального `config.MAIN_BRANCH`)
        — тогда `error` был бы `None`, а ветка/worktree — заведены, хотя
        AC-3 явно запрещает именно этот откат.
        """
        path, error = workspace.ensure(self.TASK, self.branch)

        self.assertIsNotNone(error)
        self.assertIn("база ветки недоступна: fetch origin не удался", error)
        self.assertNotIn(str(self.wt_path()), self.worktree_list())
        self.assertFalse(
            gitcmd.branch_exists(self.branch),
            "отказ fetch не должен приводить к заведению ветки от "
            "локального main")


if __name__ == "__main__":
    unittest.main()
