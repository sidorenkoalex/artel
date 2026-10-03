"""Общая надстройка планки 01M3Z2DMQRD0BD7AARFVTCVVG8: настоящий git пульта
(`tests.sandbox.RealGitSandbox`) плюс bare `origin`, синхронный с main.

Всё, что здесь есть, — наблюдение за git снаружи (`git rev-parse`,
`git ls-remote`, `git cat-file`), а не вызов внутренних функций пульта:
планка проверяет, ЧТО лежит в `refs/artifacts/<id>` и в `origin`, а не то,
каким узлом пульт туда пишет.
"""
import functools
import io
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (artel, artifact_branch, catalog, ci,  # noqa: E402
                          cleanup, config, fsm, store, workspace)
from tests.sandbox import (RealGitSandbox, capture,  # noqa: E402
                           capture_new_task_id)

TZ_TEXT = """# ТЗ: проверка ссылки документов

Текст ТЗ планки — маркер ТЗ-ПЛАНКИ-01M3Z2DM.

Зоны: orchestrator/store.py
"""
TZ_MARKER = "ТЗ-ПЛАНКИ-01M3Z2DM"
EXTERNAL_TARGET = "extproj"
REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen

FIXTURE_SPEC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: песочница планки

## Контекст

## Требования

## Критерии приёмки

AC-1. Единственный критерий песочницы.

## Не входит
"""

# Имя метода фикстуры собирается форматированием: текстовый разбор
# трассируемости этой планки не должен принять строку фикстуры за тест.
FIXTURE_PLANK = '''"""Фикстура разового файла планки песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_ac{n}_plank_fixture(self):
        """Фикстурный метод {tag}."""
        self.assertEqual(1 + 1, 2)
'''

FIXTURE_LONG_LIVED = '''"""Фикстура долгоживущего файла песочницы.

Группа: долгоживущий
"""
import random
import unittest


class FixtureLongLivedTest(unittest.TestCase):

    def test_ac{n}_long_fixture(self):
        """Фикстурный метод.

        Ловит мутацию: фикстура песочницы — сумма перестаёт совпадать.
        """
        seed = random.randrange(1 << 30)
        self.assertEqual(1 + 1, 2, f"зерно: {{seed}}")
'''

FIXTURE_PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: песочница планки

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


def plank_text(tag: str = "исходный") -> str:
    return FIXTURE_PLANK.format(n=1, tag=tag)


def long_lived_text() -> str:
    return FIXTURE_LONG_LIVED.format(n=1)


def ref_name(task_id: str) -> str:
    return f"refs/artifacts/{task_id}"


def legacy_branch(task_id: str) -> str:
    """Имя прежней ветки документов (`artifact/<id в нижнем регистре>`)."""
    return f"artifact/{task_id.lower()}"


class RefSandbox(RealGitSandbox):
    """Пульт — настоящий git-репозиторий с bare `origin`; `init` выполнен."""

    def setUp(self):
        super().setUp()
        # Прогон планки идёт из шага роли (`ARTEL_ROLE` в окружении), а
        # команды Оператора (`answer`, `zones-extend`) из окружения роли
        # отказывают — сценарий разыгрывает Оператора, маркер снимается.
        role_env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role_env.start()
        self.addCleanup(role_env.stop)
        capture(catalog.cmd_init)
        self.origin = self.add_synced_origin()
        self.conn = store.db()

    # --- заведение задачи --------------------------------------------------

    def new_task(self, title: str = "ссылка документов",
                 target: str | None = None) -> str:
        tz = self.root / ".artel" / "tz-plank.md"
        tz.parent.mkdir(parents=True, exist_ok=True)
        tz.write_text(TZ_TEXT, encoding="utf-8")
        _, task_id = capture_new_task_id(
            functools.partial(catalog.cmd_new, target=target), title, str(tz))
        return task_id

    def declare_external_target(self) -> str:
        """`targets.yaml` песочницы с внешним target `EXTERNAL_TARGET`."""
        config.TARGETS.write_text(
            "targets:\n"
            f"  {EXTERNAL_TARGET}:\n"
            "    forge: github\n"
            f"    url: http://localhost/{EXTERNAL_TARGET}\n"
            f"    base: {config.MAIN_BRANCH}\n"
            f"    token_slot: {EXTERNAL_TARGET}-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n",
            encoding="utf-8")
        return EXTERNAL_TARGET

    def run_cli(self, *argv: str) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            return self.call(artel.main)

    def call(self, fn, *args, **kwargs) -> str:
        """stdout вызова; `sys.exit` команды — текстом в конце, не исключением."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc}")
        return buf.getvalue()

    def row(self, task_id: str):
        return store.get_task(store.db(), task_id)

    def set_row(self, task_id: str, **fields) -> None:
        store.update_task(store.db(), task_id, **fields)

    def seed_docs(self, task_id: str, files: dict, message: str) -> str:
        """Фикстура документов задачи: запись в ссылку тем же узлом записи
        документов, которым пишут команды пульта (`artifact_branch.
        commit_files`); `files` — пути относительно `tasks/<id>/`."""
        sha = artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/{rel}": text
                      for rel, text in files.items()},
            f"{task_id}: {message}")
        self.assertTrue(sha, f"фикстура документов не записана: {message}")
        return sha

    def worktree(self, task_id: str) -> Path:
        wt, error = workspace.ensure(task_id, self.row(task_id)["branch"])
        self.assertIsNone(error, f"worktree не создан: {error}")
        return wt

    def wt_git(self, wt: Path, *args: str) -> str:
        res = subprocess.run(
            ["git", "-C", str(wt), "-c", "user.name=artel tests",
             "-c", "user.email=artel@example.invalid", *args],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def long_lived_rel(self, task_id: str) -> str:
        return f"tests/test_{task_id.lower()}_alpha.py"

    def prepare_tests_writing(self, task_id: str) -> Path:
        """Задача артели в `tests_writing`: SPEC с AC-1 и разовая планка в
        документах, долгоживущий файл задачи — коммитом кодовой ветки."""
        wt = self.worktree(task_id)
        self.seed_docs(task_id, {
            "SPEC.md": FIXTURE_SPEC.format(task=task_id),
            "acceptance_tests/test_ac1_plank.py": plank_text(),
        }, "SPEC и планка")
        path = wt / self.long_lived_rel(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(long_lived_text(), encoding="utf-8")
        self.wt_git(wt, "add", "--", self.long_lived_rel(task_id))
        self.wt_git(wt, "commit", "-q", "-m", f"{task_id}: долгоживущий тест")
        self.set_row(task_id, state="tests_writing")
        return wt

    def advance(self, task_id: str) -> str:
        return self.call(fsm.cmd_advance, task_id)

    def lock_plank(self, task_id: str) -> str:
        """Выход из `tests_writing` в `in_dev`; возвращает вывод `advance`."""
        out = self.advance(task_id)
        self.assertEqual(self.row(task_id)["state"], "in_dev",
                         f"выход из tests_writing не прошёл:\n{out}\n"
                         f"{self.journal_texts(task_id)[-5:]}")
        return out

    # --- наблюдение за git ---------------------------------------------------

    def git_rc(self, *args: str, cwd: Path | None = None,
               input_text: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=cwd or self.root,
                              capture_output=True, text=True,
                              input=input_text)

    def local_head(self, task_id: str) -> str:
        res = self.git_rc("rev-parse", "--verify", "--quiet",
                          ref_name(task_id) + "^{commit}")
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_head(self, task_id: str) -> str:
        res = self.git_rc("ls-remote", str(self.origin), ref_name(task_id))
        out = res.stdout.split()
        return out[0] if res.returncode == 0 and out else ""

    def _rev(self, sha: str) -> str:
        self.assertTrue(sha, "коммит не задан — ссылки или лока нет")
        return sha

    def parents(self, sha: str) -> list:
        res = self.git_rc("rev-list", "--parents", "-n", "1", self._rev(sha))
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.split()[1:]

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return self.git_rc("merge-base", "--is-ancestor",
                           ancestor, descendant).returncode == 0

    def first_commit(self, sha: str) -> list:
        """Корни истории `sha` (коммиты без родителя)."""
        res = self.git_rc("rev-list", "--max-parents=0", self._rev(sha))
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.split()

    def chain(self, sha: str) -> list:
        """Все коммиты, достижимые из `sha` (от новых к старым)."""
        res = self.git_rc("rev-list", self._rev(sha))
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.split()

    def tree_paths(self, sha: str) -> list:
        res = self.git_rc("ls-tree", "-r", "--name-only", self._rev(sha))
        self.assertEqual(res.returncode, 0, res.stderr)
        return [p for p in res.stdout.splitlines() if p]

    def file_at(self, sha: str, rel: str) -> str | None:
        res = self.git_rc("show", f"{sha}:{rel}")
        return res.stdout if res.returncode == 0 else None

    def legacy_branch_local(self, task_id: str) -> bool:
        return self.git_rc("rev-parse", "--verify", "--quiet",
                           f"refs/heads/{legacy_branch(task_id)}"
                           ).returncode == 0

    def legacy_branch_origin(self, task_id: str) -> bool:
        res = self.git_rc("ls-remote", str(self.origin),
                          f"refs/heads/{legacy_branch(task_id)}")
        return bool(res.stdout.strip())

    def doctor_checks(self) -> list:
        """Все строки `doctor` (`doctor.all_checks`) — публичный вход команды.

        Внешние процессы, кроме git, не исполняются (смоки CLI ролей,
        `gh`, `claude` отвечают «не найден»): проверяемые строки `doctor`
        живут на git, остальные строки планке безразличны. Домашний каталог
        — временный, чтобы проверки не читали дом Оператора.
        """
        from orchestrator import doctor
        with self.only_git():
            return doctor.all_checks(store.db())

    @contextmanager
    def only_git(self):
        """Внешние процессы, кроме git, не исполняются; дом — временный."""
        home = self.root / ".artel" / "dom"
        home.mkdir(parents=True, exist_ok=True)

        def is_git(cmd) -> bool:
            argv = [cmd] if isinstance(cmd, (str, bytes)) else list(cmd)
            return bool(argv) and Path(str(argv[0]).split()[0]).name == "git"

        def run(cmd, *args, **kwargs):
            if is_git(cmd):
                return REAL_RUN(cmd, *args, **kwargs)
            raise FileNotFoundError("песочница планки: внешний процесс "
                                    "не запускается")

        def popen(cmd, *args, **kwargs):
            if is_git(cmd):
                return REAL_POPEN(cmd, *args, **kwargs)
            raise FileNotFoundError("песочница планки: внешний процесс "
                                    "не запускается")

        with mock.patch.object(subprocess, "run", run), \
                mock.patch.object(subprocess, "Popen", popen), \
                mock.patch.object(Path, "home", lambda *a, **k: home):
            yield

    def assert_ref_advanced(self, task_id: str, before: str,
                            what: str) -> str:
        """Голова ссылки — новый коммит, потомок `before`; ветки
        `artifact/<id>` нет ни локально, ни в origin. Возвращает голову."""
        head = self.local_head(task_id)
        self.assertTrue(head, f"{what}: нет {ref_name(task_id)}")
        self.assertNotEqual(head, before,
                            f"{what}: нового коммита в ссылке нет")
        self.assertTrue(self.is_ancestor(before, head),
                        f"{what}: прежняя голова {before} не предок новой "
                        f"{head}")
        self.assertFalse(self.legacy_branch_local(task_id),
                         f"{what}: заведена ветка artifact/<id>")
        self.assertFalse(self.legacy_branch_origin(task_id),
                         f"{what}: ветка artifact/<id> в origin")
        return head

    def doctor_complaints(self, needle: str) -> list:
        """Строки `doctor` со статусом warn/fail, называющие `needle`."""
        return [c for c in self.doctor_checks()
                if c.status in ("warn", "fail")
                and needle in f"{c.name} {c.detail}"]

    def journal_texts(self, task_id: str) -> list:
        return [f"{s['action']} {s['detail'] or ''}"
                for s in store.task_steps(store.db(), task_id)]

    # --- внешнее воздействие на origin -------------------------------------

    def break_origin(self) -> str:
        """`origin` недоступен: url указывает в несуществующий каталог."""
        prior = self.git("remote", "get-url", "origin").strip()
        self.git("remote", "set-url", "origin",
                 str(self.root / ".artel" / "нет-такого-origin.git"))
        return prior

    def restore_origin(self, url: str) -> None:
        self.git("remote", "set-url", "origin", url)

    def advance_origin_ref(self, task_id: str) -> str:
        """Коммит в `refs/artifacts/<id>` origin мимо пульта: потомок
        нынешней головы origin; локальная ссылка его не знает."""
        base = self.origin_head(task_id)
        self.assertTrue(base, "предусловие: ссылка есть в origin")
        blob = self.git_rc("hash-object", "-w", "--stdin",
                           input_text="мимо пульта\n").stdout.strip()
        # Дерево base + новый файл в tasks/<id>/ — через временный индекс.
        env_index = self.root / ".artel" / "plank-index"
        full_env = {**os.environ, "GIT_INDEX_FILE": str(env_index)}
        subprocess.run(["git", "read-tree", base], cwd=self.root,
                       env=full_env, check=True, capture_output=True)
        subprocess.run(["git", "update-index", "--add", "--cacheinfo",
                        f"100644,{blob},tasks/{task_id}/EXTERNAL.md"],
                       cwd=self.root, env=full_env, check=True,
                       capture_output=True)
        tree = subprocess.run(["git", "write-tree"], cwd=self.root,
                              env=full_env, check=True, capture_output=True,
                              text=True).stdout.strip()
        env_index.unlink(missing_ok=True)
        commit = self.git("commit-tree", tree, "-p", base, "-m",
                          "мимо пульта").strip()
        self.git("push", "-q", "origin", f"{commit}:{ref_name(task_id)}")
        return commit

    def drop_origin_ref(self, task_id: str) -> None:
        self.git("push", "-q", "origin", f":{ref_name(task_id)}")

    def sync_origin(self, task_id: str) -> str:
        """Предусловие «ссылка совпадает с origin», обеспеченное самим
        тестом (обычный push без force): сценарию закрытия безразлично,
        каким узлом пульт отправлял ссылку раньше."""
        head = self.local_head(task_id)
        self.assertTrue(head, f"предусловие: есть {ref_name(task_id)}")
        if self.origin_head(task_id) != head:
            self.git("push", "-q", "origin",
                     f"{ref_name(task_id)}:{ref_name(task_id)}")
        self.assertEqual(self.origin_head(task_id), head)
        return head

    def reject_ref_pushes(self) -> None:
        """`origin` отвергает любую запись в `refs/artifacts/*` (хук
        `pre-receive` bare-репозитория): расхождение с origin не может
        «вылечиться» попутной отправкой пульта."""
        hook = Path(self.origin) / "hooks" / "pre-receive"
        hook.write_text(
            "#!/bin/sh\n"
            "while read old new ref; do\n"
            "  case \"$ref\" in refs/artifacts/*) "
            "echo 'планка: запись в refs/artifacts запрещена' >&2; "
            "exit 1;; esac\n"
            "done\n"
            "exit 0\n", encoding="utf-8")
        hook.chmod(0o755)

    # --- закрытие задачи ---------------------------------------------------

    def kill(self, task_id: str) -> str:
        return self.call(cleanup.cmd_kill, task_id)

    def make_target_workspace(self) -> Path:
        """Клон внешнего target (`PROJECTS/<target>/workspace`) с main и
        bare origin target."""
        target_origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, target_origin, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "--bare", "-b",
                        config.MAIN_BRANCH, str(target_origin)],
                       check=True, capture_output=True)
        ws = config.PROJECTS / EXTERNAL_TARGET / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        self.wt_git(ws, "init", "-q", "-b", config.MAIN_BRANCH)
        self.wt_git(ws, "remote", "add", "origin", str(target_origin))
        (ws / "marker.txt").write_text("main\n", encoding="utf-8")
        self.wt_git(ws, "add", "-A")
        self.wt_git(ws, "commit", "-q", "-m", "init")
        self.wt_git(ws, "push", "-q", "origin", config.MAIN_BRANCH)
        return ws

    def prepare_external_merge_gate(self, task_id: str) -> None:
        """Задача внешнего target на гейте мержа: клон target с кодовой
        веткой задачи и bare origin target (рецепт
        `tests/test_fsm_merge_gate_done_snapshot.py`); черновик MR помечен
        заведённым — сценарий не ходит в forge."""
        branch = self.row(task_id)["branch"]
        ws = self.make_target_workspace()
        self.wt_git(ws, "checkout", "-q", "-b", branch)
        (ws / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.wt_git(ws, "add", "feature.txt")
        self.wt_git(ws, "commit", "-q", "-m", f"{task_id}: код фичи")
        self.set_row(task_id, draft_mr_created=1)
        state = self.row(task_id)["state"]
        store.set_state(store.db(), task_id, "merge_gate", "fsm",
                        expected_state=state, detail="гейт мержа планки")

    def approve(self, task_id: str) -> str:
        """`approve <id>` без sha; CI ветки — зелёный (подмена `ci.branch_status`)."""
        with mock.patch.object(ci, "branch_status",
                               lambda branch: (True, "зелёный (тест)")):
            return self.call(fsm.cmd_approve, task_id)
