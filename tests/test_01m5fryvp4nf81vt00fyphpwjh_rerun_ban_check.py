"""`targets.check` отказывает компоненту с `report`, которому заданы плагины повторов pytest: аргументы, `PYTEST_ADDOPTS`, `PYTEST_PLUGINS`.

Группа: долгоживущий

Красен до реализации: `targets.check` сегодня не смотрит на аргументы повторов — запись компонента с `--reruns`, `-p rerunfailures`, `PYTEST_PLUGINS=flaky` или неразбираемым `PYTEST_ADDOPTS` проходит без отказа (AC-4, AC-13, AC-14); контроль — запись `test_profile` и компонент без запрещённых аргументов — держит существующее поведение и зелёный.

Свойство — чистая проверка записи: `targets.check(имя, запись)` на словаре
записи, без `targets.yaml`, песочницы, git и сети. Запись — внешний проект
с единственным компонентом `junit-xml` и командой pytest; `env` задаётся
при `runner: pytest-own` (иначе поле недопустимо и отказ был бы по другой
причине). Перед каждой проверкой отказа та же запись без запрещённого
аргумента проходит `check` — отказ вызван именно им.

Соседние безобидные аргументы, позиция запрещённого среди них, значения
после `=`, порядок и соседи имён в `PYTEST_PLUGINS` — из `random`; зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
проверка запрета в `targets.check` по четырём полям, `PYTEST_PLUGINS` и
перехват `ValueError` разбора — все методы файла зелёные.
"""
import random
import shlex
import unittest

from orchestrator import targets

FLAGS = ("--reruns", "--reruns-delay", "--force-flaky", "--max-runs")
NAMES = ("rerunfailures", "pytest_rerunfailures", "flaky",
         "flaky.flaky_pytest_plugin")
BENIGN = (["-q"], ["-x"], ["--maxfail=3"], ["-p", "timeout"], ["-ptimeout"],
          ["--tb=short"], ["-p", "no:cacheprovider"])
FIELDS = ("command", "report_args", "select", "env.PYTEST_ADDOPTS")
PYTEST = ["python3", "-m", "pytest"]


def component(**extra) -> dict:
    fields = {"command": list(PYTEST), "long_lived_dir": "tests",
              "long_lived_name": "test_<id>_<name>.py",
              "weakening_scope": ["tests/**/*.py"],
              "mutation_claim_scope": ["tests/test_*.py"],
              "report": "junit-xml", "runner": "pytest-own",
              "report_args": ["--junitxml", "{path}"], "select": []}
    fields.update(extra)
    return fields


def entry(*, comp: dict | None = None, profile: dict | None = None) -> dict:
    record = {"forge": "github", "url": "http://127.0.0.1/demo.git",
              "base": "main", "token_slot": "demo-token", "no_paths": [],
              "project_skills": [], "merge_gate": "operator"}
    if comp is not None:
        record["components"] = {"web": comp}
    if profile is not None:
        record["test_profile"] = profile
    return record


def forbidden_forms(rng) -> list:
    """Каждая форма запрещённого аргумента критерия — список элементов."""
    forms = []
    for flag in FLAGS:
        forms.append([flag])
        forms.append([f"{flag}={rng.randint(1, 9)}"])
    for name in NAMES:
        forms.append(["-p", name])
        forms.append([f"-p{name}"])
    forms.append(["-p", " rerunfailures"])
    forms.append(["-p rerunfailures"])
    return forms


class RerunBanCheckTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def benign(self) -> list:
        return [arg for _ in range(self.rng.randint(0, 2))
                for arg in self.rng.choice(BENIGN)]

    def placed(self, field: str, form: list) -> tuple:
        """(поля компонента с `form` в поле `field`, те же поля без него)."""
        before, after = self.benign(), self.benign()
        if field == "env.PYTEST_ADDOPTS":
            with_form = shlex.join([*before, *form, *after])
            plain = shlex.join([*before, *after])
            return (component(env={"PYTEST_ADDOPTS": with_form}),
                    component(env={"PYTEST_ADDOPTS": plain}))
        base = {"command": list(PYTEST), "report_args": ["--junitxml", "{path}"],
                "select": ["{tests}"]}[field]
        cut = self.rng.randint(len(PYTEST) if field == "command" else 0,
                               len(base))
        with_form = [*base[:cut], *before, *form, *after, *base[cut:]]
        plain = [*base[:cut], *before, *after, *base[cut:]]
        return component(**{field: with_form}), component(**{field: plain})

    def assert_refused(self, record: dict, what: str):
        try:
            targets.check("demo", record)
        except targets.TargetsError:
            return
        self.fail(self.note(f"check не отказал: {what}"))

    def test_ac4_every_forbidden_form_refused_in_every_field(self):
        """Каждая форма запрещённого аргумента в каждом из полей `command`, `report_args`, `select`, `env.PYTEST_ADDOPTS` — отказ `targets.check`; та же запись без неё — без отказа.

        Сценарий: формы — `--reruns`, `--reruns-delay`, `--force-flaky`,
        `--max-runs` элементом и с `=<значение>`; пара `-p`, `<имя>` и
        элемент `-p<имя>` для `rerunfailures`, `pytest_rerunfailures`,
        `flaky`, `flaky.flaky_pytest_plugin`; пробельные формы `-p`,
        `" rerunfailures"` и `"-p rerunfailures"`. Форма стоит среди
        случайных безобидных аргументов на случайной позиции поля; в
        `PYTEST_ADDOPTS` — строкой `shlex.join`, пробельные формы — в
        кавычках.

        Ловит мутацию: проверка смотрит только `command` (форма в
        `report_args`, `select` или `PYTEST_ADDOPTS` проходит); флаг
        сверяется только равенством (`--reruns=2` проходит); имя после
        `-p` сравнивается без снятия пробелов (`" rerunfailures"`,
        `"-p rerunfailures"` проходят); слитная форма `-p<имя>` или
        модуль `flaky.flaky_pytest_plugin` не распознаются.
        """
        for field in FIELDS:
            for form in forbidden_forms(self.rng):
                with self.subTest(field=field, form=form):
                    refused, plain = self.placed(field, form)
                    targets.check("demo", entry(comp=plain))
                    self.assert_refused(entry(comp=refused),
                                        f"{field} с {form}: {refused}")

    def test_ac4_test_profile_and_clean_component_not_refused(self):
        """Запись `test_profile` с запрещённым аргументом в `command` или `env.PYTEST_ADDOPTS` (`runner: pytest-own`) и компонент без запрещённых аргументов — без отказа.

        Сценарий: каждая форма критерия вписана в `command` либо в
        `PYTEST_ADDOPTS` записи `test_profile` с `runner: pytest-own` и
        `report` — `check` проходит. Компонент с `report` и случайными
        безобидными аргументами во всех четырёх полях (в том числе
        `-p timeout`, `-p no:cacheprovider`) — `check` проходит.

        Ловит мутацию: проверка запрета применяется и к `test_profile`
        (запись прежнего вида получает отказ); безобидный `-p <плагин>` или
        `--maxfail=…` считается запрещённым (ложный отказ компоненту).
        """
        profile_fields = dict(component(), report="junit-xml")
        for sub in ("report_args", "select"):
            profile_fields.pop(sub)
        for form in forbidden_forms(self.rng):
            with self.subTest(test_profile="command", form=form):
                targets.check("demo", entry(profile=dict(
                    profile_fields, command=[*PYTEST, *self.benign(), *form])))
            with self.subTest(test_profile="PYTEST_ADDOPTS", form=form):
                targets.check("demo", entry(profile=dict(
                    profile_fields,
                    env={"PYTEST_ADDOPTS": shlex.join([*self.benign(),
                                                       *form])})))
        for _ in range(5):
            clean = component(
                command=[*PYTEST, *self.benign()],
                report_args=["--junitxml", "{path}", *self.benign()],
                select=["{tests}", *self.benign()],
                env={"PYTEST_ADDOPTS": shlex.join(self.benign()),
                     "PYTEST_PLUGINS": "pytest_timeout"})
            with self.subTest(clean=clean):
                targets.check("demo", entry(comp=clean))

    def test_ac13_pytest_plugins_rerun_names_refused(self):
        """`env.PYTEST_PLUGINS` с `rerunfailures`, `pytest_rerunfailures`, `flaky` или `flaky.flaky_pytest_plugin` (в том числе среди других и с пробелами у запятой) — отказ; без этих имён — нет.

        Сценарий: для каждого имени — значение из одного имени и значение,
        где имя стоит на случайной позиции среди безобидных плагинов с
        пробелами вокруг запятых. Контроль — только безобидные плагины.

        Ловит мутацию: `PYTEST_PLUGINS` не проверяется; части не очищаются
        от пробелов (` flaky ` проходит); значение сверяется целиком, а не
        по частям (имя среди других проходит); имя ищется подстрокой
        (безобидный `pytest_flaky_report` получает ложный отказ).
        """
        others = ["pytest_timeout", "xdist.plugin", "pytest_flaky_report",
                  "myplug"]
        for name in NAMES:
            parts = self.rng.sample(others, self.rng.randint(1, 3))
            parts.insert(self.rng.randint(0, len(parts)), name)
            for value in (name, " , ".join(parts), ",".join(f" {p} " for p in parts)):
                with self.subTest(value=value):
                    self.assert_refused(
                        entry(comp=component(env={"PYTEST_PLUGINS": value})),
                        f"PYTEST_PLUGINS={value!r}")
        value = " , ".join(self.rng.sample(others, self.rng.randint(1, 4)))
        targets.check("demo", entry(comp=component(
            env={"PYTEST_PLUGINS": value})))

    def test_ac14_unparsable_addopts_refused_by_name(self):
        """`env.PYTEST_ADDOPTS`, который `shlex` не разбирает, — отказ записи `TargetsError` с текстом «PYTEST_ADDOPTS не разбирается», не `ValueError` наружу.

        Сценарий: значение с незакрытой кавычкой (одинарной или двойной)
        среди случайных безобидных аргументов; `shlex.split` на нём
        поднимает `ValueError` (предпосылка). `targets.check` на записи
        компонента с `report` отказывает своим исключением отказа записи
        `TargetsError`, текст которого несёт «PYTEST_ADDOPTS не
        разбирается».

        Ловит мутацию: разбор `shlex` без перехвата — `ValueError`
        «No closing quotation» уходит из `check` наружу (загрузка
        `targets.yaml` падает трассой, а не отказом записи); неразбираемое
        значение пропускается молча; отказ без имени переменной.
        """
        for quote in ("'", '"'):
            value = " ".join([*self.benign(), f"-p {quote}rerunfailures"])
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    shlex.split(value)
                record = entry(comp=component(env={"PYTEST_ADDOPTS": value}))
                try:
                    targets.check("demo", record)
                except targets.TargetsError as exc:
                    self.assertIn("PYTEST_ADDOPTS не разбирается", str(exc),
                                  self.note(str(exc)))
                except Exception as exc:  # noqa: BLE001 — исключение наружу
                    self.fail(self.note(f"исключение наружу: {exc!r}"))
                else:
                    self.fail(self.note(f"check не отказал: {value!r}"))


if __name__ == "__main__":
    unittest.main()
