"""Поле `knowledge` записи проекта в `targets.yaml`: проверка `targets.check`.

Чистая проверка записи без песочницы: запись проекта собирается в тесте
(обязательные поля `targets.FIELDS` — верные), меняется только поле
`knowledge`. Имена проектов и файлов карточек — случайные при каждом
запуске; зерно печатается и входит в текст провала.

Группа: долгоживущий
Красен до реализации: `targets.check` поле `knowledge` не проверяет (неизвестные поля записи сегодня не отвергаются) — каждая негодная форма поля принята, тесты отказа красны.
"""
import random
import unittest

from orchestrator import config, targets

LATIN = "abcdefghijklmnopqrstuvwxyz"


def entry(**extra) -> dict:
    """Верная запись проекта без поля `knowledge` плюс `extra`."""
    base = {"forge": "github", "url": "file:///nonexistent/x", "base": "main",
            "token_slot": "x-token", "no_paths": [], "project_skills": [],
            "merge_gate": "operator"}
    base.update(extra)
    return base


class KnowledgeFieldTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def name(self) -> str:
        while True:
            value = "".join(self.rng.choice(LATIN)
                            for _ in range(self.rng.randrange(3, 9)))
            if value != config.DEFAULT_TARGET:
                return value

    def refused(self, project: str, value) -> None:
        with self.assertRaises(targets.TargetsError,
                               msg=self.msg(f"{project}: knowledge={value!r} "
                                            f"принято")):
            targets.check(project, entry(knowledge=value))

    def accepted(self, project: str, value) -> None:
        try:
            targets.check(project, entry(knowledge=value))
        except targets.TargetsError as exc:
            self.fail(self.msg(f"{project}: knowledge={value!r} отвергнуто: "
                               f"{exc}"))

    def test_ac6_external_project_field_refusals(self):
        """Внешний проект `p`: не строка, `..`, `//`, обратная косая черта,
        префикс `./`, ведущая `/`, не `.yaml`, клон `repo/`, `derived/`,
        вложенный уровень, каталог другого проекта `q`, `knowledge/` пульта
        — отказ; `.artel/projects/p/knowledge/<имя>.yaml` — принят.

        Ловит мутацию: проверка смотрит только на префикс
        `.artel/projects/` (каталог другого проекта, `repo/`, `derived/`
        приняты) или только на суффикс `.yaml`; либо имя проекта в пути не
        сверяется с именем записи.
        """
        for _ in range(3):
            p, q, x = self.name(), self.name(), self.name()
            while q == p:
                q = self.name()
            good = f".artel/projects/{p}/knowledge/{x}.yaml"
            self.accepted(p, good)
            bad = (
                5, True, [good],
                f".artel/projects/{p}/knowledge/../{x}.yaml",
                f".artel/projects/{p}/../{p}/knowledge/{x}.yaml",
                f".artel/projects/{p}/knowledge//{x}.yaml",
                f".artel/projects/{p}//knowledge/{x}.yaml",
                f".artel\\projects\\{p}\\knowledge\\{x}.yaml",
                f".artel/projects/{p}/knowledge\\{x}.yaml",
                f"./.artel/projects/{p}/knowledge/{x}.yaml",
                f"/.artel/projects/{p}/knowledge/{x}.yaml",
                f".artel/projects/{p}/knowledge/{x}.yml",
                f".artel/projects/{p}/knowledge/{x}",
                f".artel/projects/{p}/repo/{x}.yaml",
                f".artel/projects/{p}/repo/knowledge/{x}.yaml",
                f".artel/projects/{p}/knowledge/derived/{x}.yaml",
                f".artel/projects/{p}/knowledge/a/b.yaml",
                f".artel/projects/{q}/knowledge/{x}.yaml",
                f"knowledge/{x}.yaml",
                "knowledge/system.yaml",
            )
            for value in bad:
                with self.subTest(project=p, value=value):
                    self.refused(p, value)

    def test_ac6_default_target_field(self):
        """Проект `config.DEFAULT_TARGET`: `knowledge/<имя>.yaml` (в том числе
        `knowledge/artel.yaml`) принят; `knowledge/system.yaml`,
        `knowledge/a/b.yaml` и путь вне `knowledge/` — отказ.

        Ловит мутацию: системный файл не исключён из допустимых проектных
        (`knowledge/system.yaml` принят), либо у артели проверяется форма
        внешнего проекта (`knowledge/artel.yaml` отвергнут).
        """
        name = config.DEFAULT_TARGET
        self.accepted(name, "knowledge/artel.yaml")
        for _ in range(3):
            x = self.name()
            self.accepted(name, f"knowledge/{x}.yaml")
            for value in ("knowledge/system.yaml", f"knowledge/{x}/b.yaml",
                          f"docs/{x}.yaml", f"{x}.yaml",
                          f".artel/projects/{name}/knowledge/{x}.yaml",
                          f"knowledge/{x}.yml", f"./knowledge/{x}.yaml",
                          f"/knowledge/{x}.yaml", f"knowledge/../{x}.yaml",
                          f"knowledge//{x}.yaml", f"knowledge\\{x}.yaml", 7):
                with self.subTest(value=value):
                    self.refused(name, value)

    def test_ac6_entry_without_field_passes_as_before(self):
        """Запись без поля `knowledge` проходит `targets.check` — у внешнего
        проекта и у `config.DEFAULT_TARGET`.

        Ловит мутацию: поле `knowledge` внесено в обязательные
        `targets.FIELDS` — запись без него отвергнута «нет поля».
        """
        for project in (self.name(), self.name(), config.DEFAULT_TARGET):
            with self.subTest(project=project):
                try:
                    targets.check(project, entry())
                except targets.TargetsError as exc:
                    self.fail(self.msg(f"{project}: {exc}"))


if __name__ == "__main__":
    unittest.main()
