"""Команда `artel.py docs <id> [файл]` / `docs --fetch-all`, подсказка `show`
и отказ процессу роли (ADR-0021 пп. 3, 13, этап 1).

`docs` подтягивает ссылку документов задачи `refs/artifacts/<id>` из
`origin` репозитория задачи (артели или внешнего проекта) и печатает файл
документов либо их перечень; `--fetch-all` подтягивает все ссылки одним
`git fetch` на репозиторий. Локальная ссылка с коммитами, которых нет в
`origin`, не перезаписывается. `show` без локальной ссылки называет
`docs <id>`. Процессу роли обе формы `docs` недоступны. `retro_corpus`
по-прежнему работает только с локальными ссылками.

Сценарии на настоящем git: главная копия пульта (`self.root`) с bare-
`origin` (`self.bare`), внешний проект — клон `make_project_repo` со своим
bare-`origin`. Коммиты ссылок собирает отдельный черновой репозиторий
(`self.scratch`) и отправляет их в нужный `origin` или в локальный
репозиторий. Команды исполняются диспетчером `artel.main` в процессе.
Идентификаторы задач, содержимое файлов и число ссылок — из `random`, зерно
печатается и входит в текст провала.

Группа: долгоживущий
Красен до реализации: команды docs в диспетчере artel.py нет («Неизвестная команда docs»), а show не печатает подсказку — методы AC-1…AC-8 и AC-10 красные; методы AC-9 (отказ роли закрытым по умолчанию белым списком) и AC-11 (retro_corpus без сети) держат существующее поведение и зелёные с рождения.
"""
import contextlib
import io
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, config, retro_corpus, store
from tests.sandbox import AutoOriginSandbox, make_project_repo

#: Первый сегмент дерева ссылки документов: `<DOCS_TOP>/<id>/<файл>`.
DOCS_TOP = "tasks"
REF_PREFIX = "refs/artifacts/"
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PROJECT_NAMES = ("sled", "sani", "drovni", "rozvalni")
NETWORK_SUBCOMMANDS = ("fetch", "pull", "ls-remote", "clone", "push")


def new_seed() -> int:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed


def git_subcommand(cmd) -> str:
    """Подкоманда git сквозь ведущие опции (`-C <путь>`, `-c k=v`, `--x`)."""
    cmd = [str(c) for c in cmd]
    if not cmd or Path(cmd[0]).name != "git":
        return ""
    i = 1
    while i < len(cmd) and cmd[i].startswith("-"):
        i += 2 if cmd[i] in ("-C", "-c") else 1
    return cmd[i] if i < len(cmd) else ""


def git_repo_of(cmd, kwargs) -> str:
    """Репозиторий, в котором исполняется git-команда: `-C` либо `cwd`."""
    cmd = [str(c) for c in cmd]
    repo = None
    for i, arg in enumerate(cmd[:-1]):
        if arg == "-C":
            repo = cmd[i + 1]
    if repo is None:
        repo = kwargs.get("cwd") or os.getcwd()
    return os.path.realpath(str(repo))


class GitCallRecorder:
    """Обёртка настоящего `subprocess.run`: запоминает git-команды."""

    def __init__(self, real_run):
        self.real_run = real_run
        self.calls: list = []

    def __call__(self, cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)):
            self.calls.append((list(cmd), dict(kwargs)))
        return self.real_run(cmd, *args, **kwargs)

    def by_subcommand(self, name: str) -> list:
        return [(c, kw) for c, kw in self.calls if git_subcommand(c) == name]


def _targets_yaml(external: str | None) -> str:
    entry = ("    forge: github\n    url: file:///nonexistent/{name}\n"
             "    base: {base}\n    token_slot: {name}-token\n"
             "    no_paths: []\n    project_skills: []\n"
             "    merge_gate: operator\n")
    text = ("targets:\n" f"  {config.DEFAULT_TARGET}:\n"
            + entry.format(name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH))
    if external:
        text += f"  {external}:\n" + entry.format(name=external,
                                                  base=config.MAIN_BRANCH)
    return text


class DocsSandbox(AutoOriginSandbox):
    """Пульт с `origin`, черновой репозиторий коммитов ссылок, генераторы
    идентификаторов и содержимого из `random`."""

    def setUp(self):
        super().setUp()
        self.seed = new_seed()
        self.rng = random.Random(self.seed)
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        config.TARGETS.write_text(_targets_yaml(None), encoding="utf-8")
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        self.scratch = Path(scratch).resolve()
        self.sgit("init", "-q", "-b", "scratch")
        self.sgit("config", "user.email", "scratch@example.invalid")
        self.sgit("config", "user.name", "scratch tests")
        self.sgit("commit", "-q", "--allow-empty", "-m", "scratch base")
        self._seq = 0

    # --- генераторы ----------------------------------------------------

    def why(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def task_id(self) -> str:
        return "01M" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))

    def text(self, label: str) -> str:
        return f"{label}-{self.rng.randrange(1 << 48):012x}\n"

    def add_task(self, task_id: str, target: str | None = None) -> None:
        store.insert_task(store.db(), task_id, "Задача", "done",
                          f"task/{task_id.lower()}-x",
                          target or config.DEFAULT_TARGET, 25.0)

    # --- git ----------------------------------------------------------

    def sgit(self, *args: str) -> str:
        return self.git("-C", str(self.scratch), *args)

    def docs_rel(self, task_id: str, name: str) -> str:
        return f"{DOCS_TOP}/{task_id}/{name}"

    def commit_docs(self, task_id: str, files: dict,
                    parent: str | None = None) -> str:
        """Коммит чернового репозитория, дерево которого — ровно
        `<DOCS_TOP>/<id>/<файлы>`; `parent` нет — коммит без родителя."""
        self._seq += 1
        if parent:
            self.sgit("checkout", "-q", "--detach", parent)
        else:
            self.sgit("checkout", "-q", "--orphan", f"orphan-{self._seq}")
        self.sgit("rm", "-rqf", "--ignore-unmatch", "--", ".")
        self.sgit("clean", "-fdxq")
        for name, content in files.items():
            path = self.scratch / self.docs_rel(task_id, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.sgit("add", "-A")
        self.sgit("commit", "-q", "-m", f"{task_id}: документы {self._seq}")
        return self.sgit("rev-parse", "HEAD").strip()

    def place_ref(self, repo, task_id: str, sha: str) -> None:
        """Ставит `refs/artifacts/<id>` = `sha` в репозиторий `repo` (bare-
        `origin` или рабочий клон) отправкой из чернового."""
        ref = REF_PREFIX + task_id
        self.sgit("push", "-q", "-f", str(repo), f"{sha}:{ref}")

    def ref_sha(self, repo, task_id: str) -> str:
        return self.git("-C", str(repo), "for-each-ref",
                        "--format=%(objectname)", REF_PREFIX + task_id).strip()

    # --- команда ------------------------------------------------------

    def run_cli(self, *argv: str, role: str | None = None) -> tuple[int, str]:
        """(код выхода, stdout+stderr+текст SystemExit) вызова `artel.main`.
        `role` — окружение процесса роли (маркер `ARTEL_ROLE`), иначе
        окружение Оператора."""
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with mock.patch.dict(os.environ), \
                mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            os.environ.pop(config.ARTEL_ROLE_ENV, None)
            if role is not None:
                os.environ[config.ARTEL_ROLE_ENV] = role
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code is None:
                    code = 0
                elif isinstance(exc.code, int):
                    code = exc.code
                else:
                    code = 1
                    err.write(str(exc.code))
        return code, out.getvalue() + err.getvalue()


class DocsFetchTest(DocsSandbox):
    """`docs <id> [файл]` для задачи артели."""

    def test_ac1_docs_pulls_newer_origin_head(self):
        """Origin впереди локальной ссылки: печатается файл головы origin.

        Локальная `refs/artifacts/<id>` стоит на коммите A, `origin` — на
        его потомке B, где файл изменён. `docs <id> <файл>` печатает
        содержимое файла из B (не из A), и локальная ссылка после команды
        равна B.

        Ловит мутацию: `docs` читает локальную ссылку, не подтянув `origin`
        (нет `git fetch` либо fetch в FETCH_HEAD без обновления ссылки) —
        в выводе старое содержимое A, локальная ссылка остаётся на A.
        """
        tid = self.task_id()
        self.add_task(tid)
        name = self.rng.choice(("SPEC.md", "PLAN.md", "REVIEW.md"))
        old, new = self.text("старое"), self.text("новое")
        a = self.commit_docs(tid, {name: old, "PASSPORT.md": self.text("п")})
        b = self.commit_docs(tid, {name: new, "PASSPORT.md": self.text("п")},
                             parent=a)
        self.place_ref(self.root, tid, a)
        self.place_ref(self.bare, tid, b)

        code, out = self.run_cli("docs", tid, name)

        self.assertEqual(code, 0, self.why(f"docs завершился с кодом {code}: {out}"))
        self.assertIn(new.strip(), out, self.why("нет содержимого из головы origin"))
        self.assertNotIn(old.strip(), out, self.why("напечатано старое содержимое"))
        self.assertEqual(self.ref_sha(self.root, tid), b,
                         self.why("локальная ссылка не равна голове origin"))

    def test_ac2_docs_without_local_ref(self):
        """Локальной ссылки нет, в origin она есть: файл печатается, ссылка появляется.

        История ссылки в `origin` — несколько коммитов (число из `random`),
        файл меняется в каждом. `docs <id> <файл>` печатает версию головы, и
        после команды локальная `refs/artifacts/<id>` существует и равна
        голове `origin`.

        Ловит мутацию: `docs` при отсутствии локальной ссылки сразу отказывает
        «ссылки нет» либо читает `FETCH_HEAD`, не заводя локальную ссылку —
        код ненулевой или локальной ссылки после команды нет.
        """
        tid = self.task_id()
        self.add_task(tid)
        parent, last = None, ""
        for _ in range(self.rng.randrange(1, 4)):
            last = self.text("версия")
            parent = self.commit_docs(tid, {"SPEC.md": last}, parent=parent)
        self.place_ref(self.bare, tid, parent)
        self.assertEqual(self.ref_sha(self.root, tid), "",
                         self.why("предусловие: локальной ссылки нет"))

        code, out = self.run_cli("docs", tid, "SPEC.md")

        self.assertEqual(code, 0, self.why(f"docs завершился с кодом {code}: {out}"))
        self.assertIn(last.strip(), out, self.why("нет файла из головы origin"))
        self.assertEqual(self.ref_sha(self.root, tid), parent,
                         self.why("локальная ссылка не заведена на голову origin"))

    def test_ac3_docs_without_file_lists_names(self):
        """Без аргумента файла — перечень файлов документов, без содержимого.

        В голове ссылки `origin` — несколько файлов (в том числе вложенный в
        подкаталог); `docs <id>` печатает имя каждого и не печатает ни одного
        содержимого.

        Ловит мутацию: ветка «нет аргумента файла» печатает все файлы целиком
        (или только первый файл) вместо перечня — в выводе появляется
        содержимое файла либо не хватает имени.
        """
        tid = self.task_id()
        self.add_task(tid)
        names = ["SPEC.md", "PLAN.md",
                 f"acceptance_tests/test_ac{self.rng.randrange(1, 20)}_x.py"]
        if self.rng.random() < 0.5:
            names.append("REVIEW.md")
        files = {n: self.text(f"содержимое-{i}") for i, n in enumerate(names)}
        self.place_ref(self.bare, tid, self.commit_docs(tid, files))

        code, out = self.run_cli("docs", tid)

        self.assertEqual(code, 0, self.why(f"docs завершился с кодом {code}: {out}"))
        for name, content in files.items():
            self.assertIn(Path(name).name, out, self.why(f"в перечне нет {name}"))
            self.assertNotIn(content.strip(), out,
                             self.why(f"напечатано содержимое {name}"))

    def test_ac4_docs_reads_historical_snapshot(self):
        """Исторический снимок — один коммит без родителя — читается как живая ссылка.

        В `origin` ссылка закрытой задачи — единственный коммит без родителя
        с деревом `<DOCS_TOP>/<id>/` (RETRO.md, SPEC.md). `docs <id> RETRO.md`
        печатает его содержимое с кодом 0.

        Ловит мутацию: чтение опирается на родителя головы (`<голова>^`,
        `log` с первого родителя) или требует паспорт живой задачи — на
        коммите без родителя команда отказывает или печатает пусто.
        """
        tid = self.task_id()
        self.add_task(tid)
        retro = self.text("ретро")
        snap = self.commit_docs(tid, {"RETRO.md": retro,
                                      "SPEC.md": self.text("спек")})
        self.assertEqual(self.sgit("rev-list", "--count", snap).strip(), "1",
                         self.why("предусловие: снимок — коммит без родителя"))
        self.place_ref(self.bare, tid, snap)

        code, out = self.run_cli("docs", tid, "RETRO.md")

        self.assertEqual(code, 0, self.why(f"docs завершился с кодом {code}: {out}"))
        self.assertIn(retro.strip(), out, self.why("снимок не прочитан"))

    def test_ac6_docs_refuses_without_any_ref(self):
        """Ссылки нет ни в origin, ни локально: именованный отказ с ненулевым кодом.

        Задача заведена, `origin` доступен, но `refs/artifacts/<id>` нет
        нигде. `docs <id>` (и с аргументом файла) завершается ненулевым кодом,
        текст называет задачу и ссылку.

        Ловит мутацию: отсутствие ссылки трактуется как пустой перечень —
        команда печатает пусто и выходит с кодом 0.
        """
        tid = self.task_id()
        self.add_task(tid)
        other = self.task_id()
        self.place_ref(self.bare, other,
                       self.commit_docs(other, {"SPEC.md": self.text("чужое")}))

        for argv in (("docs", tid), ("docs", tid, "SPEC.md")):
            code, out = self.run_cli(*argv)
            self.assertNotEqual(code, 0, self.why(f"{argv}: код 0, вывод {out!r}"))
            self.assertIn(tid, out, self.why(f"{argv}: отказ не называет задачу"))
            self.assertRegex(out, r"refs/artifacts|ссылк",
                             self.why(f"{argv}: отказ не называет ссылку"))
            self.assertEqual(self.ref_sha(self.root, tid), "",
                             self.why("ссылка появилась из ниоткуда"))

    def test_ac7_local_commits_not_overwritten(self):
        """Локальная ссылка с коммитом не из origin не перезаписывается.

        Два вида расхождения: локальная впереди `origin` (потомок его
        головы) и разошедшаяся с ним (общий предок, разные потомки). Ни
        `docs <id>`, ни `docs --fetch-all` не сдвигают локальную ссылку, и
        вывод называет `origin`.

        Ловит мутацию: fetch с принудительной заменой (`+refs/artifacts/*`,
        `--force`, `update-ref` на голову origin) — локальная ссылка после
        команды указывает на голову `origin`, локальный коммит потерян.
        """
        for shape in ("впереди", "разошлась"):
            for argv_kind in ("docs", "fetch-all"):
                with self.subTest(shape=shape, command=argv_kind):
                    tid = self.task_id()
                    self.add_task(tid)
                    base = self.commit_docs(tid, {"SPEC.md": self.text("база")})
                    local = self.commit_docs(tid, {"SPEC.md": self.text("лок")},
                                             parent=base)
                    remote = base if shape == "впереди" else self.commit_docs(
                        tid, {"SPEC.md": self.text("ориджин")}, parent=base)
                    self.place_ref(self.root, tid, local)
                    self.place_ref(self.bare, tid, remote)

                    argv = (("docs", tid) if argv_kind == "docs"
                            else ("docs", "--fetch-all"))
                    _code, out = self.run_cli(*argv)

                    self.assertEqual(self.ref_sha(self.root, tid), local,
                                     self.why(f"{shape}/{argv_kind}: локальная "
                                              f"ссылка перезаписана"))
                    self.assertIn("origin", out,
                                  self.why(f"{shape}/{argv_kind}: вывод не "
                                           f"называет расхождение с origin"))


class DocsExternalProjectTest(DocsSandbox):
    """`docs` для задачи внешнего проекта."""

    def setUp(self):
        super().setUp()
        self.target = (self.rng.choice(PROJECT_NAMES)
                       + str(self.rng.randrange(10, 100)))
        config.TARGETS.write_text(_targets_yaml(self.target), encoding="utf-8")
        self.project = make_project_repo(self.target)
        self.project_bare = config.PROJECTS / self.target / "origin.git"

    def test_ac5_docs_reads_project_origin(self):
        """Задача внешнего проекта: ссылка тянется из origin проекта, не артели.

        Под тем же id в `origin` артели лежит приманка с другим содержимым.
        `docs <id> <файл>` печатает содержимое из `origin` проекта, локальная
        ссылка появляется в клоне проекта и равна его `origin`, а в главной
        копии пульта ссылка не заводится.

        Ловит мутацию: `docs` берёт `config.ROOT` вместо репозитория по target
        задачи — в выводе приманка из `origin` артели, ссылка заведена в git
        пульта, клон проекта без ссылки.
        """
        tid = self.task_id()
        self.add_task(tid, self.target)
        name = self.rng.choice(("SPEC.md", "PLAN.md"))
        real, decoy = self.text("проект"), self.text("приманка")
        head = self.commit_docs(tid, {name: real})
        self.place_ref(self.project_bare, tid, head)
        self.place_ref(self.bare, tid, self.commit_docs(tid, {name: decoy}))

        code, out = self.run_cli("docs", tid, name)

        self.assertEqual(code, 0, self.why(f"docs завершился с кодом {code}: {out}"))
        self.assertIn(real.strip(), out, self.why("нет файла из origin проекта"))
        self.assertNotIn(decoy.strip(), out, self.why("прочитан origin артели"))
        self.assertEqual(self.ref_sha(self.project, tid), head,
                         self.why("ссылка не заведена в клоне проекта"))
        self.assertEqual(self.ref_sha(self.root, tid), "",
                         self.why("ссылка внешней задачи заведена в git пульта"))


class DocsFetchAllTest(DocsSandbox):
    """`docs --fetch-all`."""

    def test_ac8_fetch_all_counts_brought_and_updated(self):
        """`--fetch-all` приносит отсутствовавшие ссылки и печатает оба числа.

        В `origin` артели — N ссылок, которых нет локально, и M ссылок, чья
        локальная копия отстаёт (N ≠ M, оба ≥ 1, из `random`). После команды
        все они локально равны `origin`, вывод несёт числа N и M.

        Ловит мутацию: обновлённые ссылки считаются принесёнными (или
        наоборот), либо принесённые не заводятся локально — в выводе нет
        числа N или M, либо локальной ссылки после команды нет.
        """
        n_new = self.rng.randrange(1, 4)
        n_upd = self.rng.choice([k for k in range(1, 4) if k != n_new])
        expected = {}
        for _ in range(n_new):
            tid = self.task_id()
            self.add_task(tid)
            expected[tid] = self.commit_docs(tid, {"SPEC.md": self.text("н")})
            self.place_ref(self.bare, tid, expected[tid])
        for _ in range(n_upd):
            tid = self.task_id()
            self.add_task(tid)
            old = self.commit_docs(tid, {"SPEC.md": self.text("с")})
            expected[tid] = self.commit_docs(tid, {"SPEC.md": self.text("н")},
                                             parent=old)
            self.place_ref(self.root, tid, old)
            self.place_ref(self.bare, tid, expected[tid])

        code, out = self.run_cli("docs", "--fetch-all")

        self.assertEqual(code, 0, self.why(f"--fetch-all: код {code}: {out}"))
        for tid, sha in expected.items():
            self.assertEqual(self.ref_sha(self.root, tid), sha,
                             self.why(f"{tid}: локальная ссылка не равна origin"))
        numbers = set(re.findall(r"(?<![\w.])\d+(?![\w.])", out))
        self.assertIn(str(n_new), numbers,
                      self.why(f"нет числа принесённых {n_new}: {out!r}"))
        self.assertIn(str(n_upd), numbers,
                      self.why(f"нет числа обновлённых {n_upd}: {out!r}"))

    def test_ac8_fetch_all_one_fetch_per_repository(self):
        """Ровно один `git fetch` на репозиторий: артель и внешний проект с клоном.

        Ссылки (число из `random`) лежат в `origin` артели и в `origin`
        внешнего проекта. `docs --fetch-all` исполняет один `git fetch` в
        главной копии и один — в клоне проекта; ссылки обоих появляются
        локально каждая в своём репозитории.

        Ловит мутацию: fetch по ссылке на каждую задачу (цикл `git fetch
        origin refs/artifacts/<id>`) или пропуск внешних проектов — число
        вызовов `git fetch` на репозиторий не равно одному либо у проекта
        вызова нет вовсе.
        """
        target = (self.rng.choice(PROJECT_NAMES)
                  + str(self.rng.randrange(10, 100)))
        config.TARGETS.write_text(_targets_yaml(target), encoding="utf-8")
        project = make_project_repo(target)
        project_bare = config.PROJECTS / target / "origin.git"
        placed = []
        for repo, bare, tgt in ((self.root, self.bare, None),
                                (project, project_bare, target)):
            for _ in range(self.rng.randrange(2, 4)):
                tid = self.task_id()
                self.add_task(tid, tgt)
                sha = self.commit_docs(tid, {"SPEC.md": self.text("ф")})
                self.place_ref(bare, tid, sha)
                placed.append((repo, tid, sha))

        recorder = GitCallRecorder(subprocess.run)
        with mock.patch.object(subprocess, "run", recorder):
            code, out = self.run_cli("docs", "--fetch-all")

        self.assertEqual(code, 0, self.why(f"--fetch-all: код {code}: {out}"))
        per_repo: dict = {}
        for cmd, kwargs in recorder.by_subcommand("fetch"):
            key = git_repo_of(cmd, kwargs)
            per_repo[key] = per_repo.get(key, 0) + 1
        expected = {os.path.realpath(str(self.root)): 1,
                    os.path.realpath(str(project)): 1}
        self.assertEqual(per_repo, expected,
                         self.why("вызовы git fetch по репозиториям"))
        for repo, tid, sha in placed:
            self.assertEqual(self.ref_sha(repo, tid), sha,
                             self.why(f"{tid}: ссылка не принесена в {repo}"))


class RoleRefusalTest(DocsSandbox):
    """Процесс роли не исполняет `docs`."""

    def test_ac9_role_process_refused_docs(self):
        """Под окружением роли `docs <id>` и `docs --fetch-all` отказывают диспетчером.

        В `origin` лежит ссылка задачи, локально её нет. Под маркером
        `ARTEL_ROLE` (имя роли из `random`) обе формы завершаются отказом,
        называющим роль, а локальная ссылка так и не появляется.

        Ловит мутацию: `docs` внесён в белый список команд роли — команда
        исполняется под ролью, подтягивает ссылку, отказа нет.
        """
        tid = self.task_id()
        self.add_task(tid)
        self.place_ref(self.bare, tid,
                       self.commit_docs(tid, {"SPEC.md": self.text("с")}))
        role = f"role_{self.rng.randrange(1 << 30):x}"
        for argv in (("docs", tid), ("docs", tid, "SPEC.md"),
                     ("docs", "--fetch-all")):
            code, out = self.run_cli(*argv, role=role)
            self.assertNotEqual(code, 0, self.why(f"{argv}: под ролью код 0"))
            self.assertIn(role, out, self.why(f"{argv}: отказ не называет роль"))
            self.assertIn("docs", out, self.why(f"{argv}: отказ не называет команду"))
            self.assertEqual(self.ref_sha(self.root, tid), "",
                             self.why(f"{argv}: под ролью ссылка подтянута"))


class ShowHintTest(DocsSandbox):
    """`show <id>` без локальной ссылки."""

    def test_ac10_show_names_docs_command(self):
        """`show` задачи без локальной ссылки печатает подсказку `docs <id>`.

        Задача заведена в БД, локальной `refs/artifacts/<id>` нет (в
        `origin` она может быть, может не быть — из `random`). Вывод `show`
        содержит `docs <id>`.

        Ловит мутацию: подсказка печатается только для внешних target'ов
        (ветка `_artifact_frontmatter` для артели читает диск и молчит) или
        не печатается вовсе — в выводе нет `docs <id>`.
        """
        tid = self.task_id()
        self.add_task(tid)
        if self.rng.random() < 0.5:
            self.place_ref(self.bare, tid,
                           self.commit_docs(tid, {"SPEC.md": self.text("с")}))

        code, out = self.run_cli("show", tid)

        self.assertEqual(code, 0, self.why(f"show: код {code}: {out}"))
        self.assertIn(f"docs {tid}", out, self.why(f"нет подсказки: {out!r}"))


class RetroCorpusLocalTest(DocsSandbox):
    """`retro_corpus` остаётся локальным."""

    def test_ac11_retro_corpus_reads_only_local_refs(self):
        """Пересборка корпуса не ходит в сеть и не видит ссылок только из origin.

        В клоне проекта — локальная ссылка с RETRO; в его `origin` — ещё
        одна ссылка с RETRO, которой локально нет. `retro_corpus.
        rebuild_cache()` не исполняет ни одной сетевой git-команды
        (`fetch`/`pull`/`ls-remote`/`clone`/`push`), в корпусе — только
        локальная задача, а ссылка из `origin` локально так и не появляется.

        Ловит мутацию: в пересборку корпуса добавлен `docs --fetch-all`/`git
        fetch` перед проходом — в записи вызовов появляется `fetch`, корпус
        несёт задачу из `origin`.
        """
        target = (self.rng.choice(PROJECT_NAMES)
                  + str(self.rng.randrange(10, 100)))
        config.TARGETS.write_text(_targets_yaml(target), encoding="utf-8")
        project = make_project_repo(target)
        project_bare = config.PROJECTS / target / "origin.git"
        retro = ("---\noperator: o\nmodel: m\nartel_sha: "
                 f"{self.rng.randrange(1 << 40):010x}\n---\n\nретро\n")
        local_id, remote_id = self.task_id(), self.task_id()
        self.place_ref(project, local_id,
                       self.commit_docs(local_id, {"RETRO.md": retro}))
        self.place_ref(project_bare, remote_id,
                       self.commit_docs(remote_id, {"RETRO.md": retro}))

        cache = Path(tempfile.mkdtemp()) / "cache.json"
        self.addCleanup(shutil.rmtree, cache.parent, ignore_errors=True)
        recorder = GitCallRecorder(subprocess.run)
        with mock.patch.object(retro_corpus, "CACHE_PATH", cache), \
                mock.patch.object(subprocess, "run", recorder):
            rows = retro_corpus.rebuild_cache()

        network = [c for c, _kw in recorder.calls
                   if git_subcommand(c) in NETWORK_SUBCOMMANDS]
        self.assertEqual(network, [], self.why("сетевые git-команды корпуса"))
        ids = {row.get("task_id") for row in rows}
        self.assertIn(local_id, ids, self.why("локальная ссылка не в корпусе"))
        self.assertNotIn(remote_id, ids, self.why("в корпусе ссылка из origin"))
        self.assertEqual(self.ref_sha(project, remote_id), "",
                         self.why("ссылка из origin подтянута локально"))


if __name__ == "__main__":
    unittest.main()
