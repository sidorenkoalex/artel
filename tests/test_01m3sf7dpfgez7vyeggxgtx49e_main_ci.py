"""Main не краснеет незаметно: guard после снимка на гейте мержа, цвет CI
main по проверкам первой родительской линии в `pin-update`, `doctor` и
следующем мерже, ожидание CI новой головы main после мержа.

Группа: долгоживущий

Красен до реализации: гейт мержа не гоняет `guard.py --all` по дереву после снимка и пушит нарушающий снимок, `pin-update` не сверяет CI коммита, `doctor` не печатает строку о CI main, `approve` не ждёт CI новой головы main, не отказывает при красном main и не знает флага `--fixes-main`.

Методы прежнего поведения зелены и до реализации и держат его после:
чистый снимок и снимок с одними предупреждениями guard мержатся,
`pin-update` на коммит с зелёной первой родительской линией (в том числе
merge-коммит, чья влитая ветка когда-то падала) проходит, `pin --to`
CI не сверяет. Планка провалидирована временным стабом реализации (все
методы зелёные, стаб удалён).

Песочница — настоящий git: главная копия пульта (`config.ROOT`) с копией
`orchestrator/` и `scripts/` репозитория в первом коммите (гейт мержа
вправе звать `scripts/guard.py` дерева мержа), bare `origin` и
вспомогательный клон, из которого в origin/main приходят «чужие» коммиты
(код и документные). GitHub изображает подставной `gh` в начале `PATH`:
он отвечает на `gh api …/commits/<sha>/check-runs` по таблице сценария
(sha -> проверки), на `gh run list` — пустым списком, а в режиме
«недоступен» — ненулевым кодом на любой вызов. Коммит, которого нет в
таблице (новая голова main после мержа), получает проверки «по
умолчанию» сценария — первые `pending_polls` опросов они ещё идут.
Часы (`time.monotonic`/`time.time`/`time.sleep`) — подставные: пауза
двигает их мгновенно, поэтому предел ожидания измеряется без реального
ожидания.

Команды зовутся через диспетчер `artel.main()` — тем же argv, что
набирает Оператор (`approve`, `pin-update`, `pin --to`); строка
`doctor` ищется среди `doctor.all_checks` по содержанию, а не по имени
(имени SPEC не фиксирует): проверка `fail`, называющая упавшую проверку
и коммит, на котором она упала; её имя затем служит адресом той же
строки в исходах `ok`/`warn`.

Имена проверок CI, число документных коммитов поверх красного, вид
нарушения guard, основание `--fixes-main` и вид провала проверки
выбираются случайно; зерно печатается и входит в текст провала.

AC-6 (проверки в `tests/`) покрывает этот файл целиком: отказ мержа до
push при нарушающем снимке (`test_ac1_…`, заявка «мерж без guard после
снимка») и прохождение чистого снимка; исходы `pin-update` и `pin --to`
(`test_ac2_…`); три исхода строки `doctor` (`test_ac3_…`); ожидание CI
main после мержа (`test_ac4_…`); отказ следующего мержа и `--fixes-main`
(`test_ac5_…`); сценарий «красный мерж, затем документный коммит»
(`test_ac6_…`).
"""
import ast
import contextlib
import inspect
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
from pathlib import Path
from unittest import mock

from orchestrator import (artel, artifact_branch, catalog, config, doctor,
                          fixation, fsm_merge_gate, store)
from scripts import guard
from tests.sandbox import RealGitSandbox, capture, patch_pult_sleep

REPO = Path(__file__).resolve().parent.parent

# Подставной `gh`: таблица сценария лежит JSON-файлом по пути из
# переменной окружения; каждый вызов дописывается в журнал рядом
# (`<файл>.log`, одна строка JSON на вызов).
FAKE_GH = r'''
import json, os, re, sys
state_path = os.environ["ARTEL_FAKE_GH_STATE"]
with open(state_path, encoding="utf-8") as fh:
    state = json.load(fh)
with open(state_path + ".log", "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\n")
if state.get("unavailable"):
    sys.stderr.write("gh: сеть недоступна (песочница)\n")
    sys.exit(1)
args = sys.argv[1:]
joined = " ".join(args)
found = re.search(r"commits/([0-9a-fA-F]{7,40})/check-runs", joined)
if args[:1] == ["api"] and found:
    sha = found.group(1).lower()
    runs = None
    for key, value in state["checks"].items():
        if key.startswith(sha) or sha.startswith(key):
            runs = value
            break
    if runs is None:
        polls = state.setdefault("polls", {})
        polls[sha] = polls.get(sha, 0) + 1
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False)
        default = state["default"]
        runs = default["runs"]
        if polls[sha] <= default["pending_polls"]:
            runs = [{"name": r["name"], "status": "in_progress",
                     "conclusion": None} for r in runs]
    page = re.search(r"[?&]page=(\d+)", joined)
    page_runs = runs if page is None or page.group(1) == "1" else []
    print(json.dumps({"total_count": len(runs), "check_runs": page_runs},
                     ensure_ascii=False))
    sys.exit(0)
if args[:2] == ["run", "list"]:
    print("[]")
    sys.exit(0)
sys.stderr.write("gh песочницы: вызов не поддержан: " + joined + "\n")
sys.exit(1)
'''

HEX = re.compile(r"[0-9a-f]{7,40}")
# Предел ожидания CI новой головы main — от 15 до 20 минут (AC-4).
WAIT_MIN_SEC = 15 * 60
WAIT_MAX_SEC = 20 * 60


def completed(name: str, conclusion: str) -> dict:
    return {"name": name, "status": "completed", "conclusion": conclusion}


def running(name: str) -> dict:
    return {"name": name, "status": "in_progress", "conclusion": None}


def names_commit(text: str, sha: str) -> bool:
    """Текст называет коммит `sha` — его префиксом от 7 символов."""
    return any(sha.startswith(token) for token in HEX.findall(text))


class MainCiSandbox(RealGitSandbox):
    """Главная копия, bare origin, вспомогательный клон, подставной `gh`
    и подставные часы."""

    COPY_CODE = False

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.code_check = f"тесты кода {self.rng.randrange(1000, 9999)}"
        self.docs_check = f"валидация артефактов {self.rng.randrange(1000, 9999)}"
        self.failure = self.rng.choice(("failure", "timed_out"))
        if self.COPY_CODE:
            for name in ("orchestrator", "scripts"):
                shutil.copytree(REPO / name, self.root / name,
                                ignore=shutil.ignore_patterns("__pycache__"))
            config.TARGETS.write_text(
                "targets:\n"
                "  artel:\n"
                "    forge: github\n"
                "    url: http://localhost/artel\n"
                f"    base: {config.MAIN_BRANCH}\n"
                "    token_slot: artel-token\n"
                "    no_paths: []\n"
                "    project_skills: []\n"
                "    merge_gate: operator\n", encoding="utf-8")
            self.git("add", "-A")
            self.git("commit", "-q", "-m", "код пульта")
        self.base_sha = self.git("rev-parse", "HEAD").strip()
        self.origin = self.add_synced_origin()
        capture(catalog.cmd_init)
        self.conn = store.db()

        helper = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, helper, ignore_errors=True)
        self.helper = Path(helper) / "clone"
        self.git("clone", "-q", str(self.origin), str(self.helper))
        self.hgit("config", "user.email", "chuzhoy@example.invalid")
        self.hgit("config", "user.name", "chuzhoy pult")
        self.commit_no = 0

        bindir = self.root / ".artel" / "fake-bin"
        bindir.mkdir(parents=True, exist_ok=True)
        gh = bindir / "gh"
        gh.write_text(f"#!{sys.executable}\n{FAKE_GH}", encoding="utf-8")
        gh.chmod(0o755)
        self.gh_state = self.root / ".artel" / "fake-gh.json"
        self.state = {"checks": {self.base_sha: self.green()},
                      "unavailable": False,
                      "default": {"pending_polls": 0, "runs": self.green()}}
        self.save_state()
        env = mock.patch.dict(os.environ, {
            "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            "ARTEL_FAKE_GH_STATE": str(self.gh_state)})
        env.start()
        self.addCleanup(env.stop)

        self.clock = 0.0
        base_mono, base_wall = time.monotonic(), time.time()
        for target, fake in (
                ("time.monotonic", lambda: base_mono + self.clock),
                ("time.time", lambda: base_wall + self.clock)):
            patcher = mock.patch(target, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Пауза — только у модулей пульта: подмена `time.sleep` модуля
        # `time` ловила бы и паузы `subprocess` (SPEC
        # 01M443HPZBMJGCHVGV4JQN88RS).
        self.addCleanup(patch_pult_sleep(self.fake_sleep).close)

    # ---------------------------------------------------------- фикстуры CI

    def green(self) -> list:
        return [completed(self.code_check, "success"),
                completed(self.docs_check, "success")]

    def red(self) -> list:
        return [completed(self.code_check, self.failure),
                completed(self.docs_check, "success")]

    def doc_only(self) -> list:
        """Документный коммит (ADR-0016): проверка кода пропущена."""
        return [completed(self.code_check, "skipped"),
                completed(self.docs_check, "success")]

    def code_running(self) -> list:
        return [running(self.code_check), completed(self.docs_check, "success")]

    def fake_sleep(self, seconds) -> None:
        self.clock += float(seconds)
        if self.clock > 10 * 24 * 3600:
            raise AssertionError(f"зерно: {self.seed}; ожидание не кончается")

    def save_state(self) -> None:
        self.gh_state.write_text(json.dumps(self.state, ensure_ascii=False),
                                 encoding="utf-8")

    def set_checks(self, sha: str, runs: list) -> None:
        self.state["checks"][sha] = runs
        self.save_state()

    def set_default(self, runs: list, pending_polls: int = 0) -> None:
        self.state["default"] = {"pending_polls": pending_polls, "runs": runs}
        self.save_state()

    def set_gh_unavailable(self) -> None:
        self.state["unavailable"] = True
        self.save_state()

    def gh_calls(self) -> list:
        log = Path(f"{self.gh_state}.log")
        if not log.is_file():
            return []
        return [json.loads(line) for line in
                log.read_text(encoding="utf-8").splitlines() if line]

    # -------------------------------------------------------------- git

    def hgit(self, *args: str) -> str:
        return self.git("-C", str(self.helper), *args)

    def origin_main(self) -> str:
        return self.git("-C", str(self.origin), "rev-parse",
                        f"refs/heads/{config.MAIN_BRANCH}").strip()

    def push_to_origin(self, runs: list, doc: bool = False,
                       date: str | None = None) -> str:
        """Чужой коммит в origin/main из вспомогательного клона (код либо
        документ), его проверки — `runs`; главная копия его фетчит."""
        self.hgit("pull", "-q", "--ff-only", "origin", config.MAIN_BRANCH)
        self.commit_no += 1
        rel = (f"docs/zametka-{self.commit_no}.md" if doc
               else f"chuzhoy_kod_{self.commit_no}.py")
        path = self.helper / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"правка {self.commit_no}\n", encoding="utf-8")
        self.hgit("add", rel)
        env = {"GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date} if date else {}
        with mock.patch.dict(os.environ, env):
            self.hgit("commit", "-q", "-m", f"чужая правка {self.commit_no}")
        sha = self.hgit("rev-parse", "HEAD").strip()
        self.hgit("push", "-q", "origin", f"HEAD:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin")
        self.set_checks(sha, runs)
        return sha

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    # ----------------------------------------------------------- команды

    def cli(self, *argv: str) -> tuple[bool, str]:
        """(успех, stdout + текст отказа) команды `artel.py <argv>`."""
        out = io.StringIO()
        ok = True
        tail = ""
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (0, None):
                    ok = False
                    tail = f"\n{exc.code}"
        return ok, out.getvalue() + tail

    def doctor_checks(self) -> list:
        """Все проверки `doctor`: git и `gh` исполняются, прочие внешние
        процессы (CLI ролей) — нет; дом пользователя — каталог песочницы
        (пул канарейки `doctor` ищет от него)."""
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
            return doctor.all_checks(store.db())

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"


class MergeSandbox(MainCiSandbox):
    """Задачи на `merge_gate` с кодовой веткой и ссылкой документов."""

    COPY_CODE = True

    def setUp(self):
        super().setUp()
        # Сверка фиксации артефактов при `approve` — не предмет этих
        # сценариев (тот же патч, что в долгоживущем
        # `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`): после
        # первого мержа песочницы она отказывала второй задаче «живой sha
        # … расходится с зафиксированным (нет)» раньше гейта мержа.
        patcher = mock.patch.object(fixation, "read", return_value=("", True))
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_task(self, snapshot: dict | None = None) -> dict:
        """Задача на `merge_gate`: кодовая ветка от origin/main (свежая,
        опубликована, её CI зелёный) и ссылка документов
        `refs/artifacts/<id>` (отправлена в origin) со снимком `snapshot`
        ({путь внутри каталога задачи: текст})."""
        task = f"01T{self.rng.randrange(1 << 100):022X}"[:26]
        branch = f"task/{task.lower()}-x"
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-b", branch,
                 f"origin/{config.MAIN_BRANCH}")
        code = f"zadacha_{task.lower()}.py"
        (self.root / code).write_text("VALUE = 1\n", encoding="utf-8")
        self.git("add", code)
        self.git("commit", "-q", "-m", f"{task}: код")
        head = self.head()
        self.git("push", "-q", "-u", "origin", branch)
        self.git("checkout", "-q", config.MAIN_BRANCH)
        task_dir = Path(config.TASKS.name) / task
        files = snapshot if snapshot is not None else {
            "acceptance_tests/test_ac1_fixture.py":
                "import unittest\n\n\nclass Fixture(unittest.TestCase):\n"
                "    def test_ac1_fixture(self):\n"
                "        self.assertTrue(True)\n"}
        self.set_checks(head, self.green())
        store.insert_task(self.conn, task, f"Задача {task}", "merge_gate",
                          branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        # Документы задачи — в `refs/artifacts/<id>` узлом записи пульта
        # (ADR-0021 п.3): он же отправляет ссылку в origin, с которым
        # гейт мержа сверяет её перед мержем.
        docs_sha = artifact_branch.commit_files(
            task, {(task_dir / rel).as_posix(): text
                   for rel, text in files.items()}, f"{task}: артефакты")
        self.assertTrue(docs_sha, self.msg("документы задачи не записаны"))
        return {"id": task, "branch": branch, "head": head,
                "dir": task_dir.as_posix()}

    def state_of(self, task: dict) -> str:
        return store.get_task(self.conn, task["id"])["state"]

    def journal_text(self, task: dict) -> list:
        return [f"{row['action']} | {row['detail'] or ''}"
                for row in store.task_steps(self.conn, task["id"])]

    def worktrees(self) -> list:
        listing = self.git("worktree", "list", "--porcelain")
        return [line for line in listing.splitlines()
                if line.startswith("worktree ")]

    def origin_tree_has(self, rel: str) -> bool:
        listing = self.git("-C", str(self.origin), "ls-tree", "-r",
                           "--name-only", f"refs/heads/{config.MAIN_BRANCH}")
        return rel in listing.splitlines()


# --------------------------------------------------------------------- AC-1

class MergeGuardAfterSnapshotTest(MergeSandbox):
    """AC-1: `guard.py --all` по дереву мержа после снимка, до push."""

    def violating_snapshot(self) -> tuple[dict, str, str]:
        """(снимок, путь нарушающего файла в каталоге задачи, текст
        нарушения guard) — нарушение не в первом уровне каталога задачи,
        где его уже ловит прежняя проверка посторонних файлов."""
        kind = self.rng.choice(("readme", "stray", "root_md"))
        if kind == "readme":
            rel, text = "acceptance_tests/README.md", "Пояснение без frontmatter.\n"
        elif kind == "root_md":
            rel, text = "QUESTIONS.md", "# Вопросы\n\nбез frontmatter\n"
        else:
            rel, text = "acceptance_tests/fixture.json", "{}\n"
        if kind == "stray":
            reason = guard.EXTRANEOUS_ACCEPTANCE_FILE_REASON
        else:
            errors = guard.check_content("ФАЙЛ", text)
            self.assertTrue(errors, self.msg(f"фикстура {rel} не нарушает guard"))
            reason = errors[0].split("ФАЙЛ: ", 1)[-1]
        snapshot = {"acceptance_tests/test_ac1_fixture.py":
                    "import unittest\n", rel: text}
        return snapshot, rel, reason

    def test_ac1_guard_violation_after_snapshot_refuses_before_push(self):
        """Снимок артефактной ветки несёт файл, нарушающий `guard --all`
        (README без frontmatter в `acceptance_tests/`, разрешённый
        `QUESTIONS.md` без frontmatter либо посторонний файл планки).

        `approve` отказывает: в выводе — путь файла и текст нарушения;
        задача на `merge_gate`, origin/main не сдвинут, временное дерево
        мержа снято (у главной копии нет лишних git-worktree).

        Ловит мутацию: мерж без guard после снимка — снимок с нарушением
        уезжает в origin/main, задача уходит в `done`, main краснеет на
        `guard --all` (инцидент 30.09).
        """
        snapshot, rel, reason = self.violating_snapshot()
        task = self.make_task(snapshot)
        before = self.origin_main()
        worktrees_before = self.worktrees()

        ok, out = self.cli("approve", task["id"])

        self.assertFalse(ok, self.msg(f"мерж не отказал: {out}"))
        self.assertIn(rel, out, self.msg(f"отказ не называет файл: {out}"))
        self.assertIn(reason, out, self.msg(f"отказ не называет нарушение: {out}"))
        self.assertEqual(self.state_of(task), "merge_gate", self.msg(out))
        self.assertEqual(self.origin_main(), before,
                         self.msg(f"origin/main сдвинут отказавшим мержем: {out}"))
        self.assertEqual(self.worktrees(), worktrees_before,
                         self.msg(f"дерево мержа не снято: {out}"))

    def test_ac1_clean_snapshot_merges_as_before(self):
        """Снимок без нарушений guard: мерж проходит как прежде.

        Задача в `done`, origin/main сдвинут и несёт файл снимка.

        Ловит мутацию: guard после снимка зовётся не по дереву мержа (не
        из его корня либо по рабочей копии пульта) и падает «файл не
        найден»/без каталога `tasks` — отказ даже на чистом снимке.
        """
        task = self.make_task()
        before = self.origin_main()

        ok, out = self.cli("approve", task["id"])

        self.assertEqual(self.state_of(task), "done", self.msg(out))
        self.assertNotEqual(self.origin_main(), before, self.msg(out))
        self.assertTrue(self.origin_tree_has(
            f"{task['dir']}/acceptance_tests/test_ac1_fixture.py"), self.msg(out))

    def test_ac1_guard_warnings_do_not_stop_merge(self):
        """Снимок, на котором `guard --all` даёт только предупреждение
        (`_sandbox.py` планки определяет свой `disk_backed_*`).

        Мерж проходит: задача в `done`, origin/main сдвинут.

        Ловит мутацию: предупреждения guard (или любой непустой вывод
        guard) читаются как нарушение — мерж с таким снимком отказывает.
        """
        task = self.make_task({
            "acceptance_tests/test_ac1_fixture.py": "import unittest\n",
            "acceptance_tests/_sandbox.py":
                "def disk_backed_show(branch, rel):\n    return None, ''\n"})
        before = self.origin_main()

        ok, out = self.cli("approve", task["id"])

        self.assertEqual(self.state_of(task), "done", self.msg(out))
        self.assertNotEqual(self.origin_main(), before, self.msg(out))


# --------------------------------------------------------------------- AC-2

class PinUpdateMainCiTest(MainCiSandbox):
    """AC-2: `pin-update <sha>` сверяет CI коммита по проверкам первой
    родительской линии; `pin --to` CI не сверяет."""

    def green_canary(self, sha: str) -> None:
        store.insert_canary_run(
            self.conn, "20261002T000000Z", "t", "01AAA", steps=1,
            cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha=sha, verdict="green")

    def assert_refused(self, sha: str, ok: bool, out: str, pin: str) -> None:
        self.assertFalse(ok, self.msg(f"pin-update {sha[:8]} не отказал: {out}"))
        self.assertEqual(self.head(), pin,
                         self.msg(f"отказ сдвинул пин: {out}"))

    def test_ac2_red_check_refuses_naming_check_and_commit(self):
        """Целевой коммит — код с упавшей проверкой кода, канарейка на нём
        зелёная.

        Отказ называет упавшую проверку и коммит; пин не сдвинут.

        Ловит мутацию: `pin-update` сверяет только канарейку (CI коммита
        не спрашивается) — пин уезжает на коммит с красным CI main.
        """
        pin = self.head()
        red = self.push_to_origin(self.red())
        self.green_canary(red)

        ok, out = self.cli("pin-update", red)

        self.assert_refused(red, ok, out, pin)
        self.assertIn(self.code_check, out, self.msg(out))
        self.assertTrue(names_commit(out, red), self.msg(out))

    def test_ac2_skipped_check_takes_result_from_earlier_commit(self):
        """Поверх кода с упавшей проверкой — 1–3 документных коммита, где
        проверка кода пропущена; целевой — последний документный.

        Отказ называет упавшую проверку и коммит, на котором она упала
        (не документный целевой).

        Ловит мутацию: цвет CI считается по одной голове, пропуск
        проверки читается зелёным — первый же документный коммит
        маскирует красный код и пин уезжает.
        """
        pin = self.head()
        red = self.push_to_origin(self.red())
        target = red
        for _ in range(self.rng.randint(1, 3)):
            target = self.push_to_origin(self.doc_only(), doc=True)
        self.green_canary(target)

        ok, out = self.cli("pin-update", target)

        self.assert_refused(target, ok, out, pin)
        self.assertIn(self.code_check, out, self.msg(out))
        self.assertTrue(names_commit(out, red),
                        self.msg(f"отказ не называет коммит {red[:8]}: {out}"))

    def test_ac2_only_first_parent_line_counts(self):
        """origin/main: зелёный коммит, затем merge-коммит ветки, чей
        собственный (более поздний) коммит уронил проверку кода; на
        merge-коммите проверка кода пропущена.

        По первой родительской линии проверка кода берётся с зелёного
        коммита — `pin-update` на merge-коммит проходит.

        Ловит мутацию: история обходится без `--first-parent` — первым
        с исполненной проверкой кода оказывается коммит влитой ветки, и
        исправный пин получает отказ.
        """
        self.hgit("pull", "-q", "--ff-only", "origin", config.MAIN_BRANCH)
        first = self.push_to_origin(self.green(),
                                    date="2026-10-01T10:00:00+00:00")
        self.hgit("checkout", "-q", "-b", "vetka", first)
        (self.helper / "vetka.py").write_text("X = 1\n", encoding="utf-8")
        self.hgit("add", "vetka.py")
        with mock.patch.dict(os.environ, {
                "GIT_COMMITTER_DATE": "2026-10-01T11:00:00+00:00",
                "GIT_AUTHOR_DATE": "2026-10-01T11:00:00+00:00"}):
            self.hgit("commit", "-q", "-m", "коммит ветки")
        side = self.hgit("rev-parse", "HEAD").strip()
        self.set_checks(side, self.red())
        self.hgit("checkout", "-q", config.MAIN_BRANCH)
        with mock.patch.dict(os.environ, {
                "GIT_COMMITTER_DATE": "2026-10-01T12:00:00+00:00",
                "GIT_AUTHOR_DATE": "2026-10-01T12:00:00+00:00"}):
            self.hgit("merge", "-q", "--no-ff", "-m", "влита ветка", "vetka")
        merged = self.hgit("rev-parse", "HEAD").strip()
        self.hgit("push", "-q", "origin", f"HEAD:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin")
        self.set_checks(merged, self.doc_only())
        self.green_canary(merged)

        ok, out = self.cli("pin-update", merged)

        self.assertTrue(ok, self.msg(f"pin-update отказал: {out}"))
        self.assertEqual(self.head(), merged, self.msg(out))

    def test_ac2_running_check_is_not_confirmed(self):
        """Целевой коммит — проверка кода ещё идёт.

        Именованный отказ «CI не подтверждён»; пин не сдвинут.

        Ловит мутацию: незавершённая проверка не считается вовсе (как
        пропущенная) — берётся зелёный результат более раннего коммита, и
        пин уезжает на коммит, чей CI ещё не завершён.
        """
        pin = self.head()
        target = self.push_to_origin(self.code_running())
        self.green_canary(target)

        ok, out = self.cli("pin-update", target)

        self.assert_refused(target, ok, out, pin)
        self.assertIn("CI не подтверждён", out, self.msg(out))

    def test_ac2_gh_unavailable_is_not_confirmed(self):
        """`gh` не отвечает (ненулевой код на любой вызов).

        Именованный отказ «CI не подтверждён»; пин не сдвинут.

        Ловит мутацию: сбой `gh` проглатывается как «упавших проверок
        нет» — пин уезжает без подтверждённого CI.
        """
        pin = self.head()
        target = self.push_to_origin(self.green())
        self.green_canary(target)
        self.set_gh_unavailable()

        ok, out = self.cli("pin-update", target)

        self.assert_refused(target, ok, out, pin)
        self.assertIn("CI не подтверждён", out, self.msg(out))

    def test_ac2_green_ci_and_canary_moves_pin(self):
        """Целевой коммит — документный поверх зелёного кода (проверка
        кода на нём пропущена), канарейка зелёная.

        `pin-update` проходит: пин на целевом коммите.

        Ловит мутацию: пропущенная проверка читается как незавершённая
        либо как упавшая — `pin-update` отказывает на документном коммите
        с зелёным кодом под ним.
        """
        self.push_to_origin(self.green())
        target = self.push_to_origin(self.doc_only(), doc=True)
        self.green_canary(target)

        ok, out = self.cli("pin-update", target)

        self.assertTrue(ok, self.msg(f"pin-update отказал: {out}"))
        self.assertEqual(self.head(), target, self.msg(out))

    def test_ac2_pin_to_does_not_check_ci(self):
        """Пин стоит на коммите с красным CI; `gh` либо недоступен, либо
        красен по всей линии.

        `pin --to <предок>` проходит: пин на предке.

        Ловит мутацию: сверку CI добавили и в аварийный откат — `pin
        --to` отказывает именно тогда, когда откат нужен.
        """
        ancestor = self.head()
        red = self.push_to_origin(self.red())
        self.git("merge", "-q", "--ff-only", red)
        if self.rng.random() < 0.5:
            self.set_gh_unavailable()
        else:
            self.set_checks(ancestor, self.red())

        ok, out = self.cli("pin", "--to", ancestor)

        self.assertTrue(ok, self.msg(f"pin --to отказал: {out}"))
        self.assertEqual(self.head(), ancestor, self.msg(out))


# --------------------------------------------------------------------- AC-3

class DoctorMainCiLineTest(MainCiSandbox):
    """AC-3: строка `doctor` о цвете CI main от головы origin/main."""

    def red_main(self) -> tuple[str, str]:
        """origin/main красный: код с упавшей проверкой, поверх — 0–2
        документных коммита. (коммит падения, имя строки doctor)."""
        red = self.push_to_origin(self.red())
        for _ in range(self.rng.randint(0, 2)):
            self.push_to_origin(self.doc_only(), doc=True)
        checks = self.doctor_checks()
        lines = [c for c in checks if c.status == "fail"
                 and self.code_check in c.detail and names_commit(c.detail, red)]
        self.assertTrue(lines, self.msg(
            f"нет строки fail о CI main с коммитом {red[:8]} и проверкой "
            f"{self.code_check}: {[(c.name, c.status, c.detail) for c in checks]}"))
        return red, lines[0].name

    def line(self, name: str):
        found = [c for c in self.doctor_checks() if c.name == name]
        self.assertTrue(found, self.msg(f"строки {name} нет"))
        return found[0]

    def test_ac3_red_main_line_is_fail_with_commit_and_check(self):
        """origin/main: код с упавшей проверкой, затем 0–2 документных
        коммита.

        Строка `doctor` о CI main — `fail`, называет коммит падения и
        упавшую проверку.

        Ловит мутацию: строки о CI main в `doctor` нет либо цвет берётся
        с одной головы — после документного коммита строка `ok`.
        """
        self.red_main()

    def test_ac3_green_main_line_is_ok(self):
        """Тот же origin/main, затем зелёный коммит кода поверх.

        Строка о CI main — `ok`.

        Ловит мутацию: строка застревает на `fail` после починки main
        (берётся первый упавший результат по всей линии, а не последний
        исполненный).
        """
        _red, name = self.red_main()
        self.push_to_origin(self.green())

        self.assertEqual(self.line(name).status, "ok", self.msg(name))

    def test_ac3_running_or_unavailable_gh_line_is_warn(self):
        """Тот же origin/main, затем коммит кода, чья проверка кода ещё
        идёт; затем `gh` недоступен.

        Строка о CI main — `warn` в обоих случаях.

        Ловит мутацию: идущая проверка или молчащий `gh` дают `ok` (нет
        упавших — значит зелёный) либо `fail`.
        """
        _red, name = self.red_main()
        self.push_to_origin(self.code_running())
        self.assertEqual(self.line(name).status, "warn",
                         self.msg(f"{name}: проверка ещё идёт"))

        self.push_to_origin(self.green())
        self.set_gh_unavailable()
        self.assertEqual(self.line(name).status, "warn",
                         self.msg(f"{name}: gh недоступен"))


# --------------------------------------------------------------------- AC-4

class MergeWaitsForMainCiTest(MergeSandbox):
    """AC-4: после push мержа `approve` ждёт CI новой головы main."""

    def main_records(self, task: dict, new_head: str) -> list:
        """Записи журнала задачи о CI main (называют main или новую
        голову)."""
        return [r for r in self.journal_text(task)
                if config.MAIN_BRANCH in r or names_commit(r, new_head)]

    def test_ac4_green_after_running_is_reported_green(self):
        """CI новой головы main первые 1–3 опроса ещё идёт, затем зелёный.

        Голова main опрашивалась; в журнале задачи и в выводе — зелёный
        исход CI main.

        Ловит мутацию: CI новой головы main не ждут (или ждут CI ветки
        задачи) — опроса новой головы нет, зелёного итога main в журнале
        и выводе нет.
        """
        self.set_default(self.green(), pending_polls=self.rng.randint(1, 3))
        task = self.make_task()

        ok, out = self.cli("approve", task["id"])
        new_head = self.origin_main()

        self.assertEqual(self.state_of(task), "done", self.msg(out))
        polled = [c for c in self.gh_calls()
                  if names_commit(" ".join(c), new_head) and "check-runs" in " ".join(c)]
        self.assertTrue(polled, self.msg(f"CI головы {new_head[:8]} не опрошен"))

        def green(text):
            return ("зелён" in text and "не зелён" not in text
                    and "красн" not in text)
        records = [r for r in self.main_records(task, new_head) if green(r)]
        self.assertTrue(records, self.msg(
            f"нет записи журнала о зелёном CI main: {self.journal_text(task)}"))
        self.assertTrue([ln for ln in out.splitlines() if green(ln) and (
            config.MAIN_BRANCH in ln or names_commit(ln, new_head))],
            self.msg(f"нет строки вывода о зелёном CI main: {out}"))

    def test_ac4_red_is_reported_with_failed_checks(self):
        """CI новой головы main завершился с упавшей проверкой кода.

        В журнале задачи и в выводе — красный исход CI main с именем
        упавшей проверки.

        Ловит мутацию: исход CI main не пишется либо пишется без имён
        упавших проверок — записи с именем проверки нет.
        """
        self.set_default(self.red())
        task = self.make_task()

        ok, out = self.cli("approve", task["id"])
        new_head = self.origin_main()

        def red(text):
            return self.code_check in text and ("красн" in text
                                                or "не зелён" in text)
        self.assertTrue([r for r in self.main_records(task, new_head) if red(r)],
                        self.msg(f"нет записи о красном CI main: "
                                 f"{self.journal_text(task)}"))
        self.assertTrue([ln for ln in out.splitlines() if red(ln)],
                        self.msg(f"нет строки вывода о красном CI main: {out}"))

    def test_ac4_unfinished_ci_is_reported_after_15_to_20_minutes(self):
        """CI новой головы main не завершается никогда.

        Ожидание кончается исходом «не дождался» — в журнале задачи и в
        выводе; по подставным часам ожидание длилось от 15 до 20 минут
        (с точностью до одной паузы опроса), то есть не потолок
        `MERGE_GATE_CI_WAIT_CEILING_SEC`.

        Ловит мутацию: предел ожидания взят из
        `MERGE_GATE_CI_WAIT_CEILING_SEC` (час) либо ожидание не ограничено
        — исход наступает позже 20 минут или не наступает вовсе.
        """
        self.set_default(self.green(), pending_polls=10 ** 9)
        task = self.make_task()

        ok, out = self.cli("approve", task["id"])
        new_head = self.origin_main()
        elapsed = self.clock

        self.assertTrue([r for r in self.main_records(task, new_head)
                         if "не дождал" in r],
                        self.msg(f"нет записи «не дождался»: "
                                 f"{self.journal_text(task)}"))
        self.assertIn("не дождал", out, self.msg(out))
        slack = max(config.VERIFYING_POLL_INTERVAL_SEC,
                    config.MERGE_GATE_CI_WAIT_POLL_SEC)
        self.assertGreaterEqual(elapsed, WAIT_MIN_SEC, self.msg(f"{elapsed} с"))
        self.assertLessEqual(elapsed, WAIT_MAX_SEC + slack, self.msg(f"{elapsed} с"))

    def test_ac4_wait_limit_constant_lives_in_merge_gate_module(self):
        """Предел ожидания CI main — новая именованная константа модуля
        `orchestrator/fsm_merge_gate.py` (присваивание на уровне модуля),
        которой нет в `config`, со значением от 15 до 20 минут.

        Ловит мутацию: предел объявлен в `orchestrator/config.py` и
        импортирован (либо переиспользован
        `MERGE_GATE_CI_WAIT_CEILING_SEC`) — в модуле гейта мержа своей
        константы в диапазоне нет.
        """
        tree = ast.parse(inspect.getsource(fsm_merge_gate))
        assigned = {target.id for node in tree.body
                    if isinstance(node, (ast.Assign, ast.AnnAssign))
                    for target in (node.targets if isinstance(node, ast.Assign)
                                   else [node.target])
                    if isinstance(target, ast.Name)}

        def in_range(name, value) -> bool:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False
            if WAIT_MIN_SEC <= value <= WAIT_MAX_SEC:
                return True
            return "MIN" in name and 15 <= value <= 20

        found = [name for name in assigned
                 if name.isupper() and not hasattr(config, name)
                 and name != "MERGE_GATE_CI_WAIT_CEILING_SEC"
                 and in_range(name, getattr(fsm_merge_gate, name, None))]
        self.assertTrue(found, "в orchestrator/fsm_merge_gate.py нет своей "
                               "константы предела ожидания 15–20 минут")


# --------------------------------------------------------------------- AC-5

class NextMergeRefusedOnRedMainTest(MergeSandbox):
    """AC-5: красный CI main отказывает следующему `approve` на
    `merge_gate`; `--fixes-main` снимает эту сверку для названной задачи."""

    def assert_red_main_refusal(self, task: dict, red: str, ok: bool,
                                out: str, before: str) -> None:
        self.assertFalse(ok, self.msg(f"мерж при красном main не отказал: {out}"))
        self.assertIn("main красный с", out, self.msg(out))
        self.assertIn("сначала починить main", out, self.msg(out))
        self.assertTrue(names_commit(out, red),
                        self.msg(f"отказ не называет коммит {red[:8]}: {out}"))
        self.assertEqual(self.state_of(task), "merge_gate", self.msg(out))
        self.assertEqual(self.origin_main(), before, self.msg(out))

    def test_ac5_red_main_refuses_next_merge(self):
        """origin/main — коммит кода с упавшей проверкой; задача на
        `merge_gate` свежа относительно него, её CI зелёный.

        `approve` отказывает текстом «main красный с <коммит> — сначала
        починить main», задача на `merge_gate`, origin/main не сдвинут.

        Ловит мутацию: сверки цвета CI main перед мержем нет — задача
        мержится поверх красного main.
        """
        red = self.push_to_origin(self.red())
        task = self.make_task()
        before = self.origin_main()

        ok, out = self.cli("approve", task["id"])

        self.assert_red_main_refusal(task, red, ok, out, before)

    def test_ac5_fixes_main_lifts_the_check_only_for_named_task(self):
        """Тот же красный main; `approve <id> <sha> --fixes-main
        "<основание>"` первой задачи, затем `approve` второй без флага
        (CI новой головы main тоже красный).

        Первая задача смержена, основание в её журнале; вторая получает
        тот же отказ «main красный с … — сначала починить main».

        Ловит мутацию: флаг не снимает сверку (первая задача отказана)
        либо снимает её не только для названной задачи (исключение
        запоминается глобально — вторая мержится поверх красного main).
        """
        self.push_to_origin(self.red())
        self.set_default(self.red())
        fixer = self.make_task()
        reason = f"чиню main: {self.rng.choice(('README', 'guard', 'тесты'))} " \
                 f"#{self.rng.randrange(10 ** 6)}"

        ok, out = self.cli("approve", fixer["id"], fixer["head"],
                           "--fixes-main", reason)

        self.assertEqual(self.state_of(fixer), "done", self.msg(out))
        self.assertTrue([r for r in self.journal_text(fixer) if reason in r],
                        self.msg(f"основания нет в журнале: "
                                 f"{self.journal_text(fixer)}"))

        other = self.make_task()
        before = self.origin_main()
        ok, out = self.cli("approve", other["id"])

        self.assertFalse(ok, self.msg(f"вторая задача смержена: {out}"))
        self.assertIn("сначала починить main", out, self.msg(out))
        self.assertEqual(self.state_of(other), "merge_gate", self.msg(out))
        self.assertEqual(self.origin_main(), before, self.msg(out))


# --------------------------------------------------------------------- AC-6

class RedMergeThenDocCommitTest(MergeSandbox):
    """AC-6: сценарий «красный мерж, затем документный коммит»."""

    def test_ac6_red_merge_then_doc_commit_keeps_main_red(self):
        """Мерж задачи, после которого CI новой головы main красный
        (проверка кода упала); поверх — 1–2 документных коммита, где
        проверка кода пропущена.

        Следующий `approve` отказывает «main красный с <голова мержа>»,
        `pin-update` на документную голову отказывает с упавшей проверкой
        и коммитом мержа, строка `doctor` о CI main — `fail` с тем же
        коммитом.

        Ловит мутацию: цвет CI main берётся с одной головы (пропуск =
        зелёный) — документный коммит маскирует красный мерж, следующий
        мерж и `pin-update` проходят, `doctor` молчит.
        """
        self.set_default(self.red())
        first = self.make_task()
        self.cli("approve", first["id"])
        self.assertEqual(self.state_of(first), "done", self.msg("первый мерж"))
        red = self.origin_main()
        # Голова мержа закрепляется за красными проверками явно: дальше
        # проверки «по умолчанию» (для головы следующего мержа) зелёные.
        self.set_checks(red, self.red())
        doc_head = red
        for _ in range(self.rng.randint(1, 2)):
            doc_head = self.push_to_origin(self.doc_only(), doc=True)
        self.set_default(self.green())

        nxt = self.make_task()
        ok, out = self.cli("approve", nxt["id"])
        self.assertFalse(ok, self.msg(f"следующий мерж прошёл: {out}"))
        self.assertIn("main красный с", out, self.msg(out))
        self.assertTrue(names_commit(out, red), self.msg(out))
        self.assertEqual(self.state_of(nxt), "merge_gate", self.msg(out))
        self.assertEqual(self.origin_main(), doc_head, self.msg(out))

        pin = self.head()
        store.insert_canary_run(
            self.conn, "20261002T000000Z", "t", "01AAA", steps=1,
            cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha=doc_head, verdict="green")
        ok, out = self.cli("pin-update", doc_head)
        self.assertFalse(ok, self.msg(f"pin-update прошёл: {out}"))
        self.assertIn(self.code_check, out, self.msg(out))
        self.assertTrue(names_commit(out, red), self.msg(out))
        self.assertEqual(self.head(), pin, self.msg(out))

        checks = self.doctor_checks()
        self.assertTrue([c for c in checks if c.status == "fail"
                         and self.code_check in c.detail
                         and names_commit(c.detail, red)],
                        self.msg(f"нет строки doctor fail о CI main: "
                                 f"{[(c.name, c.status, c.detail) for c in checks]}"))


if __name__ == "__main__":
    unittest.main()
