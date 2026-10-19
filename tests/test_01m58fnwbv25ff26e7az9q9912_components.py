"""Компоненты проекта в записи targets.yaml: схема, profile_of, выбор по путям, идентификатор теста.

Группа: долгоживущий
Красен до реализации: проверка записи не знает поля `components:` (неверные формы проходят молча, `test_profile` вместе с `components:` не отвергается), у `project_profile` нет `components`/`select_components`/`test_id`/`parse_test_id`, у `ProfileAnswer` нет признака `multi`, `profile_of` не читает единственный компонент — вызовы падают `AttributeError`, отказы не наступают.

Свойства без песочницы путей пульта: `config.TARGETS` подменён временным
файлом, учебные записи пишутся его текстом и читаются `targets.load` (формы,
которые текстом `yamlmini` не записать, и перебор неверных форм — словарём в
`targets.check`). `for_task` получает соединение sqlite в памяти с таблицей
задач из двух колонок — `store.task_target` читает только её. Имена
каталогов, путей и значения подполей — из `random`, зерно печатается и
входит в текст каждого провала.

Отказы, действующие только до G1б/G2б (запись с несколькими компонентами у
читателей профиля, единственный компонент без пары `long_lived_dir`/
`long_lived_name`), проверяет разовая планка задачи (AC-8 — AC-10): после G1б
и G2б это поведение меняется по плану волны.
"""
import copy
import random
import sqlite3
import string
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from unittest import mock

from orchestrator import config, project_profile, repo_context, targets
from tests.sandbox import ARTEL_TEST_PROFILE

ARTEL = config.DEFAULT_TARGET

HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

# Учебная запись AC-1: `frontend` зависит от `backend` по `depends_on` вида
# `files`; у компонентов — формы требования 3 (`long_lived` без пары у
# записи с несколькими компонентами допустим).
BACKEND = r"""      backend:
        command: [cargo, test]
        weakening_scope: [backend/**/*.rs]
        mutation_claim_scope: [backend/tests/*.rs]
        paths: [^backend/, ^Cargo\.toml$]
        test_support: [testkit/**]
        install: [cargo, fetch, --locked]
        long_lived: backend/tests/test_<id>_<name>.rs
        knowledge: [docs/backend.md]
        tools:
          cargo: "1.80"
        paths_source:
          file: .github/workflows/ci.yml
          key: backend_paths
"""
FRONTEND = r"""      frontend:
        command: [npx, vitest, run]
        weakening_scope: [frontend/**/*.ts]
        mutation_claim_scope: [frontend/**/*.test.ts]
        paths: ^frontend/
        test_support: [e2e/**]
        report: pult-vitest
        long_lived: frontend/tests/test_<id>_<name>.test.ts
        depends_on:
          backend:
            via: files
            paths: [^backend/api/]
"""

ALPHABET = string.ascii_lowercase


def component_name(item) -> str:
    """Имя элемента `project_profile.components`: SPEC называет только «имя
    компонента и его поля», не форму элемента."""
    name = getattr(item, "name", None)
    if isinstance(name, str):
        return name
    if isinstance(item, Mapping):
        return item["name"]
    return item[0]


def task_conn(task_id: str, target: str) -> sqlite3.Connection:
    """Соединение с одной строкой задачи — всё, что читает
    `store.task_target`."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, target TEXT)")
    conn.execute("INSERT INTO tasks (id, target) VALUES (?, ?)",
                 (task_id, target))
    return conn


class TargetsFileTest(unittest.TestCase):
    """`config.TARGETS` — временный файл; зерно случайных входов."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="components-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "targets.yaml"
        patcher = mock.patch.object(config, "TARGETS", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def word(self, size: int = 7) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def write(self, *entries: str) -> None:
        self.path.write_text("targets:\n" + "".join(entries), encoding="utf-8")

    def artel(self) -> str:
        return HEAD.format(name=ARTEL) + ARTEL_TEST_PROFILE

    def two_components(self, name: str, reverse: bool = False) -> str:
        parts = (FRONTEND, BACKEND) if reverse else (BACKEND, FRONTEND)
        return HEAD.format(name=name) + "    components:\n" + "".join(parts)

    def names(self, target: str) -> list:
        return [component_name(c) for c in project_profile.components(target)]


# ------------------------------------------------------------------ AC-1

class TwoComponentRecordTest(TargetsFileTest):

    def test_ac1_two_component_record_loads_and_reaches_caller(self):
        """Учебная запись из двух компонентов проходит `targets.load`, разобранные значения доходят до вызывающего.

        Сценарий: текст `targets.yaml` — артель с `test_profile` и проект со
        случайным именем, у которого `components:` несёт `backend` и
        `frontend` (`paths`, `test_support`, `depends_on` вида `files` у
        `frontend` на `backend`, `paths_source`, `tools`, `install`,
        `long_lived`, `knowledge`). `targets.load` не отказывает; в
        разобранной записи — компоненты по именам, `depends_on.backend.via`
        равно `files`, `tools.cargo` — строка `1.80`, `paths_source` — `file`
        и `key`. `project_profile.components` даёт `backend`, `frontend` в
        порядке записи; при обратном порядке записи — `frontend`, `backend`.

        Ловит мутацию: проверка записи не знает поля `depends_on`/`tools`/
        `paths_source`/`long_lived` либо требует пару `long_lived_dir`/
        `long_lived_name` у каждого компонента — `load` бросает
        `TargetsError`; `components` сортирует имена — при обратном порядке
        записи выходит `backend`, `frontend`.
        """
        name = f"p{self.word()}"
        for reverse in (False, True):
            with self.subTest(reverse=reverse, seed=self.seed):
                self.write(self.artel(), self.two_components(name, reverse))
                entries = targets.load()
                comps = entries[name]["components"]
                expected = (["frontend", "backend"] if reverse
                            else ["backend", "frontend"])
                self.assertEqual(list(comps), expected, self.note())
                self.assertEqual(
                    comps["frontend"]["depends_on"]["backend"]["via"], "files",
                    self.note())
                self.assertEqual(comps["backend"]["tools"], {"cargo": "1.80"},
                                 self.note())
                self.assertEqual(comps["backend"]["paths_source"],
                                 {"file": ".github/workflows/ci.yml",
                                  "key": "backend_paths"}, self.note())
                self.assertEqual(self.names(name), expected, self.note())


# ------------------------------------------------------------------ AC-2

def base_entry() -> dict:
    return {"forge": "github", "url": "https://localhost/artel-tests/proj",
            "base": "main", "token_slot": "proj-token", "no_paths": [],
            "project_skills": [], "merge_gate": "operator"}


def multi_components() -> dict:
    return {
        "backend": {"command": ["cargo", "test"],
                    "weakening_scope": ["backend/**"],
                    "mutation_claim_scope": ["backend/tests/*.rs"],
                    "paths": ["^backend/"]},
        "frontend": {"command": ["npx", "vitest", "run"],
                     "weakening_scope": ["frontend/**"],
                     "mutation_claim_scope": ["frontend/**/*.test.ts"],
                     "paths": ["^frontend/"]},
    }


def single_components() -> dict:
    return {"app": {"command": ["python3", "-m", "pytest"],
                    "long_lived_dir": "tests",
                    "long_lived_name": "test_<id>_<name>.py",
                    "weakening_scope": ["tests/**/*.py"],
                    "mutation_claim_scope": ["tests/test_*.py"]}}


ALTERNATIVES = "не поддерживаются — разверните в несколько масок"


class ComponentFormsTest(TargetsFileTest):

    def entry_with(self, comps: dict) -> dict:
        entry = base_entry()
        entry["components"] = comps
        return entry

    def refusal(self, name: str, entry: dict) -> str:
        """Текст отказа `targets.check` без адреса файла (в нём могут быть
        любые буквы временного каталога)."""
        with self.assertRaises(targets.TargetsError, msg=self.note(
                f"нет отказа: {entry.get('components')!r}")) as caught:
            targets.check(name, entry)
        return str(caught.exception).replace(str(config.TARGETS), "<targets>")

    def field_cases(self, comp: str, other: str) -> list:
        """(подслучай, поле, значение) — неверная форма поля компонента
        `comp` записи с двумя компонентами; `other` — второй компонент."""
        good_dep = {"via": "files", "paths": ["^x/"]}
        return [
            ("command не список", "command", "pytest"),
            ("command пустой", "command", []),
            ("long_lived_dir абсолютный", "long_lived_dir", "/abs"),
            ("long_lived_name без <id>", "long_lived_name", "plain.py"),
            ("weakening_scope не список", "weakening_scope", "x/**"),
            ("mutation_claim_scope не список", "mutation_claim_scope", 7),
            ("full_suite_timeout_sec ноль", "full_suite_timeout_sec", 0),
            ("runner неизвестный", "runner", "nose"),
            ("workdir с ..", "workdir", "../up"),
            ("env не отображение", "env", "A=1"),
            ("long_lived_imports не список", "long_lived_imports", "numpy"),
            ("report вне junit-xml|pult-vitest", "report", "html"),
            ("install пустой", "install", []),
            ("checks_local пустой", "checks_local", []),
            ("long_lived без <id>", "long_lived", "tests/test_x.py"),
            ("long_lived с иным заполнителем", "long_lived",
             "tests/<file>/test_<id>.py"),
            ("plank_layout без <id>", "plank_layout", "plank/acceptance"),
            ("repo пустой", "repo", ""),
            ("report_args не список", "report_args", "-q"),
            ("report_args с пустой строкой", "report_args", [""]),
            ("select не список", "select", "unit"),
            ("select с пустой строкой", "select", [""]),
            ("failure_errors не список", "failure_errors", "Error"),
            ("failure_errors с пустой строкой", "failure_errors", [""]),
            ("layers не список", "layers", "unit"),
            ("layers с пустой строкой", "layers", [""]),
            ("knowledge с ..", "knowledge", ["../x.md"]),
            ("knowledge с ведущим /", "knowledge", ["/x.md"]),
            ("knowledge не список", "knowledge", "docs/x.md"),
            ("tests не список", "tests", "tests/**"),
            ("test_support не список", "test_support", "kit/**"),
            ("paths не компилируется", "paths", ["(unclosed"]),
            ("paths одной строкой не компилируется", "paths", "(unclosed"),
            ("paths с ,", "paths", ["^a,b"]),
            ("paths с [", "paths", ["^a[bc]"]),
            ("paths с ]", "paths", ["^a]"]),
            ('paths с "', "paths", ['^a"b']),
            ("paths с '", "paths", ["^a'b"]),
            ("paths с элементом-числом", "paths", [1]),
            ("paths пустой у записи с несколькими компонентами", "paths", []),
            ("paths_source без key", "paths_source", {"file": "ci.yml"}),
            ("paths_source с лишним подполем", "paths_source",
             {"file": "ci.yml", "key": "k", "extra": "x"}),
            ("depends_on не отображение", "depends_on", other),
            ("depends_on на несуществующий компонент", "depends_on",
             {"ghost": dict(good_dep)}),
            ("depends_on на сам компонент", "depends_on",
             {comp: dict(good_dep)}),
            ("via вне paths|files|contract", "depends_on",
             {other: {"via": "magic", "paths": ["^x/"]}}),
            ("depends_on без via", "depends_on", {other: {"paths": ["^x/"]}}),
            ("depends_on без paths", "depends_on", {other: {"via": "files"}}),
            ("depends_on с лишним полем", "depends_on",
             {other: {"via": "files", "paths": ["^x/"], "extra": "y"}}),
            ("depends_on.paths не компилируется", "depends_on",
             {other: {"via": "paths", "paths": ["(unclosed"]}}),
            ("depends_on.paths с ,", "depends_on",
             {other: {"via": "paths", "paths": ["^a,b"]}}),
            ("depends_on.paths с [", "depends_on",
             {other: {"via": "files", "paths": ["^a[b"]}}),
            ("depends_on.paths с ]", "depends_on",
             {other: {"via": "files", "paths": ["^a]"]}}),
            ("depends_on.paths с элементом-числом", "depends_on",
             {other: {"via": "contract", "paths": [1]}}),
            ("tools не отображение", "tools", "node 22"),
            ("значение tools не строка", "tools", {"node": 22}),
            ("неизвестное поле", "colour", "red"),
            ("поле name", "name", comp),
        ]

    def test_ac2_wrong_field_form_refused_naming_component_and_field(self):
        """Каждое поле компонента неверной формы даёт отказ `targets.check`, называющий компонент и поле.

        Сценарий: исправная запись внешнего проекта с компонентами `backend`
        и `frontend` проходит проверку; затем в случайно выбранный компонент
        по одному вносится каждый подслучай AC-2 (прежние подполя профиля не
        того вида, `report`, `install`/`checks_local`, `long_lived`,
        `plank_layout`, `repo`, списки строк, `knowledge`, маски, `paths`,
        `paths_source`, `depends_on` и его `paths`, `tools`, неизвестное поле
        и `name`, удалённое `paths`). Каждый раз — `TargetsError` (не
        `TypeError`/`re.error`), текст называет компонент и поле.

        Ловит мутацию: проверка компонента пропускает одно из полей (например,
        не проверяет `depends_on.paths` или элемент `paths` не строкой падает
        `TypeError` в `re.compile`), принимает лишнее подполе `paths_source`/
        `depends_on`, не отвергает `name` или поставщика — сам компонент; либо
        текст отказа не называет компонент — тест краснеет на подслучае.
        """
        targets.check("proj", self.entry_with(multi_components()))
        for label, field, value in self.field_cases("C", "O"):
            comp = self.rng.choice(("backend", "frontend"))
            other = "frontend" if comp == "backend" else "backend"
            value = copy.deepcopy(value)
            if field == "depends_on":
                value = (other if isinstance(value, str) else
                         {(comp if k == "C" else other if k == "O" else k): v
                          for k, v in value.items()})
            elif field == "name":
                value = comp
            with self.subTest(case=label, component=comp, seed=self.seed):
                comps = multi_components()
                comps[comp][field] = value
                text = self.refusal("proj", self.entry_with(comps))
                self.assertIn(comp, text, self.note(label))
                self.assertIn(field, text, self.note(label))

    def test_ac2_structure_and_entry_level_refusals(self):
        """Отказы формы `components:` целиком, имени компонента, правила артели, `workdir`/`env`, `repo` и масок с `{`.

        Сценарий: `components:` пустое и не отображение; поля компонента не
        отображение; имя компонента с `:`; у записи с несколькими
        компонентами нет `paths` у компонента; `long_lived` вместе с
        `long_lived_dir`; `long_lived_imports` у компонента записи артели;
        у записи с одним компонентом `workdir`, а также `env`, при `runner:
        pult-pytest` и без `runner`; `repo`, отличный от имени записи, —
        текст «несколько репозиториев не исполняются»; маска `tests` или
        `test_support` с `{` — текст «альтернативы `{a,b}` не
        поддерживаются — разверните в несколько масок». Каждый раз —
        `TargetsError`, текст называет компонент (или `components`) и поле.

        Ловит мутацию: правило `workdir`/`env` не перенесено на единственный
        компонент; правило `PROFILE_EXTERNAL_ONLY` не применено к компоненту
        артели; `repo` сверяется только у единственного компонента или не
        сверяется вовсе; маска с `{` молча не совпадает вместо отказа;
        `components: {}` принимается — тест краснеет на своём подслучае.
        """
        comp = self.rng.choice(("backend", "frontend"))
        cases = []
        cases.append(("components пустое", "proj", {}, ("components",), ()))
        cases.append(("components не отображение", "proj", ["backend"],
                      ("components",), ()))
        comps = multi_components()
        comps[comp] = "x"
        cases.append(("поля компонента не отображение", "proj", comps,
                      (comp,), ()))
        comps = multi_components()
        comps["a:b"] = comps.pop(comp)
        cases.append(("имя компонента с :", "proj", comps, ("a:b",), ()))
        comps = multi_components()
        del comps[comp]["paths"]
        cases.append(("paths нет у компонента записи с несколькими", "proj",
                      comps, (comp, "paths"), ()))
        comps = multi_components()
        comps[comp].update(long_lived="tests/test_<id>_<name>.py",
                           long_lived_dir="tests")
        cases.append(("long_lived вместе с long_lived_dir", "proj", comps,
                      (comp, "long_lived"), ()))
        comps = multi_components()
        comps[comp]["long_lived_imports"] = ["numpy"]
        cases.append(("long_lived_imports у артели", ARTEL, comps,
                      (comp, "long_lived_imports"), ()))
        comps = multi_components()
        comps[comp]["repo"] = f"r{self.word()}"
        cases.append(("repo не имя записи", "proj", comps, (comp, "repo"),
                      ("несколько репозиториев не исполняются",)))
        for field in ("tests", "test_support"):
            comps = multi_components()
            comps[comp][field] = ["src/{a,b}/*.py"]
            cases.append((f"{field} с {{", "proj", comps, (comp, field),
                          ("альтернативы", "{a,b}", ALTERNATIVES)))
        for field, value in (("workdir", "tests"), ("env", {"A": "1"})):
            for runner in ("pult-pytest", None):
                comps = single_components()
                comps["app"][field] = value
                if runner:
                    comps["app"]["runner"] = runner
                cases.append((f"{field} у единственного, runner={runner}",
                              "proj", comps, ("app", field), ()))
        for label, name, comps, names, texts in cases:
            with self.subTest(case=label, seed=self.seed):
                text = self.refusal(name, self.entry_with(comps))
                for part in names + texts:
                    self.assertIn(part, text, self.note(label))

    def test_ac2_allowed_forms_pass(self):
        """Без отказа проходят `report: pult-vitest` и `workdir`/`env` без `runner` у компонента записи с несколькими компонентами.

        Сценарий: в случайный компонент исправной записи с двумя
        компонентами по отдельности и вместе вносятся `report: pult-vitest`,
        `workdir` (случайный относительный каталог) и `env` (строка в
        строку) без `runner`. `targets.check` не отказывает.

        Ловит мутацию: правило `workdir`/`env` применено и к записи с
        несколькими компонентами либо `report` проверяется прежним перечнем
        `PROFILE_REPORTS` (`junit-xml`) — `targets.check` отказывает.
        """
        comp = self.rng.choice(("backend", "frontend"))
        variants = {"report": {"report": "pult-vitest"},
                    "workdir": {"workdir": f"w{self.word()}"},
                    "env": {"env": {f"V{self.word().upper()}": self.word()}}}
        variants["вместе"] = {k: v for d in list(variants.values())
                              for k, v in d.items()}
        for label, fields in variants.items():
            with self.subTest(case=label, component=comp, seed=self.seed):
                comps = multi_components()
                comps[comp].update(copy.deepcopy(fields))
                targets.check("proj", self.entry_with(comps))


# ------------------------------------------------------------------ AC-3

class ProfileAndComponentsTest(TargetsFileTest):

    def test_ac3_test_profile_with_components_refused(self):
        """Запись с одновременно `test_profile` и `components:` получает отказ проверки записи.

        Сценарий: исправный `test_profile` и исправные `components:` (с одним
        и с двумя компонентами) по отдельности проходят `targets.check`;
        запись, несущая `test_profile` и `components:` сразу, — `TargetsError`.

        Ловит мутацию: проверка смотрит `components:` только при отсутствии
        `test_profile` (или наоборот) — запись с обоими полями проходит.
        """
        profile = {"command": ["python3", "-m", "pytest"],
                   "long_lived_dir": "tests",
                   "long_lived_name": "test_<id>_<name>.py",
                   "weakening_scope": ["tests/**/*.py"],
                   "mutation_claim_scope": ["tests/test_*.py"]}
        for label, comps in (("один компонент", single_components()),
                             ("два компонента", multi_components())):
            with self.subTest(case=label, seed=self.seed):
                only_profile = base_entry()
                only_profile["test_profile"] = dict(profile)
                targets.check("proj", only_profile)
                only_comps = base_entry()
                only_comps["components"] = comps
                targets.check("proj", only_comps)
                both = dict(only_comps, test_profile=dict(profile))
                with self.assertRaises(targets.TargetsError,
                                       msg=self.note(label)):
                    targets.check("proj", both)


# ------------------------------------------------------------------ AC-4

class TestProfileUnchangedTest(TargetsFileTest):

    def external_profile(self, name: str) -> tuple:
        """(текст записи с полным `test_profile`, ожидаемый `Profile`)."""
        lld = f"c{self.word()}"
        workdir = f"w{self.word()}"
        timeout = self.rng.randrange(60, 5000)
        var, val = f"V{self.word().upper()}", f"v{self.word()}"
        text = HEAD.format(name=name) + (
            f"    test_profile:\n"
            f"      command: [python3, -m, pytest, -q]\n"
            f"      long_lived_dir: {lld}\n"
            f"      long_lived_name: check_<id>_<name>.py\n"
            f"      weakening_scope: [{lld}/**/*.py]\n"
            f"      mutation_claim_scope: [{lld}/check_*.py]\n"
            f"      report: junit-xml\n"
            f"      install: [pip, install, -e, .]\n"
            f"      full_suite_timeout_sec: {timeout}\n"
            f"      runner: pytest-own\n"
            f"      workdir: {workdir}\n"
            f"      env:\n"
            f"        {var}: {val}\n"
            f"      long_lived_imports: [numpy]\n")
        expected = project_profile.Profile(
            command=("python3", "-m", "pytest", "-q"), long_lived_dir=lld,
            long_lived_name="check_<id>_<name>.py",
            weakening_scope=(f"{lld}/**/*.py",),
            mutation_claim_scope=(f"{lld}/check_*.py",), report="junit-xml",
            install=("pip", "install", "-e", "."),
            full_suite_timeout_sec=timeout, runner="pytest-own",
            workdir=workdir, env={var: val}, long_lived_imports=("numpy",))
        return text, expected, timeout

    def random_paths(self) -> list:
        return [f"{self.word(3)}/{self.word()}.{self.rng.choice(('py', 'md', 'rs'))}"
                for _ in range(self.rng.randrange(0, 4))]

    def test_ac4_test_profile_records_read_as_before(self):
        """Записи с `test_profile` (артель и внешний проект) дают прежние `Profile`, исходы и предел; читаются одним компонентом `default`.

        Сценарий: артель с профилем песочницы и внешний проект со случайным
        полным `test_profile` (`pytest-own`, `workdir`, `env`, предел,
        `long_lived_imports`). `decide` и `for_task` дают ровно ожидаемый
        `Profile` без отказа и пропуска; `full_suite_limit` — предел профиля
        с источником «профиль тестов проекта <имя>» у внешнего и
        `config.FULL_SUITE_TIMEOUT_SEC` с источником `config` у артели;
        `profile_of` — PRESENT, `multi` ложно. `components` у каждой записи —
        один элемент `default`; `select_components` на случайных наборах
        путей (в том числе пустом) — `("default",)`.

        Ловит мутацию: чтение `test_profile` через новый путь компонента
        теряет подполе (`report`, `install`, `env`, предел) — `Profile` или
        предел отличаются; `components` у записи с `test_profile` пуст или
        называет компонент иначе, чем `default`; `select_components` при
        пустом наборе или пути вне масок даёт `()`.
        """
        ext = f"p{self.word()}"
        text, expected, timeout = self.external_profile(ext)
        self.write(self.artel(), text)
        artel_profile = project_profile.Profile(
            command=("python3", "-m", "pytest"), long_lived_dir="tests",
            long_lived_name="test_<id>_<name>.py",
            weakening_scope=("tests/**/*.py",),
            mutation_claim_scope=("tests/test_*.py",), report="junit-xml",
            install=())
        cases = ((ARTEL, artel_profile,
                  (config.FULL_SUITE_TIMEOUT_SEC, "config")),
                 (ext, expected, (timeout, f"профиль тестов проекта {ext}")))
        for target, profile, limit in cases:
            with self.subTest(target=target, seed=self.seed):
                task_id = f"T{self.rng.randrange(10**6)}"
                for decision in (project_profile.decide(target),
                                 project_profile.for_task(
                                     task_conn(task_id, target), task_id)):
                    self.assertEqual(decision.profile, profile, self.note())
                    self.assertEqual((decision.refusal, decision.skip),
                                     ("", ""), self.note())
                self.assertEqual(project_profile.full_suite_limit(target),
                                 limit, self.note())
                answer = repo_context.profile_of(target)
                self.assertEqual(answer.outcome, repo_context.PROFILE_PRESENT)
                self.assertIs(answer.multi, False, self.note())
                self.assertEqual(self.names(target), ["default"], self.note())
                for _ in range(4):
                    paths = self.random_paths()
                    self.assertEqual(
                        project_profile.select_components(target, paths),
                        ("default",), self.note(f"пути {paths}"))

    def test_ac4_texts_and_absent_record_unchanged(self):
        """Тексты отказов и пропуска у записей с `test_profile` прежние; у записи ABSENT `components` и выбор пусты.

        Сценарий: (1) внешний проект без `test_profile` и без `components:`
        — `decide` даёт прежний текст пропуска, `components` и
        `select_components` — `()`; артель без профиля — прежний текст
        отказа; (2) у внешнего проекта `test_profile` без `command` — у
        артели `decide` даёт прежний текст «профиль тестов проекта «artel»
        не прочитан (поле test_profile записи в targets.yaml): <причина
        проверки>», `full_suite_limit` — `TargetsError` с той же причиной, у
        внешнего — прежний отказ неразрешённого контекста; (3)
        `test_profile.report: pult-vitest` — `targets.load` отказывает
        прежним текстом «подполе 'test_profile.report' — 'pult-vitest',
        ожидается junit-xml».

        Ловит мутацию: `pult-vitest` добавлен в общий перечень отчётов и
        стал допустим у `test_profile`; текст отказа UNREAD переписан под
        компоненты; запись ABSENT читается как компонент `default` — тест
        краснеет на своём шаге.
        """
        ext = f"p{self.word()}"
        where = f"{config.TARGETS}: target '{ext}'"
        self.write(HEAD.format(name=ARTEL), HEAD.format(name=ext))
        with self.subTest(case="ABSENT", seed=self.seed):
            decision = project_profile.decide(ext)
            self.assertEqual(decision.skip,
                             f"у проекта «{ext}» нет test_profile в targets.yaml",
                             self.note())
            self.assertIsNone(decision.profile)
            self.assertEqual(project_profile.decide(ARTEL).refusal, (
                f"у проекта «{ARTEL}» нет поля test_profile в targets.yaml — "
                f"гейты целостности тестов пульта без профиля не отключаются "
                f"(ADR-0002)"), self.note())
            self.assertEqual(tuple(project_profile.components(ext)), (),
                             self.note())
            self.assertEqual(project_profile.select_components(
                ext, [f"src/{self.word()}.py", "docs/x.md"]), (), self.note())
        broken = HEAD.format(name=ext) + (
            "    test_profile:\n"
            "      long_lived_dir: tests\n"
            "      long_lived_name: test_<id>_<name>.py\n"
            "      weakening_scope: [tests/**/*.py]\n"
            "      mutation_claim_scope: [tests/test_*.py]\n")
        self.write(self.artel(), broken)
        reason = f"{where}: нет подполя 'test_profile.command'"
        with self.subTest(case="UNREAD", seed=self.seed):
            self.assertEqual(project_profile.decide(ARTEL).refusal, (
                f"профиль тестов проекта «{ARTEL}» не прочитан (поле "
                f"test_profile записи в targets.yaml): {reason}"), self.note())
            with self.assertRaises(targets.TargetsError) as caught:
                project_profile.full_suite_limit(ARTEL)
            self.assertEqual(str(caught.exception), reason, self.note())
            decision = project_profile.decide(ext)
            self.assertTrue(decision.unresolved, self.note())
            self.assertEqual(decision.refusal, (
                f"контекст проекта «{ext}» не разрешён: записи проекта нет в "
                f"targets.yaml или файл не читается — проверки тестов без "
                f"него не выполняются"), self.note())
        self.write(self.artel(), broken.replace(
            "    test_profile:\n",
            "    test_profile:\n      command: [python3, -m, pytest]\n"
            "      report: pult-vitest\n"))
        with self.subTest(case="report pult-vitest", seed=self.seed):
            with self.assertRaises(targets.TargetsError) as caught:
                targets.load()
            self.assertEqual(str(caught.exception), (
                f"{where}: подполе 'test_profile.report' — 'pult-vitest', "
                f"ожидается junit-xml"), self.note())


# ------------------------------------------------------------------ AC-5

class SingleComponentTest(TargetsFileTest):

    def subfields(self) -> dict:
        lld = f"c{self.word()}"
        return {
            "command": f"[python3, -m, pytest, -{self.rng.choice('qvx')}]",
            "long_lived_dir": lld,
            "long_lived_name": "check_<id>_<name>.py",
            "weakening_scope": f"[{lld}/**/*.py]",
            "mutation_claim_scope": f"[{lld}/check_*.py]",
            "report": "junit-xml",
            "install": "[pip, install, -e, .]",
            "full_suite_timeout_sec": str(self.rng.randrange(60, 5000)),
            "runner": "pytest-own",
            "workdir": f"w{self.word()}",
            "env": {f"V{self.word().upper()}": f"v{self.word()}"},
            "long_lived_imports": "[numpy]",
        }

    @staticmethod
    def block(fields: dict, indent: str) -> str:
        lines = []
        for key, value in fields.items():
            if isinstance(value, dict):
                lines.append(f"{indent}{key}:\n")
                lines.extend(f"{indent}  {k}: {v}\n" for k, v in value.items())
            else:
                lines.append(f"{indent}{key}: {value}\n")
        return "".join(lines)

    def test_ac5_single_component_reads_as_test_profile(self):
        """Запись с одним элементом `components:` даёт тот же `Profile`, что запись с теми же подполями в `test_profile`.

        Сценарий: два внешних проекта со случайными одинаковыми подполями
        (`pytest-own`, `workdir`, `env`, предел, `install`,
        `long_lived_imports`): у одного — `test_profile`, у другого —
        единственный компонент со случайным именем. `decide` и `for_task`
        у второго дают `Profile`, равный `Profile` первого, без отказа;
        `profile_of` второго — PRESENT с `multi` ложным.

        Ловит мутацию: `profile_of` отдаёт для единственного компонента
        отображение `components:` целиком (или UNREAD «несколько
        компонентов» по ошибке счёта) — `decide` отказывает или `Profile`
        другой; `profile_of` выставляет `multi=True` единственному
        компоненту; подполе компонента (например `env` или предел) не
        переносится в `Profile`.
        """
        fields = self.subfields()
        plain, single = f"p{self.word()}", f"s{self.word()}"
        comp = f"k{self.word()}"
        self.write(
            self.artel(),
            HEAD.format(name=plain) + "    test_profile:\n"
            + self.block(fields, "      "),
            HEAD.format(name=single) + f"    components:\n      {comp}:\n"
            + self.block(fields, "        "))
        expected = project_profile.decide(plain).profile
        self.assertIsNotNone(expected, self.note("учебный test_profile не прочитан"))
        answer = repo_context.profile_of(single)
        self.assertEqual(answer.outcome, repo_context.PROFILE_PRESENT,
                         self.note(answer.reason))
        self.assertIs(answer.multi, False, self.note())
        task_id = f"T{self.rng.randrange(10**6)}"
        for decision in (project_profile.decide(single),
                         project_profile.for_task(task_conn(task_id, single),
                                                  task_id)):
            self.assertEqual(decision.refusal, "", self.note())
            self.assertEqual(decision.profile, expected, self.note())

    def test_ac5_missing_weakening_scope_refuses_not_raises(self):
        """Единственный компонент без `weakening_scope` — отказ `decide` с причиной, называющей подполе, а не исключение.

        Сценарий: внешний проект с единственным компонентом со случайными
        подполями, из которых убрано `weakening_scope`. `decide` и
        `for_task` возвращают `Decision` без профиля, с отказом, в тексте
        которого есть `weakening_scope`.

        Ловит мутацию: `profile_of` отдаёт PRESENT без проверки обязательных
        подполей — `Profile.from_values` в `decide` бросает `KeyError`
        `weakening_scope`; либо отказ есть, но причина не называет подполе.
        """
        fields = self.subfields()
        del fields["weakening_scope"]
        single, comp = f"s{self.word()}", f"k{self.word()}"
        self.write(self.artel(), HEAD.format(name=single)
                   + f"    components:\n      {comp}:\n"
                   + self.block(fields, "        "))
        task_id = f"T{self.rng.randrange(10**6)}"
        for decision in (project_profile.decide(single),
                         project_profile.for_task(task_conn(task_id, single),
                                                  task_id)):
            self.assertIsNone(decision.profile, self.note())
            self.assertIn("weakening_scope", decision.refusal, self.note())


# ------------------------------------------------------------------ AC-6

class SelectComponentsTest(TargetsFileTest):

    def test_ac6_select_components_by_paths(self):
        """`select_components` на учебной записи AC-1 выбирает компоненты по `paths`, `test_support` и `depends_on`; путь вне всех — все компоненты.

        Сценарий: запись AC-1 (`frontend` зависит от `backend` по
        `depends_on` вида `files` с `paths: [^backend/api/]`). Случайные
        пути: `backend/src/<x>.rs` → `("backend",)`; `backend/api/<x>.json`
        → `("backend", "frontend")`; `testkit/<x>.rs` (маска `test_support`
        backend) → `("backend",)`; `e2e/<x>.spec.ts` (маска `test_support`
        frontend, вне её `paths`) → `("frontend",)`; `docs/<x>.md` → оба;
        набор из пути backend и `docs/<x>.md` → оба. Запись с одним
        компонентом — этот компонент при любом пути.

        Ловит мутацию: `depends_on` вида `files` не расширяет выбор
        потребителем; `test_support` не учитывается; путь вне всех
        компонентов отбрасывается (выбор пуст или только backend) вместо
        «все»; имена идут не в порядке записи; единственный компонент
        выбирается только по своим `paths`.
        """
        name = f"p{self.word()}"
        self.write(self.artel(), self.two_components(name))
        both = ("backend", "frontend")
        for _ in range(3):
            w = self.word()
            cases = (
                ([f"backend/src/{w}.rs"], ("backend",)),
                ([f"backend/api/{w}.json"], both),
                ([f"testkit/{w}.rs"], ("backend",)),
                ([f"e2e/{w}.spec.ts"], ("frontend",)),
                ([f"docs/{w}.md"], both),
                ([f"backend/src/{w}.rs", f"docs/{w}.md"], both),
            )
            for paths, expected in cases:
                with self.subTest(paths=paths, seed=self.seed):
                    self.assertEqual(
                        tuple(project_profile.select_components(name, paths)),
                        expected, self.note())
        single, comp = f"s{self.word()}", f"k{self.word()}"
        self.write(self.artel(), HEAD.format(name=single) + (
            f"    components:\n      {comp}:\n"
            f"        command: [python3, -m, pytest]\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            f"        weakening_scope: [tests/**/*.py]\n"
            f"        mutation_claim_scope: [tests/test_*.py]\n"
            f"        paths: [^src/]\n"))
        for paths in ([f"src/{self.word()}.py"], [f"docs/{self.word()}.md"],
                      [f"{self.word(3)}/{self.word()}.txt", "README.md"]):
            with self.subTest(single=paths, seed=self.seed):
                self.assertEqual(
                    tuple(project_profile.select_components(single, paths)),
                    (comp,), self.note())


# ------------------------------------------------------------------ AC-7

class TestIdTest(TargetsFileTest):

    def test_ac7_test_id_literal_and_round_trip(self):
        """`test_id` строит литерал `<компонент>:<путь>::<полное имя>[#<n>]`, `parse_test_id` разбирает его обратно.

        Сценарий: литералы AC-7 (`backend`, `backend/tests/test_x.py`,
        `TestA::test_b`, без `n` и с `n=2`), затем случайные компоненты,
        пути, полные имена с `::` и без, номера. Строка без `n` не несёт
        `#`, строка с `n` кончается `#<n>`; `parse_test_id` возвращает
        исходные четыре части (`None` без номера).

        Ловит мутацию: `parse_test_id` режет полное имя по последнему `::`
        (теряется класс) или по первому `:` после компонента не тот край;
        `#<n>` дописывается и при `n=None`; номер возвращается строкой, а не
        `int`.
        """
        self.assertEqual(project_profile.test_id(
            "backend", "backend/tests/test_x.py", "TestA::test_b"),
            "backend:backend/tests/test_x.py::TestA::test_b")
        self.assertEqual(project_profile.test_id(
            "backend", "backend/tests/test_x.py", "TestA::test_b", 2),
            "backend:backend/tests/test_x.py::TestA::test_b#2")
        self.assertEqual(project_profile.parse_test_id(
            "backend:backend/tests/test_x.py::TestA::test_b"),
            ("backend", "backend/tests/test_x.py", "TestA::test_b", None))
        self.assertEqual(project_profile.parse_test_id(
            "backend:backend/tests/test_x.py::TestA::test_b#2"),
            ("backend", "backend/tests/test_x.py", "TestA::test_b", 2))
        for _ in range(8):
            comp = self.word(5)
            path = f"{self.word(4)}/{self.word(3)}/test_{self.word(4)}.py"
            name = "::".join(self.word(5) for _ in range(self.rng.randrange(1, 4)))
            n = self.rng.choice((None, self.rng.randrange(1, 50)))
            with self.subTest(comp=comp, path=path, name=name, n=n,
                              seed=self.seed):
                text = project_profile.test_id(comp, path, name, n)
                literal = f"{comp}:{path}::{name}" + ("" if n is None else f"#{n}")
                self.assertEqual(text, literal, self.note())
                self.assertEqual(project_profile.parse_test_id(text),
                                 (comp, path, name, n), self.note())


if __name__ == "__main__":
    unittest.main()
