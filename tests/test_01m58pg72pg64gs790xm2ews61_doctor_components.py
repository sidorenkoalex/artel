"""Строки `doctor` по компонентам проекта: версии инструментов, карта путей CI, каталоги `workdir`; `doctor` на записи с компонентами не падает.

Группа: долгоживущий
Красен до реализации: строка `full-suite-timeout-<имя>` зовёт `project_profile.full_suite_limit`, который на записи с несколькими компонентами и на единственном компоненте без обязательного подполя бросает `TargetsError` — `doctor` падает исключением; строк `project-tools-…`/`project-paths-…`/`project-workdir-…` нет вовсе — поиск строки по имени не находит её; тест AC-15 (записи с `test_profile`) держит прежнее поведение и зелен с рождения.

Песочница — `tests.sandbox.TmpRootTest`: `config.TARGETS` — временный файл,
сценарий пишет в него запись артели песочницы и учебные записи проектов;
клон проекта — `make_project_repo` по адресу `repo_context`, учебные файлы
CI и каталоги `workdir` кладутся в рабочую копию клона на диск. `doctor` —
настоящая команда `doctor.cmd_doctor`, её вывод разбирается построчно
(`  [ok|WARN|FAIL|skip] <имя>: <пояснение>`).

Инструменты — учебные исполняемые файлы `/bin/sh` во временных каталогах:
каталог `env.PATH` компонента и каталог, дописанный в начало `PATH`
процесса `doctor`; запуск `<инструмент> --version` идёт настоящим процессом.
Сбой запуска и истечение таймаута изображает обёртка `doctor.subprocess.run`
(шов SPEC, требование 3) для своего инструмента; вызовы `gh` она отвечает
отказом без сети, остальные передаёт прежней подмене песочницы. Подменены
также живой вызов CLI ролей (`subprocess.Popen` программ `claude`/`gh` —
«не найден») и токен из связки ключей. Код выхода `doctor` не
проверяется: прочие проверки в песочнице вправе быть красными.

Имена проектов, компонентов, инструментов, каталогов и номера версий — от
зерна `random`; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import re
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, doctor, store, targets
from tests.sandbox import TmpRootTest, artel_target_entry, make_project_repo

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
LETTERS = "abcdefghijkmnpqrstuvwxyz"
LINE = re.compile(r"^  \[(ok|WARN|FAIL|skip)\] (\S+): ?(.*)$")
STATUS = {"ok": "ok", "WARN": "warn", "FAIL": "fail", "skip": "skip"}
MULTILINE = "многострочное значение не сравнивается"
CI_FILE = ".github/workflows/ci.yml"

HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def block(fields: dict, indent: str) -> str:
    """Текст полей компонента для `targets.yaml`: отображение — блоком,
    список — потоковым списком, прочее — как есть (кавычки — у вызывающего)."""
    out = []
    for key, value in fields.items():
        if isinstance(value, dict):
            out.append(f"{indent}{key}:\n")
            out.append(block(value, indent + "  "))
        elif isinstance(value, list):
            out.append(f"{indent}{key}: [{', '.join(value)}]\n")
        else:
            out.append(f"{indent}{key}: {value}\n")
    return "".join(out)


def q(text: str) -> str:
    return f'"{text}"'


def guarded_popen(cmd, *args, **kwargs):
    """`subprocess.Popen`, для которого CLI ролей и `gh` не найдены: живой
    смок и проверки хостинга в песочнице не ходят наружу."""
    program = cmd if isinstance(cmd, str) else (cmd[0] if cmd else "")
    name = Path(str(program).split()[0] if program else "").name
    if name in ("claude", "gh") or "claude" in name:
        raise FileNotFoundError(program)
    return REAL_POPEN(cmd, *args, **kwargs)


class DoctorComponentsSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.entries = []
        self.tool_names = set()
        self.raising = {}
        self.process_dirs = []
        self.used = set()

    def word(self, size: int = 7) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    # ---------------------------------------------------- инструменты

    def tool_name(self) -> str:
        return f"zt{self.word(6)}"

    def bin_dir(self) -> Path:
        path = self.root / f"bin-{self.word()}"
        path.mkdir()
        return path

    def process_dir(self) -> Path:
        """Каталог в начале `PATH` процесса `doctor`."""
        path = self.bin_dir()
        self.process_dirs.append(path)
        return path

    def tool(self, directory: Path, name: str, stdout: str = "",
             stderr: str = "", code: int = 0) -> None:
        lines = ["#!/bin/sh"]
        if stdout:
            lines.append(f"printf '%s\\n' '{stdout}'")
        if stderr:
            lines.append(f"printf '%s\\n' '{stderr}' >&2")
        lines.append(f"exit {code}")
        path = directory / name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path.chmod(0o755)
        self.tool_names.add(name)

    # ---------------------------------------------------- записи и клоны

    def clone(self, project: str) -> Path:
        return make_project_repo(project, origin=False)

    @staticmethod
    def put(clone: Path, rel: str, text: str = "") -> Path:
        path = clone / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def minimal(self, paths) -> dict:
        """Поля компонента записи с несколькими компонентами."""
        area = self.word(5)
        return {"command": "[python3, -m, pytest]",
                "weakening_scope": [f"{area}/**"],
                "mutation_claim_scope": [f"{area}/**"],
                "paths": paths}

    def add_components(self, project: str, comps: dict) -> None:
        text = HEAD.format(name=project) + "    components:\n"
        for comp, fields in comps.items():
            text += f"      {comp}:\n" + block(fields, "        ")
        self.entries.append(text)

    def add_entry(self, text: str) -> None:
        self.entries.append(text)

    def write_targets(self) -> str:
        text = "targets:\n" + artel_target_entry() + "".join(self.entries)
        config.TARGETS.write_text(text, encoding="utf-8")
        return text

    # ---------------------------------------------------- прогон doctor

    def run_doctor(self) -> tuple[dict, str]:
        """(строки по имени → список (исход, пояснение), весь вывод)."""
        previous = subprocess.run

        def run(cmd, *args, **kwargs):
            argv = cmd.split() if isinstance(cmd, str) else [str(a) for a in cmd]
            head = Path(argv[0]).name if argv else ""
            if head == "gh":
                return subprocess.CompletedProcess(
                    argv, 1, "", "gh: сеть в песочнице теста отключена")
            if head in self.raising:
                raise self.raising[head]
            if head in self.tool_names:
                return REAL_RUN(cmd, *args, **kwargs)
            return previous(cmd, *args, **kwargs)

        path = os.pathsep.join([*(str(d) for d in self.process_dirs),
                                os.environ.get("PATH", "")])
        buf = io.StringIO()
        with mock.patch.object(doctor.subprocess, "run", run), \
                mock.patch.object(doctor.subprocess, "Popen",
                                  side_effect=guarded_popen), \
                mock.patch.object(doctor.runner.keychain, "token",
                                  lambda slot: None), \
                mock.patch.dict(os.environ, {"PATH": path}), \
                contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            try:
                doctor.cmd_doctor()
            except SystemExit as exc:
                if exc.code not in (None, 0, 1):
                    buf.write(f"\nвыход doctor: {exc.code}\n")
        out = buf.getvalue()
        rows, last = {}, None
        for line in out.splitlines():
            m = LINE.match(line)
            if m:
                last = [STATUS[m.group(1)], m.group(3)]
                rows.setdefault(m.group(2), []).append(last)
            elif last is not None and line.strip() and not line.startswith(
                    ("DOCTOR", "Открытые", "  #")):
                last[1] += "\n" + line
            else:
                last = None
        return rows, out

    def row(self, rows: dict, name: str, out: str) -> tuple[str, str]:
        found = rows.get(name)
        self.assertTrue(found, self.note(
            f"нет строки {name} в выводе doctor:\n{out[-5000:]}"))
        self.assertEqual(len(found), 1, self.note(f"строка {name} не одна: {found}"))
        return tuple(found[0])

    def assert_status(self, rows: dict, name: str, status: str, out: str,
                      context: str = "") -> str:
        got, detail = self.row(rows, name, out)
        self.assertEqual(got, status, self.note(
            f"{context} строка {name}: [{got}] {detail}"))
        if status in ("skip", "fail", "warn"):
            self.assertTrue(detail.strip(), self.note(
                f"{context} строка {name} без причины"))
        return detail

    def assert_no_rows(self, rows: dict, prefix: str, out: str) -> None:
        extra = [name for name in rows if name.startswith(prefix)]
        self.assertEqual(extra, [], self.note(
            f"лишние строки с префиксом {prefix}:\n{out[-3000:]}"))


# ------------------------------------------------------------------ AC-1, AC-2

class DoctorOnComponentRecordsTest(DoctorComponentsSandbox):

    def test_ac1_two_component_record_rows_and_pending_timeout(self):
        """`doctor` на корректной записи с двумя компонентами не падает и печатает строки компонентов.

        Сценарий: учебная запись проекта с компонентами (имена от зерна):
        первый — `tools` с одним инструментом в каталоге `env.PATH`,
        `paths_source` (ключ в CI-файле клона) и `workdir`; второй — два
        инструмента из `PATH` процесса, `paths_source`, `workdir` и
        `depends_on` вида `files` на первый; третий — только `paths`. В клоне
        — CI-файл с обеими переменными и оба каталога. `cmd_doctor` не
        бросает исключения; в выводе — по строке `project-tools-<проект>-
        <компонент>-<инструмент>` на каждый из трёх инструментов, строки
        `project-paths-…` и `project-workdir-…` первых двух компонентов и ни
        одной строки этих видов у третьего; `full-suite-timeout-<проект>` —
        `skip` с причиной `targets.MULTI_COMPONENT_PENDING`; строка
        `full-suite-timeout-` артели напечатана.

        Ловит мутацию: строка предела по-прежнему зовёт `full_suite_limit`
        без перехвата — `doctor` падает `TargetsError` на записи с двумя
        компонентами; проверка инструментов печатает строку на компонент, а
        не на инструмент (у второго компонента одна строка вместо двух);
        строки `paths`/`workdir` печатаются и компоненту без этих полей.
        """
        project = f"p{self.word()}"
        first, second, third = (f"c{self.word(5)}" for _ in range(3))
        own_dir, shared = self.bin_dir(), self.process_dir()
        t1, t2, t3 = (self.tool_name() for _ in range(3))
        self.tool(own_dir, t1, stdout="v22.23.3")
        self.tool(shared, t2, stdout="Python 3.12.4")
        self.tool(shared, t3, stdout="v20.15.1")
        d1, d2 = f"{self.word(5)}", f"{self.word(5)}"
        clone = self.clone(project)
        self.put(clone, CI_FILE, (
            "name: ci\non:\n  pull_request:\nenv:\n"
            f"  FIRST_RE: '^({d1}/|{d2}/api/)'\n"
            f"  SECOND_RE: >-\n    ^({d2}/|shared/)\n"
            "jobs:\n  t:\n    runs-on: ubuntu-latest\n"))
        self.put(clone, f"{d1}/.keep")
        self.put(clone, f"{d2}/.keep")
        one = self.minimal([f"^{d1}/", f"^{d2}/api/"])
        one.update(tools={t1: q("22")}, env={"PATH": q(str(own_dir))},
                   paths_source={"file": CI_FILE, "key": "FIRST_RE"},
                   workdir=d1)
        two = self.minimal(f"^{d2}/")
        two.update(tools={t2: q("3.12"), t3: q("20")},
                   paths_source={"file": CI_FILE, "key": "SECOND_RE"},
                   workdir=d2,
                   depends_on={first: {"via": "files", "paths": ["^shared/"]}})
        three = self.minimal(f"^{self.word(5)}/")
        self.add_components(project, {first: one, second: two, third: three})
        text = self.write_targets()
        targets.load()
        rows, out = self.run_doctor()
        context = f"targets.yaml:\n{text}\n"
        for comp, tool in ((first, t1), (second, t2), (second, t3)):
            self.row(rows, f"project-tools-{project}-{comp}-{tool}", out)
        for comp in (first, second):
            self.row(rows, f"project-paths-{project}-{comp}", out)
            self.row(rows, f"project-workdir-{project}-{comp}", out)
        for kind in ("tools", "paths", "workdir"):
            self.assert_no_rows(rows, f"project-{kind}-{project}-{third}", out)
        detail = self.assert_status(rows, f"full-suite-timeout-{project}",
                                    "skip", out, context)
        self.assertIn(targets.MULTI_COMPONENT_PENDING, detail, self.note(detail))
        self.row(rows, f"full-suite-timeout-{config.DEFAULT_TARGET}", out)

    def test_ac2_broken_single_component_fails_its_row_only(self):
        """Единственный компонент без обязательного подполя профиля: строка предела `fail` с причиной, `doctor` не падает, строки соседней записи напечатаны.

        Сценарий: в `targets.yaml` — запись с единственным компонентом, у
        которого нет `weakening_scope` (затем — `mutation_claim_scope`), а
        ПОСЛЕ неё — внешний проект с `test_profile` (имена от зерна).
        Предпосылка: `targets.load` файл принимает. `cmd_doctor` не бросает
        исключения; `full-suite-timeout-<сломанная>` — `fail` с непустой
        причиной; у соседней записи есть строки `full-suite-timeout-` и
        `project-clone-`.

        Ловит мутацию: отказ чтения профиля перехвачен только для записи с
        несколькими компонентами (`ComponentsPending`), а прочий
        `TargetsError` по-прежнему роняет `doctor`; либо перехват съедает
        отказ и строка выходит `ok`/`skip`; либо цикл записей обрывается на
        сломанной — строк соседней записи нет.
        """
        for missing in ("weakening_scope", "mutation_claim_scope"):
            with self.subTest(missing=missing, seed=self.seed):
                self.entries = []
                broken, other = f"p{self.word()}", f"p{self.word()}"
                comp = f"c{self.word(5)}"
                fields = {"command": "[python3, -m, pytest]",
                          "long_lived_dir": "tests",
                          "long_lived_name": "test_<id>_<name>.py",
                          "weakening_scope": ["tests/**/*.py"],
                          "mutation_claim_scope": ["tests/test_*.py"]}
                del fields[missing]
                self.add_components(broken, {comp: fields})
                self.add_entry(HEAD.format(name=other) + (
                    "    test_profile:\n"
                    "      command: [python3, -m, pytest]\n"
                    "      long_lived_dir: tests\n"
                    "      long_lived_name: test_<id>_<name>.py\n"
                    "      weakening_scope: [tests/**/*.py]\n"
                    "      mutation_claim_scope: [tests/test_*.py]\n"))
                text = self.write_targets()
                targets.load()
                rows, out = self.run_doctor()
                self.assert_status(rows, f"full-suite-timeout-{broken}", "fail",
                                   out, f"targets.yaml:\n{text}\n")
                self.row(rows, f"full-suite-timeout-{other}", out)
                self.row(rows, f"project-clone-{other}", out)


# ------------------------------------------------------------------ AC-3 — AC-5

class ToolVersionTest(DoctorComponentsSandbox):

    def tools_project(self, cases: list, env_dir: Path) -> tuple[str, str]:
        """Запись из двух компонентов; первый несёт инструменты `cases`
        ((имя, требуемая версия)) и `env.PATH` = `env_dir`."""
        project, comp = f"p{self.word()}", f"c{self.word(5)}"
        fields = self.minimal(f"^{self.word(5)}/")
        fields["tools"] = {name: q(required) for name, required in cases}
        fields["env"] = {"PATH": q(str(env_dir))}
        self.add_components(project, {
            comp: fields, f"c{self.word(5)}": self.minimal(f"^{self.word(5)}/")})
        return project, comp

    def test_ac3_version_match_by_numeric_parts(self):
        """Версия сравнивается по числовым частям требуемой, не префиксом строки; пометка после пробела не влияет.

        Сценарий: инструменты компонента — учебные файлы в каталоге его
        `env.PATH`, каждый печатает свою строку версии. Пары AC-3: `22` при
        `v22.23.3` — ok, при `v20.15.1` — fail; `3.12` при `Python 3.11.9` —
        fail, при `Python 3.12.4` — ok; `3.1` при `3.12.0` — fail; `2` при
        `22.1` — fail; `22 <пометка>` при `v22.23.3` — ok, при `v20.15.1` —
        fail. Сверх них — случайные версии `a.b.c`: требуемая из первых
        1–3 частей — ok; с последней частью +1 — fail; первая цифра
        двузначной части (`1` при `17.…`) — fail.

        Ловит мутацию: совпадение префиксом строки (`3.1` ↔ `3.12.0` и `2` ↔
        `22.1` дают ok); сравнение всех частей вывода с требуемой (`22` ↔
        `v22.23.3` даёт fail); пометка после пробела не отрезана (`22 из
        .nvmrc` не совпадает ни с чем — ok-пара выходит fail).
        """
        cases = [("22", "v22.23.3", "ok"), ("22", "v20.15.1", "fail"),
                 ("3.12", "Python 3.11.9", "fail"),
                 ("3.12", "Python 3.12.4", "ok"), ("3.1", "3.12.0", "fail"),
                 ("2", "22.1", "fail")]
        mark = f"из .nvmrc {self.word(4)}"
        cases += [(f"22 {mark}", "v22.23.3", "ok"),
                  (f"22 {mark}", "v20.15.1", "fail")]
        for _ in range(3):
            parts = [self.rng.randrange(10, 40), self.rng.randrange(10, 30),
                     self.rng.randrange(0, 30)]
            shown = f"{self.rng.choice(('v', 'tool ', ''))}{'.'.join(map(str, parts))}"
            k = self.rng.randrange(1, 4)
            exact = ".".join(map(str, parts[:k]))
            bumped = ".".join(map(str, parts[:k - 1] + [parts[k - 1] + 1]))
            digit = (".".join(map(str, parts[:k - 1]))
                     + ("." if k > 1 else "") + str(parts[k - 1])[0])
            cases += [(exact, shown, "ok"), (bumped, shown, "fail")]
            if k < 3:
                cases.append((digit, shown, "fail"))
        env_dir = self.bin_dir()
        named = []
        for required, shown, expected in cases:
            name = self.tool_name()
            self.tool(env_dir, name, stdout=shown)
            named.append((name, required, shown, expected))
        project, comp = self.tools_project(
            [(n, r) for n, r, _, _ in named], env_dir)
        self.write_targets()
        rows, out = self.run_doctor()
        for name, required, shown, expected in named:
            with self.subTest(required=required, shown=shown, seed=self.seed):
                self.assert_status(rows, f"project-tools-{project}-{comp}-{name}",
                                   expected, out,
                                   f"требуемая «{required}», вывод «{shown}»:")

    def test_ac4_path_from_component_env_else_process(self):
        """Инструмент ищется и запускается по `env.PATH` компонента, без него — по `PATH` процесса `doctor`.

        Сценарий: каталог A — `env.PATH` компонента X; каталог B — в начале
        `PATH` процесса `doctor`. Инструмент T1 есть в обоих: в A печатает
        версию a, в B — версию b (a ≠ b, от зерна). Инструмент T2 есть только
        в B. У X: T1 требует a — ok (запуск по `env.PATH`), T2 — fail (его нет
        в `env.PATH`, хоть он и в `PATH` процесса). У компонента Y без `env`:
        T1 требует b — ok, T2 требует свою версию — ok (оба по `PATH`
        процесса).

        Ловит мутацию: запуск идёт с `PATH` процесса и при заданном
        `env.PATH` — у X версия T1 выходит b, строка fail; наличие ищется
        `shutil.which` без `path=` — у X T2 найден в B, строка не fail;
        `env.PATH` пустого `env` подставляется пустой строкой — у Y
        инструменты не найдены.
        """
        a, b, c = self.rng.sample(range(10, 60), 3)
        env_dir, shared = self.bin_dir(), self.process_dir()
        t1, t2 = self.tool_name(), self.tool_name()
        self.tool(env_dir, t1, stdout=f"v{a}.1.0")
        self.tool(shared, t1, stdout=f"v{b}.1.0")
        self.tool(shared, t2, stdout=f"v{c}.2.0")
        project = f"p{self.word()}"
        x, y = f"c{self.word(5)}", f"c{self.word(5)}"
        fx = self.minimal(f"^{self.word(5)}/")
        fx.update(tools={t1: q(str(a)), t2: q(str(c))},
                  env={"PATH": q(str(env_dir))})
        fy = self.minimal(f"^{self.word(5)}/")
        fy.update(tools={t1: q(str(b)), t2: q(str(c))})
        self.add_components(project, {x: fx, y: fy})
        self.write_targets()
        rows, out = self.run_doctor()
        for comp, tool, expected in ((x, t1, "ok"), (x, t2, "fail"),
                                     (y, t1, "ok"), (y, t2, "ok")):
            with self.subTest(component=comp, tool=tool, seed=self.seed):
                self.assert_status(rows, f"project-tools-{project}-{comp}-{tool}",
                                   expected, out, f"a={a} b={b} c={c}:")

    def test_ac5_missing_unreadable_failed_and_hung_tools(self):
        """Нет инструмента — fail; вывод без версии, сбой запуска, таймаут и ненулевой код — skip с причиной; версия из stderr сравнивается.

        Сценарий: компонент с `env.PATH` = каталог D; инструменты: «нет
        нигде» — fail; «только в `PATH` процесса» (не в D) — fail; печатает
        текст без цифр в оба потока — skip; печатает `v22.23.3` только в
        stderr при требуемой `22` — ok; запуск бросает `OSError` — skip;
        запуск бросает `TimeoutExpired` — skip; печатает `v22.0.0` и выходит
        с кодом N (от зерна) — skip, причина называет N. Строка инструмента
        после зависшего и строка предела артели напечатаны — `doctor` не
        упал на таймауте.

        Ловит мутацию: `TimeoutExpired` не перехвачен (`except OSError`) —
        `doctor` падает; код выхода не проверяется — `v22.0.0` при коде N
        даёт ok; stderr не читается — версия только в stderr даёт skip;
        вывод без версии считается несовпадением — fail вместо skip.
        """
        env_dir, shared = self.bin_dir(), self.process_dir()
        code = self.rng.randrange(101, 250)
        absent, elsewhere, noversion, stderr_only, broken, hung, exited = (
            self.tool_name() for _ in range(7))
        self.tool(shared, elsewhere, stdout="v22.23.3")
        self.tool(env_dir, noversion, stdout="no version here",
                  stderr="still nothing")
        self.tool(env_dir, stderr_only, stderr="v22.23.3")
        self.tool(env_dir, broken, stdout="v22.23.3")
        self.tool(env_dir, hung, stdout="v22.23.3")
        self.tool(env_dir, exited, stdout="v22.0.0", code=code)
        self.raising[broken] = OSError(f"учебный сбой запуска {broken}")
        self.raising[hung] = subprocess.TimeoutExpired([hung, "--version"], 5)
        order = [absent, elsewhere, noversion, hung, stderr_only, broken, exited]
        project, comp = self.tools_project([(n, "22") for n in order], env_dir)
        self.write_targets()
        rows, out = self.run_doctor()
        expected = {absent: "fail", elsewhere: "fail", noversion: "skip",
                    stderr_only: "ok", broken: "skip", hung: "skip",
                    exited: "skip"}
        for name in order:
            with self.subTest(tool=name, seed=self.seed):
                detail = self.assert_status(
                    rows, f"project-tools-{project}-{comp}-{name}",
                    expected[name], out)
                if name == exited:
                    self.assertRegex(detail, rf"(?<!\d){code}(?!\d)",
                                     self.note(f"причина не называет код {code}"))
        self.row(rows, f"full-suite-timeout-{config.DEFAULT_TARGET}", out)


# ------------------------------------------------------------------ AC-6 — AC-10

class PathsSourceTest(DoctorComponentsSandbox):

    def paths_row(self, rows, project, comp, out):
        return self.row(rows, f"project-paths-{project}-{comp}", out)

    def shuffled(self, items: list) -> list:
        items = list(items)
        while True:
            self.rng.shuffle(items)
            if len(items) < 2 or items != sorted(items):
                return items

    def test_ac6_sled_form_and_contract_dependency(self):
        """Форма sled (`'…'` и `>-` одной строкой) совпадает при ином порядке; `depends_on` вида `contract` в сравнение не входит.

        Сценарий: в CI-файле клона внутри `env:` — `BACK_RE: '^(…)'` в
        одинарных кавычках и `FRONT_RE: >-` со значением одной строкой на
        следующей строке с большим отступом; альтернативы перемешаны
        относительно `paths`. Компонент B: `paths` списком, `depends_on` на F
        вида `paths` (его выражение — в `BACK_RE`) и на C вида `contract`
        (его выражения в `BACK_RE` нет). Компонент F: `paths` строкой и
        `depends_on` на B вида `files` (его выражение — в `FRONT_RE`). Обе
        строки `project-paths-…` — ok.

        Ловит мутацию: `paths` поставщика вида `contract` попадают в
        объединение — у B warn; `depends_on` вида `paths`/`files` не
        учитывается — warn у обоих; блок `>-` не читается (значение — `>-`)
        — у F skip или warn; сравнение списков с порядком — warn.
        """
        project = f"p{self.word()}"
        b, f, c = (f"c{self.word(5)}" for _ in range(3))
        b1, b2, b3, f1, f2, zz = (self.word(5) for _ in range(6))
        back = self.shuffled([f"{b1}/", f"{b2}\\.toml$", f"{b3}/"])
        front = self.shuffled([f"{f1}/", f"{f2}/api/"])
        clone = self.clone(project)
        self.put(clone, CI_FILE, (
            "name: ci\non:\n  pull_request:\n  push:\n    branches: [main]\n"
            "env:\n"
            f"  BACK_RE: '^({'|'.join(back)})'\n"
            f"  FRONT_RE: >-\n    ^({'|'.join(front)})\n"
            "jobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: echo ok\n"))
        fb = self.minimal([f"^{b1}/", f"^{b2}\\.toml$"])
        fb.update(paths_source={"file": CI_FILE, "key": "BACK_RE"},
                  depends_on={f: {"via": "paths", "paths": [f"^{b3}/"]},
                              c: {"via": "contract", "paths": [f"^{zz}/"]}})
        ff = self.minimal(f"^{f1}/")
        ff.update(paths_source={"file": CI_FILE, "key": "FRONT_RE"},
                  depends_on={b: {"via": "files", "paths": [f"^{f2}/api/"]}})
        self.add_components(project, {b: fb, f: ff,
                                       c: self.minimal(f"^{zz}/")})
        text = self.write_targets()
        rows, out = self.run_doctor()
        for comp in (b, f):
            with self.subTest(component=comp, seed=self.seed):
                status, detail = self.paths_row(rows, project, comp, out)
                self.assertEqual(status, "ok", self.note(
                    f"{comp}: [{status}] {detail}\ntargets.yaml:\n{text}"))

    def test_ac7_shell_assignment_and_comment_lines(self):
        """Присваивание оболочки `KEY='…'`/`export KEY=…` находится; строка `# KEY: …` значением не считается.

        Сценарий: файл оболочки клона несёт `K1='^(…)'`, `export K2="^(…)"`
        и `export K3=^(…)` без кавычек; YAML-файл — строку-комментарий
        `  # K4: '^(чужое/)'` перед настоящим `  K4: '^(…)'`, второй YAML-файл
        — только комментарий `# K5: '^(…)'`. Компоненты сверяют каждый свою
        переменную с совпадающими `paths`: K1–K4 — ok; K5 — skip
        (переменной нет).

        Ловит мутацию: поиск знает только форму YAML `KEY:` — K1–K3 skip;
        `export` не снимается — K2/K3 skip; кавычки не снимаются — warn;
        комментарий не пропускается — K4 warn (взято чужое значение), K5 ok
        или warn вместо skip.
        """
        project = f"p{self.word()}"
        clone = self.clone(project)
        shell, yml, only_comment = (f"ci/{self.word(5)}.sh",
                                    f"ci/{self.word(5)}.yml",
                                    f"ci/{self.word(5)}.yml")
        comps, values = {}, {}
        for key in ("K1", "K2", "K3", "K4", "K5"):
            alts = [f"{self.word(5)}/" for _ in range(self.rng.randrange(2, 4))]
            values[key] = alts
            fields = self.minimal([f"^{a}" for a in alts])
            source = {"K1": shell, "K2": shell, "K3": shell, "K4": yml,
                      "K5": only_comment}[key]
            fields["paths_source"] = {"file": source, "key": key}
            comps[f"c{key.lower()}{self.word(4)}"] = fields
        joined = {k: "|".join(self.shuffled(v)) for k, v in values.items()}
        self.put(clone, shell, (
            "#!/bin/sh\nset -e\n"
            f"K1='^({joined['K1']})'\n"
            f"export K2=\"^({joined['K2']})\"\n"
            f"export K3=^({joined['K3']})\n"))
        self.put(clone, yml, (
            "env:\n"
            f"  # K4: '^({self.word(5)}/)'\n"
            f"  K4: '^({joined['K4']})'\n"))
        self.put(clone, only_comment, (
            "env:\n"
            f"  # K5: '^({joined['K5']})'\n"
            f"  OTHER: '^({self.word(5)}/)'\n"))
        self.add_components(project, comps)
        self.write_targets()
        rows, out = self.run_doctor()
        for comp, key in zip(comps, ("K1", "K2", "K3", "K4", "K5")):
            with self.subTest(key=key, seed=self.seed):
                self.assert_status(rows, f"project-paths-{project}-{comp}",
                                   "skip" if key == "K5" else "ok", out, key)

    def test_ac8_mismatch_warns_with_both_strings_and_skips(self):
        """Лишняя или недостающая альтернатива — warn с обеими строками; нет файла или переменной — skip; блок из нескольких строк — skip «многострочное значение не сравнивается».

        Сценарий: компоненты с `paths` одной строкой `^(x/|y/)`: переменная
        `^(x/|y/|z/)` (лишняя) и `^(x/)` (недостающая) — warn, пояснение
        содержит и значение переменной, и строку `paths`; файл, которого в
        клоне нет, и переменная, которой нет в файле, — skip с причиной;
        переменная блоком (`>-`/`>`/`|-`/`|`, вид от зерна) из двух строк —
        skip, причина — «многострочное значение не сравнивается».

        Ловит мутацию: сравнение только включения (`paths` ⊆ значения) —
        лишняя альтернатива даёт ok; текст warn называет лишь разницу, без
        сравниваемых строк; отсутствие файла — fail или исключение; строки
        блока склеиваются и сравниваются — warn или ok вместо skip.
        """
        project = f"p{self.word()}"
        clone = self.clone(project)
        ci = f"ci/{self.word(5)}.yml"
        x, y, z = (f"{self.word(5)}/" for _ in range(3))
        indicator = self.rng.choice((">-", ">", "|-", "|"))
        self.put(clone, ci, (
            "env:\n"
            f"  EXTRA_RE: '^({x}|{y}|{z})'\n"
            f"  LESS_RE: '^({x})'\n"
            f"  MULTI_RE: {indicator}\n"
            f"    ^({x}|\n"
            f"    {y})\n"
            f"  SAME_RE: '^({x}|{y})'\n"))
        paths = f"^({x}|{y})"
        cases = {"лишняя": (ci, "EXTRA_RE", "warn", f"^({x}|{y}|{z})"),
                 "недостающая": (ci, "LESS_RE", "warn", f"^({x})"),
                 "нет файла": (f"ci/{self.word(5)}.yml", "SAME_RE", "skip", ""),
                 "нет переменной": (ci, "NONE_RE", "skip", ""),
                 "многострочный": (ci, "MULTI_RE", "skip", MULTILINE)}
        comps = {}
        for label, (source, key, _, _) in cases.items():
            fields = self.minimal(paths)
            fields["paths_source"] = {"file": source, "key": key}
            comps[f"c{self.word(5)}"] = fields
        self.add_components(project, comps)
        self.write_targets()
        rows, out = self.run_doctor()
        for comp, (label, (_, _, status, text)) in zip(comps, cases.items()):
            with self.subTest(case=label, block=indicator, seed=self.seed):
                detail = self.assert_status(
                    rows, f"project-paths-{project}-{comp}", status, out, label)
                if status == "warn":
                    self.assertIn(text, detail, self.note(f"{label}: {detail}"))
                    self.assertIn(paths, detail, self.note(f"{label}: {detail}"))
                elif text:
                    self.assertIn(text, detail, self.note(f"{label}: {detail}"))

    def test_ac9_top_level_alternatives_and_union(self):
        """Деление идёт по `|` верхнего уровня одной ведущей группы; `paths` списком объединяется с `paths` его `depends_on`.

        Сценарий: переменные `^(a|b(c|d))` при `paths` `[a, b(c|d)]` — ok;
        `^(a|b|c)` и `a|b|c` при `paths` `[a, b, c]` — ok каждая;
        `^(z/|x/|y/)` при `paths` компонента `[^x/, ^y/]` и `depends_on` вида
        `paths` с `[^z/]` — ok. Части выражений — слова от зерна.

        Ловит мутацию: деление по каждому `|` (в том числе внутри скобок) —
        `{a, b(c, d)}` не совпадает с `paths`, первая строка warn; ведущая
        группа не раскрывается — `^(a|b|c)` даёт одну альтернативу, warn;
        `paths` списка берётся только первым элементом или `depends_on` не
        объединяется — последняя строка warn.
        """
        project = f"p{self.word()}"
        clone = self.clone(project)
        ci = f"ci/{self.word(5)}.yml"
        a, b, c, d = (self.word(5) for _ in range(4))
        nested = f"{b}(/{c}|/{d})"
        p, r, s = (self.word(5) for _ in range(3))
        u, v, w = (self.word(5) for _ in range(3))
        dep = f"c{self.word(5)}"
        self.put(clone, ci, (
            "env:\n"
            f"  NESTED_RE: '^({a}|{nested})'\n"
            f"  GROUP_RE: '^({'|'.join(self.shuffled([p, r, s]))})'\n"
            f"  PLAIN_RE: '{'|'.join(self.shuffled([p, r, s]))}'\n"
            f"  UNION_RE: '^({'|'.join(self.shuffled([u + '/', v + '/', w + '/']))})'\n"))
        cases = {"вложенная группа": ("NESTED_RE", [a, nested], None),
                 "ведущая группа": ("GROUP_RE", [p, r, s], None),
                 "без группы": ("PLAIN_RE", [p, r, s], None),
                 "объединение с depends_on": ("UNION_RE", [f"^{v}/", f"^{w}/"],
                                              f"^{u}/")}
        comps = {}
        for label, (key, paths, extra) in cases.items():
            fields = self.minimal(paths)
            fields["paths_source"] = {"file": ci, "key": key}
            if extra:
                fields["depends_on"] = {dep: {"via": "paths", "paths": [extra]}}
            comps[f"c{self.word(5)}"] = fields
        comps[dep] = self.minimal(f"^{self.word(5)}/")
        self.add_components(project, comps)
        text = self.write_targets()
        rows, out = self.run_doctor()
        for comp, label in zip(comps, cases):
            with self.subTest(case=label, seed=self.seed):
                self.assert_status(rows, f"project-paths-{project}-{comp}",
                                   "ok", out, f"{label}; targets.yaml:\n{text}\n")

    def test_ac10_unparseable_value_or_paths_skip(self):
        """Неразбираемое значение переменной или строка `paths` — skip с причиной; причина о `paths` называет строку.

        Сценарий: переменные со значением `''` (пустое), `^(x/|y/`
        (несбалансированные скобки), `x/||y/` и `^(x/|)` (пустая
        альтернатива), `^(x/|y/)z/` (хвост после ведущей группы) при `paths`
        `[^x/, ^y/]` — skip с причиной каждая; переменная `^(x/|y/)` при
        `paths` `[^x/, ^y/, <a>/||<b>/]` — skip, причина содержит `<a>/||<b>/`.

        Ловит мутацию: пустая альтернатива отбрасывается молча (`x/||y/` →
        `{x/, y/}` — ok); хвост после группы игнорируется (ok); пустое
        значение даёт пустое множество и warn; неразбираемая строка `paths`
        пропускается, а сравнение идёт по остальным (ok).
        """
        project = f"p{self.word()}"
        clone = self.clone(project)
        ci = f"ci/{self.word(5)}.yml"
        x, y, tail, m, n = (self.word(5) for _ in range(5))
        values = {"пустое": "", "несбалансированные скобки": f"^({x}/|{y}/",
                  "пустая альтернатива": f"{x}/||{y}/",
                  "пустая альтернатива в группе": f"^({x}/|)",
                  "хвост после группы": f"^({x}/|{y}/){tail}/"}
        lines, comps, labels = ["env:"], {}, []
        for i, (label, value) in enumerate(values.items()):
            key = f"BAD{i}_RE"
            lines.append(f"  {key}: '{value}'")
            fields = self.minimal([f"^{x}/", f"^{y}/"])
            fields["paths_source"] = {"file": ci, "key": key}
            comps[f"c{self.word(5)}"] = fields
            labels.append((label, None))
        lines.append(f"  GOOD_RE: '^({x}/|{y}/)'")
        bad_paths = f"{m}/||{n}/"
        fields = self.minimal([f"^{x}/", f"^{y}/", bad_paths])
        fields["paths_source"] = {"file": ci, "key": "GOOD_RE"}
        comps[f"c{self.word(5)}"] = fields
        labels.append(("неразбираемая строка paths", bad_paths))
        self.put(clone, ci, "\n".join(lines) + "\n")
        self.add_components(project, comps)
        self.write_targets()
        rows, out = self.run_doctor()
        for comp, (label, named) in zip(comps, labels):
            with self.subTest(case=label, seed=self.seed):
                detail = self.assert_status(
                    rows, f"project-paths-{project}-{comp}", "skip", out, label)
                if named:
                    self.assertIn(named, detail, self.note(detail))


# ------------------------------------------------------------------ AC-11

class WorkdirTest(DoctorComponentsSandbox):

    def test_ac11_missing_workdir_fails_absent_field_no_row(self):
        """Каталога `workdir` нет в клоне — строка `project-workdir-…` fail; компонент без `workdir` строки не получает.

        Сценарий: запись из трёх компонентов: у первого `workdir` есть в
        клоне (каталог с файлом), у второго — каталога нет, у третьего поля
        `workdir` нет. Строка первого — не fail, второго — fail с причиной;
        строки `project-workdir-<проект>-<третий>` нет.

        Ловит мутацию: проверка смотрит наличие пути от корня пульта, а не
        клона — оба fail; отсутствующий каталог даёт warn/skip; компоненту
        без `workdir` печатается строка (`workdir` — пустая строка → корень
        клона есть → ok).
        """
        project = f"p{self.word()}"
        clone = self.clone(project)
        present, missing = self.word(5), self.word(5)
        self.put(clone, f"{present}/{self.word(4)}.txt", "x\n")
        first, second, third = (f"c{self.word(5)}" for _ in range(3))
        f1 = self.minimal(f"^{present}/")
        f1["workdir"] = present
        f2 = self.minimal(f"^{missing}/")
        f2["workdir"] = missing
        self.add_components(project, {first: f1, second: f2,
                                      third: self.minimal(f"^{self.word(5)}/")})
        self.write_targets()
        rows, out = self.run_doctor()
        got, detail = self.row(rows, f"project-workdir-{project}-{first}", out)
        self.assertNotEqual(got, "fail", self.note(f"есть каталог: {detail}"))
        self.assert_status(rows, f"project-workdir-{project}-{second}", "fail", out)
        self.assert_no_rows(rows, f"project-workdir-{project}-{third}", out)


# ------------------------------------------------------------------ AC-15 (doctor)

class TestProfileRecordsUnchangedTest(DoctorComponentsSandbox):

    def test_ac15_test_profile_records_have_no_component_rows(self):
        """У записей с `test_profile` нет строк `project-tools-…`/`project-paths-…`/`project-workdir-…`, строка предела — прежнего вида.

        Сценарий: артель песочницы (`pult-pytest`) и внешний проект вида
        sled — `test_profile` с `runner: pytest-own`, `workdir` (каталог есть
        в клоне) и пределом N от зерна; в клоне CI-файл с переменной путей.
        Строк трёх новых видов ни у одной записи нет; строка
        `full-suite-timeout-<имя>` — ok с прежним текстом «проект <имя>:
        предел полного прогона tests/ <предел> с (источник: <источник>)»
        (у артели — `config.FULL_SUITE_TIMEOUT_SEC` и `config`, у проекта — N
        и «профиль тестов проекта <имя>»).

        Ловит мутацию: `test_profile` читается как компонент `default`, и
        проверка `workdir` профиля печатает `project-workdir-<имя>-default`;
        текст строки предела переписан под компоненты.
        """
        project = f"p{self.word()}"
        clone = self.clone(project)
        workdir = self.word(5)
        limit = self.rng.randrange(60, 5000)
        self.put(clone, f"{workdir}/.keep")
        self.put(clone, CI_FILE, f"env:\n  BACK_RE: '^({workdir}/)'\n")
        self.add_entry(HEAD.format(name=project) + (
            "    test_profile:\n"
            "      command: [python3, -m, pytest]\n"
            "      long_lived_dir: tests\n"
            "      long_lived_name: test_<id>_<name>.py\n"
            "      weakening_scope: [tests/**/*.py]\n"
            "      mutation_claim_scope: [tests/test_*.py]\n"
            f"      full_suite_timeout_sec: {limit}\n"
            "      runner: pytest-own\n"
            f"      workdir: {workdir}\n"))
        self.write_targets()
        rows, out = self.run_doctor()
        expected = {
            config.DEFAULT_TARGET: (config.FULL_SUITE_TIMEOUT_SEC, "config"),
            project: (limit, f"профиль тестов проекта {project}")}
        for name, (seconds, source) in expected.items():
            with self.subTest(target=name, seed=self.seed):
                for kind in ("tools", "paths", "workdir"):
                    self.assert_no_rows(rows, f"project-{kind}-{name}-", out)
                self.assertEqual(
                    self.row(rows, f"full-suite-timeout-{name}", out),
                    ("ok", f"проект {name}: предел полного прогона tests/ "
                           f"{seconds} с (источник: {source})"), self.note())


if __name__ == "__main__":
    unittest.main()
