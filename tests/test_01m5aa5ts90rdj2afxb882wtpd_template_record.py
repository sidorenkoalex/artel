"""Шаблон `long_lived` компонента: форма записи, производная пара, правило имени с `<dir>`, пример пути.

Группа: долгоживущий
Красен до реализации: запись с единственным компонентом и полем `long_lived` отказывает «long_lived исполняется после G2б», формы шаблона (`<dir>`, корень, маски `tests`) никто не проверяет, пары из шаблона и поля `Profile.long_lived_template` нет, `guard.is_long_lived_test_path` не знает `<dir>`, а `Profile.long_lived_example` не подставляет `<каталог>` — тесты AC-1…AC-4, AC-16 падают на отказе записи или отсутствующем поле; прежние тексты отказов пары полей и строки группы Python (AC-13) зелены с рождения, метод явной пары красен только на сверке пустого `Profile.long_lived_template` — поля ещё нет.

Предмет — чтение записи `targets.yaml` песочницы (`targets.check`,
`targets.load`, `targets.target`), профиль проекта
(`project_profile.decide`, `project_profile.component_profiles`), правило
планки проекта (`project_profile.plank_rule`) и правило имени
долгоживущего файла (`guard.is_long_lived_test_path`,
`Profile.is_long_lived`, `Profile.long_lived_example`). Связка с git и FSM
не нужна: песочница путей `config` — `tests.sandbox.TmpRootTest`, клон
учебного проекта — `tests.sandbox.make_project_repo` (его требует
`decide`).

Учебный проект — компоненты `pult-vitest` (шаблон
`frontend/src/<dir>/<name>.<id>.test.jsx`, маски `*.test.jsx` или
`frontend/**/*.test.jsx`) и `junit-xml` на pytest (шаблон
`backend/tests/test_<id>_<name>.py`). Имена проектов, компонентов,
подкаталогов, файлов и идентификаторы задач — из `random`; зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
форма шаблона и вывод пары в `targets.load`, поле
`Profile.long_lived_template`, `<dir>` в `guard.is_long_lived_test_path`,
`<каталог>` в `Profile.long_lived_example` — все методы файла зелёные;
прежние тексты (AC-13) зелёные и на базе ветки, и на стабе.
"""
import copy
import random
import unittest
from pathlib import Path

from orchestrator import config, project_profile, targets
from scripts import guard
from tests.sandbox import TmpRootTest, artel_target_entry, make_project_repo

LETTERS = "abcdefghijkmnpqrstuvwxyz"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

VITEST_TEMPLATE = "frontend/src/<dir>/<name>.<id>.test.jsx"
JUNIT_TEMPLATE = "backend/tests/test_<id>_<name>.py"
VITEST_COMMAND = list(project_profile.VITEST_BASE_ARGV)
PYTEST_COMMAND = ["python3", "-m", "pytest"]

ENTRY_HEAD = {"forge": "github", "base": config.MAIN_BRANCH,
              "no_paths": [], "project_skills": [], "merge_gate": "operator"}

NO_ROOT = "у шаблона long_lived нет каталога до первого заполнителя"
NO_TEMPLATE_NOR_PAIR = ("нет ни шаблона long_lived, ни пары "
                        "long_lived_dir/long_lived_name")
OLD_PENDING = "исполняется после G2б"


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def yaml_value(value) -> str:
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return str(value)


def entry_dict(name: str, comps: dict) -> dict:
    entry = dict(ENTRY_HEAD, url=f"file:///nonexistent/{name}",
                 token_slot=f"{name}-token")
    entry["components"] = copy.deepcopy(comps)
    return entry


def entry_yaml(name: str, comps: dict) -> str:
    entry = entry_dict(name, comps)
    lines = [f"  {name}:"]
    for key, value in entry.items():
        if key == "components":
            continue
        lines.append(f"    {key}: {yaml_value(value)}")
    lines.append("    components:")
    for comp, fields in comps.items():
        lines.append(f"      {comp}:")
        lines.extend(f"        {k}: {yaml_value(v)}" for k, v in fields.items())
    return "\n".join(lines) + "\n"


class TemplateRecordSandbox(TmpRootTest):
    """`targets.yaml` песочницы: артель и учебные проекты сценария."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        self.entries: dict = {}
        self.write_targets()

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def task_id(self) -> str:
        return ulid(self.rng)

    def write_targets(self) -> None:
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + "".join(self.entries.values()), encoding="utf-8")

    def declare(self, name: str, comps: dict, clone: bool = True) -> None:
        self.entries[name] = entry_yaml(name, comps)
        self.write_targets()
        if clone:
            make_project_repo(name, origin=False)

    def vitest_fields(self, template: str | None = VITEST_TEMPLATE,
                      masks=("frontend/**/*.test.jsx",),
                      paths: bool = False) -> dict:
        fields = {"command": VITEST_COMMAND, "report": "pult-vitest",
                  "weakening_scope": ["frontend/src/**"],
                  "mutation_claim_scope": ["frontend/src/**"]}
        if masks:
            fields["tests"] = list(masks)
        if template is not None:
            fields["long_lived"] = template
        if paths:
            fields["paths"] = ["^frontend/"]
        return fields

    def junit_fields(self, template: str | None = JUNIT_TEMPLATE,
                     paths: bool = False) -> dict:
        fields = {"command": PYTEST_COMMAND, "report": "junit-xml",
                  "weakening_scope": ["backend/tests/**"],
                  "mutation_claim_scope": ["backend/tests/**"],
                  "tests": ["backend/tests/test_*.py"]}
        if template is not None:
            fields["long_lived"] = template
        if paths:
            fields["paths"] = ["^backend/"]
        return fields

    def refusal(self, name: str, comps: dict) -> str:
        """Текст `TargetsError` проверки записи; провал — запись прошла."""
        with self.assertRaises(targets.TargetsError, msg=self.note(
                f"запись прошла проверку: {comps}")) as caught:
            targets.check(name, entry_dict(name, comps))
        return str(caught.exception)

    def profile(self, name: str):
        decision = project_profile.decide(name)
        self.assertIsNotNone(decision.profile, self.note(
            f"профиль {name} не получен: {decision.refusal}"))
        return decision.profile


# ---------------------------------------------------------------- AC-1

class Ac1TemplateRecordAcceptedTest(TemplateRecordSandbox):

    def test_ac1_vitest_template_record_profile_and_labelled_file(self):
        """Единственный компонент `pult-vitest` с шаблоном проходит запись, его профиль несёт производную пару и шаблон, файл модуля — файл с меткой.

        Сценарий: для каждой формы масок `tests` (`*.test.jsx` и
        `frontend/**/*.test.jsx`) — запись проекта с единственным
        компонентом `pult-vitest` и
        `long_lived: frontend/src/<dir>/<name>.<id>.test.jsx`.
        `targets.check` и `targets.load` проходят; профиль `decide` несёт
        `long_lived_dir` = `frontend/src`, `long_lived_name` =
        `<dir>/<name>.<id>.test.jsx`, `long_lived_template` = шаблон;
        правило планки проекта признаёт файлом с меткой имя файла
        `frontend/src/<подкаталог>/<имя>.<id>.test.jsx` случайной задачи.

        Ловит мутацию: отказ «long_lived исполняется после G2б» не снят —
        запись отказывает; пара выводится с завершающей `/` или корнем,
        включающим сегмент с `<dir>`, — `long_lived_dir` другой;
        `long_lived_template` не заполнен из компонента — пустая строка;
        сверка последнего сегмента с масками берёт маску целиком —
        `frontend/**/*.test.jsx` не сходится с именем, запись отказывает.
        """
        for masks in (("*.test.jsx",), ("frontend/**/*.test.jsx",)):
            with self.subTest(masks=masks, seed=self.seed):
                name, comp = f"p{self.word()}", f"v{self.word()}"
                fields = self.vitest_fields(masks=masks)
                targets.check(name, entry_dict(name, {comp: fields}))
                self.declare(name, {comp: fields})
                self.assertIn(name, targets.load(), self.note())
                profile = self.profile(name)
                self.assertEqual(profile.long_lived_dir, "frontend/src",
                                 self.note(str(profile)))
                self.assertEqual(profile.long_lived_name,
                                 "<dir>/<name>.<id>.test.jsx",
                                 self.note(str(profile)))
                self.assertEqual(profile.long_lived_template, VITEST_TEMPLATE,
                                 self.note(str(profile)))
                rule = project_profile.plank_rule(name)
                self.assertFalse(rule.refusal, self.note(rule.refusal))
                task_id = self.task_id()
                path = (f"frontend/src/{self.word()}/{self.word()}."
                        f"{task_id.lower()}.test.jsx")
                self.assertTrue(rule.is_labelled(Path(path).name),
                                self.note(f"{path} не признан файлом с меткой"))

    def test_ac1_junit_template_gives_backend_pair(self):
        """Компонент `junit-xml` с шаблоном `backend/tests/test_<id>_<name>.py` даёт пару `backend/tests` / `test_<id>_<name>.py`.

        Сценарий: запись с единственным компонентом `junit-xml` на pytest
        и тем шаблоном — профиль `decide`; запись учебного проекта с двумя
        компонентами (`junit-xml` и `pult-vitest`, у каждого шаблон и
        `paths`) — профили `component_profiles`. У `junit-xml` в обоих
        случаях пара `backend/tests` / `test_<id>_<name>.py` и шаблон, у
        `pult-vitest` второй записи — `frontend/src` /
        `<dir>/<name>.<id>.test.jsx`.

        Ловит мутацию: пара выводится только в `decide`, а
        `component_profiles` читает поля компонента без вывода — у профилей
        записи из двух компонентов пустые `long_lived_dir`/`long_lived_name`;
        корень берётся до последнего сегмента вместо сегмента с первым
        заполнителем — у шаблона с `<dir>` корень `frontend/src/<dir>`.
        """
        name, comp = f"j{self.word()}", f"b{self.word()}"
        self.declare(name, {comp: self.junit_fields()})
        profile = self.profile(name)
        self.assertEqual((profile.long_lived_dir, profile.long_lived_name,
                          profile.long_lived_template),
                         ("backend/tests", "test_<id>_<name>.py", JUNIT_TEMPLATE),
                         self.note(str(profile)))
        name2, jcomp, vcomp = f"d{self.word()}", f"b{self.word()}", f"v{self.word()}"
        self.declare(name2, {jcomp: self.junit_fields(paths=True),
                             vcomp: self.vitest_fields(paths=True)})
        found = {p.component: (p.long_lived_dir, p.long_lived_name,
                               p.long_lived_template)
                 for p in project_profile.component_profiles(name2)}
        self.assertEqual(found.get(jcomp), ("backend/tests",
                                            "test_<id>_<name>.py",
                                            JUNIT_TEMPLATE), self.note(str(found)))
        self.assertEqual(found.get(vcomp), ("frontend/src",
                                            "<dir>/<name>.<id>.test.jsx",
                                            VITEST_TEMPLATE), self.note(str(found)))


# ---------------------------------------------------------------- AC-2

class Ac2TemplateShapeTest(TemplateRecordSandbox):

    def bad_templates(self) -> list:
        sub = self.word()
        return [
            ("<name> вне последнего сегмента", f"frontend/<name>/{sub}.<id>.test.jsx"),
            ("<id> вне последнего сегмента", f"frontend/<id>/{sub}_<name>.test.jsx"),
            ("повтор <id>", "frontend/src/<name>.<id>.<id>.test.jsx"),
            ("повтор <name>", "frontend/src/<name>_<name>.<id>.test.jsx"),
            ("<dir> внутри сегмента", f"frontend/{sub}<dir>/<name>.<id>.test.jsx"),
            ("<dir> дважды", "frontend/<dir>/<dir>/<name>.<id>.test.jsx"),
            ("пустой корень", "<dir>/<name>.<id>.test.jsx"),
        ]

    def test_ac2_shape_refusals_name_component_and_field(self):
        """Каждое нарушение формы шаблона — `TargetsError`, называющий компонент и поле `long_lived`, у единственного компонента и в записи из двух.

        Сценарий: шаблоны с `<name>`/`<id>` вне последнего сегмента,
        повтором `<id>`/`<name>`, `<dir>` внутри сегмента и дважды, пустым
        корнем (первый сегмент — `<dir>`); у каждого последний сегмент
        подходит под маску `*.test.jsx`. Запись с единственным компонентом
        `pult-vitest` и запись из двух компонентов (`junit-xml` с годным
        шаблоном и `pult-vitest` с плохим, у обоих `paths`): `targets.check`
        отказывает, текст несёт имя компонента и `long_lived`.

        Ловит мутацию: пропущена одна из проверок формы — для её шаблона
        запись проходит; форма проверяется только у единственного
        компонента — запись из двух проходит; отказ не называет компонент
        или поле.
        """
        for label, template in self.bad_templates():
            for kind in ("один компонент", "два компонента"):
                with self.subTest(case=label, record=kind, seed=self.seed):
                    name, comp = f"p{self.word()}", f"v{self.word()}"
                    if kind == "один компонент":
                        comps = {comp: self.vitest_fields(template)}
                    else:
                        comps = {f"b{self.word()}": self.junit_fields(paths=True),
                                 comp: self.vitest_fields(template, paths=True)}
                    text = self.refusal(name, comps)
                    self.assertIn(comp, text, self.note(text))
                    self.assertIn("long_lived", text, self.note(text))

    def test_ac2_single_segment_template_refused_with_text(self):
        """Шаблон из одного сегмента — отказ формы с текстом «у шаблона long_lived нет каталога до первого заполнителя».

        Сценарий: `test_<id>_<name>.py` у компонента `junit-xml` на pytest
        и `x_<id>_<name>.test.jsx` у компонента `pult-vitest` (маска
        `*.test.jsx`), каждый — единственный компонент записи:
        `targets.check` отказывает, текст несёт дословную фразу, имя
        компонента и `long_lived`.

        Ловит мутацию: корень считается пустым только при заполнителе в
        первом сегменте — одиночный сегмент с текстом до заполнителя
        проходит; текст отказа иной — фразы нет.
        """
        cases = [("junit", "test_<id>_<name>.py"),
                 ("vitest", "x_<id>_<name>.test.jsx")]
        for kind, template in cases:
            with self.subTest(template=template, seed=self.seed):
                name, comp = f"p{self.word()}", f"c{self.word()}"
                fields = (self.junit_fields(template) if kind == "junit"
                          else self.vitest_fields(template, masks=("*.test.jsx",)))
                text = self.refusal(name, {comp: fields})
                self.assertIn(NO_ROOT, text, self.note(text))
                self.assertIn(comp, text, self.note(text))

    def test_ac2_short_root_template_passes_with_pair(self):
        """Шаблон `a/<dir>/<name>.<id>.test.jsx` проходит форму, его пара — `a` / `<dir>/<name>.<id>.test.jsx`.

        Сценарий: запись с единственным компонентом `pult-vitest` и этим
        шаблоном (маска `*.test.jsx`): `targets.check` проходит, профиль
        `decide` несёт `long_lived_dir` = `a` и `long_lived_name` =
        `<dir>/<name>.<id>.test.jsx`.

        Ловит мутацию: требование «корень — не меньше двух сегментов»
        вместо «хотя бы один» — шаблон отказан; корень обрезается до
        пустой строки при одном сегменте — `long_lived_dir` пуст.
        """
        name, comp = f"p{self.word()}", f"v{self.word()}"
        fields = self.vitest_fields("a/<dir>/<name>.<id>.test.jsx",
                                    masks=("*.test.jsx",))
        targets.check(name, entry_dict(name, {comp: fields}))
        self.declare(name, {comp: fields})
        profile = self.profile(name)
        self.assertEqual((profile.long_lived_dir, profile.long_lived_name),
                         ("a", "<dir>/<name>.<id>.test.jsx"), self.note(str(profile)))


# ---------------------------------------------------------------- AC-3

class Ac3TemplateRuleRefusalsTest(TemplateRecordSandbox):

    def test_ac3_masks_template_and_pair_refusals(self):
        """Шаблон не под маски `tests`, шаблон вместе с парой и компонент без обоих — отказы записи; текста «исполняется после G2б» нет ни в одном.

        Сценарий: единственный компонент `pult-vitest` (маска только
        `*.test.jsx`) с шаблоном `frontend/src/<dir>/<name>.<id>.test.ts` —
        отказ; годный шаблон вместе с `long_lived_dir` — отказ «поле
        'long_lived' вместе с 'long_lived_dir' — либо шаблон, либо пара
        полей»; единственный компонент без шаблона и без пары — отказ
        «нет ни шаблона long_lived, ни пары long_lived_dir/long_lived_name».
        Ни один из трёх текстов не несёт «исполняется после G2б».

        Ловит мутацию: сверка с масками пропущена или сделана расширением
        файла без маски — `.ts` при маске `*.test.jsx` проходит; проверка
        «шаблон или пара» снята — запись с обоими проходит; прежний текст
        «нет поля 'long_lived_dir' …» не заменён — новой фразы нет.
        """
        texts = []
        name, comp = f"p{self.word()}", f"v{self.word()}"
        texts.append(self.refusal(name, {comp: self.vitest_fields(
            "frontend/src/<dir>/<name>.<id>.test.ts", masks=("*.test.jsx",))}))
        fields = self.vitest_fields(masks=("*.test.jsx",))
        fields["long_lived_dir"] = "frontend/src"
        text = self.refusal(name, {comp: fields})
        self.assertIn("поле 'long_lived' вместе с 'long_lived_dir' — либо "
                      "шаблон, либо пара полей", text, self.note(text))
        texts.append(text)
        text = self.refusal(name, {comp: self.vitest_fields(template=None)})
        self.assertIn(NO_TEMPLATE_NOR_PAIR, text, self.note(text))
        texts.append(text)
        for text in texts:
            self.assertNotIn(OLD_PENDING, text, self.note(text))


# ---------------------------------------------------------------- AC-4

class Ac4DirNameRuleTest(TemplateRecordSandbox):

    def test_ac4_dir_paths_owned_and_foreign_refused(self):
        """Правило имени с `<dir>` признаёт файлы модуля на любой глубине корня и не признаёт скрытый каталог выкладки и чужую задачу.

        Сценарий: шаблон `frontend/src/<dir>/<name>.<id>.test.jsx` (пара
        `frontend/src` / `<dir>/<name>.<id>.test.jsx`), случайная задача.
        `guard.is_long_lived_test_path` и `Profile.is_long_lived` признают
        `frontend/src/components/button.<id>.test.jsx`,
        `frontend/src/button.<id>.test.jsx` и путь со случайной глубиной
        подкаталогов; не признают
        `frontend/src/.artel-plank/<id>/button.<id>.test.jsx`, тот же файл
        под скрытым подкаталогом, файл с id другой задачи и файл с id в
        верхнем регистре.

        Ловит мутацию: `<dir>` разобран как ровно один сегмент — файл в
        корне или на глубине два не признан; сегмент `<dir>` допускает
        ведущую точку — выкладка `.artel-plank` признана своей; `<id>`
        сверяется без учёта регистра или с любым id — чужой файл признан.
        """
        name, comp = f"p{self.word()}", f"v{self.word()}"
        self.declare(name, {comp: self.vitest_fields()})
        profile = self.profile(name)
        directory, template = "frontend/src", "<dir>/<name>.<id>.test.jsx"
        for _ in range(3):
            task_id, other = self.task_id(), self.task_id()
            low = task_id.lower()
            deep = "/".join(self.word(4) for _ in range(self.rng.randint(2, 4)))
            own = [f"frontend/src/components/button.{low}.test.jsx",
                   f"frontend/src/button.{low}.test.jsx",
                   f"frontend/src/{deep}/{self.word()}_{self.word(3)}.{low}.test.jsx"]
            foreign = [f"frontend/src/.artel-plank/{low}/button.{low}.test.jsx",
                       f"frontend/src/.{self.word()}/button.{low}.test.jsx",
                       f"frontend/src/components/button.{other.lower()}.test.jsx",
                       f"frontend/src/components/button.{task_id}.test.jsx"]
            for rel in own + foreign:
                expected = rel in own
                with self.subTest(path=rel, seed=self.seed):
                    self.assertEqual(guard.is_long_lived_test_path(
                        task_id, rel, directory, template), expected, self.note(rel))
                    self.assertEqual(profile.is_long_lived(task_id, rel),
                                     expected, self.note(rel))

    def test_ac4_long_lived_example_names_dir_and_name(self):
        """`Profile.long_lived_example` шаблона с `<dir>` — `frontend/src/<каталог>/<имя>.<id>.test.jsx`.

        Сценарий: профиль компонента `pult-vitest` с шаблоном
        `frontend/src/<dir>/<name>.<id>.test.jsx`; для нескольких случайных
        задач пример пути равен `frontend/src/<каталог>/<имя>.<id>.test.jsx`
        с id в нижнем регистре. Пример с подстановкой `*` виден фразой
        developer (`Ac15…` в файле подсказок этой задачи).

        Ловит мутацию: пример строится прежней склейкой каталога и имени
        без подстановки `<dir>` — в нём остаётся `<dir>`; id подставлен в
        исходном регистре.
        """
        name, comp = f"p{self.word()}", f"v{self.word()}"
        self.declare(name, {comp: self.vitest_fields()})
        profile = self.profile(name)
        for _ in range(3):
            task_id = self.task_id()
            self.assertEqual(profile.long_lived_example(task_id),
                             f"frontend/src/<каталог>/<имя>.{task_id.lower()}"
                             f".test.jsx", self.note(task_id))


# ---------------------------------------------------------------- AC-16

class Ac16PairOnReadTest(TemplateRecordSandbox):

    def test_ac16_load_and_target_give_pair_check_keeps_input(self):
        """`targets.load`/`targets.target` отдают поля компонента с производной парой; `targets.check` не меняет поданный словарь и повторяется с тем же исходом.

        Сценарий: запись с единственным компонентом `pult-vitest` и
        шаблоном. Словарь записи проверяется дважды — оба раза без отказа,
        после проверок он равен своей копии до них и в полях компонента нет
        `long_lived_dir`/`long_lived_name`. Та же запись в `targets.yaml`:
        `targets.load()` и `targets.target()` отдают компонент с
        `long_lived_dir` = `frontend/src` и `long_lived_name` =
        `<dir>/<name>.<id>.test.jsx` (с `/` — без отказа вида `template`),
        файл `targets.yaml` после чтения побайтно прежний.

        Ловит мутацию: пара дописывается в поданный словарь внутри `check`
        — после проверки в полях компонента есть `long_lived_dir`, а
        повторный `check` отказывает «либо шаблон, либо пара полей»; к
        производной паре применена проверка вида `template` — `load`
        отказывает «шаблон имени файла, не путь»; пара выводится только в
        `decide` — у `load`/`target` её нет.
        """
        name, comp = f"p{self.word()}", f"v{self.word()}"
        fields = self.vitest_fields()
        entry = entry_dict(name, {comp: fields})
        before = copy.deepcopy(entry)
        for attempt in (1, 2):
            with self.subTest(check=attempt, seed=self.seed):
                targets.check(name, entry)
                self.assertEqual(entry, before, self.note(str(entry)))
                for sub in ("long_lived_dir", "long_lived_name"):
                    self.assertNotIn(sub, entry["components"][comp], self.note())
        self.declare(name, {comp: fields})
        on_disk = config.TARGETS.read_bytes()
        for label, record in (("load", targets.load()[name]),
                              ("target", targets.target(name))):
            with self.subTest(reader=label, seed=self.seed):
                got = record["components"][comp]
                self.assertEqual(got.get("long_lived_dir"), "frontend/src",
                                 self.note(str(got)))
                self.assertEqual(got.get("long_lived_name"),
                                 "<dir>/<name>.<id>.test.jsx", self.note(str(got)))
                self.assertEqual(got.get("long_lived"), VITEST_TEMPLATE,
                                 self.note(str(got)))
        self.assertEqual(config.TARGETS.read_bytes(), on_disk, self.note())


# ---------------------------------------------------------------- AC-13

class Ac13PairRecordTextsUnchangedTest(TemplateRecordSandbox):

    def test_ac13_pair_field_refusals_unchanged(self):
        """Отказы записи о паре полей — побайтно прежние; компонент с явной парой проходит с прежним профилем без шаблона.

        Сценарий: единственный компонент `pult-vitest` с годным шаблоном и
        `long_lived_dir`, затем с `long_lived_name` — «поле 'long_lived'
        вместе с '<поле>' — либо шаблон, либо пара полей»; компонент только
        с `long_lived_dir` — «нет поля 'long_lived_name' — обязательно у
        единственного компонента записи», только с `long_lived_name` — «нет
        поля 'long_lived_dir' — …». Компонент с явной парой
        `web/src` / `<id>_<name>.test.js` проходит, профиль — та же пара и
        пустой `long_lived_template`.

        Ловит мутацию: новый текст «нет ни шаблона…» выдаётся и компоненту с
        одним полем пары — прежней фразы нет; шаблон выводится и для явной
        пары — `long_lived_template` не пуст или пара переписана.
        """
        name, comp = f"p{self.word()}", f"v{self.word()}"
        for sub in ("long_lived_dir", "long_lived_name"):
            fields = self.vitest_fields(masks=("*.test.jsx",))
            fields[sub] = "frontend/src" if sub == "long_lived_dir" else \
                "<id>_<name>.test.jsx"
            with self.subTest(case=f"шаблон и {sub}", seed=self.seed):
                text = self.refusal(name, {comp: fields})
                self.assertIn(f"поле 'long_lived' вместе с '{sub}' — либо "
                              f"шаблон, либо пара полей", text, self.note(text))
        for present, missing in (("long_lived_dir", "long_lived_name"),
                                 ("long_lived_name", "long_lived_dir")):
            fields = self.vitest_fields(template=None)
            fields[present] = "web/src" if present == "long_lived_dir" else \
                "<id>_<name>.test.js"
            with self.subTest(case=f"только {present}", seed=self.seed):
                text = self.refusal(name, {comp: fields})
                self.assertIn(f"нет поля '{missing}' — обязательно у "
                              f"единственного компонента записи", text,
                              self.note(text))
        fields = self.vitest_fields(template=None)
        fields.update(long_lived_dir="web/src",
                      long_lived_name="<id>_<name>.test.js")
        self.declare(name, {comp: fields})
        profile = self.profile(name)
        self.assertEqual((profile.long_lived_dir, profile.long_lived_name,
                          profile.long_lived_template),
                         ("web/src", "<id>_<name>.test.js", ""), self.note())

    def test_ac13_python_group_line_texts_unchanged(self):
        """Отказы `guard.plank_file_group` для Python — побайтно прежние тексты «в докстринге модуля».

        Сценарий: модуль Python без строки группы, со строкой неизвестного
        значения (случайное слово) и с двумя строками разных значений —
        ошибка равна прежнему тексту дословно; модуль с одной строкой
        «Группа: долгоживущий» — группа без ошибки.

        Ловит мутацию: место строки группы заменено на «в первом
        комментарии файла» и для Python — текст первой ошибки другой;
        разбор Python переведён на первый комментарий — докстринг с
        группой не распознан.
        """
        value = self.word()
        cases = [
            ('"""Модуль."""\n', None,
             "нет строки группы в докстринге модуля — допиши «Группа: "
             "долгоживущий» или «Группа: разовый»"),
            (f'"""Модуль.\n\nГруппа: {value}\n"""\n', None,
             f"неизвестное значение строки группы «{value}» — допустимы "
             f"только «долгоживущий» и «разовый»"),
            ('"""Модуль.\n\nГруппа: долгоживущий\nГруппа: разовый\n"""\n', None,
             "строк группы две с разными значениями — оставь одну"),
            ('"""Модуль.\n\nГруппа: долгоживущий\n"""\n', "долгоживущий", None),
        ]
        for source, group, error in cases:
            with self.subTest(source=source[:40], seed=self.seed):
                self.assertEqual(guard.plank_file_group(source), (group, error),
                                 self.note(source))


if __name__ == "__main__":
    unittest.main()
