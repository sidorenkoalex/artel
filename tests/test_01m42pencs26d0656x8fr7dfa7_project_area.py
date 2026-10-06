"""Область проекта (ADR-0021, этап 2): клон проекта и рабочие копии задач
под `.artel/projects/<имя>/`; git главной копии пульта в ходе задачи не
меняется.

Группа: долгоживущий

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): главная копия
пульта (`config.ROOT`) с копией `scripts/` репозитория (хуки защиты main
`scripts/git-hooks`), bare `origin` рядом и `targets.yaml`, где запись
`artel` называет этот `origin` полем `url` — клон артели пульт обязан
заводить из него. Внешний проект `sled` — свой bare-репозиторий с первым
коммитом на базовой ветке, его запись в том же `targets.yaml`. Классы
сквозного прогона FSM и мержа (`COPY_CODE`) несут в первом коммите ещё и
`orchestrator/`, `templates/`, `skills/`: гейт мержа зовёт `scripts/
guard.py` и `scripts/codebase_map.py` дерева мержа, бриф роли читает
скилы. GitHub изображает подставной `gh` в начале `PATH` (зелёные
проверки любого коммита, кроме названных сценарием), часы — подставные:
ожидание CI измеряется без реального ожидания.

Снимок главной копии — `git for-each-ref` (ветки, ссылки документов),
HEAD, `git worktree list`, `git status`; его неизменность — основной
наблюдаемый предмет. Названия задач, тексты документов и выбор вариантов
берутся случайно; зерно печатается и входит в текст провала.

Красен до реализации: `init`/`new`/`doctor --fix` не заводят
`.artel/projects/<имя>/repo` и `worktrees/<id>/` — ветка и рабочая копия
задачи артели рождаются в git главной копии (`.artel/worktrees/<id>`), у
внешнего проекта — общий `workspace/`; `repo_context` для артели отдаёт
`config.ROOT`; `note`/`doc-commit` работают через `.artel/notes-work`,
`pool-seal` пишет в рабочее дерево главной копии; `docs --fetch-all`
приносит ссылки в git главной копии.

Методы прежнего поведения зелены и до реализации и держат его после
перехода на клон: отказы гейта мержа AC-5 (защищённый путь, удалённый
тест, `guard --all`, красный main) и чтение исторической ссылки `docs`
(AC-13).

Планка провалидирована временным стабом реализации (удалён, не
закоммичен): клон по `url` из `targets.yaml` в `init`/`new`/`doctor --fix`,
рабочая копия задачи в клоне, `repo_context`/`plank-run`/рабочий каталог
роли — на клон, хуки клона — путь пина, `.artel/notes-work` заменён клоном,
база удержанных записей — `origin/main` клона, `pool-seal` коммитит в клоне,
`retro_corpus` читает клон. Под ним зелены AC-1, 2, 3, 6, 7, 9, 10, 11 и
`--fetch-all`/`retro_corpus` AC-13; случай «ссылка только в главной копии»
AC-13 у стаба без отката на главную копию красен (заявленная мутация), AC-10
у стаба «клон есть, база — HEAD главной копии» красен. Сквозные сценарии
AC-4/AC-5 стабом не покрыть — нужен сам перевод гейта мержа на клон; на
текущем коде они доходят до `done` (либо до отказа своего шага) и краснеют
только на утверждениях о клоне: ссылка документов и зонд мержа — в git
главной копии.
"""
import contextlib
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, artel, catalog, checkpoint, config,
                          doctor, fixation, keychain, notes, plank_run,
                          repo_context,
                          retro_corpus, runner, stack, store)
from tests.sandbox import (ARTEL_TEST_PROFILE, FakeProc,
                           RealGitSandbox, _stub_check_stack,
                           capture, capture_new_task_id, is_claude_call,
                           patch_pult_sleep,
                           resilient_tmp_cleanup)

REPO = Path(__file__).resolve().parent.parent
ARTEL = config.DEFAULT_TARGET
SLED = "sled"

TITLES = ("Клон проекта", "Рабочая копия задачи", "Перенос веток",
          "Ссылки документов", "Хуки клона", "Область проекта артели",
          "Подтяжка main", "Сверка удержанных записей")

TARGET_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

CODE_MAP_PLACEHOLDER = ("---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
                        "---\n\n# Карта\n")

# Подставной `gh`: таблица сценария — JSON-файл по пути из переменной
# окружения (sha -> проверки, «по умолчанию» — для остальных коммитов).
FAKE_GH = r'''
import json, os, re, sys
state_path = os.environ["ARTEL_FAKE_GH_STATE"]
with open(state_path, encoding="utf-8") as fh:
    state = json.load(fh)
args = sys.argv[1:]
joined = " ".join(args)
found = re.search(r"commits/([0-9a-fA-F]{7,40})/check-runs", joined)
if args[:1] == ["api"] and found:
    sha = found.group(1).lower()
    runs = state["default"]
    for key, value in state["checks"].items():
        if key.startswith(sha) or sha.startswith(key):
            runs = value
            break
    page = re.search(r"[?&]page=(\d+)", joined)
    page_runs = runs if page is None or page.group(1) == "1" else []
    print(json.dumps({"total_count": len(runs), "check_runs": page_runs},
                     ensure_ascii=False))
    sys.exit(0)
if args[:2] == ["run", "list"]:
    print("[]")
    sys.exit(0)
if args[:2] == ["pr", "list"] or args[:2] == ["pr", "view"]:
    print("[]")
    sys.exit(0)
sys.stderr.write("gh песочницы: вызов не поддержан: " + joined + "\n")
sys.exit(1)
'''


def green_runs() -> list:
    return [{"name": "тесты кода", "status": "completed", "conclusion": "success"}]


def red_runs() -> list:
    return [{"name": "тесты кода", "status": "completed", "conclusion": "failure"}]


class ProjectAreaSandbox(RealGitSandbox):
    """Главная копия пульта, bare `origin` артели и `targets.yaml` с
    записью артели; по запросу — внешний проект `sled`."""

    COPY_CODE = False

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        role_patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role_patcher.start()
        self.addCleanup(role_patcher.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)

        shutil.copytree(REPO / "scripts", self.root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        if self.COPY_CODE:
            for name in ("orchestrator", "templates", "skills"):
                shutil.copytree(REPO / name, self.root / name,
                                ignore=shutil.ignore_patterns("__pycache__"))
            (self.root / "docs").mkdir(exist_ok=True)
            (self.root / "docs" / "codebase-map.md").write_text(
                CODE_MAP_PLACEHOLDER, encoding="utf-8")
            (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
            (self.root / "tests").mkdir(exist_ok=True)
            (self.root / "tests" / "test_green.py").write_text(
                "def test_green():\n    assert True\n", encoding="utf-8")
        self.extra_main_files()
        # `targets.yaml` этой песочницы — файл в git главной копии (правка —
        # коммитом, `add_external_project`), а не посеянная под `.artel/`
        # запись артели `RealGitSandbox` (SPEC 01M45FJVGQT1K0P8HDEXZX6HS7).
        targets_patcher = mock.patch.object(config, "TARGETS",
                                            self.root / "targets.yaml")
        targets_patcher.start()
        self.addCleanup(targets_patcher.stop)

        origin_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, origin_tmp)
        self.origin = Path(origin_tmp.name).resolve() / "artel.git"
        self.git("init", "-q", "--bare", "-b", config.MAIN_BRANCH, str(self.origin))
        self.targets = {ARTEL: str(self.origin)}
        self.write_targets()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "пульт")
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin")
        self.clone = config.PROJECTS / ARTEL / "repo"
        self.scratch = Path(origin_tmp.name).resolve()

    def extra_main_files(self) -> None:
        """Файлы первого коммита главной копии сверх общих — точка
        расширения подклассов."""

    # ------------------------------------------------------------ targets

    def write_targets(self) -> None:
        # Запись артели — с профилем тестов (SPEC 01M45FJVGQT1K0P8HDEXZX6HS7,
        # требование 4): без него проверки тестов задачи артели отказывают.
        text = "targets:\n" + "".join(
            TARGET_ENTRY.format(name=name, url=url, base=config.MAIN_BRANCH)
            + (ARTEL_TEST_PROFILE if name == ARTEL else "")
            for name, url in self.targets.items())
        config.TARGETS.write_text(text, encoding="utf-8")

    def add_external_project(self, name: str = SLED) -> Path:
        """Внешний проект: bare-репозиторий с первым коммитом на базовой
        ветке, запись в `targets.yaml`. Клона проекта не заводит."""
        seed_repo = self.scratch / f"{name}-seed"
        bare = self.scratch / f"{name}.git"
        self.git("init", "-q", "-b", config.MAIN_BRANCH, str(seed_repo))
        (seed_repo / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        self.git("-C", str(seed_repo), "add", "-A")
        self.git("-C", str(seed_repo), "-c", "user.name=t",
                 "-c", "user.email=t@example.invalid",
                 "commit", "-q", "-m", "init")
        self.git("init", "-q", "--bare", "-b", config.MAIN_BRANCH, str(bare))
        self.git("-C", str(seed_repo), "push", "-q", str(bare),
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.targets[name] = str(bare)
        self.write_targets()
        # `targets.yaml` в git главной копии: правка — коммитом, чтобы
        # `git status` главной копии оставался чистым до сценария.
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"проект {name}")
        return bare

    # ------------------------------------------------------- главная копия

    def main_refs(self, *prefixes: str) -> str:
        return self.git("for-each-ref", "--format=%(refname) %(objectname)",
                        *prefixes)

    def main_head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def main_worktrees(self) -> str:
        return self.git("worktree", "list", "--porcelain")

    def main_status(self) -> str:
        return self.git("status", "--porcelain", "--untracked-files=all")

    def main_snapshot(self) -> dict:
        return {"refs": self.main_refs("refs/heads/", "refs/artifacts/"),
                "head": self.main_head(),
                "worktrees": self.main_worktrees()}

    # ------------------------------------------------------- область проекта

    def project_clone(self, name: str = ARTEL) -> Path:
        return config.PROJECTS / name / "repo"

    def worktree(self, task_id: str, name: str = ARTEL) -> Path:
        return config.PROJECTS / name / "worktrees" / task_id

    def docs_dir(self, task_id: str, name: str = ARTEL) -> Path:
        return config.PROJECTS / name / "tasks" / task_id

    def in_repo(self, repo: Path, *args: str) -> str:
        return self.git("-C", str(repo), *args)

    def git_ok(self, repo: Path, *args: str) -> bool:
        """Исход git-команды в `repo` без провала теста."""
        try:
            self.git("-C", str(repo), *args)
        except AssertionError:
            return False
        return True

    def is_git_repo(self, path: Path) -> bool:
        return path.is_dir() and self.git_ok(path, "rev-parse", "--git-dir") \
            and Path(self.in_repo(path, "rev-parse", "--absolute-git-dir")
                     .strip()).resolve().is_relative_to(path.resolve())

    def has_commit(self, repo: Path, sha: str) -> bool:
        return self.git_ok(repo, "cat-file", "-e", f"{sha}^{{commit}}")

    def bare_head(self, bare: Path, ref: str) -> str:
        res = self.in_repo(bare, "for-each-ref", "--format=%(objectname)", ref)
        return res.strip()

    def registered_worktrees(self, repo: Path) -> list:
        listing = self.in_repo(repo, "worktree", "list", "--porcelain")
        return [Path(line.split(" ", 1)[1]).resolve()
                for line in listing.splitlines() if line.startswith("worktree ")]

    # ------------------------------------------------------------- команды

    def init(self) -> str:
        return capture(catalog.cmd_init)

    def new_task(self, title: str | None = None, target: str | None = None) -> str:
        title = title or self.rng.choice(TITLES)
        kwargs = {} if target is None else {"target": target}
        _, task_id = capture_new_task_id(
            lambda: catalog.cmd_new(title, **kwargs))
        return task_id

    def new_refusal(self, title: str, target: str | None = None) -> str | None:
        """Текст отказа `new`; `None` — `new` не отказал."""
        kwargs = {} if target is None else {"target": target}
        try:
            capture(lambda: catalog.cmd_new(title, **kwargs))
        except SystemExit as exc:
            return "" if exc.code is None else str(exc.code)
        return None

    def branch_of(self, task_id: str) -> str:
        return store.get_task(store.db(), task_id)["branch"]

    def set_state(self, task_id: str, state: str) -> None:
        store.update_task(store.db(), task_id, state=state)

    def cli(self, *argv: str) -> tuple[bool, str]:
        """(успех, вывод + текст отказа) команды `artel.py <argv>`."""
        out = io.StringIO()
        ok, tail = True, ""
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (0, None):
                    ok, tail = False, f"\n{exc.code}"
        return ok, out.getvalue() + tail

    @contextlib.contextmanager
    def only_git_processes(self):
        """Внешние процессы песочницы: git (и подставной gh) исполняются,
        прочие (CLI ролей, openssl) — нет; дом пользователя — каталог
        песочницы."""
        real_run, real_popen = subprocess.run, subprocess.Popen

        def allowed(cmd) -> bool:
            argv = [cmd] if isinstance(cmd, (str, Path)) else list(cmd)
            return bool(argv) and Path(str(argv[0])).name in ("git", "gh")

        def run(cmd, *args, **kwargs):
            if allowed(cmd):
                return real_run(cmd, *args, **kwargs)
            raise FileNotFoundError("песочница: внешний процесс не запускается")

        def popen(cmd, *args, **kwargs):
            if allowed(cmd):
                return real_popen(cmd, *args, **kwargs)
            raise FileNotFoundError("песочница: внешний процесс не запускается")

        home = self.root / ".artel" / "dom"
        home.mkdir(parents=True, exist_ok=True)
        with mock.patch.object(subprocess, "run", side_effect=run), \
                mock.patch.object(subprocess, "Popen", side_effect=popen), \
                mock.patch.object(Path, "home", lambda *a, **k: home):
            yield

    def doctor_fix(self) -> str:
        out = io.StringIO()
        with self.only_git_processes(), contextlib.redirect_stdout(out):
            try:
                doctor.cmd_doctor(False, True)
            except SystemExit as exc:
                out.write(f"\n{exc.code}")
        return out.getvalue()

    def doctor_checks(self) -> list:
        with self.only_git_processes():
            return doctor.all_checks(store.db())

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"


# --------------------------------------------------------------------- AC-1

class ArtelTaskInProjectAreaTest(ProjectAreaSandbox):
    """AC-1: `new` задачи артели — клон, ветка и рабочая копия в области
    проекта, git главной копии не тронут."""

    def test_ac1_new_artel_task_lives_in_the_project_clone(self):
        """`init`, затем `new` задачи артели со случайным названием.

        Есть клон `.artel/projects/artel/repo` (git-репозиторий с головой
        `origin/main`), ветка `task/<id>-…` в нём, рабочая копия
        `.artel/projects/artel/worktrees/<id>/` на этой ветке и
        зарегистрирована в клоне. В главной копии ветки задачи нет,
        `git worktree list` прежний, `.artel/worktrees/<id>` не создан.

        Ловит мутацию: `workspace.ensure` по-прежнему делает `git worktree
        add -b` в git главной копии (`config.WORKTREES`) — ветка задачи
        появляется в `refs/heads` главной копии, рабочей копии под
        `.artel/projects/artel/worktrees/` нет.
        """
        self.init()
        heads_before = self.main_refs("refs/heads/")
        worktrees_before = self.main_worktrees()
        origin_main = self.bare_head(self.origin, f"refs/heads/{config.MAIN_BRANCH}")

        task = self.new_task()
        branch = self.branch_of(task)
        wt = self.worktree(task)

        self.assertTrue(branch.startswith(f"task/{task.lower()}-"), self.msg(branch))
        self.assertTrue(self.is_git_repo(self.clone),
                        self.msg(f"клона нет: {self.clone}"))
        self.assertTrue(self.has_commit(self.clone, origin_main),
                        self.msg("клон не несёт origin/main"))
        self.assertTrue(self.git_ok(self.clone, "rev-parse", "--verify", "--quiet",
                                    f"refs/heads/{branch}"),
                        self.msg(f"ветки {branch} в клоне нет"))
        self.assertTrue(wt.is_dir(), self.msg(f"рабочей копии нет: {wt}"))
        self.assertEqual(self.in_repo(wt, "rev-parse", "--abbrev-ref", "HEAD").strip(),
                         branch, self.msg("рабочая копия не на ветке задачи"))
        self.assertIn(wt.resolve(), self.registered_worktrees(self.clone),
                      self.msg("рабочая копия не зарегистрирована в клоне"))

        self.assertEqual(self.main_refs("refs/heads/"), heads_before,
                         self.msg("ветки главной копии изменились"))
        self.assertEqual(self.main_worktrees(), worktrees_before,
                         self.msg("git worktree list главной копии изменился"))
        self.assertFalse((config.WORKTREES / task).exists(),
                         self.msg(f"создан {config.WORKTREES / task}"))


# --------------------------------------------------------------------- AC-2

class ExternalTaskInProjectAreaTest(ProjectAreaSandbox):
    """AC-2: внешний проект — свой клон и рабочая копия на задачу,
    рабочий каталог роли — `worktrees/<id>/`, `workspace/` не заводится."""

    def test_ac2_external_task_gets_clone_and_worktree_not_workspace(self):
        """Внешний проект `sled` в `targets.yaml`; `init`, `new` задачи
        `sled`, затем рабочий каталог роли шага (`runner.role_cwd`).

        Есть клон `.artel/projects/sled/repo` с головой своего origin и
        рабочая копия `.artel/projects/sled/worktrees/<id>/` на ветке
        задачи; `role_cwd` — она; каталога `.artel/projects/sled/
        workspace` нет ни после `new`, ни после `role_cwd`.

        Ловит мутацию: `runner.role_cwd_path` для внешнего проекта
        по-прежнему отдаёт `PROJECTS/<имя>/workspace` и заводит его
        `mkdir` — рабочий каталог роли общий на все задачи проекта.
        """
        bare = self.add_external_project(SLED)
        self.init()
        task = self.new_task(target=SLED)
        clone = self.project_clone(SLED)
        wt = self.worktree(task, SLED)
        workspace_dir = config.PROJECTS / SLED / "workspace"

        self.assertTrue(self.is_git_repo(clone), self.msg(f"клона нет: {clone}"))
        self.assertTrue(self.has_commit(
            clone, self.bare_head(bare, f"refs/heads/{config.MAIN_BRANCH}")),
            self.msg("клон sled не несёт голову своего origin"))
        self.assertTrue(wt.is_dir(), self.msg(f"рабочей копии нет: {wt}"))
        self.assertEqual(self.in_repo(wt, "rev-parse", "--abbrev-ref", "HEAD").strip(),
                         self.branch_of(task), self.msg("не на ветке задачи"))
        self.assertFalse(workspace_dir.exists(),
                         self.msg("workspace/ заведён командой new"))

        cwd = runner.role_cwd(store.db(), task, SLED)

        self.assertEqual(Path(cwd).resolve(), wt.resolve(),
                         self.msg(f"рабочий каталог роли {cwd}, ожидался {wt}"))
        self.assertFalse(workspace_dir.exists(),
                         self.msg("workspace/ заведён рабочим каталогом роли"))


# --------------------------------------------------------------------- AC-3

class CloneCreationTest(ProjectAreaSandbox):
    """AC-3: клон заводят `init`, `doctor --fix` и `new`; повтор не меняет
    существующий клон; неудача клонирования — отказ `new` без следов."""

    def plant_marker(self) -> dict:
        """Отметки существующего клона: неотслеживаемый файл, локальная
        ветка, HEAD — их переживает только нетронутый клон."""
        name = f"metka_{self.rng.randrange(10 ** 6)}"
        (self.clone / f"{name}.txt").write_text(name, encoding="utf-8")
        self.in_repo(self.clone, "branch", name)
        return {"file": self.clone / f"{name}.txt",
                "heads": self.in_repo(self.clone, "for-each-ref",
                                      "--format=%(refname) %(objectname)",
                                      "refs/heads/"),
                "head": self.in_repo(self.clone, "rev-parse", "HEAD").strip()}

    def assert_marker_kept(self, marker: dict, step: str) -> None:
        self.assertTrue(marker["file"].is_file(),
                        self.msg(f"{step}: клон пересоздан (отметки нет)"))
        self.assertEqual(self.in_repo(self.clone, "for-each-ref",
                                      "--format=%(refname) %(objectname)",
                                      "refs/heads/"), marker["heads"],
                         self.msg(f"{step}: ветки клона изменились"))
        self.assertEqual(self.in_repo(self.clone, "rev-parse", "HEAD").strip(),
                         marker["head"], self.msg(f"{step}: HEAD клона изменился"))

    def test_ac3_init_creates_missing_clone_and_repeat_keeps_it(self):
        """`init` на пульте без клона заводит `.artel/projects/artel/repo`;
        повторный `init` оставляет клон как есть (отметка, ветки, HEAD).

        Ловит мутацию: `init` клонирует безусловно (удаляет и клонирует
        заново) — отметка клона пропадает после повторного вызова.
        """
        self.assertFalse(self.clone.exists())
        self.init()
        self.assertTrue(self.is_git_repo(self.clone), self.msg("init не завёл клон"))
        marker = self.plant_marker()

        self.init()

        self.assert_marker_kept(marker, "повторный init")

    def test_ac3_doctor_fix_creates_missing_clone_and_repeat_keeps_it(self):
        """Клон убран после `init`; `doctor --fix` заводит его заново,
        повторный `doctor --fix` оставляет как есть.

        Ловит мутацию: `doctor --fix` не знает о клоне проекта (заводит его
        только `init`) — после уборки клона его нет.
        """
        self.init()
        shutil.rmtree(self.clone, ignore_errors=True)

        out = self.doctor_fix()

        self.assertTrue(self.is_git_repo(self.clone),
                        self.msg(f"doctor --fix не завёл клон: {out}"))
        marker = self.plant_marker()
        self.doctor_fix()
        self.assert_marker_kept(marker, "повторный doctor --fix")

    def test_ac3_new_creates_missing_clone(self):
        """Клон убран после `init`; `new` задачи артели заводит его и
        рабочую копию задачи в нём; второй `new` клон не пересоздаёт.

        Ловит мутацию: `new` не заводит отсутствующий клон, а отказывает
        либо уходит в главную копию — клона и рабочей копии нет.
        """
        self.init()
        shutil.rmtree(self.clone, ignore_errors=True)

        task = self.new_task()

        self.assertTrue(self.is_git_repo(self.clone), self.msg("new не завёл клон"))
        self.assertTrue(self.worktree(task).is_dir(),
                        self.msg("рабочей копии задачи нет"))
        marker = self.plant_marker()
        self.new_task()
        self.assertTrue(marker["file"].is_file(),
                        self.msg("второй new пересоздал клон"))

    def test_ac3_failed_clone_refuses_new_without_traces(self):
        """Клона нет, а `url` записи артели ведёт в несуществующий
        репозиторий: `new` отказывает текстом, называющим причину; ни
        ветки задачи, ни новой записи `git worktree list` в главной копии,
        ни `workspace/`, ни `worktrees/` с рабочей копией.

        Ловит мутацию: при неудаче клонирования `new` откатывается на
        главную копию (рабочая копия и ветка задачи — в её git) и не
        отказывает.
        """
        self.init()
        shutil.rmtree(self.clone, ignore_errors=True)
        missing = self.scratch / f"net-takogo-{self.rng.randrange(10 ** 6)}.git"
        self.targets[ARTEL] = str(missing)
        self.write_targets()
        heads_before = self.main_refs("refs/heads/")
        worktrees_before = self.main_worktrees()
        title = self.rng.choice(TITLES)

        refusal = self.new_refusal(title)

        self.assertIsNotNone(refusal, self.msg("new не отказал без клона"))
        self.assertTrue(refusal.strip(), self.msg("отказ без причины"))
        self.assertTrue(any(word in refusal for word in (
            "клон", str(missing), missing.name, "repo")),
            self.msg(f"отказ не называет причину: {refusal}"))
        self.assertEqual(self.main_refs("refs/heads/"), heads_before,
                         self.msg("ветка задачи в главной копии"))
        self.assertEqual(self.main_worktrees(), worktrees_before,
                         self.msg("рабочая копия в главной копии"))
        self.assertFalse((config.PROJECTS / ARTEL / "workspace").exists(),
                         self.msg("workspace/ заведён"))
        worktrees_dir = config.PROJECTS / ARTEL / "worktrees"
        self.assertFalse(worktrees_dir.is_dir() and any(worktrees_dir.iterdir()),
                         self.msg("рабочая копия задачи заведена"))
        self.assertFalse(config.WORKTREES.is_dir() and any(config.WORKTREES.iterdir()),
                         self.msg("рабочая копия в .artel/worktrees"))


# --------------------------------------------------------------------- AC-6

class RepoContextOfArtelTest(ProjectAreaSandbox):
    """AC-6: репозиторный контекст артели — клон области проекта."""

    def test_ac6_artel_context_is_the_project_clone(self):
        """`init`; `repo_context.resolve("artel").path` и `path_or_none`
        от него — `.artel/projects/artel/repo`; `repo_context.git`
        исполняется в клоне (каталог git — клона, не главной копии).

        Ловит мутацию: `resolve` для артели оставлен `config.ROOT` (или
        `path_or_none` возвращает `None` для артели) — путь не совпадает
        с клоном, `git` исполняется в главной копии.
        """
        self.init()
        ctx = repo_context.resolve(ARTEL)

        self.assertIsNotNone(ctx)
        self.assertEqual(Path(ctx.path).resolve(), self.clone.resolve(),
                         self.msg(f"путь контекста {ctx.path}"))
        self.assertEqual(Path(repo_context.path_or_none(ctx)).resolve(),
                         self.clone.resolve())
        res = repo_context.git(ctx, "rev-parse", "--absolute-git-dir")
        self.assertEqual(res.returncode, 0, self.msg(res.stderr))
        git_dir = Path(res.stdout.strip()).resolve()
        self.assertTrue(git_dir.is_relative_to(self.clone.resolve()),
                        self.msg(f"git исполнен не в клоне: {git_dir}"))
        self.assertFalse(git_dir == (self.root / ".git").resolve(),
                         self.msg("git исполнен в главной копии"))


# --------------------------------------------------------------------- AC-7

PROBE_TEST = '''import os
import unittest
from pathlib import Path


class Probe(unittest.TestCase):

    def test_probe(self):
        Path({marker!r}).write_text(
            os.getcwd() + "\\n" + str(Path(__file__).resolve()), encoding="utf-8")
'''


class CodeCopyOfTaskTest(ProjectAreaSandbox):
    """AC-7: выкладка и уборка планки и документов — в `worktrees/<id>/`
    проекта задачи; каталог задач главной копии (`config.TASKS`) не
    меняется."""

    def setUp(self):
        super().setUp()
        self.init()
        self.task = self.new_task()
        self.wt = self.worktree(self.task)
        # Легаси-каталог задач главной копии с каталогом того же id: ни
        # одна уборка не вправе его тронуть.
        self.legacy = config.TASKS / self.task
        self.legacy.mkdir(parents=True, exist_ok=True)
        (self.legacy / "LEGACY.md").write_text("легаси\n", encoding="utf-8")
        self.tasks_before = self.tasks_listing()

    def tasks_listing(self) -> list:
        return sorted((p.relative_to(config.TASKS).as_posix(), p.read_bytes())
                      for p in config.TASKS.rglob("*") if p.is_file())

    def assert_main_tasks_untouched(self, step: str) -> None:
        self.assertEqual(self.tasks_listing(), self.tasks_before,
                         self.msg(f"{step}: каталог задач главной копии изменён"))

    def plank_run(self) -> tuple[str, str | None]:
        out = io.StringIO()
        refusal = None
        with contextlib.redirect_stdout(out):
            try:
                plank_run.cmd_plank_run(self.task)
            except SystemExit as exc:
                refusal = "" if exc.code in (None, 0) else str(exc.code)
        return out.getvalue(), refusal

    def test_ac7_plank_run_lays_the_plank_into_the_task_worktree(self):
        """Задача в `tests_writing`, черновик планки — тест-зонд, пишущий
        свой рабочий каталог и путь своего файла. `plank-run` гоняет его
        из `worktrees/<id>/`, файл зонда лежал в выкладке задачи внутри
        `worktrees/<id>/`, после прогона выкладки там нет, каталог задач
        главной копии прежний.

        Ловит мутацию: `plank_run` выбирает каталог кода прежней формулой
        (`config.WORKTREES/<id>` / `workspace/`) — рабочей копии там нет,
        прогон отказывает либо идёт не в рабочей копии задачи.
        """
        self.set_state(self.task, "tests_writing")
        marker = self.scratch / f"zond-{self.rng.randrange(10 ** 6)}.txt"
        plank = self.docs_dir(self.task) / "acceptance_tests"
        plank.mkdir(parents=True, exist_ok=True)
        (plank / "test_zond.py").write_text(PROBE_TEST.format(marker=str(marker)),
                                            encoding="utf-8")

        out, refusal = self.plank_run()

        self.assertIsNone(refusal, self.msg(f"plank-run отказал: {refusal}\n{out}"))
        self.assertTrue(marker.is_file(), self.msg(f"зонд не исполнен: {out}"))
        cwd, probe_file = marker.read_text(encoding="utf-8").splitlines()
        self.assertEqual(Path(cwd).resolve(), self.wt.resolve(), self.msg(out))
        self.assertTrue(Path(probe_file).is_relative_to(
            (self.wt / "tasks" / self.task).resolve()), self.msg(probe_file))
        self.assertFalse((self.wt / "tasks" / self.task).exists(),
                         self.msg("выкладка не убрана"))
        self.assert_main_tasks_untouched("plank-run")

    def test_ac7_plank_run_refuses_without_the_task_worktree(self):
        """Рабочая копия задачи снята (`git worktree remove` в клоне):
        `plank-run` отказывает, каталог задач главной копии прежний.

        Ловит мутацию: отказ остался только на «каталог кода — главная
        копия» — без рабочей копии прогон уходит в другой каталог.
        """
        self.set_state(self.task, "tests_writing")
        plank = self.docs_dir(self.task) / "acceptance_tests"
        plank.mkdir(parents=True, exist_ok=True)
        (plank / "test_zond.py").write_text(
            PROBE_TEST.format(marker=str(self.scratch / "zond.txt")), encoding="utf-8")
        self.in_repo(self.clone, "worktree", "remove", "--force", str(self.wt))

        out, refusal = self.plank_run()

        self.assertIsNotNone(refusal, self.msg(f"plank-run не отказал: {out}"))
        self.assertTrue(refusal, self.msg("отказ без текста"))
        self.assertFalse((self.scratch / "zond.txt").exists(),
                         self.msg("планка исполнена без рабочей копии"))
        self.assert_main_tasks_untouched("plank-run без рабочей копии")

    def test_ac7_drop_from_code_copy_cleans_only_the_worktree_layout(self):
        """Выкладка задачи в `worktrees/<id>/`: `acceptance.
        drop_from_code_copy(id, worktrees/<id>)` убирает её; тот же вызов
        с главной копией каталогом кода не трогает каталог задачи в
        главной копии.

        Ловит мутацию: уборка снимает каталог задачи по любому каталогу
        кода, включая главную копию — легаси-каталог задачи пропадает.
        """
        layout = self.wt / "tasks" / self.task / "acceptance_tests"
        layout.mkdir(parents=True, exist_ok=True)
        (layout / "test_x.py").write_text("x = 1\n", encoding="utf-8")

        acceptance.drop_from_code_copy(self.task, self.wt)
        acceptance.drop_from_code_copy(self.task, config.ROOT)

        self.assertFalse((self.wt / "tasks" / self.task).exists(),
                         self.msg("выкладка в рабочей копии задачи не убрана"))
        self.assert_main_tasks_untouched("drop_from_code_copy")

    def test_ac7_checkpoint_harvests_docs_from_the_task_worktree(self):
        """Документ (`PLAN.md` со случайным текстом), оставленный в
        выкладке задачи внутри `worktrees/<id>/`: чекпоинт старта шага
        (`checkpoint.harvest_code_copy_docs`) забирает его оттуда — каталог
        убран, файл в ссылке документов клона либо в возврате узла; каталог
        задач главной копии прежний.

        Ловит мутацию: чекпоинт ищет выкладку по прежней формуле
        (`config.WORKTREES/<id>` / `workspace/`) — документ остаётся
        лежать в рабочей копии задачи.
        """
        text = f"# План\n\nзаметка {self.rng.randrange(10 ** 9)}\n"
        stray = self.wt / "tasks" / self.task
        stray.mkdir(parents=True, exist_ok=True)
        (stray / "PLAN.md").write_text(text, encoding="utf-8")

        harvested = checkpoint.harvest_code_copy_docs(store.db(), self.task, ARTEL)

        self.assertFalse(stray.exists(), self.msg("выкладка не убрана"))
        rev = (f"refs/artifacts/{self.task}:"
               + "/".join(("tasks", self.task, "PLAN.md")))
        in_ref = (self.git_ok(self.clone, "cat-file", "-e", rev)
                  and self.in_repo(self.clone, "show", rev) == text)
        in_return = any(v == text.encode() for v in (harvested or {}).values())
        self.assertTrue(in_ref or in_return,
                        self.msg(f"документ потерян: {harvested}"))
        self.assert_main_tasks_untouched("harvest_code_copy_docs")


# -------------------------------------------------------------------- AC-11

class CloneHooksFromPinTest(ProjectAreaSandbox):
    """AC-11: хуки защиты main клона — из пина (`<config.ROOT>/scripts/
    git-hooks`), `doctor` сверяет их в клоне."""

    def hooks_path(self) -> Path:
        return config.ROOT / "scripts" / "git-hooks"

    def clone_hooks_value(self) -> str:
        try:
            return self.in_repo(self.clone, "config", "--get",
                                "core.hooksPath").strip()
        except AssertionError:
            return ""

    def hook_warnings(self) -> list:
        """Строки `doctor` уровня warn, говорящие о хуках клона артели."""
        found = []
        for check in self.doctor_checks():
            text = f"{check.name} {check.detail}"
            if check.status == "warn" and "hooksPath" in text and "artel" in text \
                    and ("repo" in text or "клон" in text):
                found.append(text)
        return found

    def test_ac11_clone_hooks_path_is_the_absolute_pin_path(self):
        """Клон, заведённый `init`, несёт `core.hooksPath`, равный
        абсолютному `<config.ROOT>/scripts/git-hooks`.

        Ловит мутацию: клон получает относительный `scripts/git-hooks`
        (хуки из проверяемого кода клона) либо не получает значения вовсе.
        """
        self.init()

        value = self.clone_hooks_value()

        self.assertTrue(value and Path(value).is_absolute(),
                        self.msg(f"core.hooksPath клона: {value!r}"))
        self.assertEqual(Path(value).resolve(), self.hooks_path().resolve(),
                         self.msg(f"core.hooksPath клона: {value!r}"))

    def test_ac11_manual_commit_to_clone_main_is_refused_by_the_hook(self):
        """Ручной коммит в `main` клона без маркера пульта
        (`ARTEL_PULT_GIT` снят) — отказ хука `pre-commit`, голова `main`
        клона прежняя.

        Ловит мутацию: клон без `core.hooksPath` (хуки не включены) —
        ручной коммит в `main` клона проходит.
        """
        self.init()
        bare = self.in_repo(self.clone, "rev-parse", "--is-bare-repository").strip()
        checkout = self.clone
        if bare == "true" or self.in_repo(
                self.clone, "rev-parse", "--abbrev-ref", "HEAD").strip() != config.MAIN_BRANCH:
            checkout = self.scratch / "ruchnoy-main"
            self.in_repo(self.clone, "worktree", "add", "-q", str(checkout),
                         config.MAIN_BRANCH)
        before = self.in_repo(self.clone, "rev-parse",
                              f"refs/heads/{config.MAIN_BRANCH}").strip()
        env = {k: v for k, v in os.environ.items() if k != "ARTEL_PULT_GIT"}

        with mock.patch.dict(os.environ, env, clear=True), \
                self.assertRaises(AssertionError) as refused:
            self.in_repo(checkout, "-c", "user.name=ruchnoy",
                         "-c", "user.email=r@example.invalid",
                         "commit", "-q", "--allow-empty", "-m", "ручной коммит")

        self.assertIn("pre-commit", str(refused.exception),
                      self.msg(str(refused.exception)))
        self.assertEqual(self.in_repo(self.clone, "rev-parse",
                                      f"refs/heads/{config.MAIN_BRANCH}").strip(),
                         before, self.msg("main клона сдвинут"))

    def test_ac11_doctor_warns_on_wrong_clone_hooks_and_fix_repairs(self):
        """У клона `core.hooksPath` по очереди: снят, относительный
        `scripts/git-hooks`, чужой абсолютный путь — `doctor` даёт строку
        warn о хуках клона артели; при верном значении такой строки нет.
        `doctor --fix` ставит клону абсолютный путь пина, главной копии —
        прежний `scripts/git-hooks`, её строка `git-hooks` — ok.

        Ловит мутацию: `doctor` сверяет хуки только главной копии (клон с
        относительным путём молча проходит) либо `--fix` ставит клону
        относительный путь.
        """
        self.init()
        self.doctor_fix()
        self.assertEqual(Path(self.clone_hooks_value()).resolve(),
                         self.hooks_path().resolve(),
                         self.msg(f"doctor --fix: {self.clone_hooks_value()!r}"))
        self.assertEqual(self.git("config", "--get", "core.hooksPath").strip(),
                         "scripts/git-hooks", self.msg("хуки главной копии"))
        main_line = [c for c in self.doctor_checks() if c.name == "git-hooks"]
        self.assertTrue(main_line and main_line[0].status == "ok",
                        self.msg(f"строка git-hooks: {main_line}"))
        self.assertEqual(self.hook_warnings(), [],
                         self.msg("предупреждение при верных хуках клона"))

        wrong = ["unset", "scripts/git-hooks", str(self.scratch / "chuzhie-huki")]
        self.rng.shuffle(wrong)
        for value in wrong:
            with self.subTest(core_hooksPath=value, зерно=self.seed):
                if value == "unset":
                    self.in_repo(self.clone, "config", "--unset", "core.hooksPath")
                else:
                    self.in_repo(self.clone, "config", "core.hooksPath", value)
                self.assertTrue(self.hook_warnings(),
                                self.msg(f"нет предупреждения при {value!r}"))
                self.doctor_fix()
                self.assertEqual(Path(self.clone_hooks_value()).resolve(),
                                 self.hooks_path().resolve(),
                                 self.msg(f"doctor --fix после {value!r}"))


# ------------------------------------------------------------ AC-9, AC-10

KOPILKA_HEADER = "| П | Дата | Наблюдение | Где | Состояние |"
BACKLOG_TEXT = f"""# Бэклог пульта

## Копилка

{KOPILKA_HEADER}
|---|---|---|---|---|
| 1 | 01.01 | старое наблюдение | orchestrator/x.py | состояние |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта |
|---|---|---|---|---|---|
| 1 | Кандидат А | Суть А | $10 | orchestrator/a.py | сразу |

## Очередь Оператора

| П | Действие | Условие |
|---|---|---|
| 1 | Действие А | сразу |
"""
BACKLOG_REL = "docs/backlog.md"
ROADMAP_REL = "docs/roadmap.md"
STALE_PHRASE = "файл изменился в origin после сборки записи"
ALPHABET = "абвгдежзиклмнопрстуфхцчшщэюяabcdefghijklmnopqrstuvwxyz0123456789"


class OperatorCommandsSandbox(ProjectAreaSandbox):
    """Главная копия с `docs/backlog.md` и `docs/roadmap.md`, синхронная с
    origin; клон артели заведён `init`; окно тишины закрыто."""

    def extra_main_files(self) -> None:
        for rel, text in ((BACKLOG_REL, BACKLOG_TEXT),
                          (ROADMAP_REL, "# Роадмап\n\nСтарый раздел.\n")):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def setUp(self):
        super().setUp()
        self.init()
        self.helper = self.scratch / "pomoshchnik"
        self.git("clone", "-q", str(self.origin), str(self.helper))
        self.source_dir = self.scratch / "chernoviki"
        self.source_dir.mkdir()

    def word(self, n: int = 8) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(n))

    def origin_main(self) -> str:
        return self.bare_head(self.origin, f"refs/heads/{config.MAIN_BRANCH}")

    def origin_show(self, rel: str) -> str:
        return self.in_repo(self.origin, "show", f"{config.MAIN_BRANCH}:{rel}")

    def origin_has(self, rel: str) -> bool:
        return self.git_ok(self.origin, "cat-file", "-e",
                           f"{config.MAIN_BRANCH}:{rel}")

    def main_copy(self) -> dict:
        return {"head": self.main_head(),
                "branch": self.git("rev-parse", "--abbrev-ref", "HEAD").strip(),
                "refs": self.main_refs(),
                "status": self.main_status()}

    def notes_work(self) -> Path:
        return config.ROOT / ".artel" / "notes-work"

    def push_foreign(self, rel: str, text: str) -> str:
        """Чужая правка `rel` в origin/main из вспомогательного клона; пин
        главной копии остаётся прежним. Возвращает новую голову origin."""
        self.in_repo(self.helper, "pull", "-q", "--ff-only", "origin",
                     config.MAIN_BRANCH)
        path = self.helper / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.in_repo(self.helper, "add", rel)
        self.in_repo(self.helper, "-c", "user.name=chuzhoy",
                     "-c", "user.email=c@example.invalid",
                     "commit", "-q", "-m", "чужая правка")
        self.in_repo(self.helper, "push", "-q", "origin",
                     f"HEAD:{config.MAIN_BRANCH}")
        return self.origin_main()

    def fetch_clone(self) -> None:
        """origin/main клона — текущая голова origin."""
        self.in_repo(self.clone, "fetch", "-q", "origin")

    def source(self, text: str) -> Path:
        path = self.source_dir / f"{self.word()}.md"
        path.write_text(text, encoding="utf-8")
        return path

    def command(self, fn, argv) -> str:
        buf = io.StringIO()
        tail = ""
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(list(argv))
            except SystemExit as exc:
                tail = "" if exc.code is None else f"\n{exc.code}"
        return buf.getvalue() + tail

    def open_window(self) -> None:
        store.insert_task(store.db(), "T-WIN", "окно тишины",
                          config.NOTE_SILENCE_WINDOW_STATES[0], "task/t-win",
                          ARTEL, 10.0)

    def close_window(self) -> None:
        conn = store.db()
        conn.execute("DELETE FROM tasks WHERE id=?", ("T-WIN",))
        conn.commit()

    def assert_through_clone(self, before_main: dict, before_origin: str,
                             out: str) -> str:
        """Новый коммит origin/main есть в клоне, главная копия прежняя,
        `.artel/notes-work` не заведён. Возвращает голову origin."""
        head = self.origin_main()
        self.assertNotEqual(head, before_origin, self.msg(f"origin не сдвинут: {out}"))
        self.assertTrue(self.has_commit(self.clone, head),
                        self.msg(f"коммит {head[:8]} сделан не в клоне: {out}"))
        self.assertEqual(self.main_copy(), before_main,
                         self.msg(f"главная копия изменилась: {out}"))
        self.assertFalse(self.notes_work().exists(),
                         self.msg(".artel/notes-work заведён"))
        return head


class OperatorCommandsThroughCloneTest(OperatorCommandsSandbox):
    """AC-9: `note`, `doc-commit`, `canary pool-seal` — через клон артели."""

    def test_ac9_note_commits_and_pushes_through_the_clone(self):
        """`note копилка` со случайной строкой: строка в `docs/backlog.md`
        origin/main, коммит — в клоне, HEAD/ветки/ссылки/`git status`
        главной копии прежние, `.artel/notes-work` нет.

        Ловит мутацию: `note` по-прежнему коммитит в `.artel/notes-work` —
        каталог заведён, нового коммита origin в клоне нет.
        """
        key = self.word(12)
        row = f"| 2 | 04.10 | {key} | orchestrator/y.py | новое |"
        before_main, before_origin = self.main_copy(), self.origin_main()

        out = self.command(notes.cmd_note, ["копилка", "--text", row])

        self.assert_through_clone(before_main, before_origin, out)
        self.assertIn(key, self.origin_show(BACKLOG_REL), self.msg(out))

    def test_ac9_doc_commit_commits_and_pushes_through_the_clone(self):
        """`doc-commit docs/roadmap.md --from <черновик>`: содержимое в
        origin/main, коммит — в клоне, главная копия прежняя (и файл на её
        диске), `.artel/notes-work` нет.

        Ловит мутацию: `doc-commit` правит и коммитит файл в рабочем дереве
        главной копии — `git status`/HEAD главной копии меняются.
        """
        text = f"# Роадмап\n\n{self.word(20)}\n"
        before_main, before_origin = self.main_copy(), self.origin_main()

        out = self.command(notes.cmd_doc_commit,
                       [ROADMAP_REL, "--from", str(self.source(text)),
                        "--message", self.word(6)])

        self.assert_through_clone(before_main, before_origin, out)
        self.assertEqual(self.origin_show(ROADMAP_REL), text, self.msg(out))
        self.assertEqual((self.root / ROADMAP_REL).read_text(encoding="utf-8"),
                         "# Роадмап\n\nСтарый раздел.\n", self.msg(out))

    def test_ac9_pool_seal_commits_and_pushes_through_the_clone(self):
        """`canary pool-seal` по пулу дома песочницы (1–3 шаблона) и ключу
        из подменённой связки: `canary/pool.sealed` и `canary/guids.txt` —
        в origin/main, коммит — в клоне; рабочее дерево и git главной копии
        прежние, `.artel/notes-work` нет.

        Ловит мутацию: `pool-seal` пишет файлы в рабочее дерево главной
        копии (`config.ROOT/canary/`) — `git status` главной копии
        меняется, в origin ничего не приезжает.
        """
        home = self.scratch / "dom"
        pool = home / config.CANARY_POOL_DIRNAME
        pool.mkdir(parents=True)
        for i in range(self.rng.randint(1, 3)):
            (pool / f"shablon-{i}.md").write_text(f"# ТЗ {self.word()}\n",
                                                  encoding="utf-8")
        before_main, before_origin = self.main_copy(), self.origin_main()

        with mock.patch.object(Path, "home", lambda *a, **k: home), \
                mock.patch.object(keychain, "token",
                                  lambda slot: f"klyuch-{self.seed}"):
            ok, out = self.cli("canary", "pool-seal")

        self.assertTrue(ok, self.msg(out))
        self.assert_through_clone(before_main, before_origin, out)
        self.assertTrue(self.origin_has("canary/pool.sealed"), self.msg(out))
        self.assertTrue(self.origin_has("canary/guids.txt"), self.msg(out))


class HeldRecordBaseFromCloneTest(OperatorCommandsSandbox):
    """AC-10: база сверки удержанной записи — origin/main клона."""

    def test_ac10_held_doc_commit_is_judged_by_clone_origin_main(self):
        """Чужая правка `docs/roadmap.md` в origin (пин главной копии её не
        несёт, origin/main клона — несёт); окно тишины открыто, `doc-commit`
        того же пути удержан; окно закрыто, `doc-commit --flush`.

        Запись уезжает: содержимое записи в origin, отказа «файл изменился»
        нет — HEAD главной копии отличается от origin/main клона, и исход
        определяет origin/main клона.

        Ловит мутацию: база удержанной записи по-прежнему берётся из
        `HEAD:<путь>` главной копии — при флаше blob origin не совпадает с
        базой, запись отказана как устаревшая.
        """
        foreign = f"# Роадмап\n\nчужое {self.word(16)}\n"
        self.push_foreign(ROADMAP_REL, foreign)
        self.fetch_clone()
        self.assertNotEqual(self.main_head(), self.in_repo(
            self.clone, "rev-parse", f"origin/{config.MAIN_BRANCH}").strip())
        text = f"# Роадмап\n\nсвоё {self.word(16)}\n"
        self.open_window()
        held = self.command(notes.cmd_doc_commit,
                        [ROADMAP_REL, "--from", str(self.source(text)),
                         "--message", self.word(6)])
        self.assertEqual(len(notes.pending_notes()), 1,
                         self.msg(f"запись не удержана: {held}"))
        self.close_window()

        out = self.command(notes.cmd_doc_commit, ["--flush"])

        self.assertNotIn(STALE_PHRASE, out, self.msg(out))
        self.assertEqual(self.origin_show(ROADMAP_REL), text, self.msg(out))
        self.assertEqual(notes.pending_notes(), [], self.msg(out))

    def test_ac10_origin_change_after_hold_still_refuses(self):
        """Пин и origin/main клона совпадают на момент удержания; после
        удержания чужая правка того же пути уезжает в origin (клон её
        приносит). Флаш отказывает «файл изменился в origin после сборки
        записи», в origin — чужой текст.

        Ловит мутацию: при переходе на базу клона сверка удержанной записи
        выпала вовсе — запись затирает чужую правку.
        """
        text = f"# Роадмап\n\nсвоё {self.word(16)}\n"
        self.open_window()
        self.command(notes.cmd_doc_commit,
                 [ROADMAP_REL, "--from", str(self.source(text)),
                  "--message", self.word(6)])
        self.assertEqual(len(notes.pending_notes()), 1, self.msg("не удержана"))
        foreign = f"# Роадмап\n\nчужое {self.word(16)}\n"
        self.push_foreign(ROADMAP_REL, foreign)
        self.fetch_clone()
        self.close_window()

        out = self.command(notes.cmd_doc_commit, ["--flush"])

        self.assertIn(STALE_PHRASE, out, self.msg(out))
        self.assertEqual(self.origin_show(ROADMAP_REL), foreign, self.msg(out))

    def test_ac10_held_note_apply_is_judged_by_clone_origin_main(self):
        """Чужая правка `docs/backlog.md` в origin мимо пина (origin/main
        клона её несёт); `note --apply` заготовки, собранной от свежего
        origin, удержан окном тишины; после закрытия окна `note --flush`.

        Заготовка в origin целиком — исход сверки определяет origin/main
        клона, а не отставший HEAD главной копии.

        Ловит мутацию: сверка базы `note --apply` сравнивает с blob
        `HEAD:docs/backlog.md` главной копии и ищет чужие коммиты от пина —
        чужая правка видна «после базы», заготовка отказана.
        """
        foreign = BACKLOG_TEXT + f"\n<!-- чужая правка {self.word()} -->\n"
        self.push_foreign(BACKLOG_REL, foreign)
        self.fetch_clone()
        lines = foreign.split("\n")
        lines.insert(lines.index(KOPILKA_HEADER) + 2,
                     f"| 2 | 04.10 | ЗАГОТОВКА{self.word(6)} | orchestrator/n.py | новое |")
        draft = "\n".join(lines)
        self.open_window()
        self.command(notes.cmd_note, ["--apply", str(self.source(draft)),
                                  "--message", self.word(6)])
        self.assertEqual(len(notes.pending_notes()), 1, self.msg("не удержана"))
        self.close_window()

        out = self.command(notes.cmd_note, ["--flush"])

        self.assertEqual(self.origin_show(BACKLOG_REL), draft, self.msg(out))


# ------------------------------------------------------------- AC-4, AC-5

SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: kod/
budget_usd: 10
---

# SPEC: сквозной прогон {marker}

## Контекст

## Требования

## Критерии приёмки

AC-1. Код задачи лежит в main.

## Не входит
"""

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: сквозной прогон {marker}

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
{appendix}"""

# Зонд в копии `scripts/codebase_map.py` песочницы: регенерацию карты гейт
# мержа запускает в своей временной рабочей копии мержа, и зонд пишет общий
# каталог git этой рабочей копии — чей это git (клона или главной копии),
# видно и после того, как временная копия снята. Пишет, только когда задана
# переменная окружения сценария.
MERGE_PROBE = '''
if __import__("os").environ.get("ARTEL_MERGE_PROBE"):
    import subprocess as _zond_sp
    with open(__import__("os").environ["ARTEL_MERGE_PROBE"], "a",
              encoding="utf-8") as _zond_fh:
        _zond_fh.write(_zond_sp.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True).stdout)

'''
MAIN_GUARD_LINE = 'if __name__ == "__main__":'

PLANK_FIXTURE = ("import unittest\n\n\nclass Fixture(unittest.TestCase):\n"
                 "    def test_ac1_fixture(self):\n"
                 "        self.assertTrue(True)\n")


class TaskFlowSandbox(ProjectAreaSandbox):
    """Пульт с кодом в первом коммите, подставной `gh`, ключи и pre-flight
    ролей подменены; шаг developer — штатный `runner.cmd_run` с подменённым
    агентом, мерж — `approve` на `merge_gate`."""

    COPY_CODE = True

    def extra_main_files(self) -> None:
        path = self.root / "scripts" / "codebase_map.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn(MAIN_GUARD_LINE, text, "зонду некуда встать")
        path.write_text(text.replace(MAIN_GUARD_LINE, MERGE_PROBE + MAIN_GUARD_LINE, 1),
                        encoding="utf-8")

    def setUp(self):
        super().setUp()
        self.probe = self.scratch / "zond-merzha.txt"
        patches = [mock.patch.object(stack, "check_stack", _stub_check_stack),
                   mock.patch.object(keychain, "token", lambda slot: "tok-test"),
                   mock.patch("orchestrator.doctor.preflight_checks",
                              lambda role, target: [])]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        bindir = self.root / ".artel" / "fake-bin"
        bindir.mkdir(parents=True, exist_ok=True)
        gh = bindir / "gh"
        gh.write_text(f"#!{sys.executable}\n{FAKE_GH}", encoding="utf-8")
        gh.chmod(0o755)
        self.gh_state = self.root / ".artel" / "fake-gh.json"
        self.gh = {"checks": {}, "default": green_runs()}
        self.save_gh()
        env = mock.patch.dict(os.environ, {
            "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            "ARTEL_FAKE_GH_STATE": str(self.gh_state)})
        env.start()
        self.addCleanup(env.stop)

        self.helper = self.scratch / "pomoshchnik"
        self.git("clone", "-q", str(self.origin), str(self.helper))
        self.foreign_no = 0
        self.init()

    # ----------------------------------------------------------------- gh

    def save_gh(self) -> None:
        self.gh_state.write_text(json.dumps(self.gh, ensure_ascii=False),
                                 encoding="utf-8")

    def set_checks(self, sha: str, runs: list) -> None:
        self.gh["checks"][sha] = runs
        self.save_gh()

    # ------------------------------------------------------------- origin

    def origin_main(self, bare: Path | None = None) -> str:
        return self.bare_head(bare or self.origin,
                              f"refs/heads/{config.MAIN_BRANCH}")

    def origin_tree(self, bare: Path | None = None) -> list:
        return self.in_repo(bare or self.origin, "ls-tree", "-r", "--name-only",
                            f"refs/heads/{config.MAIN_BRANCH}").splitlines()

    def origin_file(self, rel: str, bare: Path | None = None) -> str:
        return self.in_repo(bare or self.origin, "show",
                            f"{config.MAIN_BRANCH}:{rel}")

    def push_foreign(self, runs: list | None = None) -> str:
        """Чужой коммит кода в origin/main (из вспомогательного клона): ветке
        задачи на мерже нужна подтяжка main."""
        self.in_repo(self.helper, "pull", "-q", "--ff-only", "origin",
                     config.MAIN_BRANCH)
        self.foreign_no += 1
        rel = f"chuzhoy_kod_{self.foreign_no}.py"
        (self.helper / rel).write_text(f"X = {self.foreign_no}\n", encoding="utf-8")
        self.in_repo(self.helper, "add", rel)
        self.in_repo(self.helper, "-c", "user.name=chuzhoy",
                     "-c", "user.email=c@example.invalid",
                     "commit", "-q", "-m", f"чужая правка {self.foreign_no}")
        self.in_repo(self.helper, "push", "-q", "origin", f"HEAD:{config.MAIN_BRANCH}")
        sha = self.origin_main()
        if runs is not None:
            self.set_checks(sha, runs)
        return sha

    # --------------------------------------------------------------- шаги

    def developer_step(self, task: str, code: dict, docs: dict,
                       remove: tuple = (), target: str = ARTEL) -> str:
        """Шаг developer штатным `runner.cmd_run`: подменённый агент пишет
        `code` ({путь: текст}) в свой рабочий каталог и удаляет `remove`,
        `docs` — в каталог документов задачи; ничего не коммитит сам."""
        def spawn(cmd, *args, **kwargs):
            if not is_claude_call(cmd):
                return subprocess.Popen(cmd, *args, **kwargs)
            cwd = Path(kwargs.get("cwd"))
            for rel, text in code.items():
                (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
                (cwd / rel).write_text(text, encoding="utf-8")
            for rel in remove:
                (cwd / rel).unlink()
            docs_dir = self.docs_dir(task, target)
            for rel, text in docs.items():
                (docs_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                (docs_dir / rel).write_text(text, encoding="utf-8")
            return FakeProc(["готово\n"])

        store.record_fixation(store.db(), task)
        self.set_state(task, "in_dev")
        out = io.StringIO()
        with mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                contextlib.redirect_stdout(out):
            try:
                runner.cmd_run(task)
            except SystemExit as exc:
                out.write(f"\nSystemExit(run): {exc.code}")
        return out.getvalue()

    def task_docs(self, task: str, marker: str, appendix: str = "") -> dict:
        return {"SPEC.md": SPEC_READY.format(task=task, marker=marker),
                "PLAN.md": PLAN_READY.format(task=task, marker=marker,
                                             appendix=appendix),
                "acceptance_tests/test_ac1_fixture.py": PLANK_FIXTURE}

    @contextlib.contextmanager
    def fake_clock(self):
        """Подставные часы на время мержа: пауза опроса двигает их
        мгновенно."""
        state = {"clock": 0.0}
        base_mono, base_wall = time.monotonic(), time.time()

        def sleep(seconds):
            state["clock"] += float(seconds)
            if state["clock"] > 10 * 24 * 3600:
                raise AssertionError(self.msg("ожидание не кончается"))

        with mock.patch("time.monotonic", side_effect=lambda: base_mono + state["clock"]), \
                mock.patch("time.time", side_effect=lambda: base_wall + state["clock"]), \
                patch_pult_sleep(mock.Mock(side_effect=sleep)):
            yield

    def approve_until_settled(self, task: str, attempts: int = 4) -> str:
        """`approve` на `merge_gate`, пока задача на гейте (подтяжка main
        возвращает «жди» и требует повтора); весь вывод."""
        outputs = []
        # Сверка фиксации документов при `approve` — не предмет сценария
        # (тот же патч, что в `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`).
        self.probe.unlink(missing_ok=True)
        with self.fake_clock(), \
                mock.patch.dict(os.environ, {"ARTEL_MERGE_PROBE": str(self.probe)}), \
                mock.patch.object(fixation, "read", return_value=("", True)):
            for _ in range(attempts):
                ok, out = self.cli("approve", task)
                outputs.append(out)
                if store.get_task(store.db(), task)["state"] != "merge_gate":
                    break
        return "\n".join(outputs)

    def merge_git_dirs(self) -> list:
        """Общие каталоги git временных рабочих копий мержа последнего
        `approve_until_settled` (по зонду регенерации карты)."""
        if not self.probe.is_file():
            return []
        return [Path(line).resolve() for line in
                self.probe.read_text(encoding="utf-8").splitlines() if line.strip()]

    def assert_merge_copy_in_clone(self, out: str) -> None:
        dirs = self.merge_git_dirs()
        self.assertTrue(dirs, self.msg(f"зонд мержа не сработал: {out}"))
        for git_dir in dirs:
            self.assertTrue(git_dir.is_relative_to(self.clone.resolve()),
                            self.msg(f"рабочая копия мержа в git {git_dir}, "
                                     f"не в клоне {self.clone}"))

    def state_of(self, task: str) -> str:
        return store.get_task(store.db(), task)["state"]

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), task))

    def run_to_merge_gate(self, code: dict, docs_extra: dict | None = None,
                          remove: tuple = (), appendix: str = "",
                          target: str = ARTEL) -> tuple[str, str]:
        """`new` → шаг developer → чужой коммит в main → `merge_gate`.
        (id задачи, вывод шага)."""
        task = self.new_task(target=None if target == ARTEL else target)
        marker = f"m{self.rng.randrange(10 ** 9)}"
        docs = self.task_docs(task, marker, appendix)
        docs.update(docs_extra or {})
        out = self.developer_step(task, code, docs, remove, target)
        if target == ARTEL:
            self.push_foreign(green_runs())
        self.set_state(task, "merge_gate")
        return task, out


class EndToEndMainCopyUntouchedTest(TaskFlowSandbox):
    """AC-4: сквозной прогон FSM задачи артели не меняет git главной копии."""

    def test_ac4_new_to_done_leaves_main_copy_git_unchanged(self):
        """`new` → шаг developer (агент пишет код, не коммитит — коммитит
        автокоммит шага) → чужой коммит в origin/main (подтяжка main на
        мерже) → `approve` на `merge_gate` → `done`.

        `refs/heads/*`, `refs/artifacts/*`, HEAD и `git worktree list`
        главной копии — те же, что до `new`, после `new`, после шага и
        после мержа; временная рабочая копия мержа — в git клона (зонд
        регенерации карты); ссылка документов задачи есть в клоне и в его
        origin; новая голова origin/main (несёт код задачи и чужой коммит)
        есть в клоне.

        Ловит мутацию: временная рабочая копия мержа (`worktree add
        --detach`) или ветка задачи заводятся в git главной копии — зонд
        мержа видит git главной копии, её `refs/heads`/`git worktree list`
        после шага меняются, коммит мержа рождается в ней, а не в клоне.
        """
        before = self.main_snapshot()
        code_rel = f"kod/zadacha_{self.rng.randrange(10 ** 6)}.py"
        marker = f"m{self.rng.randrange(10 ** 9)}"

        task = self.new_task()
        self.assertEqual(self.main_snapshot(), before,
                         self.msg("git главной копии изменён командой new"))
        step_out = self.developer_step(task, {code_rel: "VALUE = 1\n"},
                                       self.task_docs(task, marker))
        self.assertEqual(self.main_snapshot(), before,
                         self.msg(f"git главной копии изменён шагом: {step_out}"))
        foreign = self.push_foreign(green_runs())
        self.set_state(task, "merge_gate")
        out = self.approve_until_settled(task)

        self.assertEqual(self.state_of(task), "done",
                         self.msg(f"{step_out}\n{out}\n{self.journal(task)}"))
        head = self.origin_main()
        self.assertIn(code_rel, self.origin_tree(), self.msg(out))
        self.assertTrue(self.git_ok(self.origin, "merge-base", "--is-ancestor",
                                    foreign, head), self.msg(out))
        self.assert_merge_copy_in_clone(out)
        self.assertEqual(self.main_snapshot(), before,
                         self.msg(f"git главной копии изменился: {out}"))
        ref = f"refs/artifacts/{task}"
        self.assertTrue(self.bare_head(self.origin, ref),
                        self.msg("ссылки документов нет в origin клона"))
        self.assertTrue(self.git_ok(self.clone, "rev-parse", "--verify", "--quiet", ref),
                        self.msg("ссылки документов нет в клоне"))
        self.assertTrue(self.has_commit(self.clone, head),
                        self.msg(f"голова main {head[:8]} не в клоне"))


class MergeGateStepsOnCloneTest(TaskFlowSandbox):
    """AC-5: на гейте мержа задачи артели (путь контекста — клон, не
    `config.ROOT`) исполняется каждый шаг требования 3."""

    def assert_refused(self, task: str, before: str, out: str, *names: str) -> None:
        text = f"{out}\n{self.journal(task)}"
        self.assertNotEqual(self.state_of(task), "done", self.msg(text))
        self.assertEqual(self.origin_main(), before, self.msg(f"origin/main сдвинут: {text}"))
        for name in names:
            self.assertIn(name, text, self.msg(f"отказ не называет {name}: {text}"))

    def assert_merged_in_clone(self, task: str, out: str) -> str:
        self.assertEqual(self.state_of(task), "done",
                         self.msg(f"{out}\n{self.journal(task)}"))
        head = self.origin_main()
        self.assert_merge_copy_in_clone(out)
        self.assertTrue(self.has_commit(self.clone, head),
                        self.msg(f"коммит {head[:8]} рождён не в клоне"))
        return head

    def test_ac5_protected_path_in_diff_refuses(self):
        """Код задачи трогает защищённый путь (`skills/…` либо
        `gates.yaml`, выбор случаен): мерж не проходит, origin/main не
        сдвинут, отказ называет путь.

        Ловит мутацию: проверка защищённых путей диффа включается
        сравнением пути контекста с `config.ROOT` — для клона артели она
        молча пропущена и задача мержится.
        """
        rel = self.rng.choice(("skills/novyi-skil.md", "gates.yaml"))
        task, step_out = self.run_to_merge_gate({rel: "правка\n"})
        before = self.origin_main()

        out = self.approve_until_settled(task)

        self.assert_refused(task, before, f"{step_out}\n{out}", rel)

    def test_ac5_deleted_existing_test_refuses(self):
        """Код задачи удаляет существующий тест `tests/test_green.py`: мерж
        не проходит, origin/main не сдвинут, отказ называет файл.

        Ловит мутацию: проверка сохранности тестов диффа выключена для
        пути контекста, отличного от `config.ROOT`.
        """
        task, step_out = self.run_to_merge_gate(
            {f"kod/kod_{self.rng.randrange(10 ** 6)}.py": "A = 1\n"},
            remove=("tests/test_green.py",))
        before = self.origin_main()

        out = self.approve_until_settled(task)

        self.assert_refused(task, before, f"{step_out}\n{out}", "test_green")

    def test_ac5_guard_all_violation_refuses(self):
        """Снимок документов задачи несёт `acceptance_tests/README.md` без
        frontmatter: `guard --all` по дереву мержа клона отказывает, origin/
        main не сдвинут, отказ называет файл.

        Ловит мутацию: `guard --all` включён сравнением с `config.ROOT` —
        для клона не исполняется, нарушающий снимок уезжает в main.
        """
        task, step_out = self.run_to_merge_gate(
            {f"kod/kod_{self.rng.randrange(10 ** 6)}.py": "A = 1\n"},
            docs_extra={"acceptance_tests/README.md": "Пояснение без frontmatter.\n"})
        before = self.origin_main()

        out = self.approve_until_settled(task)

        self.assert_refused(task, before, f"{step_out}\n{out}", "README.md")

    def test_ac5_red_main_ci_refuses(self):
        """Голова origin/main (чужой коммит) — с упавшей проверкой кода:
        мерж отказывает «main красный», origin/main не сдвинут.

        Ловит мутацию: сверка цвета CI `main` перед мержем включена
        сравнением с `config.ROOT` — линия main клона не сверяется, задача
        мержится поверх красного main.
        """
        task, step_out = self.run_to_merge_gate(
            {f"kod/kod_{self.rng.randrange(10 ** 6)}.py": "A = 1\n"})
        self.set_checks(self.origin_main(), red_runs())
        before = self.origin_main()

        out = self.approve_until_settled(task)

        self.assert_refused(task, before, f"{step_out}\n{out}", "main красный")

    def test_ac5_plan_appendix_is_applied_in_the_clone_merge_copy(self):
        """PLAN несёт приложение к защищённому `docs/invariants.md`
        (случайная строка): после мержа строка — в `docs/invariants.md`
        origin/main, коммит рождён в клоне.

        Ловит мутацию: наложение приложений PLAN включено сравнением с
        `config.ROOT` — для клона пропущено, строки в main нет.
        """
        line = f"| 99 | инвариант песочницы {self.rng.randrange(10 ** 9)} | — | — |"
        appendix = ("\n## Приложение: инварианты\n\n```diff\n"
                    "diff --git a/docs/invariants.md b/docs/invariants.md\n"
                    "new file mode 100644\n"
                    "--- /dev/null\n"
                    "+++ b/docs/invariants.md\n"
                    "@@ -0,0 +1 @@\n"
                    f"+{line}\n"
                    "```\n")
        task, step_out = self.run_to_merge_gate(
            {f"kod/kod_{self.rng.randrange(10 ** 6)}.py": "A = 1\n"}, appendix=appendix)

        out = self.approve_until_settled(task)

        self.assert_merged_in_clone(task, f"{step_out}\n{out}")
        self.assertIn(line, self.origin_file("docs/invariants.md"), self.msg(out))

    def test_ac5_code_map_and_retro_are_committed_in_the_clone_merge_copy(self):
        """Чистый мерж: в origin/main — `docs/retro/<id>.md` и
        регенерированная карта кодовой базы (не заглушка первого коммита),
        коммит рождён в клоне.

        Ловит мутацию: регенерация карты и RETRO включены сравнением с
        `config.ROOT` — для клона пропущены, в main нет ни RETRO, ни новой
        карты.
        """
        task, step_out = self.run_to_merge_gate(
            {f"kod/kod_{self.rng.randrange(10 ** 6)}.py": "A = 1\n"})

        out = self.approve_until_settled(task)

        self.assert_merged_in_clone(task, f"{step_out}\n{out}")
        self.assertIn(f"docs/retro/{task}.md", self.origin_tree(), self.msg(out))
        self.assertNotEqual(self.origin_file("docs/codebase-map.md"),
                            CODE_MAP_PLACEHOLDER, self.msg(out))

    def test_ac5_external_project_skips_the_artel_steps(self):
        """Задача внешнего проекта `sled` трогает `skills/…` (защищённый
        путь пульта) и мержится: `done`, файл — в main проекта; ни RETRO,
        ни карты кодовой базы в main проекта нет.

        Ловит мутацию: признак «проект задачи — артель» перепутан с «любой
        проект» — шаги артели исполняются для внешнего проекта (отказ по
        защищённому пути, RETRO в main проекта).
        """
        bare = self.add_external_project(SLED)
        self.init()
        rel = f"skills/proekt-{self.rng.randrange(10 ** 6)}.md"
        task, step_out = self.run_to_merge_gate({rel: "проект\n"}, target=SLED)

        out = self.approve_until_settled(task)

        text = f"{step_out}\n{out}\n{self.journal(task)}"
        self.assertEqual(self.state_of(task), "done", self.msg(text))
        tree = self.origin_tree(bare)
        self.assertIn(rel, tree, self.msg(text))
        self.assertNotIn(f"docs/retro/{task}.md", tree, self.msg(text))
        self.assertNotIn("docs/codebase-map.md", tree, self.msg(text))


# -------------------------------------------------------------------- AC-13

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class HistoricalDocsRefsTest(ProjectAreaSandbox):
    """AC-13: исторические ссылки документов артели читаются после этапа:
    `docs`, `docs --fetch-all`, пересборка `retro_corpus` — через клон;
    ссылки главной копии не меняются."""

    def setUp(self):
        super().setUp()
        self.src = self.scratch / "docs-src"
        self.git("init", "-q", "-b", "scratch", str(self.src))
        self.init()

    def task_id(self) -> str:
        return "01H" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))

    def docs_commit(self, task_id: str, files: dict) -> str:
        """Коммит без родителя с документами в каталоге задачи (раскладка
        ссылки документов) во вспомогательном репозитории; sha коммита."""
        self.in_repo(self.src, "checkout", "-q", "--orphan", f"o-{task_id}")
        self.in_repo(self.src, "rm", "-rfq", "--ignore-unmatch", ".")
        for name, text in files.items():
            path = self.src / "tasks" / task_id / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.in_repo(self.src, "add", "-A")
        self.in_repo(self.src, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                     "commit", "-q", "-m", f"{task_id}: документы")
        return self.in_repo(self.src, "rev-parse", "HEAD").strip()

    def place(self, repo: Path, task_id: str, sha: str) -> None:
        self.in_repo(self.src, "push", "-q", str(repo), f"{sha}:refs/artifacts/{task_id}")

    def closed_task(self, task_id: str) -> None:
        store.insert_task(store.db(), task_id, f"история {task_id}", "done",
                          f"task/{task_id.lower()}-istoriya", ARTEL,
                          config.DEFAULT_BUDGET_USD)

    def spec(self, task_id: str, marker: str) -> str:
        return (f"---\ntask: {task_id}\ntype: spec\nauthor_role: analyst\n"
                f"status: ready\nschema_version: 5\n---\n\n# SPEC: {marker}\n")

    def test_ac13_docs_reads_historical_ref_with_and_without_origin(self):
        """Две закрытые задачи, ссылки которых есть в git главной копии:
        одна есть и в origin, другая — нет (в случайном порядке).
        `docs <id> SPEC.md` возвращает документ обеих; ссылки главной копии
        после этого прежние.

        Ловит мутацию: `docs` читает только клон и `origin` — документ
        ссылки, которой нет в origin, не находится.
        """
        cases = [("v-origin", True), ("tolko-glavnaya", False)]
        self.rng.shuffle(cases)
        prepared = []
        for label, in_origin in cases:
            task = self.task_id()
            marker = f"{label}-{self.rng.randrange(10 ** 9)}"
            sha = self.docs_commit(task, {"SPEC.md": self.spec(task, marker)})
            self.place(self.root, task, sha)
            if in_origin:
                self.place(self.origin, task, sha)
            self.closed_task(task)
            prepared.append((label, task, marker))
        refs_before = self.main_refs()

        for label, task, marker in prepared:
            with self.subTest(случай=label, зерно=self.seed):
                ok, out = self.cli("docs", task, "SPEC.md")
                self.assertTrue(ok, self.msg(f"{label}: {out}"))
                self.assertIn(marker, out, self.msg(f"{label}: {out}"))
        self.assertEqual(self.main_refs(), refs_before,
                         self.msg("ссылки главной копии изменились"))

    def test_ac13_fetch_all_and_retro_corpus_go_through_the_clone(self):
        """В origin — ссылка закрытой задачи с RETRO (поля `operator`,
        `model`, `artel_sha`), которой нет ни в главной копии, ни в клоне.
        `docs --fetch-all` приносит её в клон; пересборка кэша
        `retro_corpus` находит запись этой задачи; ссылки главной копии
        прежние.

        Ловит мутацию: `docs --fetch-all` приносит ссылки в git главной
        копии (`refs/artifacts/*` главной копии меняются), а `retro_corpus`
        читает `projects/artel/workspace` — записи задачи в кэше нет.
        """
        task = self.task_id()
        operator = f"op-{self.rng.randrange(10 ** 6)}"
        retro = (f"---\ntask: {task}\ntype: retro\noperator: {operator}\n"
                 f"model: model-x\nartel_sha: {'a' * 40}\n---\n\n# RETRO\n")
        sha = self.docs_commit(task, {"SPEC.md": self.spec(task, "retro"),
                                      "RETRO.md": retro})
        self.place(self.origin, task, sha)
        self.closed_task(task)
        refs_before = self.main_refs()

        ok, out = self.cli("docs", "--fetch-all")

        self.assertTrue(self.git_ok(self.clone, "rev-parse", "--verify", "--quiet",
                                    f"refs/artifacts/{task}"),
                        self.msg(f"ссылка не в клоне: {out}"))
        cache = self.scratch / "retro-cache.json"
        with mock.patch.object(retro_corpus, "CACHE_PATH", cache):
            rows = retro_corpus.rebuild_cache()
        found = [r for r in rows if r.get("task_id") == task]
        self.assertTrue(found, self.msg(f"записи задачи нет в кэше: {rows}"))
        self.assertEqual(found[0].get("operator"), operator, self.msg(str(found)))
        self.assertEqual(self.main_refs(), refs_before,
                         self.msg(f"ссылки главной копии изменились: {out}"))


if __name__ == "__main__":
    unittest.main()
