"""Выкладка планки компонента по `plank_layout`, форма `plank_layout`, исключение остатка из полного набора и `plank-run` по правилу планки проекта.

Группа: долгоживущий
Красен до реализации: выкладки по `plank_layout` нет — `run`/`collect`/`run_plank` гонят планку `pult-vitest` из каталога планки под tasks рабочей копии (или из `long_lived_dir/.artel-plank` при `runner: pytest-own`) с подкаталогом `acceptance_tests`, в выкладку попадают общие файлы и помощник, правило планки с `refusal`, форма `plank_layout` и отсутствие `plank_layout` у компонента не на pytest не отказывают, полный набор не получает `--ignore` родителя `<id>`, `drop_from_code_copy` остаток `plank_layout` не убирает, `plank-run` ищет только `test_*.py` и не отказывает узлу `::` компонента не на pytest; методы прежнего поведения (AC-9, AC-11 и прежние ветви AC-3, AC-5, AC-6, AC-7) зелены с рождения.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): записи
учебных проектов пишутся в `config.TARGETS` песочницы, клон проекта —
`tests.sandbox.make_project_repo` со своим `origin`, рабочая копия задачи
для `plank-run` — `workspace.ensure`. Профиль компонента — публичный вход
гейтов: `project_profile.decide(<проект>).profile` у записи с одним
компонентом и `project_profile.component_profiles(<проект>)` у учебного
проекта с двумя компонентами (`junit-xml` на pytest и `pult-vitest`).
Места прогона зовутся прежним каналом: `command=` у `acceptance.run`/
`collect`/`run_full_suite`/`full_suite`, `profile=`/`task_id=` у
`acceptance.run_plank`, `plank_run.cmd_plank_run` — как команда роли.

Раннеры подменены без Node и без сети шпионом `subprocess.Popen`: запуск
команды компонента (исполняемый файл `pytest` или иной файл учебного
каталога вне дерева, `node_modules/.bin/vitest`, раннер пульта `-m pytest`)
записывает argv, рабочий каталог, содержимое наблюдаемых каталогов
выкладки и `git status --porcelain --untracked-files=all` клона в момент
запуска, пишет заранее заданный отчёт (JUnit по `--junitxml`, JSON
отчётчика пульта по `--outputFile`) с зелёным или красным тестом и
отвечает настоящим коротким процессом с кодом сценария; сценарий
«исключение» роняет запуск `RuntimeError`. Поддельная установка
`install` кладёт `node_modules/.bin` в свой рабочий каталог. Прочие
вызовы (git) — настоящий `subprocess`.

Случай «..» в `plank_layout` запись `targets.yaml` не пропускает при
загрузке (`targets._template_path_error`), поэтому он подаётся профилем
`dataclasses.replace(<профиль>, plank_layout=…)` — тем же каналом
`command=`, которым место прогона получает профиль.

Имена проектов, компонентов, каталогов и файлов — из `random`, зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации в `orchestrator/acceptance.py`
и `orchestrator/plank_run.py` (удалён, не закоммичен): `run`/`collect`/
`run_plank` у компонента из `components:` с `report` берут файлы
компонента по `plank_rule`, отказывают `refusal` правила, формой
`plank_layout` и «нет plank_layout», выкладывают файлы (и `_pult.py` у
команды pytest) прямо в `plank_layout` после записи `/<родитель>/` в
`info/exclude` и убирают в `finally`; `_report_argv` исключает родителя
`<id>`; `drop_from_code_copy` убирает остаток; `plank-run` проверяет
правило, маску и узел `::` — все методы файла зелёные. Снятие записи в
`info/exclude` краснит AC-1 на статусе git в момент запуска.
"""
import dataclasses
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, config, idgen, plank_run,
                          project_profile, store, workspace)
from tests.sandbox import RealGitSandbox, artel_target_entry, make_project_repo

REAL_POPEN = subprocess.Popen
ALPHABET = "abcdefghijkmnpqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
TASKS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
HELPER = "_pult.py"
LAYOUT_DIR = ".artel-plank"
VITEST_BIN = project_profile.VITEST_BASE_ARGV[0]
VITEST_REPORT_ARGS = ["--reporter=default", "--reporter={pult_reporter}",
                      "--outputFile={path}"]

NO_LAYOUT = "у компонента {name} нет plank_layout — выкладка планки не определена"
NODE_REFUSAL = "узел :: у компонента {name} не поддерживается; передай файл"
NOT_NORMAL = "plank_layout должен быть нормализованным путём без «.» и «..»"
NOT_LAST = "<id> должен быть последним сегментом plank_layout"
OUTSIDE = "plank_layout вне рабочего каталога компонента {name}"
NOT_HIDDEN = ("родитель <id> в plank_layout должен быть скрытым каталогом "
              "(имя с точки)")
TRACKED_TAIL = "есть отслеживаемые git файлы — выкладка спрятала бы их"
OUTSIDE_NOTE_TEXT = ("long_lived_dir профиля «{lld}» лежит вне workdir "
                     "«{workdir}» — планка идёт прежним путём из "
                     + TASKS_DIR + "/<id>/" + PLANK_DIR + ", без выкладки")

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def quoted(items) -> str:
    """Потоковый список `yamlmini` — без кавычек."""
    return "[" + ", ".join(str(item) for item in items) + "]"


def block(fields: dict, indent: str) -> str:
    """Поля для `targets.yaml`: отображение — блоком (значения в
    кавычках), список — потоковым списком, прочее — как есть."""
    out = []
    for key, value in fields.items():
        if isinstance(value, dict):
            out.append(f"{indent}{key}:\n")
            out.extend(f'{indent}  {k}: "{v}"\n' for k, v in value.items())
        elif isinstance(value, (list, tuple)):
            out.append(f"{indent}{key}: {quoted(value)}\n")
        else:
            out.append(f"{indent}{key}: {value}\n")
    return "".join(out)


def entry(name: str, components: dict | None = None,
          profile: dict | None = None) -> str:
    """Запись проекта: `test_profile` либо `components:` по порядку."""
    text = ENTRY_HEAD.format(name=name)
    if profile is not None:
        return text + "    test_profile:\n" + block(profile, "      ")
    text += "    components:\n"
    for comp, fields in components.items():
        text += f"      {comp}:\n" + block(fields, "        ")
    return text


def is_pytest(parts: list) -> bool:
    return any(Path(p).name in ("pytest", "py.test") for p in parts) or any(
        a == "-m" and b == "pytest" for a, b in zip(parts, parts[1:]))


def arg_value(args: list, flag: str) -> str | None:
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(flag + "="):
            return arg[len(flag) + 1:]
    return None


def listing(folder: Path) -> dict | None:
    """{путь от `folder`: байты} файлов каталога без кеша байткода; `None`
    — каталога нет."""
    if not folder.is_dir():
        return None
    found = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_file() and "__pycache__" not in rel.split("/"):
            found[rel] = path.read_bytes()
    return found


def junit_report(green: bool) -> str:
    failure = "" if green else (
        '<failure type="AssertionError" message="boom">boom</failure>')
    return ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
            f'<testsuite name="pytest" failures="{0 if green else 1}" '
            'errors="0" skipped="0" tests="1"><testcase classname="x_test" '
            f'file="x_test.py" name="test_x" time="0.01">{failure}'
            '</testcase></testsuite></testsuites>')


def vitest_report(green: bool) -> str:
    return json.dumps({"tests": [{
        "file": "src/a.test.js", "name": "ok",
        "state": "pass" if green else "fail", "mode": "run", "fails": False,
        "retry_count": 0, "error_name": None if green else "AssertionError",
        "timeout": False, "hook": None, "duration_ms": 5}]})


class ComponentLayoutSandbox(RealGitSandbox):
    """Учебные проекты с компонентами, подменённые раннеры, шпион запусков."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        self.conn = store.db()
        self.add_synced_origin()
        fake = Path(tempfile.mkdtemp(prefix="artel-fake-")).resolve()
        self.addCleanup(shutil.rmtree, fake, True)
        self.pytest_cmd = fake / "pytest"
        self.runner_cmd = fake / f"run{self.word()}"
        self.installer = fake / f"install{self.word()}"
        for path in (self.pytest_cmd, self.runner_cmd, self.installer):
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)
        self.select_flag = f"--sel{self.word()}"
        self.vitest_version = self.accepted_version()
        self.entries: dict = {}
        self.write_targets()
        self.calls: list = []
        self.mode = "green"
        self.watch: list = []
        self.status_repo = None
        for patcher in (mock.patch.object(subprocess, "Popen", self.spy_popen),
                        mock.patch.dict(os.environ,
                                        {config.ARTEL_ROLE_ENV: ""})):
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ входы

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(ALPHABET) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def explain(self, output: str) -> str:
        calls = "\n".join(f"{c['kind']}: {c['argv']} @ {c['cwd']}"
                          for c in self.calls)
        return self.note(f"вывод:\n{output[-3000:]}\nзапуски:\n{calls}")

    def accepted_version(self) -> str:
        """Версия Vitest из таблицы пульта, принимающая
        `--expect.requireAssertions`."""
        for major, flags in project_profile.VITEST_VERSION_FLAGS.items():
            if flags.require_assertions:
                return f"{major}.{self.rng.randint(0, 9)}.{self.rng.randint(0, 9)}"
        self.fail(self.note("в таблице версий Vitest нет принимающей "
                            "--expect.requireAssertions"))

    # ------------------------------------------------------------ записи

    def write_targets(self) -> None:
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry() + "".join(self.entries.values()),
            encoding="utf-8")

    def set_entry(self, name: str, components: dict | None = None,
                  profile: dict | None = None) -> None:
        self.entries[name] = entry(name, components, profile)
        self.write_targets()

    def commit_to_main(self, clone: Path, files: dict) -> None:
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def vitest_fields(self, wd: str, layout: str | None,
                      tests: bool = True) -> dict:
        prefix = f"{wd}/" if wd else ""
        fields = {"command": list(project_profile.VITEST_BASE_ARGV),
                  "long_lived_dir": f"{prefix}src",
                  "long_lived_name": "<id>_<name>.test.js",
                  "weakening_scope": [f"{prefix}src/**"],
                  "mutation_claim_scope": [f"{prefix}src/**"],
                  "report": "pult-vitest",
                  "report_args": VITEST_REPORT_ARGS,
                  "failure_errors": ["AssertionError"],
                  "select": [self.select_flag, "{tests}"],
                  "install": [str(self.installer)],
                  "tools": {"vitest": self.vitest_version}}
        if tests:
            fields["tests"] = [f"{prefix}src/**/*.test.jsx"]
        if wd:
            fields.update(runner="pytest-own", workdir=wd)
        if layout:
            fields["plank_layout"] = layout
        return fields

    def vitest_files(self, wd: str) -> dict:
        prefix = f"{wd}/" if wd else ""
        return {f"{prefix}package.json": '{"name": "web"}\n',
                f"{prefix}vitest.config.js": "export default {}\n",
                f"{prefix}package-lock.json": json.dumps(
                    {"lockfileVersion": 3, "seed": self.word()}) + "\n",
                f"{prefix}src/a.test.js": "// тест\n"}

    def junit_fields(self, wd: str, lld: str, *, pytest: bool = True,
                     own: bool = True, report: bool = True,
                     layout: str | None = None, tests=None) -> dict:
        fields = {"command": [str(self.pytest_cmd if pytest else self.runner_cmd)],
                  "long_lived_dir": lld,
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": [f"{lld}/**"],
                  "mutation_claim_scope": [f"{lld}/**"]}
        if report:
            fields["report"] = "junit-xml"
        if own:
            fields.update(runner="pytest-own", workdir=wd)
        if tests:
            fields["tests"] = tests
        if layout:
            fields["plank_layout"] = layout
        return fields

    def vitest_case(self, layout=True, tests: bool = True,
                    workdir: bool = True) -> dict:
        """Проект с одним компонентом `pult-vitest`; `layout=True` —
        `plank_layout` `<workdir>/src/.<скрытый>/<id>`."""
        name, comp = f"v{self.word()}", f"cv{self.word(5)}"
        wd = f"web{self.word(5)}" if workdir else ""
        if layout is True:
            layout = f"{wd + '/' if wd else ''}src/.pv{self.word(5)}/<id>"
        fields = self.vitest_fields(wd, layout or None, tests)
        self.set_entry(name, {comp: fields})
        clone = make_project_repo(name)
        self.commit_to_main(clone, self.vitest_files(wd))
        return {"name": name, "comp": comp, "wd": wd, "layout": layout or "",
                "clone": clone, "fields": fields, "profile": self.profile(name)}

    def junit_case(self, layout=True, *, pytest: bool = True, own: bool = True,
                   report: bool = True, tests=None,
                   test_profile: bool = False) -> dict:
        """Проект с одним компонентом `junit-xml` (или записью
        `test_profile`); `long_lived_dir` — внутри `workdir`; `layout=True`
        — `plank_layout` `<workdir>/.<скрытый>/<id>`."""
        name, comp = f"j{self.word()}", f"cj{self.word(5)}"
        wd = f"py{self.word(5)}" if own else ""
        lld = f"{wd}/t{self.word(5)}" if wd else f"t{self.word(5)}"
        if layout is True:
            layout = f"{wd + '/' if wd else ''}.pj{self.word(5)}/<id>"
        fields = self.junit_fields(wd, lld, pytest=pytest, own=own,
                                   report=report, layout=layout or None,
                                   tests=tests)
        if test_profile:
            fields.pop("plank_layout", None)
            self.set_entry(name, profile=fields)
        else:
            self.set_entry(name, {comp: fields})
        clone = make_project_repo(name)
        self.commit_to_main(clone, {f"{lld}/test_base.py":
                                    "def test_base():\n    pass\n"})
        return {"name": name, "comp": comp, "wd": wd, "lld": lld,
                "layout": layout or "", "clone": clone, "fields": fields,
                "profile": self.profile(name)}

    def two_components(self) -> dict:
        """Учебный проект с двумя компонентами: `junit-xml` на pytest и
        `pult-vitest`, у каждого свой `workdir` и свой `plank_layout`."""
        name = f"d{self.word()}"
        jcomp, vcomp = f"cj{self.word(5)}", f"cv{self.word(5)}"
        jwd, vwd = f"py{self.word(5)}", f"web{self.word(5)}"
        jlayout = f"{jwd}/.pj{self.word(5)}/<id>"
        vlayout = f"{vwd}/src/.pv{self.word(5)}/<id>"
        jfields = {"command": [str(self.pytest_cmd)], "report": "junit-xml",
                   "runner": "pytest-own", "workdir": jwd,
                   "tests": [f"{jwd}/tests/test_*.py"],
                   "plank_layout": jlayout, "paths": [f"^{jwd}/"]}
        vfields = self.vitest_fields(vwd, vlayout)
        vfields["paths"] = [f"^{vwd}/"]
        self.set_entry(name, {jcomp: jfields, vcomp: vfields})
        clone = make_project_repo(name)
        files = self.vitest_files(vwd)
        files[f"{jwd}/tests/test_base.py"] = "def test_base():\n    pass\n"
        self.commit_to_main(clone, files)
        profiles = {p.component: p
                    for p in project_profile.component_profiles(name)}
        self.assertEqual(set(profiles), {jcomp, vcomp}, self.note(str(profiles)))
        return {"name": name, "clone": clone,
                "junit": {"comp": jcomp, "wd": jwd, "layout": jlayout,
                          "profile": profiles[jcomp], "clone": clone},
                "vitest": {"comp": vcomp, "wd": vwd, "layout": vlayout,
                           "profile": profiles[vcomp], "clone": clone}}

    def profile(self, name: str):
        decision = project_profile.decide(name)
        self.assertIsNotNone(decision.profile, self.note(
            f"профиль {name} не получен: {decision.refusal}\n"
            f"{config.TARGETS.read_text(encoding='utf-8')}"))
        return decision.profile

    # ------------------------------------------------------------ задачи

    def task(self, name: str) -> str:
        task_id = idgen.new_task_id()
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          "in_dev", f"task/{task_id.lower()}-{self.word()}",
                          name, config.DEFAULT_BUDGET_USD)
        return task_id

    def lay_plank(self, root: Path, task_id: str, files: dict) -> Path:
        """Каталог планки задачи под tasks дерева `root` — так, как его
        кладёт пульт перед прогоном; возврат — каталог задачи."""
        tdir = root / TASKS_DIR / task_id
        for rel, text in files.items():
            path = tdir / PLANK_DIR / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return tdir

    def layout_dir(self, case: dict, task_id: str, root: Path | None = None
                   ) -> Path:
        return (root or case["clone"]) / case["layout"].replace("<id>", task_id)

    def ws_task(self, name: str, state: str = "tests_writing") -> str:
        """Задача проекта с рабочей копией кода (`workspace.ensure`)."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}", state,
                          branch, name, config.DEFAULT_BUDGET_USD)
        _wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        return task_id

    def wt(self, task_id: str, name: str) -> Path:
        return workspace.path(task_id, name)

    def docs_plank(self, task_id: str, name: str) -> Path:
        return config.PROJECTS / name / TASKS_DIR / task_id / PLANK_DIR

    def draft(self, task_id: str, name: str, files: dict) -> None:
        for rel, text in files.items():
            path = self.docs_plank(task_id, name) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def plank_run_cmd(self, task_id: str, arg: str | None = None) -> tuple:
        """(код, текст отказа `SystemExit`, весь вывод) `plank-run`."""
        self.calls = []
        out = io.StringIO()
        code = None
        with redirect_stdout(out), redirect_stderr(out):
            try:
                plank_run.cmd_plank_run(task_id, arg)
            except SystemExit as exc:
                code = exc.code
        message = "" if code is None or isinstance(code, int) else str(code)
        status = code if isinstance(code, int) else (0 if code is None else 1)
        return status, message, f"{out.getvalue()}\n{message}"

    # ------------------------------------------------------------ запуски

    def status(self, repo: Path) -> str:
        return self.git("-C", str(repo), "status", "--porcelain",
                        "--untracked-files=all")

    def answer(self, code: int, out: str, args, kwargs):
        script = f"import sys; sys.stdout.write({out!r}); sys.exit({code})"
        return REAL_POPEN([sys.executable, "-c", script], *args, **kwargs)

    def spy_popen(self, argv, *args, **kwargs):
        if not isinstance(argv, (list, tuple)) or not argv:
            return REAL_POPEN(argv, *args, **kwargs)
        parts = [str(a) for a in argv]
        head = parts[0]
        if head == str(self.installer):
            cwd = Path(str(kwargs.get("cwd") or os.getcwd()))
            (cwd / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)
            return self.answer(0, "", args, kwargs)
        if head in (str(self.pytest_cmd), str(self.runner_cmd)):
            kind = "junit"
        elif head == VITEST_BIN:
            kind = "vitest"
        elif is_pytest(parts):
            kind = "pult"
        else:
            return REAL_POPEN(argv, *args, **kwargs)
        if kind == "vitest" and parts[1:2] == ["--version"]:
            return self.answer(0, f"vitest/{self.vitest_version}\n", args, kwargs)
        cwd = os.path.realpath(str(kwargs.get("cwd") or os.getcwd()))
        self.calls.append({
            "kind": kind, "argv": parts, "cwd": cwd,
            "watch": {str(p): listing(p) for p in self.watch},
            "status": (self.status(self.status_repo)
                       if self.status_repo is not None else None)})
        if self.mode == "boom":
            raise RuntimeError(f"сбой внутри прогона (зерно {self.seed})")
        green = self.mode == "green"
        if kind == "junit":
            path = arg_value(parts, "--junitxml")
            body = junit_report(green)
        else:
            path = arg_value(parts, "--outputFile")
            body = vitest_report(green)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(body, encoding="utf-8")
        out = "1 passed in 0.01s\n" if green else "1 failed in 0.01s\n"
        return self.answer(0 if green else 1, out, args, kwargs)

    def runs(self, kind: str) -> list:
        return [c for c in self.calls if c["kind"] == kind]

    def place(self, fn: str, case: dict, task_id: str, tdir: Path,
              root: Path | None = None, extra=()) -> tuple:
        """(зелено, вывод) места прогона `fn` по планке каталога `tdir`."""
        root = root or case["clone"]
        if fn == "run":
            return acceptance.run(tdir, cwd=root, extra=list(extra),
                                  command=case["profile"])
        if fn == "collect":
            return acceptance.collect(tdir, cwd=root, extra=list(extra),
                                      command=case["profile"])
        target = os.path.relpath(tdir / PLANK_DIR, root)
        code, output = acceptance.run_plank([target], root,
                                            profile=case["profile"],
                                            task_id=task_id)
        return code == 0, output

    def resolved_after(self, call: dict, flag: str) -> set:
        """Пути-аргументы после `flag` в argv, разрешённые от `cwd`."""
        argv = call["argv"]
        if flag not in argv:
            return set()
        return {os.path.realpath(os.path.join(call["cwd"], a))
                for a in argv[argv.index(flag) + 1:] if not a.startswith("-")}

    def full_suite_argv(self, profile, root: Path) -> list:
        """argv единственного запуска раннера компонента полного набора
        `run_full_suite`."""
        self.calls = []
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            ok, output = acceptance.run_full_suite(root, command=profile)
        runs = [c for c in self.calls if c["kind"] in ("junit", "vitest")]
        self.assertEqual(len(runs), 1, self.explain(output))
        return runs[0]["argv"]


# ---------------------------------------------------------------- AC-1

class Ac1VitestLayoutPlacesTest(ComponentLayoutSandbox):

    def vitest_place(self, fn: str) -> None:
        """Общий сценарий AC-1 для одного места прогона `fn`."""
        case = self.vitest_case()
        clone = case["clone"]
        for mode in ("green", "red", "boom"):
            with self.subTest(place=fn, mode=mode, seed=self.seed):
                task_id = self.task(case["name"])
                test_file = f"ac1{self.word()}.test.jsx"
                tdir = self.lay_plank(clone, task_id, {
                    test_file: "// AC-1: тест\n",
                    f"_h{self.word()}.jsx": "// помощник\n",
                    f"n{self.word()}.md": "заметка\n",
                    HELPER: "TASK_ID = ''\n"})
                layout = self.layout_dir(case, task_id)
                before = self.status(clone)
                self.calls, self.mode = [], mode
                self.watch, self.status_repo = [layout], clone
                ok, output, error = None, "", None
                try:
                    ok, output = self.place(fn, case, task_id, tdir)
                except RuntimeError as exc:
                    error, output = exc, str(exc)
                finally:
                    self.mode, self.watch, self.status_repo = "green", [], None
                runs = self.runs("vitest")
                self.assertEqual(len(runs), 1, self.explain(output))
                seen = runs[0]["watch"][str(layout)]
                self.assertIsNotNone(seen, self.explain(
                    f"каталога {layout} нет на запуске раннера"))
                self.assertIn(test_file, seen, self.explain(
                    f"файл компонента не лежит прямо в plank_layout: {sorted(seen)}"))
                self.assertFalse([r for r in seen if r.startswith(PLANK_DIR + "/")],
                                 self.explain(f"подкаталог {PLANK_DIR}: {sorted(seen)}"))
                self.assertIn(os.path.realpath(layout / test_file),
                              self.resolved_after(runs[0], self.select_flag),
                              self.explain("файл выкладки не передан через select"))
                self.assertFalse([a for a in runs[0]["argv"] if PLANK_DIR in a],
                                 self.explain("цель под каталогом планки"))
                self.assertEqual(runs[0]["status"], before, self.explain(
                    f"выкладка видна git status:\n{runs[0]['status']}"))
                self.assertFalse(layout.exists(),
                                 self.explain("выкладка не убрана"))
                self.assertEqual(self.status(clone), before,
                                 self.explain("git status после прогона другой"))
                if mode == "boom":
                    self.assertIsInstance(error, RuntimeError, self.explain(output))
                else:
                    self.assertIsNone(error, self.explain(output))
                    expected = True if fn == "collect" else mode == "green"
                    self.assertEqual(ok, expected, self.explain(output))

    def test_ac1_run_vitest_from_plank_layout_hidden_and_cleaned(self):
        """`acceptance.run` компонента `pult-vitest` гонит файлы, выложенные прямо в `plank_layout`, и убирает выкладку на любом исходе.

        Сценарий: проект с одним компонентом `pult-vitest` (`workdir`,
        `select` с флагом-меткой, `plank_layout` `<workdir>/src/.<скрытый>/<id>`),
        планка задачи под tasks клона — тест `*.test.jsx`, помощник
        `_*.jsx`, заметка `.md` и помощник пульта. Раннер отвечает
        зелёным, красным отчётом и исключением. На запуске раннера файл
        теста лежит прямо в каталоге `plank_layout` с подставленным id (без
        подкаталога `acceptance_tests`), путь этого файла стоит в argv после
        аргументов `select`, `git status` клона равен исходному; после
        возврата (и после исключения) каталога выкладки нет, `git status`
        прежний, исход — зелёный только у зелёного отчёта.

        Ловит мутацию: выкладка `pult-vitest` по-прежнему под
        `long_lived_dir/.artel-plank` или с подкаталогом `acceptance_tests`
        — каталога `plank_layout` нет на запуске либо в нём подкаталог;
        цель передаётся без `select` — пути нет после флага-метки; шаблон
        родителя не дописан в `info/exclude` до записи файлов — строка `??`
        в статусе на запуске; уборка не в `finally` — каталог выкладки
        остаётся после исключения.
        """
        self.vitest_place("run")

    def test_ac1_collect_vitest_from_plank_layout_hidden_and_cleaned(self):
        """`acceptance.collect` компонента `pult-vitest` собирает файлы из `plank_layout` и убирает выкладку на любом исходе.

        Сценарий: тот же, что у `run`, место — сухой сбор: на запуске
        раннера файл теста прямо в `plank_layout`, передан через `select`,
        выкладка не видна `git status`; после зелёного, красного отчёта и
        исключения каталога выкладки нет, статус прежний; сбор с отчётом,
        назвавшим тест, — «собралось».

        Ловит мутацию: `collect` не переведён на выкладку по `plank_layout`
        — цель под каталогом планки, каталога выкладки нет на запуске;
        уборка `collect` пропущена на исключении — каталог остаётся.
        """
        self.vitest_place("collect")

    def test_ac1_run_plank_vitest_from_plank_layout_hidden_and_cleaned(self):
        """`acceptance.run_plank` с `task_id` у компонента `pult-vitest` гонит выкладку `plank_layout` и убирает её на любом исходе.

        Сценарий: тот же, место — `run_plank` с целью — каталогом планки
        под tasks клона (путь от клона, как его передаёт `plank-run`): на
        запуске раннера файл теста прямо в `plank_layout`, передан через
        `select`, выкладка не видна `git status`; после зелёного, красного
        отчёта и исключения каталога выкладки нет; код 0 — только у
        зелёного отчёта.

        Ловит мутацию: цель `run_plank` не переводится в путь выкладки —
        в argv путь под каталогом планки; выкладка `run_plank` идёт
        прежним путём `long_lived_dir/.artel-plank` — каталога
        `plank_layout` нет на запуске.
        """
        self.vitest_place("run_plank")


# ---------------------------------------------------------------- AC-2

class Ac2LayoutContentsTest(ComponentLayoutSandbox):

    def test_ac2_layout_holds_only_component_files_helper_only_for_pytest(self):
        """Выкладка каждого компонента учебного проекта с двумя компонентами — только его файлы; помощник `_pult.py` — только у `junit-xml` на pytest.

        Сценарий: проект с компонентами `junit-xml` (команда `pytest`,
        маска `tests/test_*.py`) и `pult-vitest` (маска `*.test.jsx`), у
        каждого свой `plank_layout`. Планка: тест и помощник `_*.py`
        pytest-компонента, тест `*.test.jsx` и помощник `_*.jsx`
        vitest-компонента, `.md`, `.txt` и `_pult.py`. `acceptance.run` с
        профилем каждого компонента: на запуске раннера в каталоге его
        `plank_layout` ровно его файлы — у `junit-xml` тест, `_*.py` и
        `_pult.py`, у `pult-vitest` тест `*.test.jsx` и `_*.jsx`, без
        `.md`/`.txt` и без помощника пульта.

        Ловит мутацию: выкладка копирует каталог планки целиком — в ней
        чужие файлы, `.md`, `.txt`; помощник кладётся всем компонентам —
        `_pult.py` в выкладке `pult-vitest`; помощник не кладётся вовсе —
        его нет у `junit-xml`; файл компонента выбирается по маске без
        правила — помощник `_*.jsx` выпадает из выкладки.
        """
        case = self.two_components()
        names = {"jtest": f"test_ac2_{self.word()}.py",
                 "jhelp": f"_u{self.word()}.py",
                 "vtest": f"ac2{self.word()}.test.jsx",
                 "vhelp": f"_h{self.word()}.jsx",
                 "md": f"n{self.word()}.md", "txt": f"l{self.word()}.txt"}
        files = {name: f"# {key}\n" for key, name in names.items()}
        files[HELPER] = "TASK_ID = ''\n"
        expected = {"junit": {names["jtest"], names["jhelp"], HELPER},
                    "vitest": {names["vtest"], names["vhelp"]}}
        for kind in ("junit", "vitest"):
            with self.subTest(component=kind, seed=self.seed):
                comp = case[kind]
                task_id = self.task(case["name"])
                tdir = self.lay_plank(case["clone"], task_id, files)
                layout = self.layout_dir(comp, task_id)
                self.calls, self.watch = [], [layout]
                try:
                    _ok, output = self.place("run", comp, task_id, tdir)
                finally:
                    self.watch = []
                runs = self.runs(kind)
                self.assertEqual(len(runs), 1, self.explain(output))
                seen = runs[0]["watch"][str(layout)]
                self.assertIsNotNone(seen, self.explain(f"выкладки {layout} нет"))
                self.assertEqual(set(seen), expected[kind], self.explain(
                    f"состав выкладки {comp['comp']}: {sorted(seen)}"))


# ---------------------------------------------------------------- AC-3

class Ac3RuleRefusalTest(ComponentLayoutSandbox):

    def test_ac3_rule_refusal_stops_every_place_without_run(self):
        """Правило планки с `refusal` отказывает `run`, `collect`, `run_plank` и `plank-run` текстом отказа; раннер не запускается.

        Сценарий: проект с одним компонентом `pult-vitest` без `tests`
        (правило планки проекта несёт `refusal`) и с `plank_layout`;
        планка — тест `*.test.jsx`. Каждое из трёх мест: исход не зелёный,
        вывод несёт текст `refusal` правила, раннер Vitest не запускался.
        Задача того же проекта в `tests_writing` с тем же черновиком:
        `plank-run` завершается ненулевым кодом с текстом `refusal`, раннер
        не запускался.

        Ловит мутацию: правило планки не спрашивается перед выкладкой —
        раннер запускается, исход зелёный по отчёту; `plank-run` сверяет
        планку без правила — прогон идёт, текста отказа нет.
        """
        case = self.vitest_case(tests=False)
        refusal = project_profile.plank_rule(case["name"]).refusal
        self.assertTrue(refusal, self.note("правило без отказа"))
        files = {f"ac3{self.word()}.test.jsx": "// AC-3\n"}
        for fn in ("run", "collect", "run_plank"):
            with self.subTest(place=fn, seed=self.seed):
                task_id = self.task(case["name"])
                tdir = self.lay_plank(case["clone"], task_id, files)
                self.calls = []
                ok, output = self.place(fn, case, task_id, tdir)
                self.assertFalse(ok, self.explain(output))
                self.assertIn(refusal, output, self.explain(output))
                self.assertEqual(self.runs("vitest"), [], self.explain(output))
        with self.subTest(place="plank-run", seed=self.seed):
            task_id = self.ws_task(case["name"])
            self.draft(task_id, case["name"], files)
            status, _message, output = self.plank_run_cmd(task_id)
            self.assertNotEqual(status, 0, self.explain(output))
            self.assertIn(refusal, output, self.explain(output))
            self.assertEqual(self.runs("vitest"), [], self.explain(output))

    def test_ac3_extra_only_run_unchanged_under_rule_refusal(self):
        """Прогон только `extra` без файлов планки при правиле с `refusal` — тот же исход и тот же вывод, что без отказа правила.

        Сценарий: проект с одним компонентом `pult-vitest` с
        `plank_layout`; каталога планки задачи нет, `extra` — файл
        `long_lived_dir` клона. `acceptance.run` дважды на том же клоне:
        запись без `tests` (правило с `refusal`) и та же запись с `tests`
        (правило без отказа). Исходы и выводы совпадают побайтно, исход
        зелёный, текста `refusal` в выводе нет, раннер запущен по разу с
        одним и тем же argv (без пути файла отчёта).

        Ловит мутацию: отказ правила проверяется до ветви прогона только
        `extra` — первый вызов не зелёный с текстом отказа, раннер не
        запущен; ветвь `extra` начинает зависеть от правила — выводы или
        argv различаются.
        """
        case = self.vitest_case(tests=False)
        task_id = self.task(case["name"])
        tdir = case["clone"] / TASKS_DIR / task_id
        extra = [f"{case['wd']}/src/a.test.js"]
        seen = {}
        for label, tests in (("refusal", False), ("rule", True)):
            with self.subTest(record=label, seed=self.seed):
                self.set_entry(case["name"], {case["comp"]: self.vitest_fields(
                    case["wd"], case["layout"], tests)})
                rule = project_profile.plank_rule(case["name"])
                self.assertEqual(bool(rule.refusal), not tests, self.note(label))
                profile = self.profile(case["name"])
                self.calls = []
                ok, output = acceptance.run(tdir, cwd=case["clone"], extra=extra,
                                            command=profile)
                runs = self.runs("vitest")
                self.assertEqual(len(runs), 1, self.explain(output))
                argv = [a for a in runs[0]["argv"]
                        if not a.startswith("--outputFile")]
                seen[label] = (ok, output, argv)
                self.assertTrue(ok, self.explain(output))
                if rule.refusal:
                    self.assertNotIn(rule.refusal, output, self.explain(output))
        self.assertEqual(seen["refusal"], seen["rule"], self.note(
            f"исходы различаются:\n{seen}"))


# ---------------------------------------------------------------- AC-4

class Ac4LayoutShapeRefusalsTest(ComponentLayoutSandbox):

    def test_ac4_layout_shape_refusals_verbatim_without_run(self):
        """Каждый из пяти случаев формы `plank_layout` — отказ подготовки дословным текстом; раннер не запускается.

        Сценарий: проект с одним компонентом `junit-xml` на pytest
        (`runner: pytest-own`, случайный `workdir`). Для каждого значения
        `plank_layout` — `run`, `collect` и `run_plank` по планке из
        одного теста: исход не зелёный, вывод несёт ожидаемый текст, раннер
        не запускался. Значения: `a/./<id>` и `.artel-plank/../src/<id>` —
        «нормализованным путём»; `<id>` в среднем сегменте и сегмент
        `<id>` с хвостом — «последним сегментом»; путь вне `workdir`
        текстом и путь внутри `workdir` через символьную ссылку наружу —
        «вне рабочего каталога компонента <имя>»; родитель без точки —
        «скрытым каталогом»; родитель с закоммиченным файлом — «в каталоге
        <родитель> есть отслеживаемые git файлы — …».

        Ловит мутацию: пропущена одна из проверок формы — для её значения
        выкладка идёт и раннер запускается; сверка `workdir` текстом, а не
        по `realpath` — путь через ссылку наружу проходит; `<id>` ищется
        в любом сегменте — среднее положение проходит; текст отказа иной —
        строки нет в выводе.
        """
        case = self.junit_case(layout=False)
        wd, clone, comp = case["wd"], case["clone"], case["comp"]
        hidden = f".pl{self.word(5)}"
        outside = Path(tempfile.mkdtemp(prefix="artel-outside-")).resolve()
        self.addCleanup(shutil.rmtree, outside, True)
        link = f"l{self.word(5)}"
        os.symlink(outside, clone / wd / link)
        tracked = f".pt{self.word(5)}"
        self.commit_to_main(clone, {f"{wd}/{tracked}/k{self.word()}.txt": "код\n"})
        cases = [
            ("a/./<id>", NOT_NORMAL),
            (".artel-plank/../src/<id>", NOT_NORMAL),
            (f"{wd}/{hidden}/<id>/x{self.word(4)}", NOT_LAST),
            (f"{wd}/{hidden}/<id>z{self.word(4)}", NOT_LAST),
            (f"o{self.word(5)}/{hidden}/<id>", OUTSIDE.format(name=comp)),
            (f"{wd}/{link}/{hidden}/<id>", OUTSIDE.format(name=comp)),
            (f"{wd}/s{self.word(5)}/<id>", NOT_HIDDEN),
            (f"{wd}/{tracked}/<id>", None),
        ]
        for layout, text in cases:
            profile = dataclasses.replace(case["profile"], plank_layout=layout)
            if ".." not in layout.split("/"):
                self.set_entry(case["name"], {comp: dict(case["fields"],
                                                         plank_layout=layout)})
                profile = self.profile(case["name"])
            this = dict(case, profile=profile)
            for fn in ("run", "collect", "run_plank"):
                with self.subTest(plank_layout=layout, place=fn, seed=self.seed):
                    task_id = self.task(case["name"])
                    tdir = self.lay_plank(clone, task_id, {
                        f"test_ac4_{self.word()}.py": "def test_x():\n    pass\n",
                        HELPER: "TASK_ID = ''\n"})
                    self.calls = []
                    ok, output = self.place(fn, this, task_id, tdir)
                    self.assertFalse(ok, self.explain(output))
                    if text is None:
                        lines = [line for line in output.splitlines()
                                 if line.endswith(TRACKED_TAIL)
                                 or (TRACKED_TAIL + " ") in line]
                        self.assertTrue(lines, self.explain(output))
                        self.assertTrue(any(f"в каталоге " in line
                                            and tracked in line
                                            for line in lines),
                                        self.explain(output))
                    else:
                        self.assertIn(text, output, self.explain(output))
                    self.assertEqual(self.runs("junit"), [], self.explain(output))


# ---------------------------------------------------------------- AC-5

class Ac5NoLayoutCasesTest(ComponentLayoutSandbox):

    def test_ac5_non_pytest_component_with_report_without_layout_refused(self):
        """Компонент с `report`, команда не pytest, без `plank_layout` — отказ «нет plank_layout» на каждом месте; раннер не запускается.

        Сценарий: три записи с одним компонентом без `plank_layout`, у
        каждой планка с файлом этого компонента: `pult-vitest` с
        `runner: pytest-own` и `workdir`, `pult-vitest` в корне без
        `runner`, `junit-xml` с командой — не pytest (`runner:
        pytest-own`). `run`, `collect`, `run_plank`: исход не зелёный,
        вывод несёт «у компонента <имя> нет plank_layout — выкладка
        планки не определена», раннер не запускался.

        Ловит мутацию: случай решается по `runner`, а не по команде —
        `pult-vitest` с `runner: pytest-own` получает выкладку под
        `long_lived_dir/.artel-plank` и запускается; отказ пропущен у
        компонента в корне — планка гонится из каталога под tasks; отказ
        ограничен `pult-vitest` — `junit-xml` не на pytest запускается.
        """
        cases = [("vitest-own", self.vitest_case(layout=None),
                  f"ac5{self.word()}.test.jsx", "vitest"),
                 ("vitest-root", self.vitest_case(layout=None, workdir=False),
                  f"ac5{self.word()}.test.jsx", "vitest"),
                 ("junit-not-pytest", self.junit_case(layout=None, pytest=False),
                  f"test_ac5_{self.word()}.py", "junit")]
        for label, case, test_file, kind in cases:
            text = NO_LAYOUT.format(name=case["comp"])
            for fn in ("run", "collect", "run_plank"):
                with self.subTest(case=label, place=fn, seed=self.seed):
                    task_id = self.task(case["name"])
                    tdir = self.lay_plank(case["clone"], task_id,
                                          {test_file: "// AC-5\n"})
                    self.calls = []
                    ok, output = self.place(fn, case, task_id, tdir)
                    self.assertFalse(ok, self.explain(output))
                    self.assertIn(text, output, self.explain(output))
                    self.assertEqual(self.runs(kind), [], self.explain(output))

    def test_ac5_pytest_component_without_layout_keeps_long_lived_layout(self):
        """Компонент `junit-xml` на pytest без `plank_layout` — прежняя выкладка `<long_lived_dir>/.artel-plank/<id>/acceptance_tests` с побайтной копией планки.

        Сценарий: запись с одним компонентом `junit-xml`, команда
        `pytest`, `runner: pytest-own`, `long_lived_dir` внутри
        `workdir`, без `plank_layout`; планка — тест, `.md` и помощник
        пульта. `run`, `collect`, `run_plank`: раннер запущен один раз,
        в момент запуска каталог
        `<long_lived_dir>/.artel-plank/<id>/acceptance_tests` побайтно
        равен каталогу планки, текста «нет plank_layout» в выводе нет.

        Ловит мутацию: третий случай требования 5 задевает и команду
        pytest — отказ «нет plank_layout», раннер не запущен; прежняя
        выкладка фильтрует файлы по правилу — `.md` выпадает из копии.
        """
        case = self.junit_case(layout=None)
        text = NO_LAYOUT.format(name=case["comp"])
        for fn in ("run", "collect", "run_plank"):
            with self.subTest(place=fn, seed=self.seed):
                task_id = self.task(case["name"])
                files = {f"test_ac5_{self.word()}.py": "def test_x():\n    pass\n",
                         f"n{self.word()}.md": "заметка\n",
                         HELPER: "TASK_ID = ''\n"}
                tdir = self.lay_plank(case["clone"], task_id, files)
                layout = (case["clone"] / case["lld"] / LAYOUT_DIR / task_id
                          / PLANK_DIR)
                self.calls, self.watch = [], [layout]
                try:
                    _ok, output = self.place(fn, case, task_id, tdir)
                finally:
                    self.watch = []
                self.assertNotIn(text, output, self.explain(output))
                runs = self.runs("junit")
                self.assertEqual(len(runs), 1, self.explain(output))
                self.assertEqual(runs[0]["watch"][str(layout)],
                                 listing(tdir / PLANK_DIR), self.explain(output))

    def test_ac5_no_report_and_test_profile_not_refused(self):
        """Компонент без `report` и запись `test_profile` с командой не pytest без `plank_layout` отказа «нет plank_layout» не получают и запускаются.

        Сценарий: запись `components:` с компонентом без `report`
        (команда — не pytest, `runner: pytest-own`) и запись `test_profile`
        с `report: junit-xml` и той же командой; планка — тест
        `test_*.py`. `run`, `collect`, `run_plank`: текста «нет
        plank_layout» в выводе нет, раннер запущен ровно раз.

        Ловит мутацию: третий случай требования 5 применяется без
        проверки `components:` и `report` — `test_profile` и компонент без
        `report` получают отказ, раннер не запущен.
        """
        cases = [("no-report", self.junit_case(layout=None, pytest=False,
                                               report=False)),
                 ("test-profile", self.junit_case(layout=None, pytest=False,
                                                  test_profile=True))]
        for label, case in cases:
            text = NO_LAYOUT.format(name=case["comp"])
            for fn in ("run", "collect", "run_plank"):
                with self.subTest(case=label, place=fn, seed=self.seed):
                    task_id = self.task(case["name"])
                    tdir = self.lay_plank(case["clone"], task_id, {
                        f"test_ac5_{self.word()}.py": "def test_x():\n    pass\n"})
                    self.calls = []
                    _ok, output = self.place(fn, case, task_id, tdir)
                    self.assertNotIn("нет plank_layout", output,
                                     self.explain(output))
                    self.assertNotIn(text, output, self.explain(output))
                    self.assertEqual(len(self.runs("junit")), 1,
                                     self.explain(output))

    def test_ac5_vitest_without_tests_and_layout_gets_rule_refusal(self):
        """`pult-vitest` без `tests` и без `plank_layout` получает текст отказа правила планки, а не «нет plank_layout».

        Сценарий: запись с одним компонентом `pult-vitest` без `tests` и
        без `plank_layout`; планка — тест `*.test.jsx`. `run`, `collect`,
        `run_plank`: исход не зелёный, вывод несёт `refusal` правила
        планки проекта и не несёт «у компонента <имя> нет plank_layout»;
        раннер не запускался.

        Ловит мутацию: отказ «нет plank_layout» проверяется раньше отказа
        правила — в выводе текст «нет plank_layout» вместо текста правила.
        """
        case = self.vitest_case(layout=None, tests=False)
        refusal = project_profile.plank_rule(case["name"]).refusal
        self.assertTrue(refusal, self.note("правило без отказа"))
        for fn in ("run", "collect", "run_plank"):
            with self.subTest(place=fn, seed=self.seed):
                task_id = self.task(case["name"])
                tdir = self.lay_plank(case["clone"], task_id, {
                    f"ac5{self.word()}.test.jsx": "// AC-5\n"})
                self.calls = []
                ok, output = self.place(fn, case, task_id, tdir)
                self.assertFalse(ok, self.explain(output))
                self.assertIn(refusal, output, self.explain(output))
                self.assertNotIn(NO_LAYOUT.format(name=case["comp"]), output,
                                 self.explain(output))
                self.assertEqual(self.runs("vitest"), [], self.explain(output))


# ---------------------------------------------------------------- AC-6

class Ac6IgnoreArgsTest(ComponentLayoutSandbox):

    def test_ac6_report_pytest_own_ignores_layout_parent(self):
        """Полный набор `junit-xml` на pytest с `runner: pytest-own`, `workdir` и `plank_layout` несёт `--ignore=` родителя `<id>` от `workdir` и не несёт `.artel-plank`.

        Сценарий: запись с одним компонентом `junit-xml`, команда
        `pytest`, `runner: pytest-own`, `plank_layout`
        `<workdir>/<каталог>/.<скрытый>/<id>`. `acceptance.run_full_suite`
        и `acceptance.full_suite` с профилем компонента: argv раннера
        несёт `--ignore=<каталог>/.<скрытый>` (путь родителя от
        `workdir`) и ни одного аргумента с `.artel-plank`.

        Ловит мутацию: `_report_argv` по-прежнему исключает
        `<long_lived_dir>/.artel-plank` — `--ignore` родителя нет,
        `.artel-plank` в argv; путь родителя не переведён к `workdir` —
        аргумент несёт префикс `workdir`.
        """
        case = self.junit_case(layout=False)
        parent = f"s{self.word(5)}/.pl{self.word(5)}"
        self.set_entry(case["name"], {case["comp"]: dict(
            case["fields"], plank_layout=f"{case['wd']}/{parent}/<id>")})
        profile = self.profile(case["name"])
        task_id = self.task(case["name"])
        argvs = {"run_full_suite": self.full_suite_argv(profile, case["clone"])}
        self.calls = []
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = acceptance.full_suite(case["clone"], task_id,
                                           command=profile, fresh=True)
        runs = self.runs("junit")
        self.assertEqual(len(runs), 1, self.explain(str(result)))
        argvs["full_suite"] = runs[0]["argv"]
        for place, argv in argvs.items():
            with self.subTest(place=place, seed=self.seed):
                self.assertIn(f"--ignore={parent}", argv, self.note(str(argv)))
                self.assertFalse([a for a in argv if LAYOUT_DIR in a],
                                 self.note(str(argv)))

    def test_ac6_pytest_own_without_report_branch_unchanged(self):
        """Ветка полного набора `pytest-own` без `report` с командой pytest — прежний argv с `--ignore=<long_lived_dir>/.artel-plank` и при заданном `plank_layout`.

        Сценарий: запись с одним компонентом без `report`, команда
        `pytest`, `runner: pytest-own`, `long_lived_dir` внутри `workdir`.
        `acceptance.run_full_suite` дважды: с `plank_layout` и без него.
        Оба argv совпадают и несут `--ignore=` пути
        `<long_lived_dir>/.artel-plank` от `workdir`.

        Ловит мутацию: ветка `pytest-own` читает `plank_layout` и у
        профиля без `report` — argv с `plank_layout` несёт `--ignore`
        его родителя и отличается от прежнего.
        """
        case = self.junit_case(layout=False, report=False)
        layout = f"{case['wd']}/.pl{self.word(5)}/<id>"
        expected = "--ignore=" + os.path.relpath(
            f"{case['lld']}/{LAYOUT_DIR}", case["wd"])
        argvs = {}
        for label, fields in (("plank_layout", dict(case["fields"],
                                                   plank_layout=layout)),
                              ("без него", case["fields"])):
            with self.subTest(record=label, seed=self.seed):
                self.set_entry(case["name"], {case["comp"]: fields})
                argvs[label] = self.full_suite_argv(self.profile(case["name"]),
                                                    case["clone"])
                self.assertIn(expected, argvs[label], self.note(str(argvs)))
        self.assertEqual(argvs["plank_layout"], argvs["без него"],
                         self.note(str(argvs)))

    def test_ac6_no_ignore_without_pytest_own_or_pytest_command(self):
        """Без `--ignore`: pytest-компонент без `runner: pytest-own`, `pult-vitest`, `pytest-own` с командой не pytest — все с `plank_layout`.

        Сценарий: три записи с одним компонентом и `plank_layout`:
        `junit-xml` с командой `pytest` в корне без `runner`;
        `pult-vitest`; `junit-xml` с `runner: pytest-own` и командой — не
        pytest. `acceptance.run_full_suite` с профилем: ни одного
        аргумента argv, начинающегося с `--ignore`.

        Ловит мутацию: `--ignore` родителя добавляется по `plank_layout`
        без проверки команды или `runner` — флаг в argv `pult-vitest`,
        команды не pytest или компонента без `pytest-own`.
        """
        cases = [("pytest-no-runner", self.junit_case(own=False)),
                 ("vitest", self.vitest_case()),
                 ("own-not-pytest", self.junit_case(pytest=False))]
        for label, case in cases:
            with self.subTest(case=label, seed=self.seed):
                self.assertTrue(case["layout"], self.note(label))
                argv = self.full_suite_argv(case["profile"], case["clone"])
                self.assertFalse([a for a in argv if a.startswith("--ignore")],
                                 self.note(f"{label}: {argv}"))


# ---------------------------------------------------------------- AC-7

class Ac7NoComponentFilesTest(ComponentLayoutSandbox):

    def test_ac7_only_shared_files_same_as_plank_absent(self):
        """Планка без файлов компонента (только `.md`/`.txt` либо файлы другого компонента) у `run`/`collect` — тот же исход, что «планка не заведена».

        Сценарий: проект с одним компонентом `pult-vitest` и планкой из
        `.md`, `.txt` и помощника пульта; проект с двумя компонентами и
        планкой из теста pytest-компонента и `.md`, место — с профилем
        `pult-vitest`. Для каждого `run`/`collect` сравниваются с тем же
        вызовом по каталогу задачи без `acceptance_tests`: исход и вывод
        совпадают, раннер Vitest не запускался.

        Ловит мутацию: «есть ли планка» решается по каталогу, а не по
        файлам компонента — раннер запускается с пустым `select` или с
        чужими файлами, исход и вывод другие.
        """
        single = self.vitest_case()
        double = self.two_components()["vitest"]
        plans = [("single", single, {f"n{self.word()}.md": "заметка\n",
                                     f"l{self.word()}.txt": "список\n",
                                     HELPER: "TASK_ID = ''\n"}),
                 ("two", double, {f"test_ac7_{self.word()}.py": "# тест\n",
                                  f"n{self.word()}.md": "заметка\n"})]
        for label, case, files in plans:
            for fn in ("run", "collect"):
                with self.subTest(case=label, place=fn, seed=self.seed):
                    task_id = self.task(case["profile"].project)
                    absent = case["clone"] / TASKS_DIR / task_id
                    self.calls = []
                    empty = self.place(fn, case, task_id, absent)
                    tdir = self.lay_plank(case["clone"], task_id, files)
                    got = self.place(fn, case, task_id, tdir)
                    self.assertEqual(got, empty, self.explain(str(got)))
                    self.assertEqual(self.runs("vitest"), [], self.explain(str(got)))

    def test_ac7_plank_run_refusal_mask_by_rule(self):
        """`plank-run` без файлов компонента отказывает с маской `tests` у правила не по умолчанию и прежним текстом «нет файлов test_*.py» у правила по умолчанию.

        Сценарий: задачи в `tests_writing` с черновиком только из `.md`.
        Проект `pult-vitest` с маской `*.test.jsx`: код ненулевой, текст
        «отказ — планки нет» с последним сегментом маски и без
        `test_*.py`. Проект с одним компонентом `junit-xml` на pytest (с
        маской `tests` и без неё — правило по умолчанию): текст отказа
        побайтно «[<id>] plank-run: отказ — планки нет: в источнике
        (черновик <каталог черновика>) нет файлов test_*.py; pytest не
        запускался». Раннер ни разу не запускался.

        Ловит мутацию: маска `test_*.py` зашита для любого правила — у
        `pult-vitest` в тексте `test_*.py`; маска компонента подставляется
        и у правила по умолчанию — прежний текст меняется.
        """
        vitest = self.vitest_case()
        mask = "*.test.jsx"
        defaults = [self.junit_case(layout=None),
                    self.junit_case(layout=None, tests=[f"t{self.word()}/test_*.py"])]
        with self.subTest(rule="vitest", seed=self.seed):
            task_id = self.ws_task(vitest["name"])
            self.draft(task_id, vitest["name"], {f"n{self.word()}.md": "заметка\n"})
            status, message, output = self.plank_run_cmd(task_id)
            self.assertNotEqual(status, 0, self.explain(output))
            self.assertIn("отказ — планки нет", message, self.explain(output))
            self.assertIn(mask, message, self.explain(output))
            self.assertNotIn("test_*.py", message, self.explain(output))
            self.assertEqual(self.calls, [], self.explain(output))
        for case in defaults:
            with self.subTest(rule="default", tests=case["fields"].get("tests"),
                              seed=self.seed):
                self.assertTrue(project_profile.plank_rule(case["name"]).is_default,
                                self.note(case["name"]))
                task_id = self.ws_task(case["name"])
                self.draft(task_id, case["name"], {f"n{self.word()}.md": "заметка\n"})
                status, message, output = self.plank_run_cmd(task_id)
                source = f"черновик {self.docs_plank(task_id, case['name'])}"
                self.assertNotEqual(status, 0, self.explain(output))
                self.assertEqual(
                    message, f"[{task_id}] plank-run: отказ — планки нет: в "
                             f"источнике ({source}) нет файлов test_*.py; "
                             f"pytest не запускался", self.explain(output))
                self.assertEqual(self.calls, [], self.explain(output))


# ---------------------------------------------------------------- AC-8

class Ac8VitestPlankRunTest(ComponentLayoutSandbox):

    def test_ac8_plank_run_vitest_files_accepted_node_refused(self):
        """`plank-run` компонента `pult-vitest` видит `*.test.jsx` тестами, принимает его как `[файл]` и отказывает `[файл]::узел`.

        Сценарий: задача проекта `pult-vitest` с `plank_layout` в
        `tests_writing`, черновик — два файла `*.test.jsx`. `plank-run
        <id>`: код 0, отказа «нет файлов test_*.py» нет, раннер запущен
        раз, путь каждого файла в выкладке — в argv после `select`.
        `plank-run <id> <файл>`: код 0, раннер запущен раз, после `select`
        — путь этого файла и только его. `plank-run <id> <файл>::<узел>`:
        код ненулевой, текст «узел :: у компонента <имя> не
        поддерживается; передай файл», раннер не запускался.

        Ловит мутацию: наличие тестов по маске `test_*.py` — отказ
        «планки нет»; выбор `[файл]` по маске pytest — отказ «файла …
        нет в планке»; узел передаётся раннеру — раннер запущен, текста
        отказа нет.
        """
        case = self.vitest_case()
        task_id = self.ws_task(case["name"])
        wt = self.wt(task_id, case["name"])
        first, second = (f"ac8{self.word()}.test.jsx", f"ac8{self.word()}.test.jsx")
        self.draft(task_id, case["name"], {first: "// AC-8\n", second: "// AC-8\n"})
        layout = self.layout_dir(case, task_id, wt)
        with self.subTest(arg=None, seed=self.seed):
            status, _message, output = self.plank_run_cmd(task_id)
            self.assertEqual(status, 0, self.explain(output))
            self.assertNotIn("test_*.py", output, self.explain(output))
            runs = self.runs("vitest")
            self.assertEqual(len(runs), 1, self.explain(output))
            seen = self.resolved_after(runs[0], self.select_flag)
            for name in (first, second):
                self.assertIn(os.path.realpath(layout / name), seen,
                              self.explain(output))
        with self.subTest(arg=first, seed=self.seed):
            status, _message, output = self.plank_run_cmd(task_id, first)
            self.assertEqual(status, 0, self.explain(output))
            runs = self.runs("vitest")
            self.assertEqual(len(runs), 1, self.explain(output))
            seen = self.resolved_after(runs[0], self.select_flag)
            self.assertIn(os.path.realpath(layout / first), seen, self.explain(output))
            self.assertNotIn(os.path.realpath(layout / second), seen,
                             self.explain(output))
        with self.subTest(arg="node", seed=self.seed):
            status, message, output = self.plank_run_cmd(
                task_id, f"{first}::ok {self.word()}")
            self.assertNotEqual(status, 0, self.explain(output))
            self.assertIn(NODE_REFUSAL.format(name=case["comp"]), output,
                          self.explain(output))
            self.assertEqual(self.runs("vitest"), [], self.explain(output))


# ---------------------------------------------------------------- AC-9

class Ac9PreviousBehaviourTest(ComponentLayoutSandbox):

    def test_ac9_outside_note_and_exclude_refusal_texts(self):
        """`LAYOUT_OUTSIDE_NOTE` и отказы записи `info/exclude` выкладки `pytest-own` — прежние тексты; шаблон `**/.artel-plank/`.

        Сценарий: константа `acceptance.LAYOUT_OUTSIDE_NOTE` равна
        прежнему тексту; запись `test_profile` с `long_lived_dir` вне
        `workdir` печатает её подстановку в выводе `run`. Запись
        `test_profile` (`runner: pytest-own`, команда `pytest`,
        `long_lived_dir` внутри `workdir`): зелёный `run` дописывает в
        `info/exclude` клона строку `**/.artel-plank/`; дерево не git —
        вывод «отказ выкладки планки: git не назвал info/exclude рабочей
        копии <дерево> (…) — pytest не запускался»; `info/exclude` —
        каталог — «отказ выкладки планки: <путь> не записан (…) — pytest
        не запускался»; раннер в отказах не запускался.

        Ловит мутацию: правка задачи меняет текст строки о случае или
        отказов `_exclude_pattern` (иное `what`, иной шаблон) — строки
        нет в выводе или шаблон в `info/exclude` другой.
        """
        self.assertEqual(acceptance.LAYOUT_OUTSIDE_NOTE, OUTSIDE_NOTE_TEXT,
                         self.note("текст строки о случае"))
        outside = self.junit_case(layout=None, test_profile=True)
        lld_out = f"o{self.word(5)}"
        self.set_entry(outside["name"], profile=dict(
            outside["fields"], long_lived_dir=lld_out,
            weakening_scope=[f"{lld_out}/**"],
            mutation_claim_scope=[f"{lld_out}/**"]))
        profile = self.profile(outside["name"])
        task_id = self.task(outside["name"])
        tdir = self.lay_plank(outside["clone"], task_id, {
            f"test_ac9_{self.word()}.py": "def test_x():\n    pass\n"})
        _ok, output = acceptance.run(tdir, cwd=outside["clone"], command=profile)
        self.assertIn(OUTSIDE_NOTE_TEXT.format(lld=lld_out, workdir=outside["wd"]),
                      output, self.explain(output))

        case = self.junit_case(layout=None, test_profile=True)
        files = {f"test_ac9_{self.word()}.py": "def test_x():\n    pass\n"}
        task_id = self.task(case["name"])
        tdir = self.lay_plank(case["clone"], task_id, files)
        ok, output = acceptance.run(tdir, cwd=case["clone"], command=case["profile"])
        self.assertTrue(ok, self.explain(output))
        exclude = Path(self.git("-C", str(case["clone"]), "rev-parse",
                                "--git-path", "info/exclude").strip())
        exclude = exclude if exclude.is_absolute() else case["clone"] / exclude
        self.assertIn(f"**/{LAYOUT_DIR}/",
                      exclude.read_text(encoding="utf-8").splitlines(),
                      self.note(exclude.read_text(encoding="utf-8")))

        bare = Path(tempfile.mkdtemp(prefix="artel-nogit-")).resolve()
        self.addCleanup(shutil.rmtree, bare, True)
        (bare / case["lld"]).mkdir(parents=True)
        tdir = self.lay_plank(bare, task_id, files)
        self.calls = []
        ok, output = acceptance.run(tdir, cwd=bare, command=case["profile"])
        self.assertFalse(ok, self.explain(output))
        lines = [line for line in output.splitlines() if line.startswith(
            f"отказ выкладки планки: git не назвал info/exclude рабочей копии "
            f"{bare} (")]
        self.assertTrue(lines, self.explain(output))
        self.assertTrue(lines[0].endswith(") — pytest не запускался"),
                        self.explain(output))
        self.assertEqual(self.runs("junit"), [], self.explain(output))

        broken = self.junit_case(layout=None, test_profile=True)
        raw = Path(self.git("-C", str(broken["clone"]), "rev-parse",
                            "--git-path", "info/exclude").strip())
        path = raw if raw.is_absolute() else broken["clone"] / raw
        if path.exists():
            path.unlink()
        path.mkdir(parents=True)
        task_id = self.task(broken["name"])
        tdir = self.lay_plank(broken["clone"], task_id, files)
        self.calls = []
        ok, output = acceptance.run(tdir, cwd=broken["clone"],
                                    command=broken["profile"])
        self.assertFalse(ok, self.explain(output))
        lines = [line for line in output.splitlines() if line.startswith(
            f"отказ выкладки планки: {path} не записан (")]
        self.assertTrue(lines, self.explain(output))
        self.assertTrue(lines[0].endswith(") — pytest не запускался"),
                        self.explain(output))
        self.assertEqual(self.runs("junit"), [], self.explain(output))

    def test_ac9_test_profile_layout_and_full_suite_argv_unchanged(self):
        """Запись `test_profile`: выкладка `<long_lived_dir>/.artel-plank/<id>/acceptance_tests`, argv полного набора и прогона по отчёту с `--ignore=<long_lived_dir>/.artel-plank` — прежние.

        Сценарий: запись `test_profile` (`runner: pytest-own`, команда
        `pytest`, `long_lived_dir` внутри `workdir`) без `report` и с
        `report: junit-xml`. `run`: раннер запущен раз, целью — каталог
        выкладки, её содержимое побайтно равно каталогу планки, исход
        зелёный. `run_full_suite`: argv — команда, `long_lived_dir` от
        `workdir`, `--ignore=<long_lived_dir>/.artel-plank` от `workdir`,
        `-p no:cacheprovider`, а у записи с `report` следом `--junitxml`.

        Ловит мутацию: правка задачи переводит `test_profile` на правило
        `plank_layout` или меняет порядок аргументов — цель не каталог
        выкладки, argv не равен прежнему.
        """
        for report in (False, True):
            with self.subTest(report=report, seed=self.seed):
                case = self.junit_case(layout=None, report=report,
                                       test_profile=True)
                task_id = self.task(case["name"])
                tdir = self.lay_plank(case["clone"], task_id, {
                    f"test_ac9_{self.word()}.py": "def test_x():\n    pass\n",
                    HELPER: "TASK_ID = ''\n"})
                layout = (case["clone"] / case["lld"] / LAYOUT_DIR / task_id
                          / PLANK_DIR)
                self.calls, self.watch = [], [layout]
                try:
                    ok, output = acceptance.run(tdir, cwd=case["clone"],
                                                command=case["profile"])
                finally:
                    self.watch = []
                self.assertTrue(ok, self.explain(output))
                runs = self.runs("junit")
                self.assertEqual(len(runs), 1, self.explain(output))
                self.assertEqual(runs[0]["watch"][str(layout)],
                                 listing(tdir / PLANK_DIR), self.explain(output))
                self.assertIn(os.path.realpath(layout),
                              {os.path.realpath(os.path.join(runs[0]["cwd"], a))
                               for a in runs[0]["argv"][1:]
                               if not a.startswith("-")},
                              self.explain(output))
                argv = self.full_suite_argv(case["profile"], case["clone"])
                wd = case["wd"]
                head = [str(self.pytest_cmd),
                        os.path.relpath(case["lld"], wd),
                        "--ignore=" + os.path.relpath(
                            f"{case['lld']}/{LAYOUT_DIR}", wd),
                        "-p", "no:cacheprovider"]
                self.assertEqual(argv[:len(head)], head, self.note(str(argv)))
                if report:
                    self.assertEqual(argv[len(head)], "--junitxml",
                                     self.note(str(argv)))
                else:
                    self.assertEqual(argv, head, self.note(str(argv)))

    def test_ac9_plank_run_texts_artel_and_test_profile(self):
        """Отказы `plank-run` «нет файлов test_*.py» и «файла … нет в планке» у артели и записи `test_profile` — прежние побайтно; прогон артели — каталог планки под tasks.

        Сценарий: задачи артели и записи `test_profile` в `tests_writing`.
        Черновик только с помощником `_*.py` — текст «[<id>] plank-run:
        отказ — планки нет: в источнике (черновик <каталог>) нет файлов
        test_*.py; pytest не запускался». Черновик с тестом и `[файл]`,
        которого в нём нет, — «[<id>] plank-run: отказ — файла <файл> нет
        в планке (черновик <каталог>); в ней: <тест>». Раннер в отказах не
        запускался. `plank-run` артели с тестом: код 0, раннер пульта
        запущен раз с целью — каталогом планки под tasks рабочей копии.

        Ловит мутацию: `plank-run` по правилу меняет текст отказа у правила
        по умолчанию — строка другая; артель переводится на выкладку —
        цель не каталог планки под tasks.
        """
        profile_case = self.junit_case(layout=None, test_profile=True)
        for name in (ARTEL, profile_case["name"]):
            with self.subTest(project=name, seed=self.seed):
                empty = self.ws_task(name)
                self.draft(empty, name, {f"_h{self.word()}.py": "A = 1\n"})
                status, message, output = self.plank_run_cmd(empty)
                source = f"черновик {self.docs_plank(empty, name)}"
                self.assertNotEqual(status, 0, self.explain(output))
                self.assertEqual(
                    message, f"[{empty}] plank-run: отказ — планки нет: в "
                             f"источнике ({source}) нет файлов test_*.py; "
                             f"pytest не запускался", self.explain(output))
                self.assertEqual(self.calls, [], self.explain(output))

                task_id = self.ws_task(name)
                test_file = f"test_ac9_{self.word()}.py"
                self.draft(task_id, name, {test_file: "def test_x():\n    pass\n"})
                missing = f"test_no_{self.word()}.py"
                status, message, output = self.plank_run_cmd(task_id, missing)
                source = f"черновик {self.docs_plank(task_id, name)}"
                self.assertNotEqual(status, 0, self.explain(output))
                self.assertEqual(
                    message, f"[{task_id}] plank-run: отказ — файла {missing} "
                             f"нет в планке ({source}); в ней: {test_file}",
                    self.explain(output))
                self.assertEqual(self.calls, [], self.explain(output))
                if name == ARTEL:
                    status, _message, output = self.plank_run_cmd(task_id)
                    self.assertEqual(status, 0, self.explain(output))
                    runs = self.runs("pult")
                    self.assertEqual(len(runs), 1, self.explain(output))
                    plank = (self.wt(task_id, name) / TASKS_DIR / task_id
                             / PLANK_DIR)
                    self.assertIn(os.path.realpath(plank),
                                  {os.path.realpath(os.path.join(runs[0]["cwd"], a))
                                   for a in runs[0]["argv"] if not a.startswith("-")},
                                  self.explain(output))

    def test_ac9_artel_run_and_collect_target_plank_dir(self):
        """`acceptance.run`/`collect` артели гонят каталог планки под tasks с прежней строкой-заголовком; выкладки нет.

        Сценарий: задача артели с рабочей копией, планка — один тест под
        tasks рабочей копии. `run` и `collect` (раннер пульта, зелёный
        ответ): исход зелёный, раннер запущен раз, целью — каталог планки,
        первая строка вывода `run` — «планка: <каталог планки>, cwd:
        <рабочая копия>»; каталогов `.artel-plank` в рабочей копии нет.

        Ловит мутацию: правило `plank_layout` или выкладка включаются у
        артели — цель не каталог планки, в рабочей копии появляется
        каталог выкладки; заголовок называет путь выкладки.
        """
        task_id = self.ws_task(ARTEL)
        wt = self.wt(task_id, ARTEL)
        tdir = self.lay_plank(wt, task_id, {
            f"test_ac9_{self.word()}.py": "def test_x():\n    pass\n"})
        for fn in (acceptance.run, acceptance.collect):
            with self.subTest(place=fn.__name__, seed=self.seed):
                self.calls = []
                ok, output = fn(tdir, cwd=wt)
                self.assertTrue(ok, self.explain(output))
                runs = self.runs("pult")
                self.assertEqual(len(runs), 1, self.explain(output))
                self.assertIn(os.path.realpath(tdir / PLANK_DIR),
                              {os.path.realpath(os.path.join(runs[0]["cwd"], a))
                               for a in runs[0]["argv"] if not a.startswith("-")},
                              self.explain(output))
                if fn is acceptance.run:
                    self.assertEqual(output.splitlines()[0],
                                     f"планка: {tdir / PLANK_DIR}, cwd: {wt}",
                                     self.explain(output))
                found = [top for top, dirs, _f in os.walk(wt)
                         if LAYOUT_DIR in dirs]
                self.assertEqual(found, [], self.explain(output))


# ---------------------------------------------------------------- AC-10

class Ac10DropLeftoverTest(ComponentLayoutSandbox):

    def test_ac10_drop_removes_leftover_keeps_code(self):
        """`drop_from_code_copy` убирает остаток выкладки `plank_layout` и опустевшего родителя, не трогая файлы кода в родителе и вне его.

        Сценарий: проекты с одним компонентом `pult-vitest` и `junit-xml`
        на pytest, у каждого `plank_layout`. В рабочей копии (клоне) по
        пути выкладки задачи лежат файлы (имитация оборванного прогона).
        Вариант «пустой родитель»: после `drop_from_code_copy` нет ни
        каталога `<id>`, ни родителя. Вариант «файл в родителе»: в
        родителе ещё файл кода — он на месте с прежним содержимым, родитель
        есть, каталога `<id>` нет. В обоих — закоммиченный файл кода
        `workdir` и неотслеживаемый файл кода вне родителя не тронуты.

        Ловит мутацию: `drop_from_code_copy` убирает только остаток
        `long_lived_dir/.artel-plank` — каталог `<id>` остаётся; родитель
        удаляется целиком — файл кода в родителе пропал; родитель не
        удаляется, опустев, — пустой каталог остаётся.
        """
        cases = [("vitest", self.vitest_case()), ("junit", self.junit_case())]
        for label, case in cases:
            clone = case["clone"]
            code_file = clone / case["wd"] / f"code{self.word()}.js"
            code_file.write_text(f"// {self.seed}\n", encoding="utf-8")
            tracked = (clone / case["lld"] / "test_base.py" if label == "junit"
                       else clone / case["wd"] / "src" / "a.test.js")
            tracked_before = tracked.read_bytes()
            for keep in (False, True):
                with self.subTest(case=label, keep=keep, seed=self.seed):
                    task_id = self.task(case["name"])
                    layout = self.layout_dir(case, task_id)
                    for rel in (f"ac10{self.word()}.test.jsx",
                                f"sub{self.word()}/x{self.word()}.py"):
                        path = layout / rel
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text("# остаток\n", encoding="utf-8")
                    keeper = layout.parent / f"keep{self.word()}.js"
                    if keep:
                        keeper.write_text(f"// {self.seed}\n", encoding="utf-8")
                    acceptance.drop_from_code_copy(task_id, clone)
                    self.assertFalse(layout.exists(), self.note(f"{layout} остался"))
                    if keep:
                        self.assertEqual(keeper.read_text(encoding="utf-8"),
                                         f"// {self.seed}\n", self.note("файл кода"))
                        keeper.unlink()
                    else:
                        self.assertFalse(layout.parent.exists(),
                                         self.note(f"{layout.parent} остался"))
                    self.assertEqual(code_file.read_text(encoding="utf-8"),
                                     f"// {self.seed}\n", self.note(str(code_file)))
                    self.assertEqual(tracked.read_bytes(), tracked_before,
                                     self.note(str(tracked)))


# ---------------------------------------------------------------- AC-11

class Ac11PathsWithoutLayoutTest(ComponentLayoutSandbox):

    def test_ac11_extra_only_and_long_lived_plank_run_unchanged(self):
        """У `pult-vitest` без `plank_layout` прогон только `extra` и `plank-run` долгоживущего файла идут прежним путём без отказа «нет plank_layout».

        Сценарий: проект с одним компонентом `pult-vitest` (`runner:
        pytest-own`, `workdir`, `tests`) без `plank_layout`. `acceptance.run`
        без каталога планки с `extra` — файлом `long_lived_dir`: исход
        зелёный, первая строка «планка: <каталог>, cwd: <workdir>,
        долгоживущие файлы: <файл>», раннер запущен раз, путь файла — в
        argv после `select`. Задача в `tests_writing` с долгоживущим файлом
        своей задачи в рабочей копии: `plank-run <id> <путь>` — код 0,
        строка «[<id>] plank-run: долгоживущий файл <путь>, cwd <рабочая
        копия>», раннер запущен раз с этим файлом. Текста «нет
        plank_layout» нигде нет.

        Ловит мутацию: отказ «нет plank_layout» проверяется до ветвей без
        выкладки — исход не зелёный, раннер не запущен.
        """
        case = self.vitest_case(layout=None)
        text = NO_LAYOUT.format(name=case["comp"])
        task_id = self.task(case["name"])
        tdir = case["clone"] / TASKS_DIR / task_id
        extra = [f"{case['wd']}/src/a.test.js"]
        self.calls = []
        ok, output = acceptance.run(tdir, cwd=case["clone"], extra=extra,
                                    command=case["profile"])
        self.assertTrue(ok, self.explain(output))
        self.assertNotIn(text, output, self.explain(output))
        self.assertEqual(output.splitlines()[0],
                         f"планка: {tdir / PLANK_DIR}, cwd: "
                         f"{case['clone'] / case['wd']}, долгоживущие файлы: "
                         f"{extra[0]}", self.explain(output))
        runs = self.runs("vitest")
        self.assertEqual(len(runs), 1, self.explain(output))
        self.assertIn(os.path.realpath(case["clone"] / extra[0]),
                      self.resolved_after(runs[0], self.select_flag),
                      self.explain(output))

        task_id = self.ws_task(case["name"])
        wt = self.wt(task_id, case["name"])
        rel = f"{case['profile'].long_lived_prefix(task_id)}{self.word()}.test.js"
        self.assertTrue(case["profile"].is_long_lived(task_id, rel), self.note(rel))
        (wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (wt / rel).write_text("// долгоживущий\n", encoding="utf-8")
        self.draft(task_id, case["name"], {f"ac11{self.word()}.test.jsx": "// t\n"})
        status, _message, output = self.plank_run_cmd(task_id, rel)
        self.assertEqual(status, 0, self.explain(output))
        self.assertNotIn(text, output, self.explain(output))
        self.assertIn(f"[{task_id}] plank-run: долгоживущий файл {rel}, cwd {wt}",
                      output, self.explain(output))
        runs = self.runs("vitest")
        self.assertEqual(len(runs), 1, self.explain(output))
        self.assertIn(os.path.realpath(wt / rel),
                      self.resolved_after(runs[0], self.select_flag),
                      self.explain(output))
