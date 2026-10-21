"""AC-6: защита части А держится на записях дочерних процессов — мерж, окно тишины, обходы окна, `canary live` и `--drop`.

Группа: разовый
Красен до реализации: подкоманды `run-task` нет — снять копию записи дочернего во время подменённой задачи нечем (вызов отказывает «нужен параметр --k»), состояния «живы родитель и дочерние» и «жив только дочерний» не строятся; после `--drop` метки вызов подкоманды отказывает той же причиной «нужен параметр --k», а не сверкой метки.

Почему разовый: запись дочернего по критерию — копия файла, снятая во
время подменённой задачи подкоманды (закрытые `_run_one_task` и `_set_plan`
подменены); правила долгоживущего файла `tests/` такие подмены запрещают.

Песочница — `tests.sandbox.RealGitSandbox` по образцу
`tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`: главная копия пульта с
копией `orchestrator/`/`scripts/`, бэклогом и заглушкой карты, bare
`origin`, подставной `gh` (зелёные проверки), подставные часы и пауза
пульта, домашний каталог подменён. Команды — диспетчером `artel.main()` тем
же argv, что набирает Оператор.

Реестр раскладывается файлами: запись родителя — поля записи
последовательного прогона с pid `os.getppid()` процесса теста (живой),
метка `<run_stamp>.lock` с тем же pid; запись дочернего — копия, снятая
подкомандой в процессе теста (pid — сам процесс теста), восстанавливаемая
для каждого состояния. Эталон «живого последовательного прогона» — запись
и метка настоящего `canary._live_run_record`. Значения порождаются от
зерна; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _runtask import RunTaskMixin, invoke, plan  # noqa: E402

from orchestrator import artel, canary, catalog, config, keychain, store  # noqa: E402
from tests.sandbox import RealGitSandbox, capture, patch_pult_sleep  # noqa: E402

REPO = Path(canary.__file__).resolve().parents[1]
TASKS_DIR = config.TASKS.name
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


def window_refusal(note: str) -> str:
    return f'{note}: команда сдвинет main — дождись итога или повтори с {FLAG} "<основание>"'


def merge_refusal(note: str) -> str:
    return (f"{note}: мерж сдвинет main под проверяемым коммитом — дождись итога "
            f'или повтори с {FLAG} "<основание>"')


class WindowConsumersTest(RunTaskMixin, RealGitSandbox):
    """Главная копия пульта с origin и бэклогом; реестр — файлами под корнем песочницы."""

    def setUp(self):
        super().setUp()
        self.setup_runtask()
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

    # ------------------------------------------------------------ фикстуры

    def fake_sleep(self, seconds) -> None:
        self.clock += float(seconds)
        if self.clock > 10 * 24 * 3600:
            raise AssertionError(self.msg("ожидание не кончается"))

    def ulid(self, n: int = 23) -> str:
        return "".join(self.rng.choice(ULID_ALPHABET) for _ in range(n))

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
        old = "01H" + self.ulid()
        plank_path = self.root / TASKS_DIR / old / "acceptance_tests" / "test_old.py"
        plank_path.parent.mkdir(parents=True)
        plank_path.write_text(plank_text(), encoding="utf-8")
        retro_path = self.root / "docs" / "retro" / f"{old}.md"
        retro_path.parent.mkdir(parents=True)
        retro_path.write_text(f"# RETRO: {old}\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "код пульта")

    def cli(self, *argv: str) -> tuple:
        out = io.StringIO()
        ok, tail = True, ""
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                mock.patch.object(keychain, "token", return_value="k" * 32), \
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
        marker = f"zapis{self.calls}-{self.ulid(8)}"
        return marker, f"2 | 18.10 | {marker} | orchestrator/n.py"

    def doc_source(self) -> tuple:
        self.calls += 1
        marker = f"doc{self.calls}-{self.ulid(8)}"
        source = self.home / f"{marker}.md"
        source.write_text(f"# Документ\n\n{marker}\n", encoding="utf-8")
        return marker, f"docs/okno-{marker.lower()}.md", source

    def held_reason(self, out: str, prologue: str) -> str:
        self.assertIn(prologue, out, self.msg(out))
        return out.split(prologue, 1)[1].split("; отправка", 1)[0]

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
        task = "01T" + self.ulid()
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

    # ------------------------------------------------------ реестр на диске

    def clear_registry(self) -> None:
        directory = self.registry()
        if directory.is_dir():
            for path in directory.iterdir():
                path.unlink()

    def lay_out(self, stamp: str, set_name: str, child: bytes | None,
                parent: bool) -> dict:
        """Состояние реестра: запись и метка родителя (`os.getppid()`), запись дочернего — копия."""
        self.clear_registry()
        files = {}
        if parent:
            files["parent"] = self.put_record(stamp, self.ppid, self.sha, set_name)
            files["mark"] = self.put_mark(stamp, self.ppid)
        if child is not None:
            path = self.registry() / self.own_record_name(stamp)
            path.write_bytes(child)
            files["child"] = path
        return files

    # ------------------------------------------------------------ проверки

    def check_consumers(self, task: dict, note: str, ctx: str, full: bool = True) -> None:
        before = self.origin_main()
        ok, out = self.cli("approve", task["id"])
        msg = self.msg(f"{ctx}, approve: {out}")
        self.assertFalse(ok, msg)
        self.assertIn(merge_refusal(note), out, msg)
        self.assertEqual(self.state_of(task), "merge_gate", msg)
        self.assertEqual(self.origin_main(), before, msg)
        ok, out = self.cli("approve", task["id"], task["head"])
        msg = self.msg(f"{ctx}, approve <sha>: {out}")
        self.assertFalse(ok, msg)
        self.assertIn(merge_refusal(note), out, msg)
        self.assertEqual(self.state_of(task), "merge_gate", msg)
        if not full:
            return

        marker, text = self.note_text()
        ok, out = self.cli("note", "копилка", "--text", text)
        self.assertEqual(self.held_reason(out, "заметка удержана: "), note,
                         self.msg(f"{ctx}, note: {out}"))
        self.assertNotIn(marker, self.origin_file("docs/backlog.md"), self.msg(ctx))
        doc_marker, rel, source = self.doc_source()
        ok, out = self.cli("doc-commit", rel, "--from", str(source),
                           "--message", "правка документа")
        self.assertEqual(self.held_reason(out, "doc-commit удержан: "), note,
                         self.msg(f"{ctx}, doc-commit: {out}"))
        self.assertEqual(self.origin_file(rel), "", self.msg(ctx))

        marker, text = self.note_text()
        for name, argv in (("note --now", ["note", "--now", "копилка", "--text", text]),
                           ("note --flush", ["note", "--flush"]),
                           ("doc-commit --flush", ["doc-commit", "--flush"]),
                           ("canary pool-seal", ["canary", "pool-seal"])):
            before = self.origin_main()
            ok, out = self.cli(*argv)
            msg = self.msg(f"{ctx}, {name}: {out}")
            self.assertFalse(ok, msg)
            self.assertIn(window_refusal(note), out, msg)
            self.assertEqual(self.origin_main(), before, msg)
        self.assertNotIn(marker, self.origin_file("docs/backlog.md"), self.msg(ctx))

    # ============================================================== AC-6

    def consumers_in_state(self, has_parent: bool, has_child: bool, full: bool,
                           name: str) -> None:
        stamp = self.stamp()
        summary = "сводка " + self.token(6)
        child = (self.capture_record(stamp, config.CANARY_DEFAULT_SET, summary)
                 if has_child else None)
        task = self.make_task()
        note = f"идёт канарейка {stamp} на {self.sha[:7]}"
        self.lay_out(stamp, config.CANARY_DEFAULT_SET, child, has_parent)
        self.check_consumers(task, note, name, full)

    def test_ac6_reference_sequential_run_outcomes(self):
        """Эталон: запись и метка живого последовательного прогона S (настоящий `canary._live_run_record`).

        Наблюдение: `approve <id>` и `approve <id> <sha>` на `merge_gate`
        отказаны текстом части А «идёт канарейка S на <sha7>: мерж сдвинет
        main …», задача на `merge_gate`, main origin тот же; `note` и
        `doc-commit` удержаны той же причиной; `note --now`, `note --flush`,
        `doc-commit --flush`, `canary pool-seal` без `--during-canary`
        отказаны «… команда сдвинет main …». Эти же ожидания проверяются в
        трёх состояниях ниже — эталон держит, что они и есть исход
        последовательного прогона.

        Зелёный с рождения: держит исход живого последовательного прогона —
        ожидания трёх состояний ниже, не код задачи.
        """
        stamp = self.stamp()
        task = self.make_task()
        note = f"идёт канарейка {stamp} на {self.sha[:7]}"
        self.clear_registry()
        with canary._live_run_record(stamp, self.sha, config.CANARY_DEFAULT_SET, 1):
            self.check_consumers(task, note, "эталон: последовательный прогон")

    def test_ac6_parent_and_child_alive(self):
        """Живы родитель (запись и метка с pid `os.getppid()`) и дочерний (копия записи подкоманды): исход эталона у всех семи команд.

        Ловит мутацию: запись дочернего пишется с набором из `--summary` или
        без `set_name`/`sha` — `live_run_note` называет прогон по ней иначе,
        чем по записи родителя («идёт канарейка S на » без sha7), и
        причина отказа расходится с эталоном.
        """
        self.consumers_in_state(True, True, True, "живы родитель и дочерний")

    def test_ac6_parent_only_alive(self):
        """Жив только родитель (запись и метка, дочерних записей нет): `approve` — исход эталона.

        Зелёный с рождения: держит, что запись и метка родителя без
        дочерних записей (состояние после конца дочерних процессов) держат
        мерж тем же текстом, что эталон; записи дочернего здесь нет.
        """
        self.consumers_in_state(True, False, False, "жив только родитель")

    def test_ac6_child_only_alive(self):
        """Жив только дочерний (запись родителя и метка убраны): исход эталона у всех семи команд.

        Ловит мутацию: запись дочернего не пишет `set_name` набора по
        умолчанию (мерж не держится — `live_run_note(default_set_only=True)`
        её пропускает) либо пишется с `tasks`/`started_at`, при которых
        `live_runs` убирает её как мёртвую — `approve` мержит, `note` уходит
        в origin.
        """
        self.consumers_in_state(False, True, True, "жив только дочерний")

    def test_ac6_other_set_child_does_not_hold_merge(self):
        """Живы родитель и дочерний прогона набора не по умолчанию (копия записи подкоманды с `--set` другого набора).

        Наблюдение: `approve` задачи артели на `merge_gate` доводит её до
        `done`, вывод не называет «идёт канарейка».

        Ловит мутацию: запись дочернего пишет `set_name` набора по умолчанию
        вместо `--set` — мерж держится прогоном другого набора.
        """
        stamp, set_name = self.stamp(), "nabor-" + self.token(5)
        child = self.capture_record(stamp, set_name, "сводка " + self.token(6))
        task = self.make_task()
        self.lay_out(stamp, set_name, child, True)
        ok, out = self.approve(task)
        self.assertEqual(self.state_of(task), "done", self.msg(out))
        self.assertNotIn("идёт канарейка", out, self.msg(out))

    def test_ac6_canary_live_lists_child_and_drop_refuses(self):
        """`canary live` и `canary live --drop S` в состоянии «живы родитель и дочерний», затем `--drop` при живом только дочернем.

        Наблюдение: `canary live` печатает строку каждой записи — родителя
        (pid `os.getppid()`) и дочернего (pid процесса теста, с `parent_pid`
        и шаблоном); `--drop S` при свежих живых записях отказывает «снимать
        нечего», метка и записи на месте.

        Ловит мутацию: запись дочернего без `process_start` (или с
        `started_at` в прошлом) — `--drop` снимает её как зависшую вместе с
        меткой; либо без `parent_pid`/`template` — строка дочернего в
        `canary live` не отличима от родительской.
        """
        stamp = self.stamp()
        child = self.capture_record(stamp, config.CANARY_DEFAULT_SET,
                                    "сводка " + self.token(6))
        files = self.lay_out(stamp, config.CANARY_DEFAULT_SET, child, True)
        ok, out = self.cli("canary", "live")
        msg = self.msg(out)
        self.assertTrue(ok, msg)
        lines = out.splitlines()
        parent_lines = [line for line in lines if f"{stamp}: pid {self.ppid}" in line]
        child_lines = [line for line in lines if f"{stamp}: pid {os.getpid()}" in line]
        self.assertEqual(len(parent_lines), 1, msg)
        self.assertEqual(len(child_lines), 1, msg)
        self.assertIn(f"parent_pid {self.ppid}", child_lines[0], msg)
        self.assertIn(f"шаблон {self.template_name}", child_lines[0], msg)

        for name, has_parent in (("живы родитель и дочерний", True),
                                 ("жив только дочерний", False)):
            with self.subTest(состояние=name):
                files = self.lay_out(stamp, config.CANARY_DEFAULT_SET, child, has_parent)
                shot = {k: p.read_bytes() for k, p in files.items()}
                ok, out = self.cli("canary", "live", "--drop", stamp, "основание теста")
                msg = self.msg(f"{name}: {out}")
                self.assertFalse(ok, msg)
                self.assertIn("снимать нечего", out, msg)
                self.assertEqual({k: p.read_bytes() for k, p in files.items() if p.exists()},
                                 shot, msg)

    def test_ac6_subcommand_after_dropped_mark_refused(self):
        """Метка S без записей снята `canary live --drop S`; затем подкоманда с `--stamp S`.

        Наблюдение: `--drop` снимает метку; подкоманда — ненулевой код
        отказом сверки метки п. 2 (б) («метка прогона S не принадлежит
        родителю <ppid>»), клон и ведение задачи не звались, строк
        `canary_runs` с run_stamp S нет.

        Ловит мутацию: отсутствие метки родителя не отказывает (сверка (б)
        пропускается, когда метки нет) — подкоманда ведёт задачу прогона,
        снятого Оператором.
        """
        stamp, set_name = self.stamp(), "nabor-" + self.token(5)
        summary = "сводка " + self.token(6)
        self.clear_registry()
        mark = self.put_mark(stamp, self.ppid)
        ok, out = self.cli("canary", "live", "--drop", stamp, "основание теста")
        self.assertTrue(ok, self.msg(out))
        self.assertFalse(mark.exists(), self.msg(out))
        with contextlib.ExitStack() as stack:
            spies = self.guards(stack)
            stack.enter_context(mock.patch.object(
                canary, "_set_plan", return_value=plan(set_name, summary)))
            runs = stack.enter_context(mock.patch.object(canary, "_run_one_task"))
            outcome = invoke(self.argv(stamp, set_name, summary))
        msg = self.msg(outcome)
        self.assertNotEqual(outcome.code, 0, msg)
        self.assertIn(f"canary run-task: метка прогона {stamp} не принадлежит "
                      f"родителю {self.ppid}", outcome.text, msg)
        self.assertFalse(runs.called, msg)
        self.assertFalse(spies["_ephemeral_clone"].called, msg)
        self.assertEqual(self.rows(stamp), [], msg)


if __name__ == "__main__":
    unittest.main()
