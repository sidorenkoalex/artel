"""Общая песочница планки 01M3PKSWPETC49WFTFZ69GH3F2: настоящий прогон
`canary.cmd_canary` на git-песочнице — копии кода пульта, в которой
проверяемый коммит несёт ДРУГОЙ код, чем код процесса пульта.

Устройство сценария (SPEC, требования 1-7):

- `self.root` — git-репозиторий «пульта» песочницы (`RealGitSandbox`), в
  него скопированы все отслеживаемые/неигнорируемые файлы кода, который
  сейчас проверяется (`CODE_ROOT` — корень пакета `orchestrator`, откуда
  импортирован пульт теста), кроме `tasks/`. Каждый коммит сценария
  (`commit_code`) дописывает в конец `orchestrator/auto.py` и
  `orchestrator/runner.py` КОММИТА подмену: `auto.cmd_auto` — один шаг
  сценария (переход состояния учебной задачи в духе шага роли), а
  `runner.cmd_run` — запись в журнал. Метка коммита входит в `detail`
  каждого перехода, который делает подмена. Ни один настоящий агент не
  запускается ни в каком процессе.
- В процессе ПУЛЬТА (этот процесс pytest) `catalog.cmd_new`,
  `workspace.ensure`, `auto.cmd_auto`, `runner.cmd_run` и помощники гейтов
  учебной задачи из `orchestrator.canary` подменены «растяжками»: вызов
  записывается в `self.tripwires` и отказывает исключением. Пока ведение
  идёт в процессе пульта (код до задачи), прогон упирается в них — и
  ни один настоящий агент не запускается и там.
- `subprocess.Popen` процесса пульта обёрнут: запуск процесса клона
  (любая не-git команда, упоминающая `canary_drive`/`canary-drive`, либо
  интерпретатор с `artel.py` и `canary`) записывается в `self.launches`
  (аргументы, рабочий каталог, HEAD и наличие входа в нём — снятые в
  момент запуска, пока клон жив) и подменяется запуском посредника
  `TAMPER_SOURCE`, который по режиму сценария исполняет исходную команду
  и наблюдает/портит её файл результата, либо изображает зависание.
  Файл результата посредник находит без знания протокола: это путь из
  аргументов (или хвост `--x=<путь>`) либо из значений окружения
  процесса, по которому после исполнения лежит JSON-объект.
- `tempfile.mkdtemp` обёрнут: каталоги с префиксом `artel-canary`
  (эфемерный клон и origin-заглушка) записываются, чтобы проверить их
  уборку.
- Таймаут (режим `hang`): у экземпляра процесса клона `communicate`/
  `wait` с заданным таймаутом получают его не больше `SHRUNK_TIMEOUT_SEC`
  — предельное время пульта (именованная константа, имя которой SPEC не
  фиксирует) сжимается без знания её имени. Ожидание вовсе без таймаута
  не сжимается: такой пульт висит, и тест краснеет по таймауту pytest.
"""
import io
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import auto, canary, catalog, config, runner, workspace  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

#: Корень кода, который сейчас проверяется (откуда импортирован пульт).
CODE_ROOT = Path(config.__file__).resolve().parent.parent

DRIVE_ENTRY = "orchestrator/canary_drive.py"

#: Помощники гейтов учебной задачи и её ведение (AC-1): в процессе пульта
#: ни один из них не вызывается. Имена, которых в модуле уже нет, не
#: подменяются (разработчик вправе перенести их в `canary_drive.py`).
CANARY_DRIVE_HELPERS = (
    "_drive_task", "_pass_spec_gate", "_pass_acceptance_gate",
    "_pass_verifying", "_pass_escalated_with_synthetic_answer",
    "_kill_at_merge_gate", "_kill_at_verifying", "_raise_task_ceiling",
    "_kill_ceiling_exhausted", "_kill_inconclusive",
)

#: Предельное время процесса клона, до которого сжимается любой таймаут
#: пульта на ожидании этого процесса.
SHRUNK_TIMEOUT_SEC = 6

TEMPLATE_TITLE = "uchebnaya-zadacha"

TEMPLATE_TEXT = """# Учебная задача песочницы

Добавить в описание проекта одну строку о назначении канарейки.

Требуется:
1. Строка есть.
"""

#: Агентские состояния, в которых подмена `auto.cmd_auto` делает шаг
#: сценария; в остальных она, как и настоящий `auto`, ничего не делает.
AGENT_STATES = ("spec_writing", "tests_writing", "in_dev", "review")

AUTO_FAKE_ACTOR = "planka-auto"

#: Сценарии ведения. Шаг — ("to", состояние, detail) либо
#: ("refuse_acceptance",); последний шаг повторяется, когда сценарий
#: исчерпан.
SCENARIO_GREEN = [("to", "merge_gate", "шаг роли песочницы")]
SCENARIO_GATES = [
    ("to", "spec_gate", "SPEC готов"),
    ("to", "verifying", "планка готова"),
    ("to", "escalated", "вопрос роли песочницы"),
    ("to", "acceptance", "ревью пройдено"),
]
SCENARIO_ESCALATED_GREEN = [
    ("to", "escalated", "вопрос роли песочницы"),
    ("to", "merge_gate", "шаг роли песочницы"),
]
SCENARIO_BUDGET =[("to", "escalated", "бюджет исчерпан: $50.00 из $50.00")]
SCENARIO_ESCALATION_CAP = [("to", "escalated", "вопрос роли песочницы")]
SCENARIO_DEV_RETRY = [("to", "in_dev", "SPEC готов"), ("refuse_acceptance",)]

_AUTO_FAKE = '''

# --- подмена цикла auto приёмочной песочницей планки 01M3PKSWPETC49WFTFZ69GH3F2 ---
_PLANK_SCRIPT = {script!r}
_PLANK_MARK = {mark!r}


def cmd_auto(task_id, session_id=None, wait_zone=False):
    conn = store.db()
    t = store.get_task(conn, task_id)
    state = t["state"]
    if state not in {agent_states!r}:
        return
    done = sum(1 for r in store.task_steps(conn, task_id)
               if r["actor"] == {actor!r} and r["action"] == "planka auto step")
    step = _PLANK_SCRIPT[min(done, len(_PLANK_SCRIPT) - 1)]
    store.journal(conn, task_id, {actor!r}, "planka auto step",
                  f"{{done + 1}}: {{step[0]}}")
    if step[0] == "to":
        if step[1] == "escalated":
            store.update_task(conn, task_id, escalated_from=state)
        store.set_state(conn, task_id, step[1], {actor!r},
                        expected_state=state,
                        detail=f"{{step[2]}} [{{_PLANK_MARK}}]")
    elif step[0] == "refuse_acceptance":
        store.journal(conn, task_id, "fsm", "переход отклонён: приёмочные тесты",
                      f"планка красна (подмена песочницы) [{{_PLANK_MARK}}]")
'''

_RUNNER_FAKE = '''

# --- подмена шага роли приёмочной песочницей планки 01M3PKSWPETC49WFTFZ69GH3F2 ---
def cmd_run(task_id, session_id=None):
    from . import store as _plank_store
    _plank_store.journal(_plank_store.db(), task_id, "planka-run",
                         "planka run", {mark!r})
'''

#: Посредник запуска процесса клона. Аргумент — путь к JSON-заданию:
#: `mode`, `args` (исходная команда), `marker`, `target`, `fake`,
#: `capture` (каталог записи наблюдений).
TAMPER_SOURCE = r'''
import json, os, subprocess, sys, time
from pathlib import Path

spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
mode, orig = spec["mode"], spec["args"]
if mode != "observe":
    print(spec["marker"], flush=True)
    print(spec["marker"], file=sys.stderr, flush=True)
if mode == "hang":
    time.sleep(600)
    sys.exit(0)
rc = subprocess.run(orig, shell=isinstance(orig, str)).returncode

cands = []
for arg in ([orig] if isinstance(orig, str) else orig):
    arg = str(arg)
    cands.append(arg)
    if "=" in arg:
        cands.append(arg.split("=", 1)[1])
cands.extend(os.environ.values())
results = []
for cand in cands:
    try:
        p = Path(cand)
        if not p.is_file() or p.stat().st_size > 5_000_000:
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        continue
    if isinstance(data, dict) and str(p) not in [r["path"] for r in results]:
        results.append({"path": str(p), "text": p.read_text(encoding="utf-8")})

for r in results:
    p = Path(r["path"])
    if mode == "rehead":
        p.write_text(r["text"].replace(spec["target"], spec["fake"]),
                     encoding="utf-8")
    elif mode == "drop":
        p.unlink()
    elif mode == "garbage":
        p.write_text("{оборванный результат", encoding="utf-8")
if mode == "fail":
    rc = 3

capture = Path(spec["capture"])
capture.mkdir(parents=True, exist_ok=True)
n = len(list(capture.glob("launch-*.json")))
(capture / f"launch-{n}.json").write_text(
    json.dumps({"rc": rc, "results": results}, ensure_ascii=False),
    encoding="utf-8")
sys.exit(rc)
'''


def _flat(args) -> str:
    if isinstance(args, (str, bytes, os.PathLike)):
        return os.fsdecode(args)
    return " ".join(os.fsdecode(a) for a in args)


def is_drive_launch(args) -> bool:
    """Запуск процесса клона, а не служебная команда пульта (git и т.п.)."""
    text = _flat(args)
    first = Path(text.split()[0]).name if text.split() else ""
    if first == "git":
        return False
    if "canary_drive" in text or "canary-drive" in text:
        return True
    return first.startswith("python") and "artel.py" in text and "canary" in text


class CloneDriveSandbox(RealGitSandbox):
    """Прогон `canary.cmd_canary` целиком против git-песочницы пульта."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self._copy_code()
        self.init_sha = self.git("rev-parse", "HEAD").strip()

        self.home = Path(tempfile.mkdtemp(prefix="planka-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir()
        (pool / f"{TEMPLATE_TITLE}.md").write_text(TEMPLATE_TEXT, encoding="utf-8")
        self._patch(Path, "home", lambda *a, **k: self.home)

        self.work = Path(tempfile.mkdtemp(prefix="planka-work-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        self.tamper = self.work / "tamper.py"
        self.tamper.write_text(TAMPER_SOURCE, encoding="utf-8")
        self.capture = self.work / "capture"

        self.tripwires = []
        for module, name in ((catalog, "cmd_new"), (workspace, "ensure"),
                             (auto, "cmd_auto"), (runner, "cmd_run")):
            self._patch(module, name, self._tripwire(f"{module.__name__}.{name}"))
        for name in CANARY_DRIVE_HELPERS:
            if hasattr(canary, name):
                self._patch(canary, name, self._tripwire(f"canary.{name}"))

        self.launches = []
        self.drive_procs = []
        self.mode = "observe"
        self.target = ""
        self.fake_head = ""
        self.marker = ""
        self._install_popen()

        self.canary_dirs = []
        real_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(*args, **kwargs):
            path = real_mkdtemp(*args, **kwargs)
            prefix = kwargs.get("prefix") or (args[1] if len(args) > 1 else "")
            if str(prefix or "").startswith("artel-canary"):
                self.canary_dirs.append(Path(path))
            return path
        self._patch(tempfile, "mkdtemp", tracking_mkdtemp)

    # --- подготовка ---------------------------------------------------

    def _patch(self, target, name, value):
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _tripwire(self, name):
        def tripwire(*args, **kwargs):
            self.tripwires.append(name)
            raise RuntimeError(f"планка: процесс пульта исполнил {name}")
        return tripwire

    def _copy_code(self):
        listed = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=CODE_ROOT, capture_output=True, text=True, check=True).stdout
        for rel in filter(None, listed.split("\0")):
            if rel.startswith(("tasks/", ".artel/")) or rel == ".gitignore":
                continue
            src = CODE_ROOT / rel
            if not src.is_file():
                continue
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "код пульта песочницы")

    def commit_code(self, scenario, marker: str, *, drop_drive: bool = False) -> str:
        """Коммит песочницы, чей код ведёт учебную задачу по `scenario` и
        метит свои переходы `marker`; `drop_drive` — коммит без входа
        `orchestrator/canary_drive.py`. Возвращает полный sha."""
        for rel, fake in (("orchestrator/auto.py", _AUTO_FAKE.format(
                              script=[list(s) for s in scenario], mark=marker,
                              agent_states=AGENT_STATES, actor=AUTO_FAKE_ACTOR)),
                          ("orchestrator/runner.py", _RUNNER_FAKE.format(mark=marker))):
            original = (CODE_ROOT / rel).read_text(encoding="utf-8")
            (self.root / rel).write_text(original + fake, encoding="utf-8")
        entry = self.root / DRIVE_ENTRY
        if drop_drive:
            entry.unlink(missing_ok=True)
        elif (CODE_ROOT / DRIVE_ENTRY).is_file():
            shutil.copy2(CODE_ROOT / DRIVE_ENTRY, entry)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", f"сценарий {marker}")
        return self.git("rev-parse", "HEAD").strip()

    def new_marker(self, label: str) -> str:
        return f"{label}-{self.rng.randrange(10**9):09d}"

    # --- обёртка запуска процесса клона -------------------------------

    def _install_popen(self):
        real_popen = subprocess.Popen
        sandbox = self

        class DrivePopen(real_popen):
            def communicate(self, input=None, timeout=None):
                return super().communicate(input, timeout=sandbox._shrunk(timeout))

            def wait(self, timeout=None):
                if self.returncode is not None:
                    return self.returncode
                return super().wait(timeout=sandbox._shrunk(timeout))

        def popen(args, *a, **kwargs):
            if not is_drive_launch(args):
                return real_popen(args, *a, **kwargs)
            cwd = Path(kwargs.get("cwd") or os.getcwd()).resolve()
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd,
                                  capture_output=True, text=True).stdout.strip()
            self.launches.append({
                "args": [os.fsdecode(x) for x in args]
                        if not isinstance(args, (str, bytes)) else [os.fsdecode(args)],
                "cwd": cwd, "head": head,
                "drive_in_cwd": (cwd / DRIVE_ENTRY).is_file(),
            })
            job = self.work / f"job-{len(self.launches)}.json"
            job.write_text(json.dumps({
                "mode": self.mode,
                "args": ([os.fsdecode(x) for x in args]
                         if not isinstance(args, (str, bytes)) else os.fsdecode(args)),
                "marker": self.marker, "target": self.target,
                "fake": self.fake_head, "capture": str(self.capture),
            }, ensure_ascii=False), encoding="utf-8")
            kwargs.pop("shell", None)
            proc = DrivePopen([sys.executable, str(self.tamper), str(job)],
                              *a, **kwargs)
            self.drive_procs.append(proc)
            return proc

        self._patch(subprocess, "Popen", popen)

    def _shrunk(self, timeout):
        """Сжатие таймаута — только в режиме зависания: в остальных режимах
        процесс клона ведёт задачу по-настоящему и сжатый предел оборвал
        бы его."""
        if timeout is None or self.mode != "hang":
            return timeout
        return min(timeout, SHRUNK_TIMEOUT_SEC)

    # --- прогон и наблюдения ------------------------------------------

    def run_canary(self, target_sha: str, *, mode: str = "observe",
                   fake_head: str = "", marker: str = "") -> str:
        """`canary.cmd_canary` на одном шаблоне пула, `--sha target_sha`.
        Возвращает весь вывод пульта (stdout+stderr и текст `SystemExit`);
        `self.exit` — `SystemExit`, если был, `self.crash` — любое иное
        исключение пульта."""
        self.mode, self.target, self.fake_head = mode, target_sha, fake_head
        self.marker = marker or self.new_marker("diag")
        out, err = io.StringIO(), io.StringIO()
        self.exit = None
        self.crash = None
        with redirect_stdout(out), redirect_stderr(err):
            try:
                canary.cmd_canary(k=1, sha=target_sha, templates=[TEMPLATE_TITLE])
            except SystemExit as exc:
                self.exit = exc
            except Exception as exc:  # noqa: BLE001 — сам факт падения и есть наблюдение
                self.crash = exc
        text = out.getvalue() + err.getvalue()
        if self.exit is not None and self.exit.code not in (None, 0):
            text += f"\n{self.exit.code}"
        self.output = text
        return text

    def canary_rows(self) -> list:
        db = config.DB
        if not Path(db).is_file():
            return []
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute("SELECT * FROM canary_runs ORDER BY id").fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def results(self) -> list:
        """Файлы результата, которые процесс клона записал (по запускам)."""
        found = []
        for path in sorted(self.capture.glob("launch-*.json")):
            found.extend(json.loads(path.read_text(encoding="utf-8"))["results"])
        return found

    def diagnostics_text(self) -> str:
        root = config.ROOT / ".artel" / "canary"
        chunks = []
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        return "\n".join(chunks)

    def summary_line(self, task_id: str) -> str:
        for line in self.output.splitlines():
            if line.startswith(f"  {task_id}:"):
                return line
        self.fail(f"строки сводки задачи {task_id} нет в выводе "
                  f"(зерно {self.seed}):\n{self.output}")

    def assert_no_pult_drive(self):
        self.assertEqual(
            self.tripwires, [],
            f"процесс пульта сам исполнил ведение учебной задачи: "
            f"{self.tripwires} (зерно {self.seed})\n{self.output}")

    def assert_clone_dirs_removed(self):
        self.assertGreaterEqual(
            len(self.canary_dirs), 2,
            f"эфемерный клон и origin-заглушка не заводились: {self.canary_dirs}")
        left = [str(p) for p in self.canary_dirs if p.exists()]
        self.assertEqual(left, [], f"не убраны: {left} (зерно {self.seed})")

    def assert_no_crash(self):
        self.assertIsNone(
            self.crash, f"пульт упал исключением {self.crash!r} (зерно "
            f"{self.seed})\n{self.output}")


def json_values(obj) -> list:
    """Все скалярные значения JSON-объекта, на любой глубине."""
    if isinstance(obj, dict):
        return [v for x in obj.values() for v in json_values(x)]
    if isinstance(obj, list):
        return [v for x in obj for v in json_values(x)]
    return [obj]
