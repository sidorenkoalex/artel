"""Приёмочные тесты AC-1, AC-2, AC-5 (SPEC 01M1SC3Y20YBTTJVQDJBF2NDQW):
идемпотентность `workspace.ensure`/`on_task_branch`/`remove` не зависит
от символических ссылок в пути worktree.

Красен до реализации: `workspace._registered` сегодня сравнивает
`str(wt_path)` с сырыми строками `git worktree list --porcelain` без
`Path.resolve()` ни с одной из сторон (orchestrator/workspace.py:38-39) —
когда регистрация случилась под путём, отличающимся от `path(task_id)`
только заменой сегмента на символическую ссылку, строки не совпадают, и
`ensure`/`on_task_branch`/`remove` ведут себя так, будто worktree вовсе
не зарегистрирован (в точности первый боевой прогон канарейки v2 05.09,
«Контекст» SPEC).

Настоящий git (по образцу `tests/test_workspace.py::RealGitWorkspaceTest`):
сама суть модуля — операции `git worktree`, подменять их заглушками
нечем проверять. Фикстура символической ссылки построена и проверена
эмпирически на этой машине: `git worktree add <алиас>/<id> ветка`
регистрирует в `git worktree list --porcelain` РЕАЛЬНЫЙ (разрешённый)
путь, а не тот, что был передан аргументом — тот же класс расхождения,
что даёт macOS `/var` (символическая ссылка) vs `/private/var`
(реальный каталог) в `tempfile.mkdtemp()`.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, gitcmd, store, workspace  # noqa: E402
from tests.sandbox import capture, resilient_tmp_cleanup  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]


class SymlinkRegisteredWorktreeTest(unittest.TestCase):
    """Worktree задачи зарегистрирован в git под путём, где корень
    worktree — символическая ссылка на другой реальный каталог;
    `path(task_id)` (то, что строит и с чем сравнивает код) остаётся
    НЕРАЗРЕШЁННЫМ алиас-путём — ровно предпосылка AC-1/AC-2/AC-5."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        # resolve(): без этого сам `self.root` уже нёс бы /var-символьную
        # ссылку macOS — предпосылка теста требует ЕДИНСТВЕННОЙ,
        # управляемой самим тестом символической ссылки, а не случайной
        # второй от временного каталога ОС.
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        # Один сегмент пути — символическая ссылка на ДРУГОЙ реальный
        # каталог (не просто "тот же каталог под другим именем"):
        # проверено эмпирически на этой машине, что `git worktree add
        # <alias>/<id> ветка` заносит в `git worktree list --porcelain`
        # РАЗРЕШЁННЫЙ путь (через `real_target`), а не переданный алиас.
        real_target = self.root / "_real_worktrees_target"
        real_target.mkdir()
        alias_worktrees = self.root / ".artel" / "worktrees"
        alias_worktrees.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(real_target, alias_worktrees)
        self.real_target = real_target

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("WORKTREES", alias_worktrees),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        title = "Символьная ссылка в пути worktree"
        self.branch = f"task/{self.TASK.lower()}-{catalog.slugify(title)}"
        store.insert_task(store.db(), self.TASK, title, "spec_writing",
                          self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        # Регистрируем worktree ЗАРАНЕЕ, напрямую через git (не через
        # `workspace.ensure` — фикстура не должна зависеть от кода,
        # который тестируется): тот же эффект, что первый вызов `ensure`
        # внутри эфемерного клона канарейки до попадания в символическую
        # ссылку в её собственном временном каталоге.
        self.query_path = workspace.path(self.TASK)  # алиас, НЕразрешённый
        self.git("worktree", "add", "-b", self.branch, str(self.query_path))
        self.real_registered_path = real_target / self.TASK

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res

    capture = staticmethod(capture)

    def worktree_list(self) -> str:
        return self.git("worktree", "list", "--porcelain").stdout

    def test_ac1_second_ensure_call_does_not_invoke_worktree_add(self):
        """Второй (и первый) вызов `ensure` для задачи, чей worktree уже
        зарегистрирован под алиас-путём, отдаёт тот же путь без ошибки и
        ни разу не зовёт `git worktree add`.

        Ловит мутацию: если `_registered` продолжает сравнивать
        `str(wt_path)` с сырыми строками `registered_paths()` без
        `Path.resolve()` хотя бы с одной стороны, сравнение не находит
        совпадения — `ensure` решает, что worktree не зарегистрирован, и
        зовёт `git worktree add` поверх уже занятого каталога (тест
        поймает это по появлению `("worktree", "add", ...)` среди
        перехваченных вызовов `gitcmd.git`).
        """
        real_git = gitcmd.git
        calls = []

        def spy_git(*args):
            calls.append(args)
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=spy_git):
            first_path, first_error = workspace.ensure(self.TASK, self.branch)
            second_path, second_error = workspace.ensure(self.TASK, self.branch)

        self.assertEqual(first_path, self.query_path)
        self.assertIsNone(first_error)
        self.assertEqual(second_path, self.query_path)
        self.assertIsNone(second_error)
        add_calls = [c for c in calls if c[:2] == ("worktree", "add")]
        self.assertEqual(
            add_calls, [],
            "ensure позвал git worktree add на уже зарегистрированный "
            "(под символической ссылкой) путь")

    def test_ac5_repeated_call_survives_symlinked_registration_without_extra_worktree(self):
        """Прогон БЕЗ подмены `gitcmd.git` (настоящий git от начала до
        конца): два подряд вызова `ensure` не падают и не плодят вторую
        запись `git worktree list` для той же задачи.

        Ловит мутацию: без `Path.resolve()` второй `ensure` реально
        зовёт `git worktree add` на каталог, который уже существует и
        занят другим worktree, — команда отказывает (rc != 0), и
        `second_error` перестаёт быть `None`; либо (при менее строгой
        поломке) в `git worktree list` появляется вторая запись на тот же
        `real_registered_path` под слегка другим представлением пути.
        """
        first_path, first_error = workspace.ensure(self.TASK, self.branch)
        second_path, second_error = workspace.ensure(self.TASK, self.branch)

        self.assertIsNone(first_error)
        self.assertIsNone(second_error)
        self.assertEqual(first_path, second_path)
        listing = self.worktree_list()
        self.assertEqual(listing.count(str(self.real_registered_path)), 1)

    def test_ac2_on_task_branch_and_remove_use_resolved_paths(self):
        """`on_task_branch`/`remove` (общая с `ensure` функция `_registered`)
        тоже обязаны узнавать worktree, зарегистрированный под алиас-путём
        — не только `ensure`.

        Ловит мутацию: если `_registered` не резолвит символическую
        ссылку, `on_task_branch` вернёт `None` (решит, что worktree ещё
        не заведён) вместо `True`, а `remove` отчитается «не найден —
        нечего убирать» вместо того, чтобы реально вызвать `git worktree
        remove` и убрать запись из `git worktree list`.
        """
        on_branch = workspace.on_task_branch(self.TASK, self.branch)
        self.assertTrue(on_branch)

        note = workspace.remove(self.TASK)

        self.assertNotIn("не найден", note)
        self.assertIn(str(self.query_path), note)
        self.assertNotIn(str(self.real_registered_path), self.worktree_list())


if __name__ == "__main__":
    unittest.main()
