"""Подполе `test_profile.long_lived_imports`: проверка записи проекта и разобранный профиль.

Группа: долгоживущий
Красен до реализации: подполя `long_lived_imports` в перечне подполей профиля ещё нет — проверка записи отказывает ему как неизвестному (годные записи AC-7 получают отказ), у `Profile` нет поля `long_lived_imports` (AC-8); отказ записи артели с подполем (AC-1) и прежний исход записи без подполя зелены с рождения — держат поведение, которое правка обязана сохранить.

Свойство — чистая проверка записи (`targets.check`) и разбор профиля
(`project_profile.Profile.from_values`): без песочницы, без git и без
`targets.yaml` на диске. Имена проекта, элементы перечня и порядок
вариантов — от `random`; зерно печатается и входит в текст провала.
"""
import dataclasses
import keyword
import random
import sys
import unittest

from orchestrator import config, project_profile, targets

FIELD = "long_lived_imports"
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def word(rng: random.Random, size: int = 7) -> str:
    """Идентификатор Python из строчных букв, не ключевое слово и не имя
    модуля стандартной библиотеки."""
    while True:
        value = "".join(rng.choice(LETTERS) for _ in range(size))
        if not keyword.iskeyword(value) and value not in sys.stdlib_module_names:
            return value


def base_profile() -> dict:
    return {"command": ["python3", "-m", "pytest"],
            "long_lived_dir": "tests",
            "long_lived_name": "test_<id>_<name>.py",
            "weakening_scope": ["tests/**/*.py"],
            "mutation_claim_scope": ["tests/test_*.py"],
            "report": "junit-xml",
            "install": []}


def entry_with(profile: dict) -> dict:
    """Запись проекта с годными обязательными полями и профилем `profile`."""
    return {"forge": "github",
            "url": "file:///nonexistent/project",
            "base": config.MAIN_BRANCH,
            "token_slot": "project-token",
            "no_paths": [],
            "project_skills": [],
            "merge_gate": "operator",
            targets.PROFILE_FIELD: profile}


class FieldTestBase(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.project = "proj" + word(self.rng, 5)

    def note(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def check_error(self, name: str, entry: dict) -> str | None:
        """Текст отказа проверки записи; `None` — запись прошла."""
        try:
            targets.check(name, entry)
        except targets.TargetsError as exc:
            return str(exc)
        return None


class ExternalRecordCheckTest(FieldTestBase):

    def test_ac7_bad_long_lived_imports_refused(self):
        """Подполе неверного вида у внешнего проекта — отказ проверки записи с именем подполя.

        Сценарий: запись внешнего проекта (имя от зерна) с годным профилем,
        в который вписано `long_lived_imports` неверного вида — каждый
        вариант отдельным подтестом в порядке от зерна: строка вместо
        списка, отображение, число; список с элементом-числом, `None`,
        пустой строкой, строкой `"src.app"`, строкой `"*"` (рядом с
        годными элементами от зерна). `targets.check` бросает
        `TargetsError`, текст которого называет `long_lived_imports`.

        Ловит мутацию: подполе внесено в перечень известных видом «список
        строк» без проверки идентификатора — `"src.app"` и `"*"` проходят;
        пустая строка не отсеивается; не-список (строка) принимается как
        перечень символов.
        """
        good = word(self.rng)
        bad_values = {
            "строка вместо списка": good,
            "отображение": {good: good},
            "число": self.rng.randint(1, 99),
            "элемент — число": [good, self.rng.randint(1, 99)],
            "элемент — None": [None, good],
            "пустая строка": [good, ""],
            "строка src.app": ["src.app", good],
            "строка *": [good, "*"],
        }
        cases = list(bad_values.items())
        self.rng.shuffle(cases)
        for label, value in cases:
            with self.subTest(вариант=label):
                profile = base_profile()
                profile[FIELD] = value
                error = self.check_error(self.project, entry_with(profile))
                self.assertIsNotNone(error, self.note(
                    f"{label}: запись с {FIELD}={value!r} прошла проверку"))
                self.assertIn(FIELD, error, self.note(
                    f"{label}: отказ не называет подполе: {error}"))

    def test_ac7_good_long_lived_imports_and_absent_pass(self):
        """`[src, fastapi]`, пустой список, перечень идентификаторов от зерна и запись без подполя — проверка пройдена.

        Сценарий: запись внешнего проекта с профилем, где
        `long_lived_imports` — `["src", "fastapi"]`, `[]`, список из
        одного–четырёх идентификаторов от зерна (с подчёркиванием и
        цифрой); и та же запись без подполя. `targets.check` не бросает
        исключения ни для одной. Контроль прежнего исхода записи без
        подполя: та же запись без обязательного подполя `command` или с
        неизвестным подполем по-прежнему получает отказ.

        Ловит мутацию: подполе не внесено в перечень известных (годная
        запись получает «неизвестное подполе»); пустой список отвергается
        видом «непустой список»; подполе сделано обязательным — запись без
        него получает «нет подполя».
        """
        lists = [["src", "fastapi"], [],
                 [word(self.rng) + "_" + str(self.rng.randint(0, 9))
                  for _ in range(self.rng.randint(1, 4))]]
        for value in lists:
            with self.subTest(перечень=value):
                profile = base_profile()
                profile[FIELD] = value
                error = self.check_error(self.project, entry_with(profile))
                self.assertIsNone(error, self.note(
                    f"запись с {FIELD}={value!r} отклонена: {error}"))
        with self.subTest(перечень="нет подполя"):
            error = self.check_error(self.project, entry_with(base_profile()))
            self.assertIsNone(error, self.note(
                f"запись без подполя отклонена: {error}"))
        missing = base_profile()
        del missing["command"]
        unknown = base_profile()
        unknown[word(self.rng)] = []
        for label, profile in (("нет command", missing),
                               ("неизвестное подполе", unknown)):
            with self.subTest(контроль=label):
                self.assertIsNotNone(
                    self.check_error(self.project, entry_with(profile)),
                    self.note(f"{label}: запись без {FIELD} прошла проверку"))


class ArtelRecordCheckTest(FieldTestBase):

    def test_ac1_artel_record_with_long_lived_imports_refused(self):
        """Запись артели с непустым `long_lived_imports` — отказ; та же запись без подполя проходит.

        Сценарий: запись под именем `config.DEFAULT_TARGET` с годным
        профилем; в профиль вписан `long_lived_imports` — `["src",
        "fastapi"]` либо перечень идентификаторов от зерна. `targets.check`
        бросает `TargetsError`; та же запись без подполя проверку проходит,
        а запись внешнего проекта с тем же перечнем — тоже проходит
        (отказ — свойство артели, а не вида подполя).

        Ловит мутацию: проверка записи не различает артель и внешний
        проект — подполе у артели принято и расширило бы её правило
        импортов; либо подполе отвергается у всех проектов (внешний
        проект с годным перечнем получает отказ).
        """
        values = [["src", "fastapi"],
                  [word(self.rng) for _ in range(self.rng.randint(1, 3))]]
        for value in values:
            with self.subTest(перечень=value):
                profile = base_profile()
                profile[FIELD] = value
                artel_error = self.check_error(config.DEFAULT_TARGET,
                                               entry_with(profile))
                self.assertIsNotNone(artel_error, self.note(
                    f"запись артели с {FIELD}={value!r} прошла проверку"))
                external_error = self.check_error(self.project,
                                                  entry_with(profile))
                self.assertIsNone(external_error, self.note(
                    f"запись внешнего проекта с {FIELD}={value!r} "
                    f"отклонена: {external_error}"))
        self.assertIsNone(
            self.check_error(config.DEFAULT_TARGET, entry_with(base_profile())),
            self.note("запись артели без подполя отклонена"))


class ParsedProfileTest(FieldTestBase):

    def test_ac8_profile_carries_long_lived_imports(self):
        """Разобранный профиль несёт перечень; без подполя и с пустым списком — пусто; прочие поля прежние.

        Сценарий: профиль записи внешнего проекта (проверенной
        `targets.check`) разбирается `project_profile.Profile.from_values`
        в трёх видах: с перечнем идентификаторов от зерна (один–четыре,
        порядок от зерна), с пустым списком, без подполя. У первого
        `long_lived_imports` поэлементно равен перечню, у двух других —
        пуст. Все прочие поля `Profile` у трёх профилей попарно равны и
        равны значениям записи (`command`, `long_lived_dir`,
        `long_lived_name`, маски областей).

        Ловит мутацию: `from_values` не переносит подполе (поле всегда
        пусто); переносит его в другое поле или теряет порядок; без
        подполя поле получает не пустое значение (например, перечень
        прошлого разбора) либо разбор без подполя падает `KeyError`.
        """
        names = [word(self.rng) for _ in range(self.rng.randint(1, 4))]
        parsed = {}
        for label, value in (("перечень", names), ("пустой", []), ("нет", None)):
            profile = base_profile()
            if value is not None:
                profile[FIELD] = list(value)
            error = self.check_error(self.project, entry_with(profile))
            self.assertIsNone(error, self.note(f"{label}: запись отклонена: {error}"))
            parsed[label] = project_profile.Profile.from_values(profile)
        self.assertEqual(list(getattr(parsed["перечень"], FIELD)), names,
                         self.note("профиль не несёт перечень записи"))
        for label in ("пустой", "нет"):
            self.assertEqual(list(getattr(parsed[label], FIELD)), [],
                             self.note(f"{label}: значение подполя не пусто"))
        others = [f.name for f in dataclasses.fields(project_profile.Profile)
                  if f.name != FIELD]
        for name in others:
            with self.subTest(поле=name):
                values = {label: getattr(p, name) for label, p in parsed.items()}
                self.assertEqual(len({repr(v) for v in values.values()}), 1,
                                 self.note(f"поле {name} разошлось: {values}"))
        reference = base_profile()
        first = parsed["перечень"]
        self.assertEqual(tuple(first.command), tuple(reference["command"]),
                         self.note("command"))
        self.assertEqual(first.long_lived_dir, reference["long_lived_dir"],
                         self.note("long_lived_dir"))
        self.assertEqual(first.long_lived_name, reference["long_lived_name"],
                         self.note("long_lived_name"))
        self.assertEqual(tuple(first.weakening_scope),
                         tuple(reference["weakening_scope"]),
                         self.note("weakening_scope"))
        self.assertEqual(tuple(first.mutation_claim_scope),
                         tuple(reference["mutation_claim_scope"]),
                         self.note("mutation_claim_scope"))


if __name__ == "__main__":
    unittest.main()
