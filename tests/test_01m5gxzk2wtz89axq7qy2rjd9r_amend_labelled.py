"""`amend-tests` для файлов с меткой `AC-<n>: ` при правиле планки не по умолчанию: проход годной правки, отказы трёх групп проверок до любой записи, удаление долгоживущего файла, состав файлов планки `--from-branch` (AC-16..AC-19, AC-23).

Группа: долгоживущий
Красен до реализации: `amend-tests` отказывает любой правке при файле с меткой в планке или долгоживущем файле с меткой временным отказом «amend-tests для файлов планки с меткой AC-<n>: — до G3б не исполняется» без записи журнала: годная правка лок не сдвигает (AC-16, AC-19), отказы не несут префикса группы и записи «amend-tests отклонён» (AC-17, AC-18), отказ `--from-branch` называет файлы списком отказа G3б, а не находками запретов (AC-23).

Стенд — настоящий git (`tests.sandbox.GitignoreCommittedRealGitSandbox`),
связка «запись проекта — правило планки — ссылка документов — кодовая ветка
— лок — журнал»: клон артели — корень песочницы с bare `origin`; учебный
внешний проект — `tests.sandbox.make_project_repo` с компонентом
`pult-vitest` (маска `tests` — `frontend/src/**/*.test.jsx`, шаблон
`long_lived`). Задача в `in_dev` с локом: планка в ссылке документов
(`.test.jsx` с меткой, `.md`, перечень сумм), долгоживущий файл с меткой —
коммит кодовой ветки. Правка Оператора: в режиме рабочей копии — файлы
планки в рабочей копии кода и незакоммиченная правка долгоживущего файла; в
`--from-branch` — коммит в ссылку документов (git-плотницкой во временной
рабочей копии клона) и коммит кодовой ветки. Команда —
`amend.cmd_amend_tests`. Сухой сбор и прогон Vitest
(`acceptance._task_own_profile`) идут через шпион `subprocess.Popen` без
Node и сети: отчёт пульта с одним пройденным тестом; прочие вызовы (git) —
настоящий `subprocess`. Наблюдаются вывод команды, запись журнала «amend-tests
отклонён», голова ссылки документов, голова кодовой ветки,
`tests_locked_sha`, число записей «правка планки» и перечень нового лока.

Имена проекта, файлов, тестов — из `random`; зерно печатается и входит в
текст каждого провала.
"""
import contextlib
import hashlib
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import (amend, checkpoint, config, github_adapter,
                          project_profile, store, workspace)
from orchestrator.advance_gates import acceptance as acceptance_gates
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox, make_project_repo

REAL_POPEN = subprocess.Popen
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
TASKS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
TEMPLATE = "frontend/src/<dir>/<name>.<id>.test.jsx"
VITEST_BIN = project_profile.VITEST_BASE_ARGV[0]
VITEST_REPORT_ARGS = ["--reporter=default", "--reporter={pult_reporter}",
                      "--outputFile={path}"]
REFUSED_ACTION = "amend-tests отклонён"
REFUSED_OUT = "amend-tests: отказ"
OLD_REFUSAL = "до G3б не исполняется"
TRACE = "трассируемость AC нарушена:"
GROUPS = "строка группы:"
LONG = "долгоживущие файлы tests/:"
REMOVAL = "удаление снимает методы"

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


def spec_text(task_id: str, numbers) -> str:
    items = "\n\n".join(f"AC-{n}. Критерий фикстуры номер {n}." for n in
                        sorted(numbers))
    return ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n"
            "# SPEC: фикстура правки планки\n\n## Контекст\n\n## Требования\n\n"
            f"## Критерии приёмки\n\n{items}\n\n## Не входит\n")


def arg_value(args: list, flag: str) -> str | None:
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(flag + "="):
            return arg[len(flag) + 1:]
    return None


class AmendSandbox(GitignoreCommittedRealGitSandbox):
    """Клон артели с `origin`; учебный проект `pult-vitest` и задачи с
    локом заводит сценарий; Vitest — шпион `subprocess.Popen`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        fake = Path(tempfile.mkdtemp(prefix="artel-fake-")).resolve()
        self.addCleanup(shutil.rmtree, fake, True)
        self.installer = fake / f"install{self.word()}"
        self.installer.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.installer.chmod(0o755)
        self.vitest_version = next(
            f"{major}.0.0" for major, flags in
            project_profile.VITEST_VERSION_FLAGS.items()
            if flags.require_assertions)
        for patcher in (
                mock.patch.object(github_adapter, "ensure_head_in_origin",
                                  lambda *args, **kwargs: (True, "")),
                mock.patch.object(subprocess, "Popen", self.spy_popen)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
        self.clones = {config.DEFAULT_TARGET: self.root}
        self.conn = store.db()
        self.name = self.vitest_project()

    # --- входы ----------------------------------------------------------

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # --- шпион Vitest ---------------------------------------------------

    def answer(self, code: int, out: str, args, kwargs):
        script = f"import sys; sys.stdout.write({out!r}); sys.exit({code})"
        return REAL_POPEN([sys.executable, "-c", script], *args, **kwargs)

    def spy_popen(self, argv, *args, **kwargs):
        if not isinstance(argv, (list, tuple)) or not argv:
            return REAL_POPEN(argv, *args, **kwargs)
        parts = [str(a) for a in argv]
        if parts[0] == str(self.installer):
            cwd = Path(str(kwargs.get("cwd") or os.getcwd()))
            (cwd / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)
            return self.answer(0, "", args, kwargs)
        if parts[0] != VITEST_BIN:
            return REAL_POPEN(argv, *args, **kwargs)
        if parts[1:2] == ["--version"]:
            return self.answer(0, f"vitest/{self.vitest_version}\n", args, kwargs)
        path = arg_value(parts, "--outputFile")
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps({"tests": [{
                "file": "frontend/src/a.test.jsx", "name": "ok",
                "state": "pass", "mode": "run", "fails": False,
                "retry_count": 0, "error_name": None, "timeout": False,
                "hook": None, "duration_ms": 5}]}), encoding="utf-8")
        return self.answer(0, "1 passed in 0.01s\n", args, kwargs)

    # --- проект ---------------------------------------------------------

    def vitest_project(self) -> str:
        name, comp = f"v{self.word()}", f"c{self.word()}"
        fields = {"command": flow(project_profile.VITEST_BASE_ARGV),
                  "report": "pult-vitest",
                  "report_args": flow(VITEST_REPORT_ARGS),
                  "failure_errors": flow(["AssertionError"]),
                  "select": flow([f"--sel{self.word()}", "{tests}"]),
                  "install": flow([str(self.installer)]),
                  "tests": flow(["frontend/src/**/*.test.jsx"]),
                  "plank_layout": f"frontend/src/.pv{self.word(5)}/<id>",
                  "long_lived": TEMPLATE,
                  "weakening_scope": flow(["frontend/src/**"]),
                  "mutation_claim_scope": flow(["frontend/src/**"])}
        lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                 f"      {comp}:\n"]
        lines += [f"        {key}: {value}\n" for key, value in fields.items()]
        lines += ["        tools:\n", f'          vitest: "{self.vitest_version}"\n']
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + "".join(lines),
                                  encoding="utf-8")
        clone = make_project_repo(name)
        files = {"package.json": '{"name": "web"}\n',
                 "vitest.config.js": "export default {}\n",
                 "package-lock.json": json.dumps({"lockfileVersion": 3}) + "\n",
                 "frontend/src/app.jsx": "export const app = 1;\n"}
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.clones[name] = clone
        self.assertFalse(project_profile.plank_rule(name).is_default,
                         self.note("фикстура: правило планки по умолчанию"))
        return name

    # --- тексты фикстур -------------------------------------------------

    def plank_jsx(self, numbers, group: bool = True, ban: bool = False) -> str:
        """Файл планки с меткой: строка группы «разовый» (если `group`),
        маркер красноты, по `it('AC-<n>: …')` на критерий; `ban` —
        у последнего теста числовой литерал в аргументах."""
        head = "// Группа: разовый\n" if group else ""
        head += f"// Красен до реализации: фикстура {self.word()}.\n"
        body = ""
        for i, n in enumerate(numbers):
            tail = ", 5000" if ban and i == len(numbers) - 1 else ""
            body += (f"it('AC-{n}: кнопка {self.word()}', () => "
                     f"{{ expect({n}).toBe({n}); }}{tail});\n")
        return head + "import { expect, it } from 'vitest';\n\n" + body

    def long_jsx(self, numbers, group: bool = True, claims: bool = True,
                 ban: bool = False) -> str:
        """Долгоживущий файл с меткой: строка группы «долгоживущий»,
        «Ловит мутацию: …» над каждым вызовом (если `claims`); `ban` —
        последний тест с числовым литералом в аргументах."""
        head = "// Группа: долгоживущий\n" if group else ""
        head += f"// Красен до реализации: фикстура {self.word()}.\n"
        body = ""
        for i, n in enumerate(numbers):
            tail = ", 5000" if ban and i == len(numbers) - 1 else ""
            if claims:
                body += f"// Ловит мутацию: фикстура {self.word()} — сумма другая.\n"
            body += (f"it('AC-{n}: модуль {self.word()}', () => "
                     f"{{ expect({n} + 1).toBe({n + 1}); }}{tail});\n\n")
        return head + "import { expect, it } from 'vitest';\n\n" + body

    # --- задача с локом -------------------------------------------------

    def locked(self, criteria=(1, 2), plank_numbers=(2,), long_numbers=(1,),
               plank_ban: bool = False, long_ban: bool = False):
        """Задача `in_dev` с локом: планка — `.test.jsx` на `plank_numbers`
        (пусто — планка только из `.md`), `.md` и перечень; долгоживущий
        файл на `long_numbers` закоммичен в кодовую ветку."""
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        store.insert_task(self.conn, tid, "Фикстура правки планки", "in_dev",
                          branch, self.name, 25.0)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch, wt=Path(wt),
                            criteria=criteria)
        t.docs = config.PROJECTS / self.name / TASKS_DIR / tid
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(tid, criteria),
                                        encoding="utf-8")
        sub = "".join(f"{self.word(5)}/" for _ in range(self.rng.randint(0, 2)))
        t.long_rel = f"frontend/src/{sub}{self.word()}.{t.low}.test.jsx"
        t.long_text = self.long_jsx(long_numbers, ban=long_ban)
        self.write_code(t, t.long_rel, t.long_text)
        self.git("-C", str(t.wt), "add", "--", t.long_rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", "долгоживущий файл")
        digest = hashlib.sha256((t.wt / t.long_rel).read_bytes()).hexdigest()
        t.md = f"n{self.word()}.md"
        t.plank = {t.md: "заметка\n",
                   guard.LONG_LIVED_MANIFEST_NAME:
                       guard.render_long_lived_manifest({t.long_rel: digest})}
        t.jsx = ""
        if plank_numbers:
            t.jsx = f"a{self.word()}.test.jsx"
            t.plank[t.jsx] = self.plank_jsx(plank_numbers, ban=plank_ban)
        folder = t.docs / PLANK_DIR
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in t.plank.items():
            (folder / name).write_text(text, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, tid, "developer")
        head = self.docs_head(t)
        self.assertTrue(head, self.note("ссылки документов нет"))
        store.update_task(self.conn, tid, tests_locked_sha=head)
        store.record_fixation(self.conn, tid)
        return t

    def write_code(self, t, rel: str, text: str) -> None:
        path = t.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit_code(self, t, rel: str, text: str | None) -> None:
        """Коммит кодовой ветки: правка `rel` (`None` — удаление)."""
        if text is None:
            self.git("-C", str(t.wt), "rm", "-q", "--", rel)
        else:
            self.write_code(t, rel, text)
            self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", "правка кодовой ветки")

    def wt_plank(self, t, files: dict) -> None:
        """Правка Оператора в рабочей копии: планка целиком `files`."""
        folder = t.wt / TASKS_DIR / t.id / PLANK_DIR
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def docs_commit(self, t, files: dict, removed=()) -> None:
        """Коммит ссылки документов поверх её головы: `files` (путь от
        каталога планки → текст), `removed` — удалить; правка Оператора
        фиксируется."""
        clone = self.clones[self.name]
        old = self.docs_head(t)
        scratch = self.root / ".artel" / f"docs-copy-{self.word()}"
        self.git("-C", str(clone), "worktree", "add", "-q", "--detach",
                 str(scratch), old)
        try:
            folder = scratch / TASKS_DIR / t.id / PLANK_DIR
            for rel, text in files.items():
                path = folder / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            for rel in removed:
                self.git("-C", str(scratch), "rm", "-q", "--",
                         str((folder / rel).relative_to(scratch)))
            self.git("-C", str(scratch), "add", "-A")
            self.git("-C", str(scratch), "commit", "-q", "-m",
                     f"правка ссылки документов {self.word()}")
            new = self.git("-C", str(scratch), "rev-parse", "HEAD").strip()
        finally:
            self.git("-C", str(clone), "worktree", "remove", "--force",
                     str(scratch))
        ref = "refs/artifacts/" + t.id
        self.git("-C", str(clone), "update-ref", ref, new, old)
        self.git("-C", str(clone), "push", "-q", "-f", "origin", f"{ref}:{ref}")
        store.record_fixation(self.conn, t.id)

    # --- наблюдения -----------------------------------------------------

    def docs_head(self, t) -> str:
        return self.git("-C", str(self.clones[self.name]), "for-each-ref",
                        "--format=%(objectname)", "refs/artifacts/" + t.id).strip()

    def state_of(self, t) -> tuple:
        row = store.get_task(self.conn, t.id)
        code = self.git("-C", str(t.wt), "rev-parse", t.branch).strip()
        amends = [r for r in store.task_steps(self.conn, t.id)
                  if r["action"] == amend.AMEND_ACTION]
        return (self.docs_head(t), code, row["tests_locked_sha"], len(amends))

    def refusals(self, t) -> list:
        return [r["detail"] or "" for r in store.task_steps(self.conn, t.id)
                if r["action"] == REFUSED_ACTION]

    def amend(self, t, from_branch: bool = False) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                amend.cmd_amend_tests(t.id, f"правка {self.seed}",
                                      from_branch=from_branch)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def manifest(self, t) -> dict:
        row = store.get_task(self.conn, t.id)
        digests, reason = acceptance_gates.long_lived_manifest(t.id, row,
                                                               self.name)
        self.assertEqual(reason, "", self.note(reason))
        return digests

    def assert_refused(self, t, out: str, before: tuple, prefix: str,
                       needle: str = "") -> str:
        """Отказ до любой записи: четыре величины прежние, вывод и
        последняя запись «amend-tests отклонён» — с префиксом группы."""
        context = self.note(f"вывод:\n{out}\nзаписи: {self.refusals(t)}")
        self.assertNotIn(OLD_REFUSAL, out, context)
        self.assertEqual(self.state_of(t), before, context)
        self.assertIn(f"{REFUSED_OUT} — {prefix}", out, context)
        found = self.refusals(t)
        self.assertTrue(found and found[-1].startswith(prefix), context)
        if needle:
            self.assertIn(needle, out, context)
        return out

    def assert_passed(self, t, out: str, before: tuple) -> tuple:
        """Проход: отказа нет, `tests_locked_sha` сдвинут и равен голове
        ссылки документов, записей «правка планки» на одну больше."""
        after = self.state_of(t)
        context = self.note(f"вывод:\n{out}\nдо {before}\nпосле {after}\n"
                            f"записи отказа: {self.refusals(t)}")
        self.assertNotIn(OLD_REFUSAL, out, context)
        self.assertNotIn(REFUSED_OUT, out, context)
        self.assertNotEqual(after[2], before[2], context)
        self.assertEqual(after[2], after[0], context)
        self.assertEqual(after[3], before[3] + 1, context)
        return after


# ---------------------------------------------------------------- AC-16

class Ac16ValidPlankTest(AmendSandbox):

    def test_ac16_valid_labelled_plank_file_moves_lock_in_both_paths(self):
        """Годная правка `.test.jsx` с меткой: оба пути `amend-tests` сдвигают лок, отказа G3б нет.

        Сценарий: задача `in_dev` с локом; (а) рабочая копия — в `.test.jsx`
        планки добавлен ещё один годный тест `AC-<n>`; (б) `--from-branch`
        — та же правка коммитом в ссылку документов. Вывод без «amend-tests:
        отказ» и без текста отказа G3б; `tests_locked_sha` сдвинут и равен
        голове ссылки документов; записей «правка планки» на одну больше.

        Ловит мутацию: отказ G3б снят только в одном пути — второй
        отказывает; проверки файлов с меткой отказывают годному файлу
        (строка группы `//` не читается) — отказ «строка группы:».
        """
        for from_branch in (False, True):
            with self.subTest(from_branch=from_branch, seed=self.seed):
                t = self.locked()
                edited = t.plank[t.jsx] + (
                    f"it('AC-2: ещё {self.word()}', () => "
                    f"{{ expect(2).toBe(2); }});\n")
                before = self.state_of(t)
                if from_branch:
                    self.docs_commit(t, {t.jsx: edited})
                    before = self.state_of(t)
                else:
                    self.wt_plank(t, dict(t.plank, **{t.jsx: edited}))
                self.assert_passed(t, self.amend(t, from_branch), before)


# ---------------------------------------------------------------- AC-17

class Ac17RefusalGroupsTest(AmendSandbox):

    CASES = (
        ("планка: запрет", GROUPS),
        ("планка: нет строки группы", GROUPS),
        ("долгоживущий: нет «Ловит мутацию»", LONG),
        ("только .md: планка с запретом", GROUPS),
        ("трассируемость", TRACE),
        ("удалён единственный файл планки", TRACE),
        ("долгоживущий: запрет", LONG),
        ("долгоживущий: нет строки группы", LONG),
        ("только .md: долгоживущий с запретом", LONG),
        ("планка из .md: долгоживущий с нарушением", LONG),
    )

    def scenario(self, case: str, from_branch: bool) -> tuple:
        """Задача с локом и правкой случая; (задача, состояние до команды,
        подстрока вывода)."""
        needle = ""
        if case == "только .md: планка с запретом":
            t = self.locked(plank_ban=True)
        elif case == "только .md: долгоживущий с запретом":
            t = self.locked(long_ban=True)
        elif case == "планка из .md: долгоживущий с нарушением":
            t = self.locked(criteria=(1,), plank_numbers=())
        else:
            t = self.locked()
        plank_edit, removed, long_edit = {}, [], None
        if case == "планка: запрет":
            plank_edit = {t.jsx: self.plank_jsx((2,), ban=True)}
            needle = guard.PLANK_BAN_TAIL
        elif case == "планка: нет строки группы":
            plank_edit = {t.jsx: self.plank_jsx((2,), group=False)}
        elif case == "трассируемость":
            plank_edit = {t.jsx: self.plank_jsx((1,))}
        elif case == "удалён единственный файл планки":
            removed = [t.jsx]
        elif case.startswith("только .md"):
            plank_edit = {t.md: t.plank[t.md] + f"ещё {self.word()}\n"}
            needle = guard.PLANK_BAN_TAIL
        elif case == "долгоживущий: нет «Ловит мутацию»":
            long_edit = self.long_jsx((1,), claims=False)
        elif case == "долгоживущий: запрет":
            long_edit = self.long_jsx((1,), ban=True)
            needle = guard.PLANK_BAN_TAIL
        elif case == "долгоживущий: нет строки группы":
            long_edit = self.long_jsx((1,), group=False)
        else:
            long_edit = self.long_jsx((1,), ban=True)
        if from_branch:
            if plank_edit or removed:
                self.docs_commit(t, plank_edit, removed)
            if long_edit is not None:
                self.commit_code(t, t.long_rel, long_edit)
        else:
            files = {n: v for n, v in t.plank.items() if n not in removed}
            files.update(plank_edit)
            self.wt_plank(t, files)
            if long_edit is not None:
                self.write_code(t, t.long_rel, long_edit)
        return t, self.state_of(t), needle

    def run_cases(self, from_branch: bool) -> None:
        for case, prefix in self.CASES:
            with self.subTest(case=case, from_branch=from_branch, seed=self.seed):
                t, before, needle = self.scenario(case, from_branch)
                out = self.amend(t, from_branch)
                self.assert_refused(t, out, before, prefix, needle)

    def test_ac17_worktree_mode_refusals_by_group(self):
        """Рабочая копия: каждый случай нарушения — отказ до любой записи с префиксом своей группы в выводе и в записи «amend-tests отклонён».

        Случаи: файл планки с меткой с запретом (`5000` в аргументах) и без строки
        группы — «строка группы:» (у запрета — строка «… — запрещено в
        тексте планки»); долгоживущий файл с меткой без «Ловит мутацию», с
        запретом (`5000` в аргументах) и без строки группы — «долгоживущие
        файлы tests/:»; изменён только `.md`, а неизменённый файл планки
        либо долгоживущий файл несёт запрет — их группы; нарушенная
        трассируемость и удаление единственного файла планки, покрывавшего
        критерий, — «трассируемость AC нарушена:»; планка только из `.md` и
        долгоживущий файл с нарушением — «долгоживущие файлы tests/:».
        Голова ссылки документов, голова кодовой ветки, `tests_locked_sha` и
        число записей «правка планки» прежние.

        Ловит мутацию: проверяются только изменённые файлы — случаи «только
        .md» проходят; запреты не входят в группу файлов планки — отказ без
        «запрещено в тексте планки» либо проход; удаление файла планки не
        проверяется трассируемостью — проход; долгоживущие файлы с меткой
        проверяются прежним путём Python — заявка в комментарии не
        читается, префикс иной; отказ стоит после коммита — голова ссылки
        документов сдвинута.
        """
        self.run_cases(from_branch=False)

    def test_ac17_from_branch_refusals_by_group(self):
        """`--from-branch`: те же случаи коммитами в ссылку документов и кодовую ветку — отказ до любой записи с префиксом своей группы.

        Сценарий: правка планки — коммит в ссылку документов поверх лока
        (удаление — тоже коммитом); правка долгоживущего файла — коммит
        кодовой ветки; в случае «только .md, долгоживущий с запретом»
        долгоживущие файлы с перечнем лока не расходятся. Четыре величины
        прежние (голова ссылки документов — после записанного коммита),
        вывод и запись «amend-tests отклонён» — с префиксом группы.

        Ловит мутацию: статические проверки долгоживущих файлов идут только
        при расхождении с перечнем лока — случай «только .md, долгоживущий с
        запретом» проходит; файлы планки берутся только из диффа лока и
        головы — «только .md, планка с запретом» проходит; трассируемость
        `--from-branch` не видит удаления — проход.
        """
        self.run_cases(from_branch=True)


# ---------------------------------------------------------------- AC-18

class Ac18LongLivedRemovalTest(AmendSandbox):

    def test_ac18_removed_long_lived_test_only_there_refused(self):
        """Удаление долгоживущего файла с меткой, чей тест есть только в нём, — отказ «долгоживущие файлы tests/:» с «удаление снимает методы …», хотя критерий покрыт планкой.

        Сценарий: SPEC с одним критерием, планка (`.test.jsx`) и
        долгоживущий файл оба покрывают `AC-1` тестами с разными именами.
        Рабочая копия: долгоживущий файл удалён из рабочей копии;
        `--from-branch`: удалён коммитом кодовой ветки. Отказ с префиксом
        «долгоживущие файлы tests/:» и текстом «удаление снимает методы»;
        голова ссылки документов, голова кодовой ветки, `tests_locked_sha` и
        число записей «правка планки» прежние.

        Ловит мутацию: удаление сверяется только трассируемостью критериев —
        `AC-1` покрыт планкой, проход; имена тестов удалённого файла
        читаются разбором Python — имён нет, снимать нечего, проход.
        """
        for from_branch in (False, True):
            with self.subTest(from_branch=from_branch, seed=self.seed):
                t = self.locked(criteria=(1,), plank_numbers=(1,))
                if from_branch:
                    self.commit_code(t, t.long_rel, None)
                else:
                    self.wt_plank(t, t.plank)
                    (t.wt / t.long_rel).unlink()
                before = self.state_of(t)
                self.assert_refused(t, self.amend(t, from_branch), before, LONG,
                                    REMOVAL)


# ---------------------------------------------------------------- AC-19

class Ac19ValidLongLivedTest(AmendSandbox):

    def test_ac19_valid_long_lived_edit_accepted_in_both_paths(self):
        """Годная правка долгоживущего файла с меткой принята в обоих путях: лок сдвинут, перечень нового лока несёт сумму правленого файла.

        Сценарий: задача с локом; в долгоживущий файл добавлен ещё один
        годный тест `AC-1` с «Ловит мутацию»: (а) в рабочей копии —
        незакоммиченной правкой; (б) `--from-branch` — коммитом кодовой
        ветки. Проход: отказа нет, `tests_locked_sha` сдвинут на голову
        ссылки документов, записей «правка планки» на одну больше; перечень
        нового лока несёт SHA-256 правленого файла; в (а) голова кодовой
        ветки сдвинута коммитом правки.

        Ловит мутацию: долгоживущий файл с меткой проверяется прежним путём
        Python — строка группы `//` не найдена, отказ; перечень нового лока
        считается по прежней голове — сумма старого текста.
        """
        for from_branch in (False, True):
            with self.subTest(from_branch=from_branch, seed=self.seed):
                t = self.locked()
                edited = t.long_text + (
                    f"// Ловит мутацию: фикстура {self.word()} — сумма другая.\n"
                    f"it('AC-1: ещё {self.word()}', () => "
                    f"{{ expect(3).toBe(3); }});\n")
                if from_branch:
                    self.commit_code(t, t.long_rel, edited)
                else:
                    self.wt_plank(t, t.plank)
                    self.write_code(t, t.long_rel, edited)
                before = self.state_of(t)
                after = self.assert_passed(t, self.amend(t, from_branch), before)
                if not from_branch:
                    self.assertNotEqual(after[1], before[1], self.note(
                        "голова кодовой ветки не сдвинута"))
                digest = hashlib.sha256(edited.encode("utf-8")).hexdigest()
                self.assertEqual(self.manifest(t).get(t.long_rel), digest,
                                 self.note(f"перечень: {self.manifest(t)}"))


# ---------------------------------------------------------------- AC-23

class Ac23FromBranchCompositionTest(AmendSandbox):

    def test_ac23_from_branch_names_first_level_labelled_files_as_guard(self):
        """`--from-branch` проверяет файлы с меткой первого уровня тем же составом, что `guard.acceptance_test_files`: вложенный файл с меткой не назван.

        Сценарий: планка на голове ссылки документов — два-три файла
        `.test.jsx` первого уровня, файл `.test.jsx` во вложенном каталоге,
        помощник компонента `_<имя>.jsx`, `.md`, `test_*.py` со строкой
        группы; каждый файл с меткой несёт запрет (`5000` в аргументах). Отказ
        «строка группы:» называет каждый файл с меткой первого уровня
        строкой «<файл>:<строка>: … — запрещено в тексте планки» и не
        называет вложенный. Множество названных файлов с меткой совпадает
        с файлами с меткой, которые `guard.acceptance_test_files(tdir,
        правило)` даёт для той же планки на диске.

        Ловит мутацию: состав `--from-branch` — все `*.test.jsx` под
        `acceptance_tests/` на любой глубине — вложенный файл назван;
        только `test_*.py` (прежний `_test_files`) — файлы с меткой не
        названы, запреты не найдены.
        """
        t = self.locked(criteria=(1,), plank_numbers=(1,))
        rule = project_profile.plank_rule(self.name)
        top = [t.jsx] + [f"b{self.word()}.test.jsx"
                         for _ in range(self.rng.randint(1, 2))]
        nested = f"s{self.word(4)}/c{self.word()}.test.jsx"
        files = {name: self.plank_jsx((1,), ban=True) for name in top}
        files[nested] = self.plank_jsx((1,), ban=True)
        files[f"_{self.word()}.jsx"] = "export const helper = 1;\n"
        files[f"test_{self.word()}.py"] = (
            '"""Разовая фикстура.\n\nГруппа: разовый\nКрасен до реализации: '
            'фикстура ждёт кода.\n"""\nimport unittest\n\n\n'
            "class FixtureTest(unittest.TestCase):\n\n"
            "    def test_ac1_fixture(self):\n"
            '        """Фикстурный метод."""\n'
            "        self.assertEqual(2 + 2, 4)\n")
        self.docs_commit(t, files)
        before = self.state_of(t)
        out = self.assert_refused(t, self.amend(t, from_branch=True), before,
                                  GROUPS, guard.PLANK_BAN_TAIL)
        named = {rel for rel in [*top, nested]
                 if f"{PLANK_DIR}/{rel}:" in out}
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            for rel, text in {**t.plank, **files}.items():
                path = tdir / PLANK_DIR / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            by_guard = {str(Path(label).relative_to(PLANK_DIR))
                        for label, _text in guard.acceptance_test_files(tdir, rule)
                        if rule.is_labelled(Path(label).name)}
        context = self.note(f"названы {named}, guard {by_guard}\n{out}")
        self.assertEqual(named, set(top), context)
        self.assertEqual(named, by_guard, context)


if __name__ == "__main__":
    unittest.main()
