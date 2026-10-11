"""Мерж не кладёт в main проекта ни каталог документов задачи, ни её RETRO:
RETRO живёт только в коммите закрытия ссылки документов `refs/artifacts/<id>`
и не беднеет, документы мержащейся задачи проверяются на голове этой ссылки,
провал коммита закрытия на путях мержа и `kill` виден Оператору инцидентом,
читатели, привязанные к main, отвечают по ссылке (ADR-0021 п.4, этап 4).

Группа: долгоживущий

Красен до реализации: мерж накладывает снимок ссылки документов на main (коммит «снимок артефактной ветки поверх merge», каталог задачи в main и у артели, и у внешнего проекта), коммитит в main RETRO задачи и killed-RETRO долгов, RETRO закрытия несёт sha головы пульта и без строки приложений, недоступная ссылка документов мерж не отказывает, провал коммита закрытия инцидента не заводит (а сбой построения RETRO обрывает уборку исключением), `retro.build_done` без `address` пишет адрес `<sha>:<каталог задачи>`, `cleanup.artifacts_in_main` ссылку документов не видит.

Зелёные и до реализации, и после — держат то, что реализация обязана
сохранить, снимая наложение: строки стоимости и счётчиков RETRO закрытия
(AC-2), порядок «merge — приложения — карта» и `guard --all` по дереву с
приложениями (AC-5), отказ мержа по постороннему файлу документов задачи
(AC-9, AC-10, отказ AC-12 — сегодня его даёт проверка наложенного
снимка), «сохранены» исторического каталога и «не сохранены» задачи без
следов (AC-13). Планка провалидирована временным стабом реализации (все
методы зелёные, стаб удалён, не закоммичен).

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): главная копия
пульта, она же клон артели, и bare `origin` рядом. Классам мержа артели с
кодом (`COPY_CODE`) первый коммит несёт копию `orchestrator/` и `scripts/`
репозитория (гейт мержа зовёт `scripts/guard.py` и `scripts/codebase_map.py`
дерева мержа), заглушку карты кодовой базы (её регенерация даёт отдельный
коммит карты) и исторический каталог закрытой задачи с её
`docs/retro/<id>.md` (без каталога задач в дереве гейт `guard --all` не
зовёт). В копию `scripts/guard.py` вставлен зонд: при запуске `--all` он
дописывает в файл, названный окружением, содержимое перечисленных
окружением путей рабочего каталога — так видно, какое дерево видел guard.
Внешний проект — клон с bare `origin` (`tests.sandbox.make_project_repo`).

Задача заводится прямо на `merge_gate`: кодовая ветка от origin/main
(опубликована), ссылка документов — коммит вспомогательного репозитория,
отправленный и в репозиторий задачи, и в его `origin`, затем фиксация
(`store.record_fixation`). Команды — диспетчером `artel.main()` тем же
argv, что набирает Оператор (`approve`, `kill`). GitHub изображает
подставной `gh` в начале `PATH` (все проверки любого коммита зелёные),
часы подставные — ожидание CI без реального ожидания.

Провал коммита закрытия создаётся на наблюдаемой границе: сразу после
перехода задачи в `done`/`killed` (обёртка над `store.set_state`, после
настоящего перехода) ссылка документов удаляется, сдвигается коммитом
мимо пульта либо запирается файлом `<ссылка>.lock` (git отказывает в
`update-ref`); сбой построения RETRO — подмена `retro.build_done`/
`retro.build_killed`, бросающая исключение. «Incident-алерт с target этой
задачи» — открытый `incident`, заведённый за этот прогон, с `target`,
равным проекту задачи (так заводят инциденты задачи прочие узлы мержа),
либо её id; песочница этих сценариев без кода пульта в дереве мержа, и
других источников инцидентов в ней нет.

Идентификаторы задач, число тестов планки и пометок, стоимость, счётчики,
имена посторонних файлов, пути приложений и состояние перед `kill`
выбираются случайно; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import json
import os
import random
import re
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (alerts, artel, catalog, cleanup, config,
                          fsm_postmerge, retro, store)
from scripts import guard
from tests.sandbox import (RealGitSandbox, capture, make_project_repo,
                           patch_pult_sleep)

REPO = Path(__file__).resolve().parent.parent
TASKS_DIR = config.TASKS.name
SLED = "sled"
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
MAP_REL = "docs/codebase-map.md"
MAP_PLACEHOLDER = ("---\nbuilt_at_sha: " + "0" * 40 + "\n---\n\n"
                   "# Карта кодовой базы (заглушка песочницы)\n")
SNAPSHOT_SUBJECT = "снимок артефактной ветки поверх merge"
RETRO_SUBJECT = "RETRO задачи"
DEBT_SUBJECT = "killed-RETRO долга"
DONE_SHA = re.compile(r"^Итог: done, sha ([0-9a-f]{40})$", re.M)

# Подставной `gh`: зелёные проверки на любой коммит, пустые списки прогонов
# и запросов на слияние; прочие вызовы — отказ.
FAKE_GH = r'''
import json, re, sys
args = sys.argv[1:]
joined = " ".join(args)
if args[:1] == ["api"] and "/check-runs" in joined:
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

# Зонд копии `scripts/guard.py`: при `--all` дописывает строку JSON
# {путь: содержимое или null} для путей из окружения, относительно
# рабочего каталога запуска.
GUARD_MAIN = 'if __name__ == "__main__":\n    sys.exit(main())'
GUARD_PROBE = '''
def artel_guard_probe():
    import json as probe_json
    import os as probe_os
    target = probe_os.environ.get("ARTEL_GUARD_PROBE")
    if not target or sys.argv[1:] != ["--all"]:
        return
    rels = [r for r in probe_os.environ.get(
        "ARTEL_GUARD_PROBE_FILES", "").split(":") if r]
    seen = {}
    for rel in rels:
        path = Path(rel)
        seen[rel] = path.read_text(encoding="utf-8") if path.is_file() else None
    with open(target, "a", encoding="utf-8") as fh:
        fh.write(probe_json.dumps(seen, ensure_ascii=False) + "\\n")


if __name__ == "__main__":
    artel_guard_probe()
    sys.exit(main())'''


def plank_text(tests: int, manual: int) -> str:
    """Планка задачи песочницы: `tests` методов и `manual` пометок.
    Метки собираются заменой при сборке строки, чтобы сканер планки пульта
    не принял литералы за тесты и пометки ЭТОГО файла."""
    lines = ['"""Планка задачи песочницы."""']
    lines += [f"# @AC-{90 + k}: manual — проверяется руками."
              for k in range(manual)]
    lines += ["import unittest", "", "", "class Fixture(unittest.TestCase):"]
    for n in range(1, tests + 1):
        lines += [f"    def test_@ac{n}_fixture(self):", "        pass", ""]
    return ("\n".join(lines) + "\n").replace("@ac", "ac").replace("@AC", "AC")


def spec_text(task: str) -> str:
    return (f"---\ntask: {task}\ntype: spec\nauthor_role: analyst\n"
            f"status: ready\nschema_version: 5\nzones: kod/\nbudget_usd: 10\n---\n\n"
            f"# SPEC: задача {task}\n\n"
            f"## Контекст\n\nЗадача песочницы мержа.\n\n## Требования\n\n"
            f"1. Требование.\n\n## Критерии приёмки\n\n@AC-1. Критерий.\n\n"
            f"## Не входит\n\n- Ничего.\n").replace("@AC", "AC")


def plan_text(task: str, appendix: str = "") -> str:
    return (f"---\ntask: {task}\ntype: plan\nauthor_role: developer\n"
            f"status: ready\nschema_version: 1\n---\n\n# PLAN: задача {task}\n\n"
            f"## Подход\n\nФикстура.\n\n## Шаги\n\n## Покрытие требований\n\n"
            f"## Влияние на систему\n{appendix}")


class DocsSandbox(RealGitSandbox):
    """Главная копия (она же клон артели), bare `origin`, вспомогательный
    репозиторий документов задач."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        role = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role.start()
        self.addCleanup(role.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        self.prepare_main()
        self.origin = self.add_synced_origin()
        self.conn = store.db()
        src = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, ignore_errors=True)
        self.docs_src = Path(src) / "docs-src"
        self.git("init", "-q", "-b", "docs-src", str(self.docs_src))

    def prepare_main(self) -> None:
        """Первый коммит главной копии сверх шаблона — точка расширения."""

    # ----------------------------------------------------------------- git

    def in_repo(self, repo: Path, *args: str) -> str:
        return self.git("-C", str(repo), *args)

    def git_ok(self, repo: Path, *args: str) -> bool:
        try:
            self.in_repo(repo, *args)
        except AssertionError:
            return False
        return True

    def task_id(self) -> str:
        return "01T" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))

    def ref(self, task: str) -> str:
        return f"refs/artifacts/{task}"

    def docs_rel(self, task: str, rel: str = "") -> str:
        return f"{TASKS_DIR}/{task}/{rel}" if rel else f"{TASKS_DIR}/{task}/"

    def put_docs(self, repo: Path, origin: Path, task: str, files: dict) -> str:
        """Коммит документов задачи (раскладка ссылки документов) во
        вспомогательном репозитории, отправленный в `repo` и `origin`
        ссылкой `refs/artifacts/<id>`; sha коммита."""
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
        for dest in (repo, origin):
            self.in_repo(src, "push", "-q", str(dest), f"{sha}:{self.ref(task)}")
        return sha

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"


class MergeSandbox(DocsSandbox):
    """Задачи на `merge_gate`, подставной `gh` и часы; `COPY_CODE` — код
    пульта, заглушка карты и исторический каталог задачи в main."""

    COPY_CODE = False

    def prepare_main(self) -> None:
        if not self.COPY_CODE:
            return
        for name in ("orchestrator", "scripts"):
            shutil.copytree(REPO / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        guard_py = self.root / "scripts" / "guard.py"
        text = guard_py.read_text(encoding="utf-8")
        self.assertIn(GUARD_MAIN, text, "зонду guard некуда встать")
        guard_py.write_text(text.replace(GUARD_MAIN, GUARD_PROBE), encoding="utf-8")
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / MAP_REL).write_text(MAP_PLACEHOLDER, encoding="utf-8")
        old = "01H" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))
        plank = self.root / TASKS_DIR / old / "acceptance_tests" / "test_old.py"
        plank.parent.mkdir(parents=True)
        plank.write_text(plank_text(1, 0), encoding="utf-8")
        retro_path = self.root / "docs" / "retro" / f"{old}.md"
        retro_path.parent.mkdir(parents=True)
        retro_path.write_text(f"# RETRO: {old}\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "код пульта")

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.conn = store.db()
        self.probe = Path(tempfile.mkdtemp()) / "guard-probe.jsonl"
        self.addCleanup(shutil.rmtree, self.probe.parent, ignore_errors=True)

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

    def fake_sleep(self, seconds) -> None:
        self.clock += float(seconds)
        if self.clock > 10 * 24 * 3600:
            raise AssertionError(self.msg("ожидание не кончается"))

    # ----------------------------------------------------------- проекты

    def repo_of(self, target: str) -> Path:
        if target == config.DEFAULT_TARGET:
            return self.root
        return config.PROJECTS / target / "repo"

    def origin_of(self, target: str) -> Path:
        if target == config.DEFAULT_TARGET:
            return self.origin
        return config.PROJECTS / target / "origin.git"

    def commit_to_main(self, target: str, files: dict) -> None:
        """Коммит в main проекта (и его origin) до заведения задачи — поверх
        origin/main: прежние мержи песочницы двигали только origin."""
        repo = self.repo_of(target)
        self.in_repo(repo, "fetch", "-q", "origin")
        self.in_repo(repo, "merge", "-q", "--ff-only", f"origin/{config.MAIN_BRANCH}")
        for rel, text in files.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.in_repo(repo, "add", rel)
        self.in_repo(repo, "commit", "-q", "-m", "правка main до задачи")
        self.in_repo(repo, "push", "-q", "origin",
                     f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def make_task(self, *, target: str = config.DEFAULT_TARGET,
                  state: str = "merge_gate", docs: dict | None = None,
                  extra_docs: dict | None = None, appendix: str = "",
                  with_ref: bool = True, task: str | None = None) -> dict:
        """Задача на `state`: кодовая ветка от origin/main, опубликована;
        ссылка документов (если `with_ref`) в репозитории задачи и его
        origin, затем фиксация."""
        repo = self.repo_of(target)
        if self.COPY_CODE and target == config.DEFAULT_TARGET:
            # Заглушка карты в main перед каждой задачей: регенерация на
            # её мерже даёт коммит карты и во втором мерже песочницы.
            self.commit_to_main(target, {
                MAP_REL: f"{MAP_PLACEHOLDER}\n{self.rng.randrange(10 ** 9)}\n"})
        task = task or self.task_id()
        branch = f"task/{task.lower()}-x"
        self.in_repo(repo, "fetch", "-q", "origin")
        self.in_repo(repo, "checkout", "-q", "-b", branch,
                     f"origin/{config.MAIN_BRANCH}")
        code = f"zadacha_{task.lower()}.py"
        (repo / code).write_text(f"VALUE = {self.rng.randrange(10 ** 6)}\n",
                                 encoding="utf-8")
        self.in_repo(repo, "add", code)
        self.in_repo(repo, "commit", "-q", "-m", f"{task}: код")
        head = self.in_repo(repo, "rev-parse", "HEAD").strip()
        self.in_repo(repo, "push", "-q", "-u", "origin", branch)
        self.in_repo(repo, "checkout", "-q", config.MAIN_BRANCH)
        store.insert_task(self.conn, task, f"Задача {task}", state, branch,
                          target, config.DEFAULT_BUDGET_USD)
        files = docs if docs is not None else {
            "SPEC.md": spec_text(task), "PLAN.md": plan_text(task, appendix),
            "acceptance_tests/test_ac1_fixture.py": plank_text(1, 0)}
        files.update(extra_docs or {})
        if with_ref:
            self.put_docs(repo, self.origin_of(target), task, files)
            store.record_fixation(self.conn, task)
        return {"id": task, "branch": branch, "head": head, "code": code,
                "target": target, "repo": repo, "origin": self.origin_of(target)}

    # ------------------------------------------------------------ команды

    def cli(self, *argv: str) -> tuple[bool, str]:
        """(успех, вывод + текст отказа или исключения) `artel.py <argv>`."""
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

    def approve(self, task: dict, probe_files: tuple = ()) -> str:
        """`approve` на `merge_gate`, пока задача на гейте; весь вывод."""
        outputs = []
        env = {"ARTEL_GUARD_PROBE": str(self.probe),
               "ARTEL_GUARD_PROBE_FILES": ":".join(probe_files)}
        with mock.patch.dict(os.environ, env):
            for _ in range(3):
                ok, out = self.cli("approve", task["id"])
                outputs.append(out)
                if not ok or self.state_of(task) != "merge_gate":
                    break
        return "\n".join(outputs) + "\n" + "\n".join(self.journal(task))

    # -------------------------------------------------------------- чтение

    def state_of(self, task: dict) -> str:
        return store.get_task(store.db(), task["id"])["state"]

    def journal(self, task: dict) -> list:
        return [f"{row['action']} | {row['detail'] or ''}"
                for row in store.task_steps(store.db(), task["id"])]

    def origin_main(self, origin: Path) -> str:
        return self.in_repo(origin, "rev-parse",
                            f"refs/heads/{config.MAIN_BRANCH}").strip()

    def origin_subjects(self, origin: Path) -> list:
        return [s for s in self.in_repo(
            origin, "log", "--format=%s",
            f"refs/heads/{config.MAIN_BRANCH}").splitlines() if s]

    def origin_tree(self, origin: Path) -> list:
        return self.in_repo(origin, "ls-tree", "-r", "--name-only",
                            f"refs/heads/{config.MAIN_BRANCH}").splitlines()

    def origin_retro(self, task: dict) -> str:
        return self.in_repo(task["origin"], "show",
                            f"{self.ref(task['id'])}:"
                            f"{self.docs_rel(task['id'], 'RETRO.md')}")

    def first_parent_line(self, origin: Path) -> list:
        """Коммиты первой родительской линии main origin, от старых к новым."""
        return self.in_repo(origin, "rev-list", "--first-parent", "--reverse",
                            f"refs/heads/{config.MAIN_BRANCH}").split()

    def parents(self, origin: Path, sha: str) -> list:
        return self.in_repo(origin, "rev-list", "--parents", "-n", "1",
                            sha).split()[1:]

    def changed_files(self, origin: Path, sha: str) -> set:
        return set(self.in_repo(origin, "diff-tree", "--no-commit-id",
                                "--name-only", "-r", sha).split())

    def merge_commit_index(self, task: dict, line: list) -> int:
        """Индекс коммита merge кодовой ветки задачи на первой родительской
        линии: второй родитель — голова ветки задачи."""
        found = [i for i, sha in enumerate(line)
                 if task["head"] in self.parents(task["origin"], sha)[1:]]
        self.assertEqual(len(found), 1, self.msg(f"коммит merge задачи: {found}"))
        return found[0]

    def merge_sha(self, task: dict) -> str:
        """sha коммита мержа задачи в main origin: merge кодовой ветки и
        следующие за ним коммиты первой линии до коммита карты кодовой базы
        (коммит, меняющий только карту), без него."""
        line = self.first_parent_line(task["origin"])
        i = self.merge_commit_index(task, line)
        while (i + 1 < len(line)
               and self.changed_files(task["origin"], line[i + 1]) != {MAP_REL}):
            i += 1
        return line[i]

    def branch_exists(self, task: dict) -> bool:
        return bool(self.in_repo(task["repo"], "branch", "--list",
                                 task["branch"]).strip())

    def failed_details(self, task: dict) -> list:
        return [row["detail"] or "" for row in store.task_steps(store.db(), task["id"])
                if row["action"] == "merge FAILED"]

    def appendix(self, count: int = 2) -> tuple[str, list, str]:
        """(раздел приложений PLAN, пути, метка строки) — новые файлы под
        защищёнными путями, по блоку ```diff на файл."""
        marker = f"правка Оператора {self.rng.randrange(10 ** 9)}"
        n = self.rng.randrange(100, 999)
        pool = ["docs/invariants.md", f"skills/pesochnica-{n}.md",
                f"docs/adr/0{n}-pesochnica.md"]
        paths = self.rng.sample(pool, count)
        blocks = []
        for path in paths:
            blocks.append("```diff\n"
                          f"diff --git a/{path} b/{path}\n"
                          "new file mode 100644\n"
                          "--- /dev/null\n"
                          f"+++ b/{path}\n"
                          "@@ -0,0 +1 @@\n"
                          f"+{marker} ({path})\n"
                          "```\n")
        section = "\n## Приложение: правка защищённых путей\n\n" + "\n".join(blocks)
        return section, paths, marker


class ArtelMergeTest(MergeSandbox):
    """Мерж задачи артели с кодом пульта, генератором карты и историческим
    каталогом задачи в main."""

    COPY_CODE = True

    def test_ac1_main_gets_neither_snapshot_nor_retro(self):
        """Мерж задачи артели через `approve`: задача в `done`.

        В истории main origin нет коммитов «снимок артефактной ветки поверх
        merge», «RETRO задачи», «killed-RETRO долга»; в дереве main origin
        нет ни каталога документов задачи, ни `docs/retro/<id>.md`, а код
        задачи есть.

        Ловит мутацию: наложение снимка ссылки документов на дерево мержа
        оставлено (или оставлен коммит RETRO в main) — в истории появится
        коммит снимка/RETRO, а в дереве main — каталог задачи или её RETRO.
        """
        task = self.make_task()

        out = self.approve(task)

        self.assertEqual(self.state_of(task), "done", self.msg(out))
        subjects = self.origin_subjects(task["origin"])
        for subject in (SNAPSHOT_SUBJECT, RETRO_SUBJECT, DEBT_SUBJECT):
            self.assertEqual([s for s in subjects if subject in s], [],
                             self.msg(f"коммит «{subject}» в main: {subjects}"))
        tree = self.origin_tree(task["origin"])
        self.assertIn(task["code"], tree, self.msg(out))
        self.assertEqual([p for p in tree if p.startswith(self.docs_rel(task["id"]))],
                         [], self.msg("каталог документов задачи в main"))
        self.assertNotIn(f"docs/retro/{task['id']}.md", tree, self.msg(out))

    def test_ac2_closing_retro_carries_outcome_cost_and_counters(self):
        """Мерж задачи с заданными стоимостью, числом итераций ревью,
        отказами приёмки и планкой из случайного числа тестов и пометок
        `manual`.

        `RETRO.md` каталога задачи в `refs/artifacts/<id>` на origin несёт
        «Итог: done», «Стоимость итого: $<стоимость>», строку ревью/приёмки
        с этими счётчиками и строку приёмочных тестов с числами планки.

        Ловит мутацию: RETRO закрытия строится не `retro.build_done`, а
        урезанным текстом (только исход и адрес) после переноса RETRO из
        main — строк стоимости и счётчиков в ссылке не окажется.
        """
        tests, manual = self.rng.randrange(1, 5), self.rng.randrange(0, 3)
        cost = self.rng.randrange(100, 9000) / 100
        iters, rejects = self.rng.randrange(0, 5), self.rng.randrange(0, 3)
        task = self.make_task(extra_docs={
            "acceptance_tests/test_ac1_fixture.py": plank_text(tests, manual)})
        store.update_task(self.conn, task["id"], spent_usd=cost,
                          review_iters=iters, accept_rejects=rejects)

        out = self.approve(task)

        self.assertEqual(self.state_of(task), "done", self.msg(out))
        text = self.origin_retro(task)
        self.assertIn("Итог: done", text, self.msg(text))
        self.assertIn(f"Стоимость итого: ${cost:.2f}", text, self.msg(text))
        self.assertIn(f"Ревью: {iters} итераций; приёмка: {rejects} отказ(ов)",
                      text, self.msg(text))
        self.assertIn(f"Приёмочные тесты: {tests} тест(ов), {manual} manual, "
                      f"0 skip", text, self.msg(text))

    def test_ac3_closing_retro_names_the_merge_commit(self):
        """Два мержа: без приложений PLAN и с ними.

        sha строки «Итог: done, sha …» RETRO закрытия в origin — коммит
        мержа задачи в main origin (merge кодовой ветки плюс коммит
        приложений, если он был; коммит карты кодовой базы не входит) и не
        HEAD главной копии пульта.

        Ловит мутацию: в «Итог: done» уходит `gitcmd.head_sha()` пульта
        (прежнее значение) либо sha головы, отправленной в main (вместе с
        коммитом карты), — sha не совпадёт с коммитом мержа.
        """
        for case in ("без приложений", "с приложениями"):
            with self.subTest(случай=case, зерно=self.seed):
                section = self.appendix()[0] if case == "с приложениями" else ""
                task = self.make_task(appendix=section)

                out = self.approve(task)

                self.assertEqual(self.state_of(task), "done", self.msg(out))
                found = DONE_SHA.findall(self.origin_retro(task))
                self.assertEqual(len(found), 1, self.msg(f"строка «Итог: done»: {found}"))
                expected = self.merge_sha(task)
                self.assertNotEqual(expected, self.origin_main(task["origin"]),
                                    self.msg("в стенде нет коммита карты поверх мержа"))
                self.assertEqual(found[0], expected, self.msg(out))
                self.assertNotEqual(found[0], self.git("rev-parse", "HEAD").strip(),
                                    self.msg(out))

    def test_ac4_closing_retro_lists_applied_appendices(self):
        """Мерж с двумя применимыми приложениями PLAN и мерж без приложений.

        RETRO закрытия первого содержит ровно одну строку, начинающуюся с
        `fsm_postmerge.APPENDICES_RETRO_PREFIX`, и она называет пути обоих
        приложений; у второго такой строки нет.

        Ловит мутацию: перечень применённых приложений не доезжает до
        коммита закрытия (строка дописывалась только к `docs/retro/<id>.md`
        main) — в RETRO ссылки строки нет; либо строка дописывается
        безусловно — она появится и у мержа без приложений.
        """
        section, paths, _ = self.appendix()
        with_appendix = self.make_task(appendix=section)
        out = self.approve(with_appendix)
        self.assertEqual(self.state_of(with_appendix), "done", self.msg(out))
        lines = [ln for ln in self.origin_retro(with_appendix).splitlines()
                 if ln.startswith(fsm_postmerge.APPENDICES_RETRO_PREFIX)]
        self.assertEqual(len(lines), 1, self.msg(f"строки приложений: {lines}"))
        for path in paths:
            self.assertIn(path, lines[0], self.msg(lines[0]))

        plain = self.make_task()
        out = self.approve(plain)
        self.assertEqual(self.state_of(plain), "done", self.msg(out))
        self.assertEqual([ln for ln in self.origin_retro(plain).splitlines()
                          if ln.startswith(fsm_postmerge.APPENDICES_RETRO_PREFIX)],
                         [], self.msg("строка приложений у мержа без приложений"))

    def test_ac5_appendix_commit_between_merge_and_map_seen_by_guard(self):
        """Мерж с приложениями PLAN; в дереве — генератор карты и `guard`.

        На первой линии main origin: коммит merge кодовой ветки, после него
        коммит приложений (меняет ровно пути приложений), после него коммит
        карты кодовой базы (меняет только карту). Зонд `guard --all` в дереве
        мержа (дерево, несущее код задачи) видел файлы приложений с текстом
        правки — каждый его запуск по такому дереву.

        Ловит мутацию: `_apply_plan_appendices` переставлен за
        `_guard_all_or_refuse` — зонд guard видит дерево без файлов
        приложений; переставлен за вычисление sha для push — коммита
        приложений в main origin нет вовсе.
        """
        section, paths, marker = self.appendix()
        task = self.make_task(appendix=section)

        out = self.approve(task, probe_files=(task["code"], *paths))

        self.assertEqual(self.state_of(task), "done", self.msg(out))
        origin = task["origin"]
        line = self.first_parent_line(origin)
        merge_at = self.merge_commit_index(task, line)
        # Сам стенд кладёт в main заглушку карты до задачи — коммиты карты
        # и приложений ищутся только выше коммита merge этой задачи.
        after = range(merge_at + 1, len(line))
        applied = [i for i in after
                   if self.changed_files(origin, line[i]) == set(paths)]
        mapped = [i for i in after
                  if self.changed_files(origin, line[i]) == {MAP_REL}]
        self.assertEqual(len(applied), 1, self.msg(f"коммит приложений: {applied}; {out}"))
        self.assertEqual(len(mapped), 1, self.msg(f"коммит карты: {mapped}; {out}"))
        self.assertFalse([i for i in range(merge_at)
                          if self.changed_files(origin, line[i]) == set(paths)],
                         self.msg(f"коммит приложений ниже merge: {line}"))
        self.assertLess(applied[0], mapped[0], self.msg(str(line)))

        records = [json.loads(r) for r in
                   self.probe.read_text(encoding="utf-8").splitlines() if r] \
            if self.probe.is_file() else []
        merge_tree = [r for r in records if r.get(task["code"]) is not None]
        self.assertTrue(merge_tree, self.msg(f"guard --all по дереву мержа не "
                                             f"запускался: {records}"))
        for record in merge_tree:
            for path in paths:
                self.assertIn(marker, record.get(path) or "",
                              self.msg(f"guard видел {path} без приложения: {record}"))

    def test_ac6_merge_commits_no_killed_retro_debt(self):
        """В БД — задача в `killed` без `docs/retro/<id>.md` в main; мержится
        другая задача артели.

        `docs/retro/<killed-id>.md` в дереве main origin нет, коммита
        «killed-RETRO долга» в истории main origin нет.

        Ловит мутацию: подбор killed-долгов оставлен на мерже — в main
        приедет RETRO ликвидированной задачи отдельным коммитом долга.
        """
        killed = self.task_id()
        store.insert_task(self.conn, killed, f"Задача {killed}", "killed",
                          f"task/{killed.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        task = self.make_task()

        out = self.approve(task)

        self.assertEqual(self.state_of(task), "done", self.msg(out))
        self.assertNotIn(f"docs/retro/{killed}.md", self.origin_tree(task["origin"]),
                         self.msg(out))
        self.assertEqual([s for s in self.origin_subjects(task["origin"])
                          if DEBT_SUBJECT in s], [], self.msg(out))

    # ------------------------------------------------------------ отказы

    def assert_refused(self, task: dict, before: str, name: str, out: str) -> None:
        self.assertEqual(self.state_of(task), "merge_gate", self.msg(out))
        self.assertEqual(self.origin_main(task["origin"]), before,
                         self.msg(f"main origin сдвинут: {out}"))
        details = self.failed_details(task)
        self.assertTrue([d for d in details if name in d],
                        self.msg(f"«merge FAILED» не называет {name}: {details}; {out}"))

    def test_ac9_stray_docs_file_refuses_despite_retro_in_main_and_ref(self):
        """Посторонний файл на голове `refs/artifacts/<id>`: отдельно на
        первом уровне каталога задачи и в его подкаталоге. В стенде есть и
        `docs/retro/<id>.md` в main, и `RETRO.md` в ссылке.

        Мерж отказан: запись «merge FAILED» называет файл, задача на
        `merge_gate`, голова main origin прежняя.

        Ловит мутацию: проверка документов задачи освобождает задачу с
        `docs/retro/<id>.md` в main (или с `RETRO.md` в ссылке) как
        закрытую историю, либо смотрит только первый уровень каталога —
        посторонний файл уезжает, мерж проходит.
        """
        cases = [("первый уровень",
                  self.rng.choice(("_head_map.md", "zametki.md", "PLAN_chernovik.md"))),
                 ("подкаталог",
                  self.rng.choice(("wip/_head_map.md", "tmp/zametki.md",
                                   "chernovik/plan.txt")))]
        for case, rel in cases:
            with self.subTest(случай=case, файл=rel, зерно=self.seed):
                self.assertTrue(guard.is_extraneous_task_root_file(rel),
                                self.msg(f"фикстура {rel} не посторонняя"))
                task_id = self.task_id()
                self.commit_to_main(config.DEFAULT_TARGET,
                                    {f"docs/retro/{task_id}.md": f"# RETRO: {task_id}\n"})
                task = self.make_task(task=task_id, extra_docs={
                    rel: "посторонний файл\n", "RETRO.md": f"# RETRO: {task_id}\n"})
                before = self.origin_main(task["origin"])

                out = self.approve(task)

                self.assert_refused(task, before, Path(rel).name, out)

    def test_ac10_stray_acceptance_file_refuses(self):
        """Посторонний файл в каталоге планки на голове ссылки документов
        задачи артели.

        Мерж отказан тем же путём: «merge FAILED» с именем файла, задача на
        `merge_gate`, main origin не тронут.

        Ловит мутацию: правила `guard --all` к документам задачи артели
        применялись только по наложенному снимку — сняв наложение, их не
        перенесли на дерево ссылки, и посторонний файл планки проходит.
        """
        name = self.rng.choice(("fixture.json", "dannye.csv", "nastroika.yaml",
                                "obshchee.py"))
        self.assertTrue(guard.is_extraneous_acceptance_test_file(name),
                        self.msg(f"фикстура {name} не посторонняя"))
        task = self.make_task(extra_docs={f"acceptance_tests/{name}": "{}\n"})
        before = self.origin_main(task["origin"])

        out = self.approve(task)

        self.assert_refused(task, before, name, out)

    def test_ac11_unreadable_docs_ref_refuses(self):
        """Ссылка документов задачи на проверке документов: её нет вовсе
        (ни в репозитории задачи, ни в origin) либо её дерево не читается
        (объект корневого дерева коммита ссылки удалён из репозитория).

        Мерж отказан: запись «merge FAILED», задача на `merge_gate`, main
        origin не тронут.

        Ловит мутацию: несчитанная ссылка документов читается как «пустой
        каталог задачи» — проверка проходит, мерж уезжает в main.
        """
        self.git("config", "receive.unpackLimit", "100000")
        for case in ("ссылки нет", "дерево не читается"):
            with self.subTest(случай=case, зерно=self.seed):
                task = self.make_task(with_ref=case != "ссылки нет")
                if case == "дерево не читается":
                    tree = self.git("rev-parse", f"{self.ref(task['id'])}^{{tree}}").strip()
                    git_dir = Path(self.git("rev-parse", "--absolute-git-dir").strip())
                    obj = git_dir / "objects" / tree[:2] / tree[2:]
                    self.assertTrue(obj.is_file(), self.msg(f"объект дерева {tree} не "
                                                            f"лежит отдельным файлом"))
                    obj.unlink()
                before = self.origin_main(task["origin"])

                out = self.approve(task)

                self.assertEqual(self.state_of(task), "merge_gate", self.msg(out))
                self.assertEqual(self.origin_main(task["origin"]), before, self.msg(out))
                self.assertTrue(self.failed_details(task),
                                self.msg(f"нет записи «merge FAILED»: {out}"))


class ExternalMergeTest(MergeSandbox):
    """AC-12: мерж задачи внешнего проекта."""

    def setUp(self):
        super().setUp()
        make_project_repo(SLED)

    def test_ac12_external_main_gets_no_snapshot(self):
        """Мерж задачи внешнего проекта: задача в `done`.

        В истории main проекта нет коммита «снимок артефактной ветки поверх
        merge», в дереве main проекта нет каталога документов задачи и
        `docs/retro/<id>.md`; код задачи есть.

        Ловит мутацию: отмена наложения снимка сделана только для артели —
        у внешнего проекта снимок по-прежнему накладывается на main.
        """
        task = self.make_task(target=SLED)

        out = self.approve(task)

        self.assertEqual(self.state_of(task), "done", self.msg(out))
        self.assertEqual([s for s in self.origin_subjects(task["origin"])
                          if SNAPSHOT_SUBJECT in s], [], self.msg(out))
        tree = self.origin_tree(task["origin"])
        self.assertIn(task["code"], tree, self.msg(out))
        self.assertEqual([p for p in tree if p.startswith(self.docs_rel(task["id"]))],
                         [], self.msg(out))
        self.assertNotIn(f"docs/retro/{task['id']}.md", tree, self.msg(out))

    def test_ac12_external_stray_docs_file_refuses(self):
        """Посторонний файл первого уровня в документах задачи внешнего
        проекта на голове ссылки.

        Мерж отказан: «merge FAILED» с именем файла, задача на `merge_gate`,
        main проекта не тронут.

        Ловит мутацию: проверка документов задачи на ссылке включена только
        для артели — у внешнего проекта, лишённого наложения, посторонний
        файл больше никто не смотрит.
        """
        rel = self.rng.choice(("_head_map.md", "zametki.md", "PLAN_chernovik.md"))
        self.assertTrue(guard.is_extraneous_task_root_file(rel))
        task = self.make_task(target=SLED, extra_docs={rel: "посторонний файл\n"})
        before = self.origin_main(task["origin"])

        out = self.approve(task)

        self.assertEqual(self.state_of(task), "merge_gate", self.msg(out))
        self.assertEqual(self.origin_main(task["origin"]), before, self.msg(out))
        self.assertTrue([d for d in self.failed_details(task) if rel in d],
                        self.msg(f"«merge FAILED» не называет {rel}: {out}"))


class ClosingFailureTest(MergeSandbox):
    """AC-7, AC-8: провал коммита закрытия на путях мержа и `kill`."""

    CAUSES = ("ссылки нет", "голова разошлась с фиксацией", "git не ответил",
              "построение RETRO бросило исключение")

    def sabotage(self, task: dict, cause: str) -> None:
        """Ломает запись коммита закрытия задачи `task` по причине `cause`
        (кроме исключения построения — его даёт подмена)."""
        repo, ref = task["repo"], self.ref(task["id"])
        if cause == "ссылки нет":
            self.in_repo(repo, "update-ref", "-d", ref)
        elif cause == "голова разошлась с фиксацией":
            head = self.in_repo(repo, "rev-parse", ref).strip()
            moved = self.in_repo(repo, "commit-tree", f"{head}^{{tree}}", "-p", head,
                                 "-m", "правка мимо пульта").strip()
            self.in_repo(repo, "update-ref", ref, moved, head)
        elif cause == "git не ответил":
            git_dir = Path(self.in_repo(repo, "rev-parse", "--absolute-git-dir").strip())
            lock = git_dir / f"{ref}.lock"
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text("", encoding="utf-8")

    @contextlib.contextmanager
    def failing_closing(self, task: dict, cause: str, state: str, builder: str):
        """Сразу после перехода `task` в `state` — поломка `cause`;
        исключение построения — подмена `retro.<builder>`."""
        real = store.set_state

        def set_state(conn, task_id, new_state, *args, **kwargs):
            real(conn, task_id, new_state, *args, **kwargs)
            if task_id == task["id"] and new_state == state:
                self.sabotage(task, cause)

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(store, "set_state", set_state))
            if cause == "построение RETRO бросило исключение":
                stack.enter_context(mock.patch.object(
                    retro, builder, side_effect=RuntimeError(
                        f"стенд: {builder} упал")))
            yield

    def incidents_of(self, task: dict, known: set) -> list:
        return [dict(row) for row in alerts.open_alerts(store.db(), "incident")
                if row["id"] not in known
                and row["target"] in (task["target"], task["id"])]

    def known_incidents(self) -> set:
        return {row["id"] for row in alerts.open_alerts(store.db(), "incident")}

    def test_ac7_merge_closing_failure_keeps_done_cleanup_and_raises_incident(self):
        """Путь мержа, по прогону на причину провала коммита закрытия: ссылки
        документов нет; голова ссылки разошлась с фиксацией; git не ответил
        (ссылка заперта); `retro.build_done` бросил исключение.

        В каждом случае задача в `done`, ветка задачи убрана, в alerts —
        новый открытый incident-алерт с target этой задачи.

        Ловит мутацию: провал коммита закрытия только печатается и пишется в
        журнал (прежнее поведение) — инцидента нет; исключение построения
        RETRO не перехвачено — уборка ветки не выполняется.
        """
        for cause in self.CAUSES:
            with self.subTest(причина=cause, зерно=self.seed):
                task = self.make_task()
                known = self.known_incidents()

                with self.failing_closing(task, cause, "done", "build_done"):
                    out = self.approve(task)

                self.assertEqual(self.state_of(task), "done", self.msg(out))
                self.assertFalse(self.branch_exists(task),
                                 self.msg(f"ветка задачи не убрана: {out}"))
                self.assertTrue(self.incidents_of(task, known),
                                self.msg(f"нет инцидента: {out}"))

    def test_ac8_kill_closing_failure_keeps_killed_cleanup_and_raises_incident(self):
        """Путь `kill` (из случайного рабочего состояния), по прогону на
        причину провала коммита закрытия: ссылки документов нет; голова
        разошлась с фиксацией; git не ответил; `retro.build_killed` бросил
        исключение.

        В каждом случае задача в `killed`, ветка задачи убрана, в alerts —
        новый открытый incident-алерт с target этой задачи.

        Ловит мутацию: провал коммита закрытия на пути `kill` остаётся
        строкой вывода без инцидента; исключение `build_killed` прерывает
        `kill` до уборки хвостов задачи.
        """
        for cause in self.CAUSES:
            with self.subTest(причина=cause, зерно=self.seed):
                state = self.rng.choice(("in_dev", "review", "merge_gate"))
                task = self.make_task(state=state)
                known = self.known_incidents()

                with self.failing_closing(task, cause, "killed", "build_killed"):
                    ok, out = self.cli("kill", task["id"])
                out = f"{out}\n" + "\n".join(self.journal(task))

                self.assertEqual(self.state_of(task), "killed", self.msg(out))
                self.assertFalse(self.branch_exists(task),
                                 self.msg(f"ветка задачи не убрана: {out}"))
                self.assertTrue(self.incidents_of(task, known),
                                self.msg(f"нет инцидента: {out}"))


class MainBoundReadersTest(DocsSandbox):
    """AC-13: читатели, привязанные к main, — по ссылке документов."""

    def test_ac13_build_done_addresses_the_docs_ref_by_default(self):
        """`retro.build_done(conn, id, sha)` без `address` для нескольких
        задач со случайными id и sha.

        Текст содержит «Адрес артефактов: refs/artifacts/<id>».

        Ловит мутацию: адрес по умолчанию остаётся контент-адресным
        `<sha>:<каталог задачи>` main — строки с ссылкой не будет.
        """
        for _ in range(3):
            task = self.task_id()
            sha = "".join(self.rng.choice("0123456789abcdef") for _ in range(40))
            store.insert_task(self.conn, task, f"Задача {task}", "done",
                              f"task/{task.lower()}-x", config.DEFAULT_TARGET,
                              config.DEFAULT_BUDGET_USD)
            with self.subTest(задача=task, зерно=self.seed):
                text = retro.build_done(self.conn, task, sha)
                self.assertIn(f"Адрес артефактов: refs/artifacts/{task}", text,
                              self.msg(text))

    def test_ac13_artifacts_in_main_answers_by_docs_ref_or_history(self):
        """Три задачи в случайном порядке: каталога в main нет, ссылка
        документов есть (в репозитории и в origin); исторический каталог
        задачи в main, ссылки нет; ни каталога, ни ссылки.

        `cleanup.artifacts_in_main` — `True`, `True`, `False`
        соответственно.

        Ловит мутацию: признак «сохранены» по-прежнему смотрит только дерево
        main — задача, чьи документы живут лишь в ссылке, читается «не
        сохранены»; либо ссылка проверяется без имени задачи — «сохранены»
        получает и задача без следов.
        """
        by_ref, historical, bare = self.task_id(), self.task_id(), self.task_id()
        self.put_docs(self.root, self.origin, by_ref,
                      {"SPEC.md": spec_text(by_ref)})
        path = self.root / TASKS_DIR / historical / "SPEC.md"
        path.parent.mkdir(parents=True)
        path.write_text(spec_text(historical), encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"исторический каталог {historical}")
        self.git("push", "-q", "origin", f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        cases = [("ссылка без каталога", by_ref, True),
                 ("исторический каталог", historical, True),
                 ("ни каталога, ни ссылки", bare, False)]
        self.rng.shuffle(cases)
        for case, task, expected in cases:
            with self.subTest(случай=case, зерно=self.seed):
                self.assertIs(cleanup.artifacts_in_main(task), expected,
                              self.msg(case))


if __name__ == "__main__":
    unittest.main()
