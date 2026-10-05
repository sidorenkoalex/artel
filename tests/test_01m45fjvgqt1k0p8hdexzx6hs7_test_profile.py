"""Профиль тестов проекта — поле `test_profile` записи `targets.yaml`
(ADR-0021 пп. 8-9): разбор и проверка в `orchestrator/targets.py`.

Группа: долгоживущий

Песочница — `tests.sandbox.TmpRootTest` (`config.TARGETS` во временном
каталоге). Вход — запись проекта целиком (`targets.check`) и файл
`targets.yaml` (`targets.load`). Значения профиля, имена проектов и выбор
дефекта на каждом прогоне берутся случайно; зерно печатается и входит в
текст провала.

Красен до реализации: `targets.check` не знает поля `test_profile` — верный
профиль проходит (лишние поля записи не проверяются), а ни один дефект
профиля не даёт `TargetsError`. Метод верного профиля зелен и сегодня
(лишнее поле не проверяется) и держит, что разбор профиля не отвергнет
законную запись.

Планка провалидирована временным стабом разбора профиля в
`targets.check` (удалён, не закоммичен): под ним зелены все методы.
"""
import random
import unittest

from orchestrator import config, targets
from tests.sandbox import TmpRootTest

REQUIRED = ("command", "long_lived_dir", "long_lived_name", "weakening_scope",
            "mutation_claim_scope")


def base_entry(name: str) -> dict:
    return {"forge": "github", "url": f"file:///nonexistent/{name}",
            "base": "main", "token_slot": f"{name}-token", "no_paths": [],
            "project_skills": [], "merge_gate": "operator"}


def random_profile(rng: random.Random) -> dict:
    directory = rng.choice(["tests", "checks", "spec/unit", "t"])
    stem = rng.choice(["test_<id>_<name>.py", "<id>_<name>_test.py",
                       "check_<name>_<id>.py"])
    return {
        "command": rng.choice([["python3", "-m", "pytest"],
                               ["python3", "-m", "pytest", "-x"],
                               ["pytest"], ["python3", "-m", "pytest", "-q"]]),
        "long_lived_dir": directory,
        "long_lived_name": stem,
        "weakening_scope": rng.choice([[f"{directory}/**/*.py"],
                                       [f"{directory}/*.py", "more/**/*.py"]]),
        "mutation_claim_scope": rng.choice([[f"{directory}/test_*.py"],
                                            [f"{directory}/**/test_*.py"]]),
        "report": "junit-xml",
        "install": rng.choice([[], ["pip", "install", "-e", "."]]),
    }


def render_entry(name: str, entry: dict) -> str:
    def value(v):
        return "[" + ", ".join(v) + "]" if isinstance(v, list) else v

    lines = [f"  {name}:"]
    for key, val in entry.items():
        if isinstance(val, dict):
            lines.append(f"    {key}:")
            lines += [f"      {k}: {value(v)}" for k, v in val.items()]
        else:
            lines.append(f"    {key}: {value(val)}")
    return "\n".join(lines) + "\n"


class ProfileCheckTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def defects(self, profile: dict) -> list:
        """(подполе, испорченный профиль) — по одному дефекту на элемент."""
        cases = []
        for field in REQUIRED:
            broken = dict(profile)
            del broken[field]
            cases.append((field, broken))
        wrong_kind = {
            "command": [[], "python3 -m pytest", ["python3", ["-m"]]],
            "long_lived_dir": ["", ["tests"]],
            "long_lived_name": ["", ["test_<id>_<name>.py"]],
            "weakening_scope": [[], "tests/**/*.py"],
            "mutation_claim_scope": [[], "tests/test_*.py"],
            "report": [["junit-xml"]],
            "install": ["pip install", [["pip"]]],
        }
        for field, values in wrong_kind.items():
            for bad in values:
                cases.append((field, dict(profile, **{field: bad})))
        for bad_report in ("junit", "xml", "tap", "JUNIT-XML"):
            cases.append(("report", dict(profile, report=bad_report)))
        cases.append(("long_lived_name",
                      dict(profile, long_lived_name="test_<name>.py")))
        cases.append(("long_lived_name",
                      dict(profile, long_lived_name="test_<id>.py")))
        unknown = self.rng.choice(["timeout", "runner", "lang", "paths"])
        cases.append((unknown, dict(profile, **{unknown: "x"})))
        return cases

    def test_ac1_valid_profile_and_entry_without_profile_pass(self):
        """Запись со всеми подполями верного вида и запись без поля
        `test_profile` проходят `targets.check` и `targets.load` из файла.

        Ловит мутацию: поле `test_profile` объявлено обязательным полем
        записи (в `FIELDS`) либо вложенный список разбирается не как
        список строк — запись без профиля или верный профиль из файла
        получает `TargetsError`.
        """
        for _ in range(5):
            name = self.rng.choice(["artel", "sled", "kedr", "vega"])
            profile = random_profile(self.rng)
            with self.subTest(seed=self.seed, profile=profile):
                targets.check(name, dict(base_entry(name), test_profile=profile))
                targets.check(name, base_entry(name))
                text = ("targets:\n"
                        + render_entry(name, dict(base_entry(name),
                                                  test_profile=profile))
                        + render_entry("plain", base_entry("plain")))
                config.TARGETS.write_text(text, encoding="utf-8")
                loaded = targets.load()
                self.assertEqual(loaded[name]["test_profile"], profile,
                                 f"зерно {self.seed}")
                self.assertNotIn("test_profile", loaded["plain"])

    def test_ac1_each_profile_defect_names_field_and_subfield(self):
        """Каждый дефект профиля — нет обязательного подполя, неверный вид,
        `report` не `junit-xml`, шаблон без `<id>`/`<name>`, неизвестное
        подполе — даёт `TargetsError`, причина называет `test_profile` и
        подполе.

        Ловит мутацию: проверка пропускает один класс дефекта (например, не
        сверяет `report` с `junit-xml`, не ищет `<id>` в шаблоне имени или
        молча принимает неизвестное подполе) — для этого дефекта
        `TargetsError` не поднимается либо причина не называет подполе.
        """
        name = self.rng.choice(["artel", "sled", "kedr"])
        for field, broken in self.defects(random_profile(self.rng)):
            with self.subTest(seed=self.seed, field=field, profile=broken):
                with self.assertRaises(targets.TargetsError,
                                       msg=f"зерно {self.seed}") as caught:
                    targets.check(name, dict(base_entry(name),
                                             test_profile=broken))
                reason = str(caught.exception)
                self.assertIn("test_profile", reason, f"зерно {self.seed}")
                self.assertIn(field, reason, f"зерно {self.seed}")

    def test_ac1_profile_not_a_mapping_is_refused(self):
        """Значение `test_profile` — не вложенное отображение (строка,
        список) — `TargetsError` с именем поля.

        Ловит мутацию: разбор профиля начинается с `.get()` без проверки
        вида значения — строка в поле роняет код `AttributeError` вместо
        именованного отказа либо проходит молча.
        """
        name = self.rng.choice(["artel", "sled"])
        for bad in ("pytest", ["python3", "-m", "pytest"], ""):
            with self.subTest(seed=self.seed, value=bad):
                with self.assertRaises(targets.TargetsError) as caught:
                    targets.check(name, dict(base_entry(name), test_profile=bad))
                self.assertIn("test_profile", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
