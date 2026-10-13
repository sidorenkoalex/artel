"""Поле `core_reference` записи проекта в `targets.yaml`: проверка и чтение.

Группа: долгоживущий
Красен до реализации: `targets.check` ещё не проверяет поле `core_reference`, а функции `targets.core_reference` нет — неверные поля принимаются, чтение падает AttributeError.

`targets.check(name, entry)` проверяет поле тем же приёмом, что
`test_profile`: отказ `TargetsError` называет проект, поле и подполе.
`targets.core_reference(name)` читает поле одного проекта из временного
`targets.yaml` (подмена `config.TARGETS`) и проверяет только его запись —
сломанная чужая запись справочник этого проекта не отключает.
"""
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, targets

BASE_ENTRY = {"forge": "github", "url": "file:///nonexistent/proj",
              "base": "main", "token_slot": "proj-token", "no_paths": [],
              "project_skills": [], "merge_gate": "operator"}

ENTRY_TEXT = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

# (случай, значение поля, подполе, которое обязан назвать отказ)
BAD_CASES = (
    ("modules пуст", {"modules": []}, "modules"),
    ("modules не список", {"modules": "lib/a.py"}, "modules"),
    ("modules не из строк", {"modules": ["lib/a.py", 7]}, "modules"),
    ("путь не на .py", {"modules": ["lib/a.txt"]}, "modules"),
    ("путь без расширения", {"modules": ["lib/a"]}, "modules"),
    ("абсолютный путь", {"modules": ["/lib/a.py"]}, "modules"),
    ("пустой сегмент", {"modules": ["lib//a.py"]}, "modules"),
    ("сегмент . в начале", {"modules": ["./lib/a.py"]}, "modules"),
    ("сегмент . внутри", {"modules": ["lib/./a.py"]}, "modules"),
    ("сегмент .. в начале", {"modules": ["../a.py"]}, "modules"),
    ("сегмент .. внутри", {"modules": ["lib/../a.py"]}, "modules"),
    ("обратный слэш", {"modules": ["lib\\a.py"]}, "modules"),
    ("повтор модуля", {"modules": ["lib/a.py", "lib/a.py"]}, "modules"),
    ("constants_module вне modules",
     {"modules": ["lib/a.py"], "constants_module": "lib/b.py", "constants": ["A"]},
     "constants_module"),
    ("constants пуст",
     {"modules": ["lib/a.py"], "constants_module": "lib/a.py", "constants": []},
     "constants"),
    ("constants с цифры",
     {"modules": ["lib/a.py"], "constants_module": "lib/a.py", "constants": ["1A"]},
     "constants"),
    ("constants с дефисом",
     {"modules": ["lib/a.py"], "constants_module": "lib/a.py", "constants": ["A-B"]},
     "constants"),
    ("constants не строка",
     {"modules": ["lib/a.py"], "constants_module": "lib/a.py", "constants": [5]},
     "constants"),
    ("повтор константы",
     {"modules": ["lib/a.py"], "constants_module": "lib/a.py",
      "constants": ["A", "A"]},
     "constants"),
    ("constants без constants_module",
     {"modules": ["lib/a.py"], "constants": ["A"]}, "constants"),
    ("constants_module без constants",
     {"modules": ["lib/a.py"], "constants_module": "lib/a.py"}, "constants"),
    ("неизвестное подполе", {"modules": ["lib/a.py"], "extra_knob": "x"},
     "extra_knob"),
)

GOOD_CASES = (
    {"modules": ["a.py"]},
    {"modules": ["lib/a.py", "conf/b.py"], "constants_module": "conf/b.py",
     "constants": ["A", "B_2", "_c"]},
)


def field_yaml(value: dict) -> str:
    lines = ["    core_reference:"]
    for key, item in value.items():
        if isinstance(item, list):
            lines.append(f"      {key}: [{', '.join(str(x) for x in item)}]")
        else:
            lines.append(f"      {key}: {item}")
    return "\n".join(lines) + "\n"


def entry_yaml(name: str, value: dict | None = None) -> str:
    text = ENTRY_TEXT.format(name=name)
    return text + field_yaml(value) if value is not None else text


def as_dict(answer) -> dict:
    """Подполя ответа без незаданных (`None`, пустых): форма ответа SPEC не фиксирует."""
    if isinstance(answer, dict):
        items = dict(answer)
    else:
        items = {key: getattr(answer, key, None) for key in
                 ("modules", "constants_module", "constants")}
    return {key: (list(value) if isinstance(value, (list, tuple)) else value)
            for key, value in items.items() if value not in (None, [], ())}


class TargetsFileTest(unittest.TestCase):
    """Временный `targets.yaml` на тест: `config.TARGETS` подменён."""

    def use_targets(self, text: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "targets.yaml"
        path.write_text(text, encoding="utf-8")
        patcher = mock.patch.object(config, "TARGETS", path)
        patcher.start()
        self.addCleanup(patcher.stop)
        return path


class CoreReferenceFieldTest(TargetsFileTest):
    """AC-9: каждый неверный случай поля — отказ с проектом, полем и подполем."""

    def test_ac9_check_refuses_every_invalid_case_naming_project_field_subfield(self):
        """`targets.check` отказывает каждому неверному случаю требования 3 и принимает верные.

        Ловит мутацию: пропущена одна из проверок (путь без `.py`,
        абсолютный, `.`/`..`/пустой сегмент, обратный слэш, повтор,
        `constants_module` вне `modules`, не-идентификатор, взаимная
        обязательность `constants` и `constants_module`, неизвестное
        подполе) — `check` примет случай; либо отказ не называет проект,
        `core_reference` или подполе.
        """
        project = f"proj{random.randrange(10 ** 6)}"
        print(f"проект: {project}")
        for case, value, sub in BAD_CASES:
            with self.subTest(case=case):
                entry = dict(BASE_ENTRY, core_reference=value)
                with self.assertRaises(targets.TargetsError) as caught:
                    targets.check(project, entry)
                message = str(caught.exception)
                for fragment in (project, "core_reference", sub):
                    self.assertIn(fragment, message)
        for value in GOOD_CASES:
            with self.subTest(good=value):
                targets.check(project, dict(BASE_ENTRY, core_reference=value))

    def test_ac9_core_reference_reads_and_refuses_the_field_of_one_project(self):
        """`targets.core_reference(name)` отдаёт верное поле и отказывает неверному из файла.

        Неверные случаи, выразимые в подмножестве YAML файла, пишутся в
        запись проекта временного `targets.yaml`; отказ называет проект,
        поле и подполе.

        Ловит мутацию: `core_reference` читает поле без проверки (неверное
        поле принято) или проверка на пути чтения — другая, чем у `check`
        (отказ не называет подполе).
        """
        project = f"proj{random.randrange(10 ** 6)}"
        print(f"проект: {project}")
        for value in GOOD_CASES:
            with self.subTest(good=value):
                self.use_targets("targets:\n" + entry_yaml(project, value))
                self.assertEqual(value, as_dict(targets.core_reference(project)))
        for case, value, sub in BAD_CASES:
            with self.subTest(case=case):
                self.use_targets("targets:\n" + entry_yaml(project, value))
                with self.assertRaises(targets.TargetsError) as caught:
                    targets.core_reference(project)
                message = str(caught.exception)
                for fragment in (project, "core_reference", sub):
                    self.assertIn(fragment, message)

    def test_ac9_broken_foreign_entry_does_not_disable_the_project(self):
        """Сломанная чужая запись (без поля `forge`, с неверным `core_reference`) не мешает чтению.

        Ловит мутацию: `core_reference(name)` идёт через `load()`, который
        проверяет все записи файла, — чужая сломанная запись отказывает
        справочнику проекта `TargetsError`.
        """
        value = {"modules": ["lib/a.py", "conf/b.py"],
                 "constants_module": "conf/b.py", "constants": ["A"]}
        broken = {
            "без поля forge": ENTRY_TEXT.format(name="other").replace(
                "    forge: github\n", ""),
            "неверное поле": entry_yaml("other", {"modules": []}),
        }
        for case, other in broken.items():
            with self.subTest(case=case):
                self.use_targets("targets:\n" + other + entry_yaml("proj", value))
                self.assertEqual(value, as_dict(targets.core_reference("proj")))

    def test_ac9_modules_and_constants_come_from_the_setting(self):
        """Случайные пути модулей и имена констант настройки возвращаются как записаны.

        Ловит мутацию: перечень модулей или констант зашит в код (модули
        артели, `PROTECTED_PATHS`…) или переупорядочен — случайные значения
        настройки не совпадут.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        modules = [f"d{rng.randrange(10 ** 6)}/m{i}_{rng.randrange(10 ** 6)}.py"
                   for i in range(rng.randint(1, 6))]
        constants = [f"C{rng.randrange(10 ** 6)}_{i}" for i in range(rng.randint(1, 5))]
        value = {"modules": modules, "constants_module": rng.choice(modules),
                 "constants": constants}
        self.use_targets("targets:\n" + entry_yaml("proj", value))
        self.assertEqual(value, as_dict(targets.core_reference("proj")),
                         f"зерно: {seed}")


if __name__ == "__main__":
    unittest.main()
