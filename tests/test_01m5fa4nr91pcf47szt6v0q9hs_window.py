"""Метка живой канарейки без записи реестра у потребителей окна: `note`, `note --now`, `approve` на `merge_gate`; прежнее поведение без такой метки.

Группа: долгоживущий
Красен до реализации: окно тишины, отказ мержа и обходы окна читают только записи реестра — метка без записи с живым pid их не держит (заметка уходит в origin, мерж двигает main), а метка мёртвой записи остаётся на диске после уборки записи.

Связка, которую держит файл: «каталог реестра под корнем песочницы —
команды Оператора `note`/`note --now`/`doc-commit`/`approve`/`canary`
диспетчером `artel.main()` тем же argv, что набирает Оператор — main
настоящего bare `origin` и журнал пульта». Песочница —
`tests.sandbox.RealGitSandbox` по образцу файла потребителей реестра части
А: главная копия пульта с копией `orchestrator/`/`scripts/`, бэклогом и
заглушкой карты, bare `origin`, подставной `gh` (зелёные проверки, пустые
списки), подставные часы и пауза пульта, пул канарейки из одного учебного
шаблона в подменённом домашнем каталоге.

Реестр раскладывается руками: каталог
`config.ROOT/.artel/config.CANARY_LIVE_DIRNAME`, запись
`<run_stamp>-<pid>.json` (поля записи прогона), метка `<run_stamp>.lock` с
pid текстом. Живой pid — дочерний процесс-сон (снимается в уборке теста),
мёртвый — pid завершённого и дождавшегося процесса. Прогон `canary` в
AC-21 — в процессе теста, ведение задачи в клоне подменено на уровне
`subprocess.Popen` (ролей и сети нет).

Идентификаторы, тексты записей и `run_stamp` порождаются от зерна; зерно
печатается и входит в текст каждого провала.
"""
import contextlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, catalog, config, doctor, runner, store
from tests.sandbox import RealGitSandbox, capture, patch_pult_sleep

REPO = Path(__file__).resolve().parent.parent
TASKS_DIR = config.TASKS.name
STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
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
ABSENT = "(запись реестра отсутствует)"

# Подставной `gh`: зелёные проверки на любой коммит, пустые списки прогонов
# и запросов на слияние.
FAKE_GH = r'''
import json, re, sys
args = sys.argv[1:]
joined = " ".join(args)
if args[:1] == ["api"] and "/check-runs" in joined:
    page = re.search(r"[?&]page=(\d+)", joined)
    runs = [{"name": "тесты кода", "status": "completed", "conclusion": "success"}]
    shown = runs if page is None or page.group(1) == "1" else []
    print(json.dumps({"total_count": len(runs), "check_runs": shown}, ensure_ascii=False))
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


def merge_refusal(note: str) -> str:
    return (f"{note}: мерж сдвинет main под проверяемым коммитом — дождись итога "
            f'или повтори с {FLAG} "<основание>"')


class MarkWindowTest(RealGitSandbox):
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
        self.home = Path(tempfile.mkdtemp(prefix="mark-window-home-"))
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

        bindir = self.root / ".artel" / "fake-bin"
        bindir.mkdir(parents=True, exist_ok=True)
        gh = bindir / "gh"
        gh.write_text(f"#!{sys.executable}\n{FAKE_GH}", encoding="utf-8")
        gh.chmod(0o755)
        env = mock.patch.dict(os.environ, {
            "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"})
        env.start()
        self.addCleanup(env.stop)

        self.clock = 0.0
        base_mono, base_wall = time.monotonic(), time.time()
        for target, fake in (("time.monotonic", lambda: base_mono + self.clock),
                             ("time.time", lambda: base_wall + self.clock)):
            patcher = mock.patch(target, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(patch_pult_sleep(self.fake_sleep).close)
        self.calls = 0
        self.used = set()

    # ------------------------------------------------------------ фикстуры

    def token(self, n: int = 10) -> str:
        return "".join(self.rng.choice(ULID_ALPHABET) for _ in range(n))

    def msg(self, text) -> str:
        return f"зерно: {self.seed}; {text}"

    def fake_sleep(self, seconds) -> None:
        self.clock += float(seconds)
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

    # ------------------------------------------------------ реестр на диске

    def registry(self) -> Path:
        path = Path(config.ROOT) / ".artel" / config.CANARY_LIVE_DIRNAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    def stamp(self) -> str:
        while True:
            moment = datetime(2031, 1, 1, tzinfo=timezone.utc) + timedelta(
                seconds=self.rng.randrange(300 * 24 * 3600))
            text = moment.strftime(STAMP_FORMAT)
            if text not in self.used:
                self.used.add(text)
                return text

    def live_pid(self) -> int:
        proc = subprocess.Popen([sys.executable, "-c",
                                 "import time; time.sleep(600)"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        return proc.pid

    @staticmethod
    def dead_pid() -> int:
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        return proc.pid

    def put_mark(self, stamp: str, pid) -> Path:
        mark = self.registry() / f"{stamp}.lock"
        mark.write_text(f"{pid}\n", encoding="utf-8")
        return mark

    def put_record(self, stamp: str, pid: int, sha: str, start_known: bool = True) -> Path:
        started = doctor.process_start_time(pid) if start_known else None
        record = self.registry() / f"{stamp}-{pid}.json"
        record.write_text(json.dumps({
            "pid": pid,
            "process_start": None if started is None else started.isoformat(),
            "run_stamp": stamp, "sha": sha, "set_name": config.CANARY_DEFAULT_SET,
            "started_at": (datetime.now(timezone.utc)
                           - timedelta(seconds=300)).isoformat(),
            "tasks": 1}), encoding="utf-8")
        return record

    def swept(self) -> list:
        return [dict(r) for r in store.all_steps(store.db())
                if r["action"] == canary.LIVE_RUN_SWEPT_ACTION]

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

    def origin_main(self) -> str:
        return self.git("--git-dir", str(self.origin), "rev-parse",
                        f"refs/heads/{config.MAIN_BRANCH}").strip()

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

    def held_reason(self, out: str, prologue: str) -> str:
        self.assertIn(prologue, out, self.msg(out))
        return out.split(prologue, 1)[1].split("; отправка", 1)[0]

    # ------------------------------------------------------- задачи мержа

    def in_repo(self, repo: Path, *args: str) -> str:
        return self.git("-C", str(repo), *args)

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

    def make_task(self) -> dict:
        """Задача артели на `merge_gate`: ветка опубликована, документы на ссылке, фиксация."""
        self.commit_to_main({
            MAP_REL: f"{MAP_PLACEHOLDER}\n{self.rng.randrange(10 ** 9)}\n"})
        task = "01T" + self.token(23)
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
        store.insert_task(self.conn, task, f"Задача {task}", "merge_gate", branch,
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        self.put_docs(task, {"SPEC.md": spec_text(task), "PLAN.md": plan_text(task),
                             "acceptance_tests/test_ac1_fixture.py": plank_text()})
        store.record_fixation(self.conn, task)
        fixed = store.get_task(self.conn, task)["fixed_sha"] or head
        return {"id": task, "branch": branch, "head": fixed}

    def state_of(self, task: dict) -> str:
        return store.get_task(store.db(), task["id"])["state"]

    def approve(self, task: dict, *extra: str) -> tuple:
        outputs, ok = [], True
        for _ in range(3):
            ok, out = self.cli("approve", task["id"], *extra)
            outputs.append(out)
            if not ok or self.state_of(task) != "merge_gate":
                break
        return ok, "\n".join(outputs)

    def run_canary(self) -> tuple:
        """`canary --k 1 --sha <main origin> --template <шаблон>` в процессе теста; ведение подменено."""
        real_popen = subprocess.Popen
        sha = self.origin_main()

        def launch(argv, *args, **kw):
            words = ([os.fsdecode(a) for a in argv]
                     if isinstance(argv, (list, tuple)) else [])
            if canary.CANARY_DRIVE_MODULE not in words:
                return real_popen(argv, *args, **kw)
            result = Path(words[words.index("--result") + 1])
            result.write_text(json.dumps({
                "task_id": "01FIXTURE", "head": sha, "outcome": "killed",
                "escalated": False,
                "metrics": {"steps": 1, "cost_usd": 0.0, "review_iterations": 0,
                            "escalations": [], "dev_retries": 0, "outcome": "killed",
                            "kill_note": "штатно", "test_author_visited": False,
                            "ceiling_exhausted": False, "ceiling_raise": None},
                "steps": []}))
            return real_popen([sys.executable, "-c", "pass"], *args, **kw)

        with mock.patch.object(catalog, "cmd_init"), \
                mock.patch.object(subprocess, "Popen", launch), \
                mock.patch.object(runner, "in_role_environment", return_value=False):
            return self.cli("canary", "--k", "1", "--sha", sha, "--template", TEMPLATE)

    # ============================================================== AC-1

    def test_ac1_mark_with_live_pid_holds_note_merge_and_note_now(self):
        """Метка S без записи с живым pid: `approve` задачи артели на `merge_gate`, `note --now` и обычный `note`.

        Наблюдение: `approve` отказан текстом, содержащим «идёт канарейка S
        (запись реестра отсутствует)», задача на `merge_gate`, main origin
        тот же; `note --now` отказан с той же причиной, запись в origin не
        ушла; обычный `note` удержан окном тишины, причина содержит ту же
        строку, запись в origin не ушла. Метка на месте.

        Ловит мутацию: метка без записи учитывается только окном тишины
        `note`, а отказ мержа смотрит лишь на прогоны набора по умолчанию
        из записей (у метки набора нет) — `approve` мержит и двигает main;
        либо причина не называет отсутствие записи.
        """
        stamp = self.stamp()
        mark = self.put_mark(stamp, self.live_pid())
        reason = f"идёт канарейка {stamp} {ABSENT}"
        task = self.make_task()
        before = self.origin_main()
        ok, out = self.approve(task)
        self.assertFalse(ok, self.msg(out))
        self.assertIn(reason, out, self.msg(out))
        self.assertEqual(self.state_of(task), "merge_gate", self.msg(out))
        self.assertEqual(self.origin_main(), before, self.msg(out))

        marker, text = self.note_text()
        ok, out = self.cli("note", "--now", "копилка", "--text", text)
        self.assertFalse(ok, self.msg(out))
        self.assertIn(reason, out, self.msg(out))
        self.assertNotIn(marker, self.origin_file("docs/backlog.md"), self.msg(out))

        marker, text = self.note_text()
        ok, out = self.cli("note", "копилка", "--text", text)
        self.assertIn(reason, self.held_reason(out, "заметка удержана: "), self.msg(out))
        self.assertNotIn(marker, self.origin_file("docs/backlog.md"), self.msg(out))
        self.assertEqual(self.origin_main(), before, self.msg(out))
        self.assertTrue(mark.exists(), self.msg("метка живого прогона убрана"))

    # ============================================================== AC-5

    def test_ac5_mark_beside_dead_record_one_note_call(self):
        """Мёртвая запись S и метка S; один вызов `note`: (i) метка с живым чужим pid, (ii) метка с pid мёртвой записи.

        (i): запись убрана со строкой `LIVE_RUN_SWEPT_ACTION`, метка на
        месте, этот же `note` удержан с причиной «идёт канарейка S (запись
        реестра отсутствует)». (ii): убраны и запись, и метка, этот же
        `note` не удержан — запись ушла в origin.

        Ловит мутацию: метки сверяются до уборки записей (метка (i) видит
        ещё не убранную запись и пропускается — `note` уходит в origin), либо
        осиротевшая метка проверяется только следующим вызовом.
        """
        for case in ("i", "ii"):
            with self.subTest(случай=case):
                stamp = self.stamp()
                dead = self.dead_pid()
                record = self.put_record(stamp, dead, self.origin_main(),
                                         start_known=False)
                owner = self.live_pid() if case == "i" else dead
                mark = self.put_mark(stamp, owner)
                swept = len(self.swept())
                marker, text = self.note_text()
                ok, out = self.cli("note", "копилка", "--text", text)
                self.assertFalse(record.exists(), self.msg(f"{case}: запись осталась\n{out}"))
                self.assertGreater(len(self.swept()), swept, self.msg(out))
                if case == "i":
                    self.assertTrue(mark.exists(), self.msg(f"метка живого pid убрана\n{out}"))
                    reason = self.held_reason(out, "заметка удержана: ")
                    self.assertIn(f"идёт канарейка {stamp} {ABSENT}", reason, self.msg(out))
                    self.assertNotIn(marker, self.origin_file("docs/backlog.md"))
                    mark.unlink()
                    ok, out = self.cli("note", "--flush")
                    self.assertTrue(ok, self.msg(out))
                else:
                    self.assertFalse(mark.exists(), self.msg(f"метка осталась\n{out}"))
                    self.assertNotIn("удержана", out, self.msg(out))
                    self.assertIn(marker, self.origin_file("docs/backlog.md"), self.msg(out))

    # ============================================================= AC-21

    def test_ac21_without_stray_mark_consumers_unchanged(self):
        """Без метки без записи: пустой реестр и живая запись со своей меткой.

        Пустой реестр: `note` и `doc-commit` уходят в origin без упоминания
        канарейки, `approve` доводит задачу до `done`, прогон `canary` печатает
        прежние первую строку «[canary] прогон <run_stamp>: 1 задач из пула …»
        и последнюю «[canary] прогон <run_stamp> завершён». Живая запись R со
        своей меткой: `note` и `doc-commit` удержаны причиной ровно «идёт
        канарейка R на <sha7>», `approve` отказан прежним текстом мержа с той
        же причиной; пометки об отсутствии записи нет нигде.

        Ловит мутацию: метка рядом с живой записью читается новой логикой
        как отдельный прогон (причина первой называет «запись реестра
        отсутствует»), либо окно открывается на пустом реестре (обычная
        заметка удержана, `approve` отказан).
        """
        marker, text = self.note_text()
        ok, out = self.cli("note", "копилка", "--text", text)
        self.assertNotIn("удержан", out, self.msg(out))
        self.assertNotIn("канарейк", out, self.msg(out))
        self.assertIn(marker, self.origin_file("docs/backlog.md"), self.msg(out))
        doc_marker, rel, source = self.doc_source()
        ok, out = self.cli("doc-commit", rel, "--from", str(source), "--message", "правка")
        self.assertNotIn("канарейк", out, self.msg(out))
        self.assertIn(doc_marker, self.origin_file(rel), self.msg(out))
        task = self.make_task()
        ok, out = self.approve(task)
        self.assertEqual(self.state_of(task), "done", self.msg(out))
        self.assertNotIn("канарейк", out, self.msg(out))
        ok, out = self.run_canary()
        self.assertTrue(ok, self.msg(out))
        lines = [line for line in out.splitlines() if line.startswith("[canary] прогон ")]
        self.assertTrue(lines, self.msg(out))
        run_stamp = re.match(r"\[canary\] прогон (\d{8}T\d{6}Z)", lines[0]).group(1)
        self.assertTrue(lines[0].startswith(f"[canary] прогон {run_stamp}: 1 задач из пула "),
                        self.msg(out))
        self.assertEqual(lines[-1], f"[canary] прогон {run_stamp} завершён", self.msg(out))
        self.assertNotIn(ABSENT, out, self.msg(out))

        stamp = self.stamp()
        sha = self.origin_main()
        pid = self.live_pid()
        self.put_record(stamp, pid, sha)
        self.put_mark(stamp, pid)
        note = f"идёт канарейка {stamp} на {sha[:7]}"
        marker, text = self.note_text()
        ok, out = self.cli("note", "копилка", "--text", text)
        self.assertEqual(self.held_reason(out, "заметка удержана: "), note, self.msg(out))
        doc_marker, rel, source = self.doc_source()
        ok, out = self.cli("doc-commit", rel, "--from", str(source), "--message", "правка")
        self.assertEqual(self.held_reason(out, "doc-commit удержан: "), note, self.msg(out))
        task = self.make_task()
        before = self.origin_main()
        ok, out = self.cli("approve", task["id"])
        self.assertFalse(ok, self.msg(out))
        self.assertIn(merge_refusal(note), out, self.msg(out))
        self.assertNotIn(ABSENT, out, self.msg(out))
        self.assertEqual(self.state_of(task), "merge_gate", self.msg(out))
        self.assertEqual(self.origin_main(), before, self.msg(out))


if __name__ == "__main__":
    unittest.main()
