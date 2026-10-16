"""Подполя `runner`, `workdir`, `env` профиля тестов проекта: проверка
`targets.check` и доставка в `project_profile.Profile`.

Группа: долгоживущий

Вход — запись проекта текстом `targets.yaml`, разобранная `yamlmini`
(тем же разбором, что `targets.load`), либо вложенный набор подполей
напрямую (провалидировано временным стабом подполей в `targets.py` и
`project_profile.py`, удалён, не закоммичен: под ним зелены все методы);
запись — `tests.sandbox.artel_target_entry` плюс строки
подполей. `config.TARGETS` подменён коротким путём: текст отказа начинается
с адреса файла, и случайное «env» в пути корня не должно сойти за имя
подполя. Значения подполей, имена переменных и проектов берутся случайно
на каждом прогоне; зерно печатается и входит в текст провала. Песочница
путей не нужна: `targets.check` и `Profile.from_values` — чистые функции
записи.

Красен до реализации: `runner`, `workdir`, `env` — неизвестные подполя `test_profile` (`targets.PROFILE_FIELDS`), верный профиль с ними получает `TargetsError` «неизвестное подполе», а у `Profile` нет полей `runner`/`workdir`/`env` — методы отказа по значению зелены случайно лишь там, где отказ «неизвестное подполе» тоже называет имя.
"""
import collections.abc
import random
import string
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, project_profile, targets, yamlmini
from orchestrator.providers import PROVIDERS
from tests.sandbox import artel_target_entry

FORGE_SECRETS = ("GITHUB_TOKEN", "GH_TOKEN")
NAMES = ("artel", "sled", "kedr", "vega")


def registry_secrets() -> set:
    """Перечень секретов на момент вызова: имена всех провайдеров реестра
    плюс токены форжа."""
    names = set(FORGE_SECRETS)
    for provider in PROVIDERS.values():
        names.update(provider.secret_env_names())
    return names


def entry_from_yaml(name: str, profile_lines: list) -> dict:
    """Запись `name` из текста `targets.yaml`: запись артели песочницы и
    строки подполей `test_profile` (отступ подполя — 6 пробелов)."""
    text = ("targets:\n" + artel_target_entry(name)
            + "".join(line + "\n" for line in profile_lines))
    return yamlmini.mapping(text)["targets"][name]


def env_lines(env: dict) -> list:
    lines = ["      env:"]
    lines += [f'        {key}: "{value}"' for key, value in env.items()]
    return lines


class ProfileSubfieldsTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        patcher = mock.patch.object(config, "TARGETS", Path("targets.yaml"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def word(self, alphabet=string.ascii_lowercase, k=6) -> str:
        return "".join(self.rng.choices(alphabet, k=k))

    def var_name(self) -> str:
        name = "ARTEL_PROBE_" + self.word(string.ascii_uppercase, 8)
        self.assertNotIn(name, registry_secrets(), f"зерно {self.seed}")
        return name

    def name(self) -> str:
        return self.rng.choice(NAMES)

    def refused(self, name: str, entry: dict, why: str) -> str:
        with self.assertRaises(targets.TargetsError,
                               msg=f"{why}; зерно {self.seed}") as caught:
            targets.check(name, entry)
        return str(caught.exception)

    def passes(self, name: str, entry: dict, why: str) -> None:
        try:
            targets.check(name, entry)
        except targets.TargetsError as exc:
            self.fail(f"{why}: отказ «{exc}»; зерно {self.seed}")

    def test_ac1_env_secret_names_refused_by_exact_name(self):
        """Имя секрета в `env` при `runner: pytest-own` — отказ; близкие имена проходят.

        Для каждого имени перечня (`secret_env_names()` всех провайдеров
        реестра, `GITHUB_TOKEN`, `GH_TOKEN`) запись с `env: {имя: строка}`
        получает `TargetsError`, называющий `test_profile` и `env`. То же
        имя строчными буквами и то же имя со случайным суффиксом проходят.

        Ловит мутацию: сверка без учёта регистра или по префиксу
        (`startswith`/`in`) — имя с суффиксом или строчное получает отказ;
        пропущен `GH_TOKEN` или имена одного провайдера — запись с этим
        именем проходит без `TargetsError`.
        """
        secrets = registry_secrets()
        self.assertTrue({"GITHUB_TOKEN", "GH_TOKEN"} <= secrets)
        for secret in sorted(secrets):
            name = self.name()
            value = self.word()
            with self.subTest(secret=secret, seed=self.seed):
                reason = self.refused(
                    name, entry_from_yaml(name, [
                        "      runner: pytest-own",
                        *env_lines({secret: value})]),
                    f"секрет {secret} в env")
                self.assertIn("test_profile", reason, f"зерно {self.seed}")
                self.assertIn("env", reason, f"зерно {self.seed}")
                suffix = "_" + self.word(string.ascii_uppercase, 3)
                for near in (secret.lower(), secret + suffix):
                    if near in secrets:
                        continue
                    self.passes(name, entry_from_yaml(name, [
                        "      runner: pytest-own",
                        *env_lines({near: value})]),
                        f"близкое к секрету имя {near}")

    def test_ac1_secret_list_is_read_from_registry_at_check_time(self):
        """Подменённый набор имён провайдера меняет перечень секретов проверки.

        Для каждого провайдера реестра `secret_env_names()` подменён и
        возвращает новое случайное имя: `targets.check` отказывает этому
        имени в `env`, а имена прежнего набора провайдера, не названные
        другим провайдером и не токены форжа, проходят.

        Ловит мутацию: перечень секретов зашит литералом в `targets.py` или
        собран один раз при импорте модуля — новое имя проходит без отказа,
        а исключённое (`CLAUDE_CODE_OAUTH_TOKEN`) по-прежнему отказывается.
        """
        for key, provider in PROVIDERS.items():
            original = set(provider.secret_env_names())
            others = set(FORGE_SECRETS)
            for other_key, other in PROVIDERS.items():
                if other_key != key:
                    others.update(other.secret_env_names())
            fresh = "ARTEL_FAKE_SECRET_" + self.word(string.ascii_uppercase, 8)
            name = self.name()
            with self.subTest(provider=key, fresh=fresh, seed=self.seed), \
                    mock.patch.object(provider, "secret_env_names",
                                      return_value=(fresh,)):
                reason = self.refused(name, entry_from_yaml(name, [
                    "      runner: pytest-own",
                    *env_lines({fresh: self.word()})]),
                    f"новое имя {fresh} подменённого провайдера {key}")
                self.assertIn("env", reason, f"зерно {self.seed}")
                for dropped in sorted(original - others):
                    self.passes(name, entry_from_yaml(name, [
                        "      runner: pytest-own",
                        *env_lines({dropped: self.word()})]),
                        f"имя {dropped}, исключённое из набора {key}")

    def test_ac2_workdir_absolute_or_dotdot_segment_refused(self):
        """`workdir` абсолютный или с сегментом `..` — отказ; `a..b` — проходит.

        При `runner: pytest-own` записи с `workdir` вида `/abs/…`,
        `a/../b`, `../a`, `a/..` получают `TargetsError`; `workdir`, где
        `..` — часть имени сегмента (`a..b`, `x/a..b`, `..x`), проходит.
        Имена сегментов случайны.

        Ловит мутацию: проверка подстрокой `".." in workdir` — `a..b`
        получает отказ; проверка только ведущего `..` или без проверки
        ведущего `/` — `a/../b` или `/abs` проходит.
        """
        a, b = self.word(), self.word()
        bad = [f"/{a}/{b}", f"{a}/../{b}", f"../{a}", f"{a}/..", ".."]
        good = [f"{a}..{b}", f"{a}/{b}..{a}", f"..{a}", f"{a}/{b}"]
        name = self.name()
        for workdir in bad:
            with self.subTest(workdir=workdir, seed=self.seed):
                self.refused(name, entry_from_yaml(name, [
                    "      runner: pytest-own", f"      workdir: {workdir}"]),
                    f"workdir {workdir}")
        for workdir in good:
            with self.subTest(workdir=workdir, seed=self.seed):
                self.passes(name, entry_from_yaml(name, [
                    "      runner: pytest-own", f"      workdir: {workdir}"]),
                    f"workdir {workdir}")

    def test_ac3_unknown_runner_value_refused(self):
        """`runner` вне `pult-pytest | pytest-own` — отказ.

        Значения: случайное слово, `pytest`, `PULT-PYTEST`, `pytest_own`,
        `pult-pytest-x` — каждое даёт `TargetsError`; оба допустимых
        значения в той же записи проходят.

        Ловит мутацию: `runner` принят как любая непустая строка (вид
        `text`) или сверяется без учёта регистра — `PULT-PYTEST` и
        случайное слово проходят.
        """
        name = self.name()
        for runner in (self.word(), "pytest", "PULT-PYTEST", "pytest_own",
                       "pult-pytest-x"):
            with self.subTest(runner=runner, seed=self.seed):
                self.refused(name, entry_from_yaml(
                    name, [f"      runner: {runner}"]), f"runner {runner}")
        for runner in ("pult-pytest", "pytest-own"):
            with self.subTest(runner=runner, seed=self.seed):
                self.passes(name, entry_from_yaml(
                    name, [f"      runner: {runner}"]), f"runner {runner}")

    def test_ac4_workdir_or_env_refused_without_pytest_own(self):
        """`workdir` или `env` при `runner: pult-pytest` и без `runner` — отказ.

        Верные по виду `workdir` (относительный каталог) и `env`
        (отображение строк без секретов) в записи с `runner: pult-pytest`
        и в такой же записи без подполя `runner` дают `TargetsError`; та
        же запись с `runner: pytest-own` проходит.

        Ловит мутацию: условие читает `profile.get("runner")` без
        значения по умолчанию и отказывает только при явном `pult-pytest`
        — запись без `runner` с `workdir`/`env` проходит.
        """
        name = self.name()
        variants = {
            "workdir": [f"      workdir: {self.word()}/{self.word()}"],
            "env": env_lines({self.var_name(): self.word()}),
        }
        for field, lines in variants.items():
            for runner_lines in (["      runner: pult-pytest"], []):
                with self.subTest(field=field, runner=runner_lines,
                                  seed=self.seed):
                    self.refused(name, entry_from_yaml(
                        name, runner_lines + lines),
                        f"{field} при {runner_lines or 'runner по умолчанию'}")
            with self.subTest(field=field, runner="pytest-own", seed=self.seed):
                self.passes(name, entry_from_yaml(
                    name, ["      runner: pytest-own"] + lines),
                    f"{field} при pytest-own")

    def test_ac5_profile_without_new_subfields_has_defaults(self):
        """Профиль без новых подполей проходит проверку и даёт значения по умолчанию.

        Запись артели песочницы без `runner`/`workdir`/`env` проходит
        `targets.check`; `Profile.from_values` её профиля несёт `runner`
        = `pult-pytest`, `workdir` = `""`, пустое отображение `env`. Тем же
        значениям равен `Profile`, построенный именованными аргументами
        без новых полей (как в `tests/test_project_profile_gates.py`).

        Ловит мутацию: значение по умолчанию `runner` — `""` или `None`,
        либо новые поля объявлены без умолчаний — построение
        именованными аргументами падает `TypeError`, `from_values` —
        `KeyError`.
        """
        name = self.name()
        entry = entry_from_yaml(name, [])
        self.passes(name, entry, "профиль без новых подполей")
        built = project_profile.Profile(
            command=("python3", "-m", "pytest"), long_lived_dir="tests",
            long_lived_name="test_<id>_<name>.py",
            weakening_scope=("tests/**/*.py",),
            mutation_claim_scope=("tests/test_*.py",))
        for label, profile in (
                ("from_values", project_profile.Profile.from_values(
                    entry["test_profile"])),
                ("kwargs", built)):
            with self.subTest(build=label):
                self.assertEqual(profile.runner, "pult-pytest")
                self.assertEqual(profile.workdir, "")
                self.assertIsInstance(profile.env, collections.abc.Mapping)
                self.assertEqual(dict(profile.env), {})

    def test_ac6_pytest_own_values_reach_profile(self):
        """`runner: pytest-own` с верными `workdir` и `env` доходит до `Profile`.

        Случайные `workdir` (в том числе вида `a..b`) и `env` из одной–
        четырёх переменных со строковыми значениями (в том числе пустой
        строкой) проходят `targets.check`; `Profile.from_values` профиля
        несёт ровно эти `runner`, `workdir`, `env`.

        Ловит мутацию: `from_values` не переносит `workdir` или `env`
        (оставляет умолчание) либо переносит `env` списком пар — поле
        `Profile` расходится с записью.
        """
        name = self.name()
        for _ in range(4):
            workdir = self.rng.choice([
                self.word(), f"{self.word()}/{self.word()}",
                f"{self.word()}..{self.word()}"])
            env = {self.var_name(): self.rng.choice(["", self.word()])
                   for _ in range(self.rng.randint(1, 4))}
            with self.subTest(workdir=workdir, env=env, seed=self.seed):
                entry = entry_from_yaml(name, [
                    "      runner: pytest-own", f"      workdir: {workdir}",
                    *env_lines(env)])
                self.passes(name, entry, "верный профиль pytest-own")
                profile = project_profile.Profile.from_values(
                    entry["test_profile"])
                self.assertEqual(profile.runner, "pytest-own")
                self.assertEqual(profile.workdir, workdir)
                self.assertEqual(dict(profile.env), env, f"зерно {self.seed}")

    def test_ac6_env_not_mapping_or_non_string_value_refused(self):
        """`env` — не отображение или значение переменной — не строка: отказ с `test_profile` и `env`.

        При `runner: pytest-own`: `env` строкой и списком; значение
        переменной `1`, `true`, `null`, пустое (разбор `yamlmini` даёт int,
        bool, `None`) и `1.5` (float) — каждый случай `TargetsError`, текст
        называет `test_profile` и `env`.

        Ловит мутацию: значения `env` не проверяются на строку — `A: 1`
        проходит; `env` проверяется видом `list`/`text` — строка или
        список проходит либо отказ не называет `env`.
        """
        name = self.name()
        var = self.var_name()
        cases = {
            "строка": ["      env: " + self.word()],
            "список": [f"      env: [{var}, {self.word()}]"],
        }
        for raw in ("1", "true", "null", "", "1.5"):
            cases[f"значение {raw!r}"] = ["      env:", f"        {var}: {raw}"]
        for label, lines in cases.items():
            with self.subTest(case=label, seed=self.seed):
                entry = entry_from_yaml(
                    name, ["      runner: pytest-own"] + lines)
                reason = self.refused(name, entry, f"env: {label}")
                self.assertIn("test_profile", reason, f"зерно {self.seed}")
                self.assertIn("env", reason, f"зерно {self.seed}")

    def test_ac8_refusal_names_test_profile_and_subfield(self):
        """Отказ для неверных `runner`, `workdir`, `env` называет `test_profile.<подполе>`.

        Неверный `runner` (`x` — случай `tests/test_01m45…_test_profile.py`
        — и случайное слово), абсолютный `workdir` и `env` строкой при
        `runner: pytest-own` — у каждого отказа в тексте `test_profile` и
        имя подполя.

        Ловит мутацию: отказ нового подполя собран без имени подполя
        (общий текст «профиль тестов не годен») — имени `runner`/`workdir`/
        `env` в тексте нет.
        """
        name = self.name()
        cases = [
            ("runner", ["      runner: x"]),
            ("runner", [f"      runner: {self.word()}"]),
            ("workdir", ["      runner: pytest-own",
                         f"      workdir: /{self.word()}"]),
            ("env", ["      runner: pytest-own", "      env: " + self.word()]),
        ]
        for field, lines in cases:
            with self.subTest(field=field, lines=lines, seed=self.seed):
                reason = self.refused(name, entry_from_yaml(name, lines),
                                      f"неверный {field}")
                self.assertIn("test_profile", reason, f"зерно {self.seed}")
                self.assertIn(field, reason, f"зерно {self.seed}")


if __name__ == "__main__":
    unittest.main()
