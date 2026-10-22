"""Поля компонента `test_support`, `layers`, `paths` в профиле, действующие слои `layers_of` и проверка `layers` в `targets.check`.

Группа: долгоживущий
Красен до реализации: у `Profile` нет полей `test_support`, `layers`, `paths` (обращение к атрибуту — `AttributeError`), функции `project_profile.layers_of` нет, а `targets.check` принимает любой элемент `layers` и `python-ast` у команды не pytest.

Стенд — `tests.sandbox.TmpRootTest`: `targets.yaml` песочницы с записью
артели и записями учебных проектов (компонент `components:` либо
`test_profile`), клон проекта — `tests.sandbox.make_project_repo`. Профиль
читается публичными `project_profile.decide` и
`project_profile.component_profiles`. Имена проектов, компонентов, маски и
выражения `paths` — из `random`; зерно печатается и входит в текст
каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
поля профиля, `layers_of` и проверка `layers` в `_check_component_rules`
— все методы файла зелёные.
"""
import random

from orchestrator import config, project_profile, targets
from tests.sandbox import TmpRootTest, make_project_repo

LETTERS = "abcdefghijkmnpqrstuvwxyz"
PYTEST_LAYERS = ("python-ast",)

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


class ProfileFieldsSandbox(TmpRootTest):
    """Песочница путей `config` с зерном и словарём уникальных слов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def append_entry(self, text: str) -> None:
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + text,
                                  encoding="utf-8")

    def component_entry(self, fields: dict) -> tuple:
        """(проект, компонент): запись с единственным компонентом
        `components:` с полями `fields` (значения — уже текстом YAML)."""
        name, comp = f"p{self.word()}", f"c{self.word()}"
        lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                 f"      {comp}:\n"]
        for key, value in fields.items():
            lines.append(f"        {key}: {value}\n")
        self.append_entry("".join(lines))
        make_project_repo(name, origin=False)
        return name, comp

    def pytest_fields(self) -> dict:
        return {"command": flow([f"/opt/{self.word()}/pytest"]),
                "report": "junit-xml",
                "long_lived_dir": "tests",
                "long_lived_name": "test_<id>_<name>.py",
                "weakening_scope": flow(["tests/**"]),
                "mutation_claim_scope": flow(["tests/**"])}

    def vitest_fields(self) -> dict:
        return {"command": flow(project_profile.VITEST_BASE_ARGV),
                "report": "pult-vitest",
                "tests": flow(["frontend/src/**/*.test.jsx"]),
                "long_lived": "frontend/src/<dir>/<name>.<id>.test.jsx",
                "weakening_scope": flow(["frontend/src/**"]),
                "mutation_claim_scope": flow(["frontend/claims/**"])}

    def profile_of(self, name: str):
        decision = project_profile.decide(name)
        self.assertIsNotNone(decision.profile, self.note(
            f"решение профиля проекта {name}: отказ «{decision.refusal}», "
            f"пропуск «{decision.skip}»"))
        return decision.profile


class Ac1ProfileFieldsTest(ProfileFieldsSandbox):

    def test_ac1_component_fields_carried_and_defaults_empty(self):
        """Поля `test_support`, `layers`, `paths` компонента переносятся в профиль; у артели и `test_profile` они пусты.

        Сценарий (подслучай): (а) компонент с масками `test_support`,
        списком `layers` и строкой `paths` — профиль `decide` и профиль
        `component_profiles` несут маски и слои кортежами, `paths` —
        кортеж из одной строки; (б) тот же вид записи с `paths` потоковым
        списком из нескольких выражений — кортеж всех выражений по
        порядку; (в) компонент без этих полей — все три `()`; (г) артель
        и запись `test_profile` — все три `()`.

        Ловит мутацию: `_with_component_fields` не переносит одно из полей —
        у профиля компонента пустой кортеж вместо масок или слоёв; строка
        `paths` разобрана посимвольно (`tuple("^src/")`) — кортеж из
        символов вместо одного выражения; поле без значения по умолчанию
        у `test_profile` — `AttributeError`.
        """
        support = (f"{self.word()}/**", f"conf/{self.word()}.json")
        single = f"^{self.word()}/"
        many = (f"^{self.word()}/", f"^lib/{self.word()}/")
        with self.subTest(case="строка paths", seed=self.seed):
            fields = dict(self.pytest_fields(), test_support=flow(support),
                          layers=flow(PYTEST_LAYERS), paths=single)
            name, comp = self.component_entry(fields)
            decided = self.profile_of(name)
            listed = project_profile.component_profiles(name)
            self.assertEqual(len(listed), 1, self.note(str(listed)))
            for where, profile in (("decide", decided),
                                   ("component_profiles", listed[0])):
                self.assertEqual(profile.component, comp, self.note(where))
                self.assertEqual(profile.test_support, support, self.note(where))
                self.assertEqual(profile.layers, PYTEST_LAYERS, self.note(where))
                self.assertEqual(profile.paths, (single,), self.note(where))
        with self.subTest(case="список paths", seed=self.seed):
            fields = dict(self.vitest_fields(), paths=flow(many))
            name, _comp = self.component_entry(fields)
            profile = self.profile_of(name)
            self.assertEqual(profile.paths, many, self.note("decide"))
            self.assertEqual(profile.test_support, (), self.note("decide"))
            self.assertEqual(profile.layers, (), self.note("decide"))
        with self.subTest(case="без полей", seed=self.seed):
            name, _comp = self.component_entry(self.pytest_fields())
            profile = self.profile_of(name)
            self.assertEqual((profile.test_support, profile.layers,
                              profile.paths), ((), (), ()), self.note(name))
        with self.subTest(case="артель", seed=self.seed):
            profile = self.profile_of(config.DEFAULT_TARGET)
            self.assertEqual((profile.test_support, profile.layers,
                              profile.paths), ((), (), ()), self.note("артель"))
        with self.subTest(case="test_profile", seed=self.seed):
            name = f"t{self.word()}"
            lines = [ENTRY_HEAD.format(name=name), "    test_profile:\n"]
            for key, value in self.pytest_fields().items():
                lines.append(f"      {key}: {value}\n")
            lines.append("      runner: pytest-own\n")
            self.append_entry("".join(lines))
            make_project_repo(name, origin=False)
            profile = self.profile_of(name)
            self.assertEqual((profile.test_support, profile.layers,
                              profile.paths), ((), (), ()),
                             self.note("test_profile"))

    def test_ac1_layers_of_explicit_or_by_command(self):
        """`layers_of` отдаёт явное поле `layers`, а без поля — `("python-ast",)` у команды pytest и `()` у команды не pytest.

        Сценарий (подслучай): компонент `junit-xml` с командой pytest без
        `layers` (путь к `pytest` из случайного каталога либо
        `python3 -m pytest`); тот же с явным `layers: [python-ast]`;
        компонент `pult-vitest` без `layers`.

        Ловит мутацию: умолчание `python-ast` у любой команды — у Vitest
        `("python-ast",)` вместо `()`; признак pytest только по имени файла
        команды — у `python3 -m pytest` `()`; явное поле игнорируется —
        умолчание вместо него.
        """
        commands = (flow([f"/opt/{self.word()}/pytest"]),
                    flow(["python3", "-m", "pytest"]))
        for command in commands:
            with self.subTest(case=f"pytest без поля: {command}", seed=self.seed):
                name, _comp = self.component_entry(
                    dict(self.pytest_fields(), command=command))
                self.assertEqual(project_profile.layers_of(self.profile_of(name)),
                                 PYTEST_LAYERS, self.note(command))
        with self.subTest(case="pytest с явным полем", seed=self.seed):
            name, _comp = self.component_entry(
                dict(self.pytest_fields(), layers=flow(PYTEST_LAYERS)))
            self.assertEqual(project_profile.layers_of(self.profile_of(name)),
                             PYTEST_LAYERS, self.note("явное поле"))
        with self.subTest(case="vitest без поля", seed=self.seed):
            name, _comp = self.component_entry(self.vitest_fields())
            self.assertEqual(project_profile.layers_of(self.profile_of(name)),
                             (), self.note("vitest"))


class Ac2LayersCheckTest(ProfileFieldsSandbox):

    def entry(self, fields: dict) -> dict:
        return {"forge": "github", "url": f"file:///nonexistent/{self.word()}",
                "base": "main", "token_slot": f"{self.word()}-token",
                "no_paths": [], "project_skills": [],
                "merge_gate": "operator", "components": {self.comp: fields}}

    def setUp(self):
        super().setUp()
        self.comp = f"c{self.word()}"

    def pytest_component(self) -> dict:
        return {"command": [f"/opt/{self.word()}/pytest"], "report": "junit-xml",
                "long_lived_dir": "tests", "long_lived_name": "test_<id>_<name>.py",
                "weakening_scope": ["tests/**"],
                "mutation_claim_scope": ["tests/**"]}

    def vitest_component(self) -> dict:
        return {"command": list(project_profile.VITEST_BASE_ARGV),
                "report": "pult-vitest",
                "long_lived": "frontend/src/<dir>/<name>.<id>.test.jsx",
                "tests": ["frontend/src/**/*.test.jsx"],
                "weakening_scope": ["frontend/src/**"],
                "mutation_claim_scope": ["frontend/claims/**"]}

    def refusal(self, name: str, entry: dict) -> str:
        with self.assertRaises(targets.TargetsError,
                               msg=self.note(f"check принял запись {entry}")) as ctx:
            targets.check(name, entry)
        return str(ctx.exception)

    def test_ac2_foreign_layer_refused(self):
        """Элемент `layers`, отличный от `python-ast`, — отказ «<место>: поле 'layers' — '<элемент>': допустим только python-ast».

        Сценарий: компонент pytest и компонент Vitest с `layers` из
        случайного слова (у pytest — ещё в паре с `python-ast` вторым
        элементом); `targets.check` бросает `TargetsError`, текст которого
        называет проект и компонент (место) и кончается названной фразой.

        Ловит мутацию: проверки элементов `layers` нет — `check` принимает
        запись; отказ только при единственном элементе — пара
        `[python-ast, <слово>]` проходит; в тексте не тот элемент.
        """
        for label, base, layers in (
                ("pytest", self.pytest_component, None),
                ("pytest с python-ast", self.pytest_component, "pair"),
                ("vitest", self.vitest_component, None)):
            foreign = f"x{self.word()}"
            value = ["python-ast", foreign] if layers == "pair" else [foreign]
            name = f"p{self.word()}"
            with self.subTest(case=label, seed=self.seed):
                text = self.refusal(name, self.entry(dict(base(), layers=value)))
                self.assertTrue(text.endswith(
                    f": поле 'layers' — '{foreign}': допустим только "
                    f"python-ast"), self.note(text))
                self.assertIn(f"'{name}'", text, self.note(text))
                self.assertIn(f"'{self.comp}'", text, self.note(text))

    def test_ac2_python_ast_by_command(self):
        """`python-ast` у команды не pytest — отказ «<место>: поле 'layers' — python-ast у команды не pytest»; у команды pytest — проходит.

        Сценарий: (а) компонент `pult-vitest` с `layers: [python-ast]` —
        `TargetsError` с местом (проект, компонент) и названной фразой;
        (б) компонент `junit-xml` с командой pytest (путь к `pytest` либо
        `python3 -m pytest`) и `layers: [python-ast]` — `check` проходит.

        Ловит мутацию: признак pytest перевёрнут — отказ у pytest и
        пропуск у Vitest; проверки команды нет — Vitest с `python-ast`
        принят.
        """
        with self.subTest(case="vitest", seed=self.seed):
            name = f"p{self.word()}"
            text = self.refusal(name, self.entry(
                dict(self.vitest_component(), layers=["python-ast"])))
            self.assertTrue(text.endswith(
                ": поле 'layers' — python-ast у команды не pytest"),
                self.note(text))
            self.assertIn(f"'{name}'", text, self.note(text))
            self.assertIn(f"'{self.comp}'", text, self.note(text))
        for command in ([f"/opt/{self.word()}/pytest"],
                        ["python3", "-m", "pytest"]):
            with self.subTest(case=f"pytest {command}", seed=self.seed):
                entry = self.entry(dict(self.pytest_component(), command=command,
                                        layers=["python-ast"]))
                try:
                    targets.check(f"p{self.word()}", entry)
                except targets.TargetsError as exc:
                    self.fail(self.note(f"check отказал pytest с python-ast: {exc}"))
