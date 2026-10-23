"""Команда `prune`: вид «бесхозные каталоги .artel/worktrees» — план и
удаление каталогов, которые не носят имя незакрытой задачи и не
зарегистрированы рабочими копиями ни главной копии, ни клона артели.

Группа: долгоживущий
Красен до реализации: `prune.cmd_prune` не смотрит в `config.WORKTREES` — строк «каталог .artel/worktrees/<имя> … будет удалён | удалён», «…: не удалён — …» и «каталоги .artel/worktrees: пропущено — git worktree list не ответил» нет, бесхозные каталоги переживают `--execute`, а при сбое перечня печатается «нечего убирать» (AC-4, AC-5, AC-6). Методы AC-7 зелены и до реализации — они держат «пустой вид не зовёт git и не печатает строки» и прежнее «нечего убирать», которые реализация обязана не сломать.

Планка провалидирована временным стабом вида в `orchestrator/prune.py` (все методы зелёные, стаб удалён, не закоммичен).

Связка «`prune.cmd_prune` — настоящий git главной копии и клона артели —
файловая система» (`tests.sandbox.RealGitSandbox`): корень песочницы —
главная копия пульта, клон артели — отдельный настоящий репозиторий на его
месте `config.PROJECTS/artel/repo` (`ARTEL_CLONE_IS_ROOT = False`: иначе
клон — ссылка на корень, и два перечня неразличимы). Зарегистрированные
рабочие копии заводятся настоящим `git worktree add` внутри
`config.WORKTREES`. Сбой перечня и шпион вызовов — подмена запуска git
(`gitcmd.git`, через него идёт и `gitcmd.in_repo` с `-C <путь>`): на
`worktree list` нужного репозитория подмена отвечает ненулевым кодом,
остальные вызовы уходят в настоящий git.

Имена каталогов, состояние незакрытой задачи и число файлов порождаются
при каждом запуске от зерна; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, prune, store
from tests.sandbox import RealGitSandbox

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
OPEN_STATES = ("in_dev", "review", "tests_writing", "escalated", "merge_gate")
SKIP_LINE = "каталоги .artel/worktrees: пропущено — git worktree list не ответил"
NOTHING = "нечего убирать"
KIND_MARK = ".artel/worktrees"


def plan_line(name: str, count: int) -> str:
    return f"  каталог .artel/worktrees/{name} ({count} файлов) будет удалён"


def done_line(name: str, count: int) -> str:
    return f"  каталог .artel/worktrees/{name} ({count} файлов) удалён"


def failure_prefix(name: str) -> str:
    return f"  каталог .artel/worktrees/{name}: не удалён — "


def is_worktree_list(args) -> bool:
    words = [str(a) for a in args]
    return "worktree" in words and "list" in words


def git_repo_of(args) -> Path:
    """Репозиторий вызова git: `-C <путь>` либо корень пульта (`gitcmd.git`
    без `-C` работает в `config.ROOT`)."""
    words = [str(a) for a in args]
    if len(words) >= 2 and words[0] == "-C":
        return Path(words[1]).resolve()
    return Path(config.ROOT).resolve()


def tree_listing(path: Path) -> set:
    """Все пути под `path`, без перехода по символическим ссылкам."""
    found = set()
    for dirpath, dirnames, filenames in os.walk(path):
        for name in dirnames + filenames:
            found.add(os.path.relpath(os.path.join(dirpath, name), path))
    return found


class WorktreesSandbox(RealGitSandbox):
    """Главная копия — корень песочницы; клон артели — свой репозиторий с
    одним коммитом; `config.WORKTREES` заполняет сценарий."""

    ARTEL_CLONE_IS_ROOT = False

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.used = set()
        self.clone = config.PROJECTS / config.DEFAULT_TARGET / "repo"
        self.clone.parent.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", config.MAIN_BRANCH, str(self.clone))
        self.git("-C", str(self.clone), "config", "user.email",
                 "artel@example.invalid")
        self.git("-C", str(self.clone), "config", "user.name", "artel tests")
        (self.clone / "clone.txt").write_text("клон\n", encoding="utf-8")
        self.git("-C", str(self.clone), "add", "clone.txt")
        self.git("-C", str(self.clone), "commit", "-q", "-m", "init")
        self.wt = Path(config.WORKTREES)

    def ctx(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def unique(self, make) -> str:
        while True:
            name = make()
            if name not in self.used:
                self.used.add(name)
                return name

    def task_id(self) -> str:
        return self.unique(lambda: "".join(
            self.rng.choice(ULID_ALPHABET) for _ in range(26)))

    def orphan_name(self) -> str:
        """Имя бесхозного каталога: id задачи, которой нет в БД, старый
        `Tnnn` или произвольное имя."""
        form = self.rng.choice(("ulid", "tnnn", "slug"))
        if form == "ulid":
            return self.task_id()
        if form == "tnnn":
            return self.unique(lambda: f"T{self.rng.randint(1, 999):03d}")
        return self.unique(lambda: "old-" + "".join(
            self.rng.choice("abcdefxyz0123") for _ in range(8)))

    def orphan(self, name: str | None = None) -> tuple[str, int]:
        """Бесхозный каталог без `.git` со случайным числом файлов, часть —
        во вложенном подкаталоге. Возвращает (имя, число файлов)."""
        name = name or self.orphan_name()
        root = self.wt / name
        nested = root / "sub" / "deep"
        nested.mkdir(parents=True)
        count = self.rng.randint(1, 6)
        for i in range(count):
            where = root if i % 2 == 0 else nested
            (where / f"f{i}.txt").write_text(f"{self.seed}-{i}\n",
                                             encoding="utf-8")
        return name, count

    def open_task_dir(self) -> str:
        task_id = self.task_id()
        store.insert_task(self.conn, task_id, "Задача",
                          self.rng.choice(OPEN_STATES),
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          25.0)
        path = self.wt / task_id
        path.mkdir(parents=True)
        (path / "work.txt").write_text("работа\n", encoding="utf-8")
        return task_id

    def main_registered(self) -> str:
        name = self.orphan_name()
        self.wt.mkdir(parents=True, exist_ok=True)
        self.git("worktree", "add", "-q", "--detach", str(self.wt / name))
        return name

    def clone_registered(self) -> str:
        name = self.orphan_name()
        self.wt.mkdir(parents=True, exist_ok=True)
        self.git("-C", str(self.clone), "worktree", "add", "-q", "--detach",
                 str(self.wt / name))
        return name

    def symlinked(self) -> tuple[str, Path]:
        """Символическая ссылка в `WORKTREES` на каталог вне него."""
        target = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        (target / "keep.txt").write_text("цель\n", encoding="utf-8")
        name = self.orphan_name()
        self.wt.mkdir(parents=True, exist_ok=True)
        (self.wt / name).symlink_to(target, target_is_directory=True)
        return name, target

    def run_prune(self, execute: bool, fail_repo: Path | None = None):
        """`prune.cmd_prune(execute)`; `fail_repo` — репозиторий, чей
        `worktree list` отвечает сбоем. Возвращает (вывод stdout+stderr,
        аргументы всех вызовов git)."""
        real_git = prune.gitcmd.git
        calls = []
        failing = Path(fail_repo).resolve() if fail_repo is not None else None
        rc = self.rng.randint(1, 128)

        def spy(*args):
            calls.append(args)
            if (failing is not None and is_worktree_list(args)
                    and git_repo_of(args) == failing):
                return subprocess.CompletedProcess(
                    list(args), rc, "", "fatal: подменённый сбой worktree list")
            return real_git(*args)

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(prune.gitcmd, "git", side_effect=spy), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            prune.cmd_prune(execute=execute)
        return out.getvalue() + err.getvalue(), calls

    def assert_kept(self, open_id, main_wt, clone_wt, link, link_target,
                    output: str) -> None:
        self.assertTrue((self.wt / open_id / "work.txt").is_file(),
                        self.ctx(f"каталог незакрытой задачи удалён\n{output}"))
        self.assertTrue((self.wt / main_wt / "marker.txt").is_file(),
                        self.ctx(f"рабочая копия главной копии удалена\n{output}"))
        self.assertTrue((self.wt / main_wt / ".git").exists(), self.ctx(output))
        self.assertTrue((self.wt / clone_wt / "clone.txt").is_file(),
                        self.ctx(f"рабочая копия клона артели удалена\n{output}"))
        self.assertTrue((self.wt / clone_wt / ".git").exists(), self.ctx(output))
        self.assertTrue((self.wt / link).is_symlink(),
                        self.ctx(f"символическая ссылка удалена\n{output}"))
        self.assertTrue((link_target / "keep.txt").is_file(),
                        self.ctx(f"цель ссылки тронута\n{output}"))


class OrphanWorktreesPlanAndExecuteTest(WorktreesSandbox):

    def test_ac4_orphan_planned_then_removed_protected_entries_kept(self):
        """План называет бесхозный каталог и ничего не удаляет; `--execute` удаляет только его.

        В `config.WORKTREES`: 1–3 бесхозных каталога без `.git` со
        случайным числом файлов; каталог с именем незакрытой задачи;
        рабочая копия, зарегистрированная в главной копии; рабочая копия,
        зарегистрированная в клоне артели; символическая ссылка на каталог
        вне `WORKTREES`. `prune` без `--execute` печатает строку
        «  каталог .artel/worktrees/<имя> (<N> файлов) будет удалён» на
        каждый бесхозный каталог, дерево `WORKTREES` не меняется. `prune
        --execute` печатает «… (<N> файлов) удалён», бесхозных каталогов
        нет; остальные четыре элемента целы при обоих прогонах.

        Ловит мутацию: вид сверяет только перечень клона артели (как
        `workspace.registered_paths()` без аргумента) — рабочая копия
        главной копии удаляется; либо пропускает проверку имени задачи —
        каталог незакрытой задачи удаляется; либо фильтр «каталог» берёт
        `is_dir()` без `is_symlink()` — ссылка попадает в план и удаляется;
        либо план исполняет удаление — после прогона без `--execute`
        бесхозного каталога нет; либо N считается без вложенных файлов —
        строка с неверным числом.
        """
        orphans = [self.orphan() for _ in range(self.rng.randint(1, 3))]
        open_id = self.open_task_dir()
        main_wt = self.main_registered()
        clone_wt = self.clone_registered()
        link, link_target = self.symlinked()
        kept = (open_id, main_wt, clone_wt, link, link_target)
        before = tree_listing(self.wt)

        output, _calls = self.run_prune(execute=False)
        lines = output.splitlines()
        for name, count in orphans:
            self.assertIn(plan_line(name, count), lines, self.ctx(output))
        self.assertEqual(tree_listing(self.wt), before,
                         self.ctx(f"план что-то удалил\n{output}"))
        self.assert_kept(*kept, output)

        output, _calls = self.run_prune(execute=True)
        lines = output.splitlines()
        for name, count in orphans:
            self.assertIn(done_line(name, count), lines, self.ctx(output))
            self.assertFalse(os.path.lexists(self.wt / name),
                             self.ctx(f"{name} не удалён\n{output}"))
        self.assert_kept(*kept, output)


class OrphanWorktreeRemovalFailureTest(WorktreesSandbox):

    def test_ac5_one_removal_failure_reported_others_removed(self):
        """Сбой удаления одного каталога — строка «не удалён — <причина>», остальные удалены.

        Бесхозных каталогов 2–4; в одном подкаталог закрыт на запись
        (`chmod 0o500`), так что удаление файла в нём отказывает. `prune
        --execute` печатает строку «  каталог .artel/worktrees/<имя>: не
        удалён — <причина>» с непустой причиной, все прочие бесхозные
        каталоги удалены.

        Ловит мутацию: строки сбоя оставлены прежнего формата
        `_remove_dirs` («<метка> не удалён: <ошибка>») — строки
        «…: не удалён — …» нет; либо сбой одного каталога прерывает цикл
        (исключение или `break`) — каталоги после него не удалены.
        """
        orphans = [self.orphan() for _ in range(self.rng.randint(2, 4))]
        bad, _count = self.rng.choice(orphans)
        locked = self.wt / bad / "sub"
        locked.chmod(0o500)
        self.addCleanup(locked.chmod, 0o700)

        output, _calls = self.run_prune(execute=True)
        prefix = failure_prefix(bad)
        failures = [line for line in output.splitlines()
                    if line.startswith(prefix)]
        self.assertTrue(failures, self.ctx(f"нет строки сбоя\n{output}"))
        self.assertTrue(failures[0][len(prefix):].strip(),
                        self.ctx(f"причина пуста: {failures[0]!r}"))
        for name, _n in orphans:
            if name != bad:
                self.assertFalse(os.path.lexists(self.wt / name),
                                 self.ctx(f"{name} не удалён после сбоя "
                                          f"{bad}\n{output}"))


class WorktreeListFailureTest(WorktreesSandbox):

    def test_ac6_any_unreceived_list_skips_whole_kind(self):
        """Не получен любой из двух перечней — вид пропущен целиком, строка «пропущено».

        В `WORKTREES`: бесхозный каталог, рабочая копия главной копии и
        рабочая копия клона артели. Два случая: `worktree list` главной
        копии отвечает сбоем (каталог клона артели зарегистрирован в
        полученном перечне) и `worktree list` клона артели отвечает сбоем
        (каталог главной копии зарегистрирован в полученном перечне). В
        каждом — план и `--execute`: ни один каталог вида не удалён,
        напечатано «каталоги .artel/worktrees: пропущено — git worktree
        list не ответил», «нечего убирать» нет.

        Ловит мутацию: пропуск только при обоих неполученных перечнях
        (сбой читается как пустой перечень, как у
        `workspace.registered_paths`) — в первом случае удаляются
        бесхозный каталог и рабочая копия главной копии, во втором —
        бесхозный каталог и рабочая копия клона, строки «пропущено» нет;
        либо при пропуске вид пуст без строки — печатается «нечего убирать».
        """
        orphan, _count = self.orphan()
        main_wt = self.main_registered()
        clone_wt = self.clone_registered()
        names = (orphan, main_wt, clone_wt)
        cases = (("главная копия", config.ROOT),
                 ("клон артели", self.clone))
        for label, failing in cases:
            for execute in (False, True):
                with self.subTest(сбой=label, execute=execute):
                    output, calls = self.run_prune(execute=execute,
                                                   fail_repo=failing)
                    self.assertTrue(
                        any(is_worktree_list(a) for a in calls),
                        self.ctx(f"{label}: worktree list не вызван: {calls}"))
                    for name in names:
                        self.assertTrue(
                            (self.wt / name).is_dir(),
                            self.ctx(f"{label}: {name} удалён\n{output}"))
                    self.assertIn(SKIP_LINE, output, self.ctx(output))
                    self.assertNotIn(NOTHING, output, self.ctx(output))


class EmptyWorktreesKindTest(WorktreesSandbox):

    def assert_kind_silent(self, label: str) -> None:
        for execute in (False, True):
            output, calls = self.run_prune(execute=execute)
            listed = [a for a in calls if is_worktree_list(a)]
            self.assertEqual(listed, [], self.ctx(
                f"{label}, execute={execute}: worktree list вызван: {listed}"))
            self.assertNotIn(KIND_MARK, output, self.ctx(
                f"{label}, execute={execute}: строка вида\n{output}"))

    def test_ac7_no_worktrees_dir_or_no_candidates_calls_no_git(self):
        """Нет `WORKTREES` или нет кандидатов по имени и типу — git не зовётся, строки вида нет.

        Случай 1: каталога `config.WORKTREES` нет. Случай 2: в нём только
        каталоги с именами незакрытых задач, символические ссылки на
        каталоги и обычные файлы (случайное число каждого). В обоих — план
        и `--execute`: шпион запуска git не видит ни одного `worktree
        list`, в выводе нет `.artel/worktrees`; во втором случае элементы
        целы.

        Ловит мутацию: перечни `git worktree list` запрашиваются до отбора
        по имени и типу — шпион видит вызов; либо при отсутствии каталога
        или кандидатов печатается строка вида (заголовок или «пропущено»),
        либо `iterdir()` по отсутствующему каталогу роняет команду
        `FileNotFoundError`.
        """
        self.assertFalse(os.path.lexists(self.wt), self.ctx())
        self.assert_kind_silent("каталога нет")

        open_ids = [self.open_task_dir()
                    for _ in range(self.rng.randint(1, 3))]
        links = [self.symlinked() for _ in range(self.rng.randint(1, 2))]
        files = []
        for _ in range(self.rng.randint(1, 2)):
            name = self.orphan_name()
            (self.wt / name).write_text("файл\n", encoding="utf-8")
            files.append(name)
        self.assert_kind_silent("нет кандидатов")
        for task_id in open_ids:
            self.assertTrue((self.wt / task_id / "work.txt").is_file(),
                            self.ctx(task_id))
        for name, target in links:
            self.assertTrue((self.wt / name).is_symlink(), self.ctx(name))
            self.assertTrue((target / "keep.txt").is_file(), self.ctx(name))
        for name in files:
            self.assertTrue((self.wt / name).is_file(), self.ctx(name))

    def test_ac7_bare_sandbox_still_says_nothing_to_clean(self):
        """Песочница без логов и каталогов — `prune` печатает «нечего убирать».

        Ни `.artel/logs/`, ни `config.WORKTREES`, ни прочих кандидатов;
        план и `--execute` оба печатают «нечего убирать».

        Ловит мутацию: «нечего убирать» подавляется не только строкой
        «пропущено», но и пустым видом (например, флаг «вид проверен»
        поставлен при отсутствии каталога) — строки «нечего убирать» нет.
        """
        self.assertFalse(os.path.lexists(self.wt), self.ctx())
        for execute in (False, True):
            output, _calls = self.run_prune(execute=execute)
            self.assertIn(NOTHING, output,
                          self.ctx(f"execute={execute}\n{output}"))


if __name__ == "__main__":
    unittest.main()
