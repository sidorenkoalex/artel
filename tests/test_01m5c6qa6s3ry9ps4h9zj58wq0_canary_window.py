"""Потребители реестра живого прогона канарейки: сверка живости, окно тишины note/doc-commit, мерж на merge_gate и обходы окна с --during-canary.

Группа: долгоживущий
Красен до реализации: реестра живых прогонов нет — окно тишины, гейт мержа и обходы окна канарейку не видят (запись уходит в origin, мерж идёт), а флага --during-canary команды не знают.

Связка, которую держит файл: «живой прогон канарейки в ДРУГОМ процессе —
его запись реестра — команды Оператора `note`/`doc-commit`/`canary
pool-seal`/`approve` (диспетчером `artel.main()` тем же argv, что набирает
Оператор) — main настоящего bare `origin` и журнал пульта». Живой прогон —
настоящая команда `artel.py canary --k 1 --sha <sha> --template <шаблон>`
в дочернем процессе с подменённым ведением задачи (процесс-сон, без ролей
и сети); о старте ведения ребёнок сообщает строкой в канал — ни ожидания по
часам, ни зависимости от настоящей канарейки на машине. Конец прогона —
SIGTERM ребёнку (штатная уборка), «мёртвый pid» — SIGKILL (запись остаётся).
Время старта процесса при сверке задаётся подменой ответа `ps -o lstart=`
(его читает `process_start_time`) в процессе теста.

Песочница — `tests.sandbox.RealGitSandbox` по образцу
`tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`: главная копия
пульта (она же клон артели) с копией `orchestrator/`/`scripts/`, бэклогом и
заглушкой карты, bare `origin`, подставной `gh` (зелёные проверки),
подставные часы и пауза пульта. Набор канарейки не по умолчанию — запись
`canary_sets:` локального слоя песочницы на модели каталога-фикстуры.

Запись реестра ищется по поведению (имена каталога и формата SPEC не
задаёт): файл под корнем песочницы вне `.git` и вне временных клонов, в
имени — `run_stamp` и pid прогона; метка — файл того же каталога с тем же
`run_stamp` в имени и без других цифр.

Идентификаторы, тексты записей и основания порождаются от зерна; зерно
печатается и входит в текст провала.
"""
import contextlib
import io
import json
import os
import random
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import (artel, canary, catalog, config, doctor, keychain, models,
                          store)
from tests.sandbox import (ALL_CONFIG_ATTRS, FIXTURE_OTHER_MODEL, RealGitSandbox,
                           capture, declare_target, patch_pult_sleep)

REPO = Path(__file__).resolve().parent.parent
TASKS_DIR = config.TASKS.name
STAMP_RE = re.compile(r"\d{8}T\d{6}Z")
LSTART_FORMAT = "%a %b %d %H:%M:%S %Y"
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
MAP_REL = "docs/codebase-map.md"
MAP_PLACEHOLDER = ("---\nbuilt_at_sha: " + "0" * 40 + "\n---\n\n"
                   "# Карта кодовой базы (заглушка песочницы)\n")
BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое наблюдение | orchestrator/x.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |
"""
FLAG = "--during-canary"
TEMPLATE = "uchebnaya"
# Допуск сверки времени старта — `_LSTART_SPAN` (2 с,
# orchestrator/doctor/stale_cycles.py:36): сдвиг «внутри» — 1 с, «снаружи» — час.
INSIDE_SPAN = timedelta(seconds=1)
OUTSIDE_SPAN = timedelta(hours=1)

_CHILD = r'''
import contextlib, json, os, subprocess, sys
from pathlib import Path
from unittest import mock
from orchestrator import artel, canary, catalog, config, runner
settings = json.loads(Path(sys.argv[1]).read_text())
for name, value in settings["config"].items():
    setattr(config, name, Path(value))
ready = int(settings["ready_fd"])
real_popen = subprocess.Popen
real_run = subprocess.run
def run(argv, *args, **kwargs):
    words = [os.fsdecode(a) for a in argv] if isinstance(argv, (list, tuple)) else []
    if settings.get("ps_none") and "lstart=" in words and str(os.getpid()) in words:
        return subprocess.CompletedProcess(argv, 1, "", "")
    return real_run(argv, *args, **kwargs)
def launch(argv, *args, **kwargs):
    words = [os.fsdecode(a) for a in argv] if isinstance(argv, (list, tuple)) else []
    if canary.CANARY_DRIVE_MODULE not in words:
        return real_popen(argv, *args, **kwargs)
    drive = real_popen([sys.executable, "-c", "import time; time.sleep(600)"],
                       *args, **kwargs)
    os.write(ready, (json.dumps({"pid": os.getpid(), "drive_pid": drive.pid})
                     + "\n").encode())
    return drive
with contextlib.ExitStack() as stack:
    stack.enter_context(mock.patch.object(Path, "home", return_value=Path(settings["home"])))
    stack.enter_context(mock.patch.object(catalog, "cmd_init"))
    stack.enter_context(mock.patch.object(subprocess, "Popen", launch))
    stack.enter_context(mock.patch.object(subprocess, "run", run))
    stack.enter_context(mock.patch.object(runner, "in_role_environment", return_value=False))
    sys.argv = ["artel.py", "canary", *settings["argv"]]
    artel.main()
'''

# Подставной `gh`: зелёные проверки на любой коммит, пустые списки прогонов
# и запросов на слияние. Флаг-файл `spawn` рядом со скриптом — при первом
# запросе проверок, называющем sha из флага (голова origin/main до мержа:
# сверка цвета CI main — последняя проверка тела окна перед плотницким
# мержем и push), он запускает дочернюю канарейку (настройки — в файле) и
# ждёт старта её ведения: так канарейка стартует посреди тела окна мержа.
FAKE_GH = r'''
import json, os, re, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
joined = " ".join(args)
here = Path(__file__).resolve().parent
if args[:1] == ["api"] and "/check-runs" in joined:
    spawn = here / "spawn.json"
    job = json.loads(spawn.read_text()) if spawn.exists() else None
    if job is not None and job["match"] in joined:
        spawn.unlink()
        read_fd, write_fd = os.pipe()
        settings = json.loads(Path(job["settings"]).read_text())
        settings["ready_fd"] = write_fd
        Path(job["settings"]).write_text(json.dumps(settings))
        with open(job["log"], "wb") as log:
            child = subprocess.Popen([sys.executable, "-c", Path(job["child"]).read_text(),
                                      job["settings"]],
                                     cwd=job["cwd"], stdout=log, stderr=subprocess.STDOUT,
                                     pass_fds=(write_fd,), start_new_session=True)
        os.close(write_fd)
        with os.fdopen(read_fd) as ready:
            line = ready.readline()
        Path(job["state"]).write_text(json.dumps({"child": child.pid, "ready": line}))
    page = re.search(r"[?&]page=(\d+)", joined)
    runs = [{"name": "тесты кода", "status": "completed",
             "conclusion": "success"}]
    shown = runs if page is None or page.group(1) == "1" else []
    print(json.dumps({"total_count": len(runs), "check_runs": shown},
                     ensure_ascii=False))
    sys.exit(0)
if args[:2] in (["run", "list"], ["pr", "list"], ["pr", "view"]):
    print("[]")
    sys.exit(0)
sys.stderr.write("gh песочницы: вызов не поддержан: " + joined + "\n")
sys.exit(1)
'''


def plank_text() -> str:
    return ('"""Планка задачи песочницы."""\nimport unittest\n\n\n'
            'class Fixture(unittest.TestCase):\n'
            '    def test_@ac1_fixture(self):\n        pass\n').replace("@ac", "ac")


def spec_text(task: str) -> str:
    return (f"---\ntask: {task}\ntype: spec\nauthor_role: analyst\n"
            f"status: ready\nschema_version: 5\nzones: kod/\nbudget_usd: 10\n---\n\n"
            f"# SPEC: задача {task}\n\n"
            f"## Контекст\n\nЗадача песочницы мержа.\n\n## Требования\n\n"
            f"1. Требование.\n\n## Критерии приёмки\n\n@AC-1. Критерий.\n\n"
            f"## Не входит\n\n- Ничего.\n").replace("@AC", "AC")


def plan_text(task: str) -> str:
    return (f"---\ntask: {task}\ntype: plan\nauthor_role: developer\n"
            f"status: ready\nschema_version: 1\n---\n\n# PLAN: задача {task}\n\n"
            f"## Подход\n\nФикстура.\n\n## Шаги\n\n## Покрытие требований\n\n"
            f"## Влияние на систему\n")


def window_refusal(stamp: str, sha: str) -> str:
    return (f"идёт канарейка {stamp} на {sha[:7]}: команда сдвинет main — "
            f'дождись итога или повтори с {FLAG} "<основание>"')


def merge_refusal(stamp: str, sha: str) -> str:
    return (f"идёт канарейка {stamp} на {sha[:7]}: мерж сдвинет main под "
            f"проверяемым коммитом — дождись итога или повтори с {FLAG} "
            f'"<основание>"')


class CanaryWindowTest(RealGitSandbox):
    """Главная копия пульта с origin, бэклогом и пулом канарейки; БД без задач."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        role = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role.start()
        self.addCleanup(role.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        self.temp_root = self.root / ".artel" / "canary-test-tmp"
        self.temp_root.mkdir(parents=True)
        temp_patch = mock.patch.object(tempfile, "tempdir", str(self.temp_root))
        temp_patch.start()
        self.addCleanup(temp_patch.stop)
        env_patch = mock.patch.dict(os.environ, {"TMPDIR": str(self.temp_root)})
        env_patch.start()
        self.addCleanup(env_patch.stop)

        self.use_catalog_fixture()
        self.use_role_map()
        self.set_name = "nabor-" + self.token(6).lower()
        layer = models.local_template_text() + (
            f"\ncanary_sets:\n  {self.set_name}:\n"
            f"    developer:\n      provider: claude\n"
            f"      model: {FIXTURE_OTHER_MODEL}\n")
        config.MODELS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        config.MODELS_LOCAL.write_text(layer, encoding="utf-8")

        self.home = Path(tempfile.mkdtemp(prefix="canary-window-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir()
        (pool / f"{TEMPLATE}.md").write_text("# учебная задача\n", encoding="utf-8")
        home_patch = mock.patch.object(Path, "home", return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

        self.prepare_main()
        self.origin = self.add_synced_origin()
        src = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, ignore_errors=True)
        self.docs_src = Path(src) / "docs-src"
        self.git("init", "-q", "-b", "docs-src", str(self.docs_src))
        capture(catalog.cmd_init)
        self.conn = store.db()

        self.bindir = self.root / ".artel" / "fake-bin"
        self.bindir.mkdir(parents=True, exist_ok=True)
        gh = self.bindir / "gh"
        gh.write_text(f"#!{sys.executable}\n{FAKE_GH}", encoding="utf-8")
        gh.chmod(0o755)
        env = mock.patch.dict(os.environ, {
            "PATH": f"{self.bindir}{os.pathsep}{os.environ.get('PATH', '')}"})
        env.start()
        self.addCleanup(env.stop)
        self.child_file = self.home / "child.py"
        self.child_file.write_text(_CHILD, encoding="utf-8")

        self.clock = 0.0
        self.on_sleep = None
        base_mono, base_wall = time.monotonic(), time.time()
        for target, fake in (("time.monotonic", lambda: base_mono + self.clock),
                             ("time.time", lambda: base_wall + self.clock)):
            patcher = mock.patch(target, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(patch_pult_sleep(self.fake_sleep).close)

        self.children = []
        self.stray_pids = []
        self.calls = 0
        self.addCleanup(self.stop_children)

    # ------------------------------------------------------------ фикстуры

    def token(self, n: int = 10) -> str:
        return "".join(self.rng.choice(ULID_ALPHABET) for _ in range(n))

    def msg(self, text) -> str:
        return f"зерно: {self.seed}; {text}"

    def fake_sleep(self, seconds) -> None:
        self.clock += float(seconds)
        hook, self.on_sleep = self.on_sleep, None
        if hook is not None:
            hook()
        if self.clock > 10 * 24 * 3600:
            raise AssertionError(self.msg("ожидание не кончается"))

    def prepare_main(self) -> None:
        for name in ("orchestrator", "scripts"):
            shutil.copytree(REPO / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / MAP_REL).write_text(MAP_PLACEHOLDER, encoding="utf-8")
        (self.root / "docs" / "backlog.md").write_text(BACKLOG_TEXT, encoding="utf-8")
        entry = self.root / canary.CANARY_DRIVE_ENTRY
        if not entry.exists():
            entry.parent.mkdir(parents=True, exist_ok=True)
            entry.write_text("# вход заменён процессом теста\n", encoding="utf-8")
        old = "01H" + self.token(23)
        plank = self.root / TASKS_DIR / old / "acceptance_tests" / "test_old.py"
        plank.parent.mkdir(parents=True)
        plank.write_text(plank_text(), encoding="utf-8")
        retro_path = self.root / "docs" / "retro" / f"{old}.md"
        retro_path.parent.mkdir(parents=True)
        retro_path.write_text(f"# RETRO: {old}\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "код пульта")

    def stop_children(self):
        for child in self.children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=30)
        for pid in self.stray_pids:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pid, signal.SIGKILL)
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGKILL)

    # ------------------------------------------------------ реестр на диске

    def scan(self) -> list:
        found = []
        for path in self.root.rglob("*"):
            if ".git" in path.parts or self.temp_root in path.parents:
                continue
            if path.is_file() and STAMP_RE.search(path.name):
                found.append(path)
        return found

    def records(self, pid: int) -> list:
        return [p for p in self.scan()
                if re.search(rf"(?<!\d){pid}(?!\d)", p.name)]

    @staticmethod
    def marks(record: Path) -> list:
        stamp = STAMP_RE.search(record.name).group(0)
        return [p for p in record.parent.iterdir() if p.is_file()
                and stamp in p.name and not re.search(r"\d", p.name.replace(stamp, ""))]

    # ------------------------------------------------- живой прогон канарейки

    def origin_main(self) -> str:
        return self.git("--git-dir", str(self.origin), "rev-parse",
                        f"refs/heads/{config.MAIN_BRANCH}").strip()

    def child_settings(self, set_name=None, ps_none=False) -> Path:
        sha = self.origin_main()
        argv = ["--k", "1", "--sha", sha, "--template", TEMPLATE]
        if set_name is not None:
            argv += ["--set", set_name]
        config_paths = {name: str(getattr(config, name)) for name in ALL_CONFIG_ATTRS}
        config_paths.update(ROLES=str(config.ROLES), MODELS=str(config.MODELS))
        path = self.home / f"settings-{len(self.children)}-{self.token(4)}.json"
        path.write_text(json.dumps({"config": config_paths, "home": str(self.home),
                                    "argv": argv, "ready_fd": -1, "sha": sha,
                                    "ps_none": ps_none}), encoding="utf-8")
        return path

    def adopt(self, pid: int, line: str, log: Path, child=None) -> dict:
        if not line:
            self.fail(self.msg("дочерняя канарейка не дошла до ведения: "
                               + log.read_text(errors="replace")))
        state = json.loads(line)
        self.stray_pids.append(state["drive_pid"])
        records = self.records(pid)
        self.assertEqual(len(records), 1, self.msg(f"запись реестра ребёнка: {records}"))
        state.update(pid=pid, child=child, log=log, record=records[0],
                     stamp=STAMP_RE.search(records[0].name).group(0),
                     marks=self.marks(records[0]))
        return state

    def start_live(self, set_name=None, ps_none=False) -> dict:
        """Дочерняя канарейка; возврат после старта подменённого ведения."""
        settings_path = self.child_settings(set_name, ps_none)
        settings = json.loads(settings_path.read_text())
        read_fd, write_fd = os.pipe()
        settings["ready_fd"] = write_fd
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        log = self.home / f"child-{len(self.children)}.log"
        with open(log, "wb") as out:
            child = subprocess.Popen([sys.executable, "-c", _CHILD,
                                      str(settings_path)], cwd=REPO, stdout=out,
                                     stderr=subprocess.STDOUT, pass_fds=(write_fd,),
                                     start_new_session=True)
        os.close(write_fd)
        self.children.append(child)
        with os.fdopen(read_fd, encoding="utf-8") as ready:
            line = ready.readline()
        state = self.adopt(child.pid, line, log, child)
        state["sha"] = settings["sha"]
        return state

    @contextlib.contextmanager
    def live_run(self, set_name=None, ps_none=False):
        live = self.start_live(set_name, ps_none)
        try:
            yield live
        finally:
            self.stop_live(live)

    def stop_live(self, state: dict, signum=signal.SIGTERM) -> None:
        with contextlib.suppress(ProcessLookupError):
            os.kill(state["pid"], signum)
        # Канарейку, запущенную подставным `gh`, ждать нечем (не наш
        # ребёнок): её уборку здесь не проверяют, только останавливают.
        if state.get("child") is not None:
            state["child"].wait(timeout=60)

    def arm_gh_spawn(self) -> dict:
        """Канарейку запустит подставной `gh` при первом запросе проверок."""
        settings = self.child_settings()
        job = {"settings": str(settings), "child": str(self.child_file),
               "match": self.origin_main(),
               "cwd": str(REPO), "log": str(self.home / "gh-child.log"),
               "state": str(self.home / "gh-child.json")}
        (self.bindir / "spawn.json").write_text(json.dumps(job), encoding="utf-8")
        return job

    def gh_spawned(self, job: dict) -> dict:
        state_path = Path(job["state"])
        self.assertTrue(state_path.exists(),
                        self.msg("подставной gh не запустил канарейку"))
        state = json.loads(state_path.read_text())
        live = self.adopt(state["child"], state["ready"], Path(job["log"]))
        live["sha"] = json.loads(Path(job["settings"]).read_text())["sha"]
        self.stray_pids.append(state["child"])
        return live

    # ----------------------------------------------------------- команды

    def cli(self, *argv: str) -> tuple:
        out = io.StringIO()
        ok, tail = True, ""
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (0, None):
                    ok, tail = False, f"\n{exc.code}"
            except Exception as exc:  # noqa: BLE001 — исход сценария, не сбой теста
                ok, tail = False, f"\nисключение: {exc!r}"
        return ok, out.getvalue() + tail

    def origin_file(self, rel: str) -> str:
        tree = self.git("--git-dir", str(self.origin), "ls-tree", "-r", "--name-only",
                        config.MAIN_BRANCH)
        if rel not in tree.splitlines():
            return ""
        return self.git("--git-dir", str(self.origin), "show",
                        f"{config.MAIN_BRANCH}:{rel}")

    def note_text(self) -> tuple:
        self.calls += 1
        marker = f"zapis{self.calls}-{self.token(8)}"
        return marker, f"2 | 18.10 | {marker} | orchestrator/n.py"

    def doc_source(self) -> tuple:
        self.calls += 1
        marker = f"doc{self.calls}-{self.token(8)}"
        source = self.home / f"{marker}.md"
        source.write_text(f"# Документ\n\n{marker}\n", encoding="utf-8")
        return marker, f"docs/okno-{marker.lower()}.md", source

    def pending(self) -> list:
        from orchestrator import notes
        return notes.pending_notes()

    def journal_rows(self) -> list:
        return [dict(row) for row in store.all_steps(store.db())]

    def journal_with(self, text: str, rows=None) -> list:
        rows = self.journal_rows() if rows is None else rows
        return [r for r in rows if text in f"{r.get('action') or ''} {r.get('detail') or ''}"]

    def held_reason(self, out: str, prologue: str) -> str:
        self.assertIn(prologue, out, self.msg(out))
        return out.split(prologue, 1)[1].split("; отправка", 1)[0]

    def pool_key(self):
        return mock.patch.object(keychain, "token", return_value="k" * 32)

    def reason(self) -> str:
        return f"основание {self.token(8)}"

    # ------------------------------------------------------- задачи мержа

    def in_repo(self, repo: Path, *args: str) -> str:
        return self.git("-C", str(repo), *args)

    def task_id(self) -> str:
        return "01T" + self.token(23)

    def put_docs(self, task: str, files: dict) -> None:
        src = self.docs_src
        self.in_repo(src, "checkout", "-q", "--orphan", f"d-{task}")
        self.in_repo(src, "rm", "-rfq", "--ignore-unmatch", ".")
        for rel, text in files.items():
            path = src / TASKS_DIR / task / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.in_repo(src, "add", "-A")
        self.in_repo(src, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                     "commit", "-q", "-m", f"{task}: документы")
        sha = self.in_repo(src, "rev-parse", "HEAD").strip()
        for dest in (self.root, self.origin):
            self.in_repo(src, "push", "-q", str(dest), f"{sha}:refs/artifacts/{task}")

    def commit_to_main(self, files: dict) -> None:
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", config.MAIN_BRANCH)
        self.git("merge", "-q", "--ff-only", f"origin/{config.MAIN_BRANCH}")
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.git("add", rel)
        self.git("commit", "-q", "-m", "правка main до задачи")
        self.git("push", "-q", "origin", f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def make_task(self, state: str = "merge_gate", target=None) -> dict:
        """Задача артели на `merge_gate`: ветка опубликована, документы на ссылке, фиксация."""
        self.commit_to_main({
            MAP_REL: f"{MAP_PLACEHOLDER}\n{self.rng.randrange(10 ** 9)}\n"})
        task = self.task_id()
        branch = f"task/{task.lower()}-x"
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-b", branch, f"origin/{config.MAIN_BRANCH}")
        code = f"zadacha_{task.lower()}.py"
        (self.root / code).write_text(f"VALUE = {self.rng.randrange(10 ** 6)}\n",
                                      encoding="utf-8")
        self.git("add", code)
        self.git("commit", "-q", "-m", f"{task}: код")
        self.git("push", "-q", "-u", "origin", branch)
        head = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", config.MAIN_BRANCH)
        store.insert_task(self.conn, task, f"Задача {task}", state, branch,
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        if target is not None:
            store.update_task(self.conn, task, target=target)
        self.put_docs(task, {"SPEC.md": spec_text(task), "PLAN.md": plan_text(task),
                             "acceptance_tests/test_ac1_fixture.py": plank_text()})
        store.record_fixation(self.conn, task)
        # sha, который Оператор передаёт `approve <id> <sha>`, — зафиксированный.
        fixed = store.get_task(self.conn, task)["fixed_sha"] or head
        return {"id": task, "branch": branch, "head": fixed, "code": head}

    def state_of(self, task: dict) -> str:
        return store.get_task(store.db(), task["id"])["state"]

    def approve(self, task: dict, *extra: str) -> str:
        outputs = []
        for _ in range(3):
            ok, out = self.cli("approve", task["id"], *extra)
            outputs.append(out)
            if not ok or self.state_of(task) != "merge_gate":
                break
        return "\n".join(outputs)

    def assert_merge_refused(self, task: dict, live: dict, before: str, out: str,
                             ctx: str) -> None:
        msg = self.msg(f"{ctx}: {out}")
        self.assertIn(merge_refusal(live["stamp"], live["sha"]), out, msg)
        self.assertEqual(self.state_of(task), "merge_gate", msg)
        self.assertEqual(self.origin_main(), before, msg)
        self.assertEqual([dict(r) for r in store.merge_lock_rows(store.db())], [], msg)

    # ============================================================== AC-5

    def assert_note_held_by(self, live: dict, ctx: str) -> None:
        marker, text = self.note_text()
        ok, out = self.cli("note", "копилка", "--text", text)
        reason = self.held_reason(out, "заметка удержана: ")
        self.assertEqual(reason, f"идёт канарейка {live['stamp']} на {live['sha'][:7]}",
                         self.msg(f"{ctx}: {out}"))
        self.assertNotIn(marker, self.origin_file("docs/backlog.md"), self.msg(ctx))
        self.assertTrue(live["record"].exists(), self.msg(f"{ctx}: запись удалена"))
        self.cli("note", "--flush")

    def assert_note_sweeps(self, live: dict, ctx: str) -> None:
        before = len(self.journal_rows())
        marker, text = self.note_text()
        ok, out = self.cli("note", "копилка", "--text", text)
        msg = self.msg(f"{ctx}: {out}")
        self.assertNotIn("удержана", out, msg)
        self.assertIn(marker, self.origin_file("docs/backlog.md"), msg)
        self.assertFalse(live["record"].exists(), self.msg(f"{ctx}: запись не убрана"))
        for mark in live["marks"]:
            self.assertFalse(mark.exists(), self.msg(f"{ctx}: метка не убрана"))
        fresh = [r for r in self.journal_rows()[before:]
                 if not r.get("task_id")
                 and not (r.get("action") or "").startswith("заметка")]
        self.assertTrue(fresh, self.msg(f"{ctx}: строки журнала без задачи нет; "
                                        f"{self.journal_rows()[before:]}"))

    def ps_patch(self, pid: int, shift=None, fail=False):
        """Ответ `ps -o lstart=` для `pid`: сдвиг от настоящего старта либо отказ."""
        real = doctor.process_start_time(pid)
        self.assertIsNotNone(real, self.msg("время старта ребёнка не определилось"))
        current = subprocess.run

        def run(argv, *args, **kw):
            words = ([os.fsdecode(a) for a in argv]
                     if isinstance(argv, (list, tuple)) else [])
            if "lstart=" in words and str(pid) in words:
                if fail:
                    return subprocess.CompletedProcess(argv, 1, "", "")
                moment = (real + shift).astimezone().replace(tzinfo=None)
                return subprocess.CompletedProcess(
                    argv, 0, moment.strftime(LSTART_FORMAT) + "\n", "")
            return current(argv, *args, **kw)

        return mock.patch.object(subprocess, "run", run)

    def test_ac5_live_read_keeps_live_and_sweeps_stale_records(self):
        """Каждый случай сверки живости — своя дочерняя канарейка; решение видно по обычному `note`.

        Живая (запись остаётся, `note` удержан причиной этого прогона):
        время старта при сверке сдвинуто на 1 с (внутри допуска); `ps` при
        сверке не ответил (`None`); время старта при записи не определилось
        (`ps` ребёнка не ответил), pid жив. Не живая (`note` ушёл в origin,
        запись и её метка убраны, в журнале пульта — новая строка без задачи,
        помимо строки самой заметки): pid мёртв (SIGKILL); время старта при
        сверке сдвинуто на час; возраст больше потолка (потолок
        `CANARY_DRIVE_TIMEOUT_SEC` подменён отрицательным); запись без
        времени старта с мёртвым pid и старше потолка.

        Ловит мутацию: сверка времени старта — точным равенством (сдвиг 1 с
        читается как чужой процесс, `note` уходит в origin), либо `None` при
        сверке читается как «не совпало» (запись удалена, окно закрыто),
        либо мёртвая запись просто пропускается без уборки (файл остаётся).
        """
        cases = [
            ("сдвиг внутри допуска", dict(), dict(shift=INSIDE_SPAN), True),
            ("ps не ответил при сверке", dict(), dict(fail=True), True),
            ("старт не записан, pid жив", dict(ps_none=True), None, True),
            ("мёртвый pid", dict(), "kill", False),
            ("сдвиг вне допуска", dict(), dict(shift=OUTSIDE_SPAN), False),
            ("старше потолка", dict(), "old", False),
            ("старт не записан, мёртвый pid", dict(ps_none=True), "kill", False),
            ("старт не записан, старше потолка", dict(ps_none=True), "old", False),
        ]
        for name, start, check, alive in cases:
            with self.subTest(случай=name):
                with self.live_run(**start) as live, contextlib.ExitStack() as stack:
                    if check == "kill":
                        self.stop_live(live, signal.SIGKILL)
                    elif check == "old":
                        stack.enter_context(mock.patch.object(
                            canary, "CANARY_DRIVE_TIMEOUT_SEC", -2 * 3600))
                    elif check is not None:
                        stack.enter_context(self.ps_patch(live["pid"], **check))
                    if alive:
                        self.assert_note_held_by(live, name)
                    else:
                        self.assert_note_sweeps(live, name)

    # ============================================================== AC-7

    def test_ac7_note_and_doc_commit_held_by_live_run_and_flushed_after(self):
        """Прогон набора по умолчанию и прогон набора из `canary_sets:` — по очереди живые.

        Наблюдение: при живом прогоне `note копилка` и `doc-commit` удержаны,
        причина ровно «идёт канарейка <run_stamp> на <sha7>»; origin их не
        видит. После SIGTERM прогону `note --flush` и `doc-commit --flush`
        досылают обе записи в origin, удержанных нет. Без живого прогона те
        же команды уходят в origin сразу.

        Ловит мутацию: окно открывается только прогоном набора по умолчанию —
        при живом прогоне второго набора запись уходит в origin; либо
        причина называет pid вместо run_stamp/sha7.
        """
        for set_name in (None, self.set_name):
            with self.subTest(набор=set_name or config.CANARY_DEFAULT_SET):
                with self.live_run(set_name) as live:
                    reason = f"идёт канарейка {live['stamp']} на {live['sha'][:7]}"
                    marker, text = self.note_text()
                    ok, out = self.cli("note", "копилка", "--text", text)
                    self.assertEqual(self.held_reason(out, "заметка удержана: "),
                                     reason, self.msg(out))
                    doc_marker, rel, source = self.doc_source()
                    ok, out = self.cli("doc-commit", rel, "--from", str(source),
                                       "--message", "правка документа")
                    self.assertEqual(self.held_reason(out, "doc-commit удержан: "),
                                     reason, self.msg(out))
                    self.assertNotIn(marker, self.origin_file("docs/backlog.md"))
                    self.assertEqual(self.origin_file(rel), "", self.msg(out))
                ok, out = self.cli("note", "--flush")
                self.assertTrue(ok, self.msg(out))
                ok, out = self.cli("doc-commit", "--flush")
                self.assertTrue(ok, self.msg(out))
                self.assertIn(marker, self.origin_file("docs/backlog.md"), self.msg(out))
                self.assertIn(doc_marker, self.origin_file(rel), self.msg(out))
                self.assertEqual(self.pending(), [], self.msg(out))
        marker, text = self.note_text()
        ok, out = self.cli("note", "копилка", "--text", text)
        self.assertIn(marker, self.origin_file("docs/backlog.md"), self.msg(out))
        doc_marker, rel, source = self.doc_source()
        ok, out = self.cli("doc-commit", rel, "--from", str(source),
                           "--message", "правка документа")
        self.assertIn(doc_marker, self.origin_file(rel), self.msg(out))

    # ============================================================== AC-8

    def test_ac8_approve_refused_during_default_set_run(self):
        """Живой прогон набора по умолчанию; `approve <id>` и `approve <id> <sha>` задачи артели на `merge_gate`.

        Наблюдение: отказ текстом «идёт канарейка <run_stamp> на <sha7>: мерж
        сдвинет main …»; задача на `merge_gate`, main origin тот же, строк
        мьютекса мержа нет.

        Ловит мутацию: проверка канарейки стоит только на пути без sha (или
        только с sha) — второй вариант мержит и двигает main origin.
        """
        for with_sha in (False, True):
            with self.subTest(sha=with_sha):
                task = self.make_task()
                with self.live_run() as live:
                    before = self.origin_main()
                    extra = (task["head"],) if with_sha else ()
                    ok, out = self.cli("approve", task["id"], *extra)
                    self.assertFalse(ok, self.msg(out))
                    self.assert_merge_refused(task, live, before, out,
                                              f"sha={with_sha}")

    # ============================================================== AC-9

    def test_ac9_approve_waiting_in_queue_refused_before_push(self):
        """Мьютекс мержа держит живой держатель; `approve` встаёт в очередь, на первой паузе очереди стартует канарейка и мьютекс освобождается.

        Наблюдение: одобрение, дождавшееся окна, отказано тем же текстом;
        задача на `merge_gate`, main origin тот же, мьютекс снят.

        Ловит мутацию: проверка канарейки — при входе в `approve` до очереди
        мьютекса (канарейки тогда ещё нет) — дождавшееся одобрение мержит.
        """
        task = self.make_task()
        holder = "01Q" + self.token(23)
        session = "s-" + self.token(8).lower()
        store.set_merge_lock(store.db(), holder, session, os.getpid(),
                             socket.gethostname(), store.now())
        started = {}

        def start_and_release():
            started["live"] = self.start_live()
            self.addCleanup(self.stop_live, started["live"])
            store.release_merge_lock(store.db(), session, os.getpid())

        self.on_sleep = start_and_release
        before = self.origin_main()
        ok, out = self.cli("approve", task["id"])
        self.assertIn("live", started, self.msg(f"очереди не было: {out}"))
        self.assertFalse(ok, self.msg(out))
        self.assert_merge_refused(task, started["live"], before, out, "очередь")

    def test_ac9_canary_started_inside_merge_body_refused_before_push(self):
        """Канарейку запускает подставной `gh` при первом запросе проверок CI — уже в теле окна мержа.

        Наблюдение: `approve` отказан тем же текстом с run_stamp этой
        канарейки; задача на `merge_gate`, main origin тот же, мьютекс снят.

        Ловит мутацию: проверка канарейки стоит при входе в тело окна мержа
        (до проверки CI), а не непосредственно перед push — канарейка,
        стартовавшая после входа, не замечена, main origin сдвинут.
        """
        task = self.make_task()
        job = self.arm_gh_spawn()
        before = self.origin_main()
        ok, out = self.cli("approve", task["id"])
        live = self.gh_spawned(job)
        self.addCleanup(self.stop_live, live)
        self.assertFalse(ok, self.msg(out))
        self.assert_merge_refused(task, live, before, out, "старт в теле")

    # ============================================================= AC-10

    def test_ac10_during_canary_flag_merges_and_journals_reason(self):
        """Живой прогон набора по умолчанию; `approve <id> [sha] --during-canary "<основание>"`.

        Наблюдение: задача доходит до `done`, main origin сдвинут; в журнале
        задачи — строка с основанием; в варианте с sha основание не принято
        за sha (мерж идёт).

        Ловит мутацию: флаг не внесён в `_approve_reason_indices` —
        основание в варианте без sha читается как sha, approve отказывает
        сверкой фиксации; либо основание не пишется в журнал задачи.
        """
        for with_sha in (False, True):
            with self.subTest(sha=with_sha):
                task = self.make_task()
                with self.live_run():
                    before = self.origin_main()
                    reason = self.reason()
                    extra = (task["head"],) if with_sha else ()
                    out = self.approve(task, *extra, FLAG, reason)
                self.assertEqual(self.state_of(task), "done", self.msg(out))
                self.assertNotEqual(self.origin_main(), before, self.msg(out))
                rows = [f"{r['action']} {r['detail'] or ''}"
                        for r in store.task_steps(store.db(), task["id"])]
                self.assertTrue([r for r in rows if reason in r], self.msg(rows))

    # ============================================================= AC-11

    def flag_commands(self, task: dict) -> list:
        marker, text = self.note_text()
        doc_marker, rel, source = self.doc_source()
        return [
            ("approve", ["approve", task["id"]]),
            ("note", ["note", "копилка", "--text", text]),
            ("doc-commit", ["doc-commit", rel, "--from", str(source),
                            "--message", "правка документа"]),
            ("canary pool-seal", ["canary", "pool-seal"]),
        ]

    def test_ac11_empty_reason_refused_by_every_command(self):
        """`--during-canary` в конце строки и с пустым основанием у `approve`, `note`, `doc-commit`, `canary pool-seal` — без живого прогона и при живом.

        Наблюдение: отказ «--during-canary требует основание …», команда не
        исполнена: main origin тот же, удержанных записей нет, задача на
        `merge_gate`.

        Ловит мутацию: пустое основание проверяется только у `approve` (или
        только при живом прогоне) — `note`/`doc-commit`/`pool-seal` с пустым
        флагом идут прежним путём и двигают main.
        """
        task = self.make_task()
        for live_run in (False, True):
            with self.live_run() if live_run else contextlib.nullcontext():
                self.check_empty_reason(task, live_run)

    def check_empty_reason(self, task: dict, live_run: bool) -> None:
        if True:
            for name, argv in self.flag_commands(task):
                for tail in ([FLAG], [FLAG, ""]):
                    with self.subTest(живой=live_run, команда=name, хвост=tail):
                        before = self.origin_main()
                        with self.pool_key():
                            ok, out = self.cli(*argv, *tail)
                        msg = self.msg(out)
                        self.assertFalse(ok, msg)
                        self.assertIn(f"{FLAG} требует основание", out, msg)
                        self.assertEqual(self.origin_main(), before, msg)
                        self.assertEqual(self.pending(), [], msg)
                        self.assertEqual(self.state_of(task), "merge_gate", msg)

    def test_ac11_flag_outside_merge_gate_refused(self):
        """`approve <id> --during-canary "<основание>"` у задачи в состоянии не `merge_gate`.

        Наблюдение: отказ «[<id>] approve отклонён: флаг --during-canary
        допустим только в состоянии merge_gate, задача в <состояние>»;
        состояние задачи не изменилось.

        Ловит мутацию: флаг молча игнорируется вне `merge_gate` — approve
        другого гейта исполняется (задача двигается) без отказа.
        """
        for state in ("review", "acceptance", "spec_gate"):
            with self.subTest(состояние=state):
                task = self.make_task(state=state)
                ok, out = self.cli("approve", task["id"], FLAG, self.reason())
                msg = self.msg(out)
                self.assertFalse(ok, msg)
                for part in (f"[{task['id']}] approve отклонён", FLAG, "merge_gate",
                             f"задача в {state}"):
                    self.assertIn(part, out, msg)
                self.assertEqual(self.state_of(task), state, msg)

    # ============================================================= AC-12

    def test_ac12_external_task_and_other_set_do_not_hold_merge(self):
        """(1) Живой прогон набора не по умолчанию: `approve` задачи артели на `merge_gate` доводит её до `done`.

        (2) Живой прогон набора по умолчанию: `approve` задачи внешнего
        проекта (объявлен в `targets.yaml` песочницы) идёт прежним путём —
        вывод без отказа канарейки и с точностью до id задачи совпадает с
        выводом такого же `approve` без живого прогона.

        Ловит мутацию: мерж держит прогон любого набора (задача артели
        отказана при живом прогоне второго набора) либо проверка не смотрит
        на проект задачи (внешняя задача отказана текстом канарейки).
        """
        task = self.make_task()
        with self.live_run(self.set_name):
            out = self.approve(task)
        self.assertEqual(self.state_of(task), "done", self.msg(out))
        self.assertNotIn("идёт канарейка", out, self.msg(out))

        external = "ext" + self.token(6).lower()
        declare_target(external)

        def external_out(during_live: bool) -> str:
            ext = self.make_task(target=external)
            with self.live_run() if during_live else contextlib.nullcontext():
                ok, out = self.cli("approve", ext["id"])
            for value in (ext["id"], ext["id"].lower(), ext["head"], ext["code"],
                          ext["branch"]):
                out = out.replace(value, "<задача>")
            return re.sub(r"\b[0-9a-f]{7,40}\b", "<sha>", out)

        with_live = external_out(True)
        self.assertNotIn("идёт канарейка", with_live, self.msg(with_live))
        self.assertEqual(with_live, external_out(False), self.msg(with_live))

    # ============================================================= AC-13

    def bypass_commands(self) -> list:
        marker, text = self.note_text()
        return [
            ("note --now", ["note", "--now", "копилка", "--text", text], marker),
            ("note --flush", ["note", "--flush"], None),
            ("doc-commit --flush", ["doc-commit", "--flush"], None),
            ("canary pool-seal", ["canary", "pool-seal"], None),
        ]

    def test_ac13_window_bypasses_refused_and_flag_passes(self):
        """При живом прогоне каждого из двух наборов — `note --now`, `note --flush`, `doc-commit --flush`, `canary pool-seal`.

        Наблюдение без флага: отказ текстом «идёт канарейка <run_stamp> на
        <sha7>: команда сдвинет main — …», main origin тот же. С
        `--during-canary "<основание>"`: команда идёт прежним путём (запись
        `note --now` в origin, `pool-seal` двигает main origin, флаши
        проходят), в журнале пульта — строка с основанием.

        Ловит мутацию: обход `--now`/`--flush` по-прежнему минует окно —
        при живом прогоне запись уходит в origin; либо отказ стоит только у
        набора по умолчанию; либо основание флага не пишется в журнал.
        """
        for set_name in (None, self.set_name):
            with self.live_run(set_name) as live:
                self.check_bypasses(live, set_name)

    def check_bypasses(self, live: dict, set_name) -> None:
        for name, argv, marker in self.bypass_commands():
            with self.subTest(набор=set_name, команда=name):
                before = self.origin_main()
                with self.pool_key():
                    ok, out = self.cli(*argv)
                msg = self.msg(out)
                self.assertFalse(ok, msg)
                self.assertIn(window_refusal(live["stamp"], live["sha"]), out, msg)
                self.assertEqual(self.origin_main(), before, msg)
                reason = self.reason()
                with self.pool_key():
                    ok, out = self.cli(*argv, FLAG, reason)
                msg = self.msg(out)
                self.assertTrue(ok, msg)
                self.assertNotIn("идёт канарейка", out, msg)
                if marker is not None:
                    self.assertIn(marker, self.origin_file("docs/backlog.md"), msg)
                if name == "canary pool-seal":
                    self.assertNotEqual(self.origin_main(), before, msg)
                self.assertTrue(self.journal_with(reason), msg)

    # ============================================================= AC-15

    def test_ac15_without_live_run_commands_unchanged(self):
        """Без живого прогона: `note` (обычная, `--now`, `--flush`), `doc-commit` (обычный, `--flush`), `canary pool-seal`, `approve` и вывод `canary`.

        Наблюдение: записи уходят в origin сразу, `pool-seal` двигает main,
        `approve` доводит задачу до `done`; ни один вывод не называет
        канарейку отказом окна; первая строка вывода прогона канарейки —
        прежняя «[canary] прогон <run_stamp>: 1 задач из пула …».

        Ловит мутацию: окно канарейки открывается без живой записи (например,
        по любой записи реестра, включая убранную), — обычная заметка
        удержана, `approve` отказан.
        """
        live = self.start_live()
        self.stop_live(live)
        first = live["log"].read_text(errors="replace").splitlines()[0]
        self.assertTrue(first.startswith(f"[canary] прогон {live['stamp']}: 1 задач из пула "),
                        self.msg(first))
        for name, argv, marker in [*self.bypass_commands(),
                                   ("note", ["note", "копилка", "--text",
                                             self.note_text()[1]], None)]:
            with self.subTest(команда=name):
                before = self.origin_main()
                with self.pool_key():
                    ok, out = self.cli(*argv)
                self.assertTrue(ok, self.msg(out))
                self.assertNotIn("канарейк", out.replace("[canary]", ""), self.msg(out))
                if marker is not None:
                    self.assertIn(marker, self.origin_file("docs/backlog.md"), self.msg(out))
                if name == "canary pool-seal":
                    self.assertNotEqual(self.origin_main(), before, self.msg(out))
        doc_marker, rel, source = self.doc_source()
        ok, out = self.cli("doc-commit", rel, "--from", str(source), "--message", "правка")
        self.assertIn(doc_marker, self.origin_file(rel), self.msg(out))
        task = self.make_task()
        out = self.approve(task)
        self.assertEqual(self.state_of(task), "done", self.msg(out))
        self.assertNotIn("канарейк", out, self.msg(out))

    def test_ac15_flag_without_live_run_accepted_silently(self):
        """Без живого прогона: `approve <id> --during-canary "<основание>"` на `merge_gate` и `note --now … --during-canary "<основание>"`.

        Наблюдение: задача доходит до `done`, запись — в origin; строки
        журнала с основанием нет; вывод `note --now` с флагом совпадает с
        выводом без флага с точностью до текста записи и sha.

        Ловит мутацию: основание флага пишется в журнал всегда, а не только
        при живом прогоне, — в журнале появляется строка с основанием.
        """
        reason = self.reason()
        task = self.make_task()
        out = self.approve(task, FLAG, reason)
        self.assertEqual(self.state_of(task), "done", self.msg(out))
        marker, text = self.note_text()
        ok, with_flag = self.cli("note", "--now", "копилка", "--text", text, FLAG, reason)
        self.assertTrue(ok, self.msg(with_flag))
        self.assertIn(marker, self.origin_file("docs/backlog.md"), self.msg(with_flag))
        self.assertEqual(self.journal_with(reason), [], self.msg(self.journal_with(reason)))
        plain_marker, plain_text = self.note_text()
        ok, plain = self.cli("note", "--now", "копилка", "--text", plain_text)

        def norm(out, mark):
            return re.sub(r"\b[0-9a-f]{7,40}\b", "<sha>", out.replace(mark, "<запись>"))

        self.assertEqual(norm(with_flag, marker), norm(plain, plain_marker),
                         self.msg(f"{with_flag!r} != {plain!r}"))


if __name__ == "__main__":
    unittest.main()
