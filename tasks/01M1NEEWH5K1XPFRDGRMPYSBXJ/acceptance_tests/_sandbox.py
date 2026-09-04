"""Общая песочница приёмочных тестов «Канарейка v2» (не test_*.py — не
подхватывается `unittest discover` напрямую, только импортом из
test_ac*.py). Расширяет приём `tasks/T065/acceptance_tests/_sandbox.py`
(v1 канарейки): настоящий git-репозиторий пульта, `SmartAgent` —
подмена `runner.cmd_run`, которая коммитит в ветку задачи ровно тот
артефакт, которого ждёт следующий `fsm.cmd_advance`, по ТЕКУЩЕМУ
состоянию задачи (см. докстринг `SmartAgent` там же для обоснования
приёма) — тот же приём, тот же список причин, здесь не повторяется.

Три расширения под v2, которых не было у v1:

1. Пул шаблонов ВНЕ корня пульта (`~/.artel-canary`, требование 1
   SPEC) — `Path.home()` подменена (и переменная окружения HOME — на
   случай, если реализация вместо `Path.home()` читает `os.environ`)
   на ОТДЕЛЬНЫЙ временный каталог, не совпадающий с `self.root`:
   `write_pool_templates` сеет туда `*.md`.

2. Настоящий `origin`-remote пульта (bare-репозиторий) — нужен
   `pin.cmd_pin_update`/будущему `pin --to <sha>` (оба дёргают
   настоящий `git fetch origin`/`git merge --ff-only`, ADR-0013 ч.3):
   заглушкой `gitcmd.git` эту логику не проверить (прецедент T051,
   «мок душил git» — `skills/test-authoring.md`), только настоящим
   git. `advance_origin_main` двигает `origin` вперёд отдельным
   рабочим клоном, не трогая `self.root`, — имитирует «main пульта
   ушёл дальше» независимо от пина запущенной версии.

3. `_EphemeralDirTracker` — перехватывает `tempfile.mkdtemp` и
   `shutil.rmtree` (оба — единственные стандартные способы завести и
   убрать временный каталог в CPython; `tempfile.TemporaryDirectory`
   изнутри зовёт ИМЕННО их через атрибут модуля, не через `from
   shutil import rmtree`, так что патч ловит и этот путь) — снимает
   снимок каталога ПЕРЕД его удалением (`.git`, sqlite-файлы,
   `origin`-remote), не полагаясь на то, каким именно из трёх приёмов
   («создаём и подчищаем сами», `TemporaryDirectory` как контекстный
   менеджер) реализация заведёт эфемерный клон — SPEC называет только
   наблюдаемые свойства клона (AC-2, AC-4), не механизм.

Роль `analyst` (SPEC требование 5 из TZ) и полный маршрут
tests_writing — вне охвата этой песочницы: как и в T065,
синтетические ТЗ этого файла пишутся `schema_version: 1` (без
AC-разметки), `guard.requires_ac_markup` на них ложно, цикл
заканчивается в `in_dev` сразу после `spec_gate` — лишний агентский
шаг только раздувал бы песочницу, а маршрут analyst/эскалация читаемы
и без него (AC-6/AC-8 эскалируют прямо из `spec_writing`, см.
`SmartAgent.escalate_titles` ниже).
"""
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (artel, catalog, config, fixation,  # noqa: E402
                          gitcmd, runner, store)

SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: канареечная задача v2

## Контекст

синтетическое ТЗ канарейки v2, неподвижный вход

## Требования

1. сделать маленькую синтетическую правку

## Критерии приёмки

1. правка сделана

## Не входит
"""

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: канареечная задача v2

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 1
---

# REVIEW: канареечная задача v2

## Соответствие SPEC

## Замечания

## Вердикт
"""

# Батч вопросов, которым `SmartAgent` эскалирует задачу вместо готового
# SPEC.md — тот же документ и тот же приём, что `tests/test_answer.py::
# _ArtifactBranchAnswerTest._escalate()` сеет напрямую: здесь тот же
# эффект достигается ЧЕРЕЗ агентский шаг (коммит `runner.cmd_run`), не
# прямой сшивкой в обход `_drive_task`-эквивалента — так эскалация
# происходит ровно там, где её должна поймать сама механика прогона
# (AC-6), а не искусственно подготовленной снаружи.
QUESTIONS_TEXT = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: батч

## Вопросы

1. **Какой вариант выбрать?** — варианты: A) первый; B) второй — дефолт: A.
"""

# Синтетический текст ответа Оператора, которым механика прогона обязана
# закрыть эскалацию сама (AC-6, заглушка): узнаваемый маркер в тексте —
# чтобы тест мог отличить «свой» синтетический ответ от случайного.
SYNTHETIC_ANSWER_MARKER = "CANARY-V2-SYNTHETIC-ANSWER"

# Подстрока в title заведённой задачи (= `f.stem` исходного файла пула,
# `catalog.cmd_new(f.stem, tz_path=..., canary=True)` — тем же приёмом,
# что и v1 `canary.cmd_canary`, SPEC v2 — «переработка v1», не новый
# способ заводить задачу), по которой `SmartAgent` решает эскалировать
# ли эту задачу вместо обычного happy path. Решение ИМЕННО по имени
# файла шаблона, не по машиночитаемому маркеру AC-8 внутри тела ТЗ —
# два независимых сигнала специально: AC-8 проверяет СОВПАДЕНИЕ
# заявленного ожидания с фактическим исходом, а для этого нужно уметь
# конструировать оба сочетания (ожидали эскалацию — не случилась,
# и наоборот) независимо от текста маркера.
ESCALATE_TITLE_MARKER = "triggers-escalation"

# Машиночитаемый маркер «ожидается эскалация» (требование 8/AC-8) —
# HTML-комментарий в теле шаблона: `catalog.cmd_new`/`_tz_document`
# оборачивает СЫРОЙ текст файла пула СВОИМ фронтматтером (`task/type/
# author_role/status/schema_version`) и кладёт исходный текст ЦЕЛИКОМ
# телом документа под `# ТЗ: {{title}}` (`orchestrator/catalog.py::
# _tz_document`) — маркер во фронтматтере САМОГО шаблона до `cmd_new`
# не доедет как фронтматтер итогового TZ.md, только как текст тела;
# HTML-комментарий читаем и парсибелен, и невидим при рендере markdown
# — минимальное по риску соглашение, раз SPEC формат маркера не называет
# (содержание/разметка шаблонов — вне объёма этой задачи, «Не входит»).
MARK_EXPECT_ESCALATION_YES = "<!-- canary-expect-escalation: yes -->"
MARK_EXPECT_ESCALATION_NO = "<!-- canary-expect-escalation: no -->"


class SmartAgent:
    """Подмена `runner.cmd_run`, см. докстринг модуля выше и оригинал
    `tasks/T065/acceptance_tests/_sandbox.py::SmartAgent` — тот же приём,
    дополненный веткой эскалации (AC-6/AC-8)."""

    def __init__(self):
        self.calls: list[str] = []
        self.extra_review_rounds: dict[str, int] = {}
        # По ЗАГОЛОВКУ задачи (= имени файла шаблона пула, стабильному
        # МЕЖДУ прогонами), не по task_id (свежий ULID каждый прогон,
        # AC-9: баланс между прогонами нужно раздувать по СТАБИЛЬНОЙ
        # идентичности шаблона, не по одноразовому id задачи, которого
        # до заведения задачи ещё не существует).
        self.extra_review_rounds_by_title: dict[str, int] = {}
        self.extra_review_rounds_default = 0
        self._review_rounds_done: dict[str, int] = {}
        self._escalated_once: set[str] = set()
        self._nonce = 0

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        self.calls.append(task_id)
        conn = store.db()
        t = store.get_task(conn, task_id)
        state = t["state"]
        branch = t["branch"]
        title = t["title"] or ""

        if state == "spec_writing":
            if (ESCALATE_TITLE_MARKER in title
                    and task_id not in self._escalated_once):
                self._escalated_once.add(task_id)
                self._commit(task_id, branch, "QUESTIONS.md",
                            QUESTIONS_TEXT.format(task=task_id))
                return
            self._commit(task_id, branch, "SPEC.md",
                        SPEC_READY.format(task=task_id))
        elif state == "in_dev":
            self._commit(task_id, branch, "PLAN.md",
                        PLAN_READY.format(task=task_id))
        elif state == "review":
            done = self._review_rounds_done.get(task_id, 0)
            if task_id in self.extra_review_rounds:
                need = self.extra_review_rounds[task_id]
            elif title in self.extra_review_rounds_by_title:
                need = self.extra_review_rounds_by_title[title]
            else:
                need = self.extra_review_rounds_default
            iteration = t["reviewed_iter"] + 1
            if done < need:
                self._review_rounds_done[task_id] = done + 1
                status = "changes_requested"
            else:
                status = "approved"
            self._commit(task_id, branch, "REVIEW.md",
                        REVIEW_MD.format(task=task_id, status=status,
                                         iteration=iteration))
        # Прочие агентские состояния (tests_writing и т.п.) вне охвата
        # песочницы (см. докстринг модуля).

    def _commit(self, task_id: str, branch: str, name: str, text: str) -> None:
        self._nonce += 1
        text = f"{text}\n<!-- agent stub, вызов {self._nonce} -->\n"
        wt_path = config.WORKTREES / task_id
        path = wt_path / "tasks" / task_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", f"tasks/{task_id}/{name}"], cwd=wt_path,
                       check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "-c", f"user.name={fixation.FIXATION_AUTHOR_NAME}",
             "-c", f"user.email={fixation.FIXATION_AUTHOR_EMAIL}",
             "commit", "-q", "-m", f"{task_id}: {name} (agent stub #{self._nonce})"],
            cwd=wt_path, check=True, capture_output=True, text=True)


def has_canary_mark(text: str) -> bool:
    """Несёт ли текст пометку canary (латиница `canary` или «канаре*») —
    тот же приём и то же обоснование, что и в T065 `_sandbox.py`."""
    lowered = text.lower()
    return "canary" in lowered or "канаре" in lowered


def task_metrics(data, task_id: str):
    """Запись метрик задачи из разобранного JSON/dict-отчёта: либо прямо
    на верхнем уровне, либо под обёрткой `data["tasks"]` — тот же приём,
    что T065 `_sandbox.py::task_metrics`."""
    if not isinstance(data, dict):
        return None
    if task_id in data:
        return data[task_id]
    tasks = data.get("tasks")
    if isinstance(tasks, dict) and task_id in tasks:
        return tasks[task_id]
    return None


def _snapshot_dir(p: Path, deep: bool = False) -> dict:
    """Снимок каталога ПЕРЕД его удалением — не полагается на то, каким
    приёмом реализация завела эфемерный клон (см. докстринг модуля,
    п.3): есть ли `.git`, куда смотрит его `origin` (если есть), есть ли
    файлы БД внутри.

    `deep=True` (AC-6/AC-8: нужно увидеть ИСХОД задачи и коммиты
    ANSWER-*.md ДО того, как клон физически исчезнет, — снаружи клона
    после его удаления смотреть уже не на что, AC-3/AC-4) — открывает
    найденный файл БД клона (sqlite3, только на чтение) и достаёт
    `tasks`/`steps`, плюс список файлов `tasks/<id>/ANSWER-*.md`,
    когда-либо закоммиченных в ЛЮБУЮ ветку клона (`git log --all
    --name-only` — артефактная ветка внутри клона может называться
    как угодно, разбор по буквальному имени ветки был бы лишней
    привязкой к недокументированному соглашению)."""
    if not p.exists():
        return {"existed": False}
    entries = sorted(e.name for e in p.iterdir()) if p.is_dir() else []
    git_dir = p / ".git"
    has_git = git_dir.exists()
    origin_url = None
    if has_git:
        res = subprocess.run(["git", "remote", "get-url", "origin"], cwd=p,
                             capture_output=True, text=True)
        if res.returncode == 0:
            origin_url = res.stdout.strip()
    db_files = [str(f) for f in p.rglob("*.db")] if p.is_dir() else []
    snap = {"existed": True, "entries": entries, "has_git": has_git,
            "origin_url": origin_url, "db_files": db_files}
    if deep:
        snap["tasks"] = []
        snap["steps_by_task"] = {}
        for db_path in db_files:
            try:
                import sqlite3
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                tnames = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if "tasks" in tnames:
                    snap["tasks"].extend(
                        dict(r) for r in conn.execute("SELECT * FROM tasks"))
                if "steps" in tnames and "tasks" in tnames:
                    for row in snap["tasks"]:
                        tid = row["id"]
                        snap["steps_by_task"][tid] = [
                            dict(r) for r in conn.execute(
                                "SELECT * FROM steps WHERE task_id=? "
                                "ORDER BY id", (tid,))]
                conn.close()
            except Exception:  # noqa: BLE001 — снимок best-effort
                pass
        answer_files = set()
        if has_git:
            log = subprocess.run(
                ["git", "log", "--all", "--name-only", "--pretty=format:"],
                cwd=p, capture_output=True, text=True)
            if log.returncode == 0:
                for line in log.stdout.splitlines():
                    if "/ANSWER-" in line and line.endswith(".md"):
                        answer_files.add(line.strip())
        snap["answer_files"] = sorted(answer_files)
    return snap


class _EphemeralDirTracker:
    """Перехватывает `tempfile.mkdtemp`/`shutil.rmtree` за время своего
    `start()`-`stop()` окна и копит по каждому убранному каталогу снимок
    (см. `_snapshot_dir`), снятый ДО удаления."""

    def __init__(self):
        self.created: list[Path] = []
        self.snapshots: dict[str, dict] = {}
        self._patchers: list = []

    def start(self, test: unittest.TestCase, deep: bool = False) -> None:
        real_mkdtemp = tempfile.mkdtemp

        def spy_mkdtemp(*a, **kw):
            p = real_mkdtemp(*a, **kw)
            self.created.append(Path(p))
            return p

        real_rmtree = shutil.rmtree

        def spy_rmtree(path, *a, **kw):
            p = Path(path)
            key = str(p)
            if key not in self.snapshots:
                self.snapshots[key] = _snapshot_dir(p, deep=deep)
            return real_rmtree(path, *a, **kw)

        p1 = mock.patch("tempfile.mkdtemp", side_effect=spy_mkdtemp)
        p2 = mock.patch("shutil.rmtree", side_effect=spy_rmtree)
        p1.start()
        p2.start()
        self._patchers = [p1, p2]
        test.addCleanup(self.stop)

    def stop(self) -> None:
        for p in self._patchers:
            p.stop()
        self._patchers = []

    def git_like_snapshots(self) -> list[dict]:
        """Только снимки каталогов, похожих на клон пульта (несут
        `.git`) — рассеивает шум чужих временных каталогов (например,
        `tempfile.TemporaryDirectory`, которым в setUp этой же
        песочницы заведён `self.root`, — тот УЖЕ убран к моменту
        сравнения, за пределами окна `start()`-`stop()` конкретного
        теста, см. докстринг модуля)."""
        return [s for s in self.snapshots.values() if s.get("has_git")]


class CanarySandbox(unittest.TestCase):
    """Настоящий git-репозиторий пульта (main) + настоящий `origin`
    (bare-репозиторий) + отдельный от `self.root` каталог пула вне корня
    (`Path.home()` подменена) + настоящие worktree/ветки задач
    (`catalog.cmd_new`) — единственная логическая подмена: агент шага
    (`SmartAgent`)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): на macOS /var — симлинк на /private/var (тот же
        # приём, что tests/test_invariants.py::KillKeepsMainIntactTest).
        self.root = Path(tmp.name).resolve()

        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "artel-tests@example.invalid")
        self._git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        gitignore = REPO_ROOT / ".gitignore"
        if gitignore.exists():
            shutil.copy(gitignore, self.root / ".gitignore")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "init")

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)

        self.agent = SmartAgent()
        agent_patcher = mock.patch.object(runner, "cmd_run", self.agent)
        agent_patcher.start()
        self.addCleanup(agent_patcher.stop)

        # --- пул шаблонов вне корня пульта (требование 1, AC-1) --------
        home_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(home_tmp.cleanup)
        self.fake_home = Path(home_tmp.name).resolve()
        self.pool_dir = self.fake_home / ".artel-canary"
        self.pool_dir.mkdir(parents=True)
        home_patcher = mock.patch.object(Path, "home",
                                         return_value=self.fake_home)
        home_patcher.start()
        self.addCleanup(home_patcher.stop)
        env_patcher = mock.patch.dict("os.environ", {"HOME": str(self.fake_home)})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        # --- настоящий origin (bare) пульта (AC-12, AC-13, AC-14, AC-15) -
        origin_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(origin_tmp.cleanup)
        self.origin_bare = Path(origin_tmp.name).resolve() / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main",
                       str(self.origin_bare)],
                       check=True, capture_output=True, text=True)
        self._git("remote", "add", "origin", str(self.origin_bare))
        self._git("push", "-q", "origin", "main")

    # ------------------------------------------------------------ утилиты

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=self.root, timeout=30,
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res

    def main_sha(self) -> str:
        return self._git("rev-parse", "main").stdout.strip()

    def origin_main_sha(self) -> str:
        res = subprocess.run(["git", "-C", str(self.origin_bare),
                             "rev-parse", "main"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.strip()

    def advance_origin_main(self, n: int = 1) -> str:
        """Двигает `origin` (bare) вперёд на `n` коммитов ОТДЕЛЬНЫМ
        рабочим клоном — не трогая `self.root`/его HEAD (пин запущенной
        версии не обязан следовать за origin автоматически, ADR-0013).
        Возвращает итоговый sha `origin`'ского `main`."""
        work_tmp = tempfile.mkdtemp()
        try:
            subprocess.run(["git", "clone", "-q", str(self.origin_bare), work_tmp],
                           check=True, capture_output=True, text=True)
            subprocess.run(["git", "-C", work_tmp, "config", "user.email",
                           "artel-tests@example.invalid"], check=True,
                           capture_output=True, text=True)
            subprocess.run(["git", "-C", work_tmp, "config", "user.name",
                           "artel tests"], check=True,
                           capture_output=True, text=True)
            for i in range(n):
                marker = Path(work_tmp) / f"advance-{self._nonce_counter()}.txt"
                marker.write_text(f"advance {i}\n", encoding="utf-8")
                subprocess.run(["git", "-C", work_tmp, "add", "-A"], check=True,
                               capture_output=True, text=True)
                subprocess.run(["git", "-C", work_tmp, "commit", "-q", "-m",
                               f"advance origin {i}"], check=True,
                               capture_output=True, text=True)
            subprocess.run(["git", "-C", work_tmp, "push", "-q", "origin", "main"],
                           check=True, capture_output=True, text=True)
        finally:
            shutil.rmtree(work_tmp, ignore_errors=True)
        return self.origin_main_sha()

    _NONCE = [0]

    def _nonce_counter(self) -> int:
        CanarySandbox._NONCE[0] += 1
        return CanarySandbox._NONCE[0]

    @staticmethod
    def capture(fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def write_pool_templates(self, texts: dict) -> Path:
        """`*.md` файлы пула — В ФЕЙКОВОМ HOME (вне `self.root`,
        требование 1: Оператор держит пул вне корня пульта)."""
        for name, text in texts.items():
            (self.pool_dir / name).write_text(text, encoding="utf-8")
        return self.pool_dir

    def run_cli(self, *argv_tail: str) -> str:
        """Настоящий CLI-диспетчер (`orchestrator/artel.py::main`), не
        прямой вызов внутреннего модуля — SPEC называет только команды,
        не модуль/функцию, которая их реализует (решение developer,
        тот же приём, что `tasks/T065/acceptance_tests/_sandbox.py::
        run_canary`). Команды может не быть в таблице до реализации
        задачи — `SystemExit` («Неизвестная команда …») перехватывается
        и попадает в возвращаемый текст: необработанный `SystemExit` —
        не `Exception`, и unittest сам его не ловит, а завершает им ВЕСЬ
        прогон `discover` вместо одного красного теста."""
        argv = ["artel.py", *argv_tail]
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", argv):
            with redirect_stdout(buf):
                try:
                    artel.main()
                except SystemExit as exc:
                    buf.write(f"\n[SystemExit] {exc}\n")
        return buf.getvalue()

    def run_canary_pool(self, k: int, *extra_args: str) -> str:
        """`artel.py canary --k <k>` — прогон пула (требование 1, AC-1):
        каталог ТЗ больше не позиционный аргумент (пул фиксирован,
        `~/.artel-canary`), `--k` — минимальное по риску развитие
        существующего флагового стиля v1 (`--rewrite-baseline`,
        `tasks/T065/SPEC.md`) под новый параметр выборки; SPEC называет
        только поведение (требование 1), не имя флага — developer волен
        назвать иначе, тогда красный тест будет красным по этой же
        причине (команда не узнаёт `--k`), не по опечатке песочницы."""
        return self.run_cli("canary", "--k", str(k), *extra_args)

    def run_pin_update(self, sha: str) -> str:
        return self.run_cli("pin-update", sha)

    def run_pin_rollback(self, sha: str | None = None) -> str:
        """`pin --to <sha>` (ADR-0013 ч.3, буквальная цитата в SPEC,
        требование 14/AC-14) — без явного `<sha>` `--to` идёт БЕЗ
        значения (откат на предыдущий зелёный по журналу канарейки)."""
        if sha is None:
            return self.run_cli("pin", "--to")
        return self.run_cli("pin", "--to", sha)

    def task_ids(self) -> list[str]:
        return [t["id"] for t in store.all_tasks(store.db())]

    def task_row(self, task_id: str):
        return store.get_task(store.db(), task_id)

    def journal(self, task_id: str):
        return store.task_steps(store.db(), task_id)

    def journal_text(self, task_id: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                         for r in self.journal(task_id))

    def sqlite_table_names(self) -> set[str]:
        conn = store.db()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {r["name"] if hasattr(r, "keys") else r[0] for r in rows}

    def artifact_branch_files(self, task_id: str) -> list:
        from orchestrator import artifact_branch
        branch = artifact_branch.branch_name(task_id)
        return gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []

    def artifact_branch_text(self, task_id: str, rel: str) -> str | None:
        from orchestrator import artifact_branch
        branch = artifact_branch.branch_name(task_id)
        text, _reason = gitcmd.show(branch, f"tasks/{task_id}/{rel}")
        return text


if __name__ == "__main__":
    unittest.main()
