"""AC-17: раздел «Модели: каталог, ярусы, тариф» в `docs/stack.md` и
шаблон локального слоя `docs/reference/models-local.example.yaml` — тот
же, что кладёт `init`.

Содержательность текста раздела (насколько понятно описана цепочка)
сверяет ревьювер: здесь механически проверяется то, что проверяемо, —
сам раздел есть, он говорит про все три слоя и про действия Оператора, а
пример шаблона совпадает с тем, что реально кладёт команда.

Красен до реализации: раздела «Модели: каталог, ярусы, тариф» в
`docs/stack.md` нет (первый тест падает на его поиске), файла-примера нет,
а сценарий второго теста падает ещё на отсутствующем `models.yaml` —
каталог, пример и раздел приносит эта задача.
"""
import re
import unittest
from unittest import mock

import _models
from _sandbox import CatalogSandbox
from orchestrator import catalog, gitcmd, yamlmini
from tests.sandbox import capture, fake_git

STACK_DOC = _models.REPO_ROOT / "docs" / "stack.md"
EXAMPLE = _models.REPO_ROOT / "docs" / "reference" / "models-local.example.yaml"
SECTION_TITLE = "Модели: каталог, ярусы, тариф"


def section_body(text: str, title: str) -> str | None:
    """Тело раздела с заголовком `title` до следующего заголовка того же
    или более высокого уровня; `None` — раздела нет."""
    lines = text.splitlines()
    start = level = None
    for i, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if match and match.group(2) == title:
            start, level = i + 1, len(match.group(1))
            break
    if start is None:
        return None
    body = []
    for line in lines[start:]:
        match = re.match(r"^(#{1,6})\s+", line)
        if match and len(match.group(1)) <= level:
            break
        body.append(line)
    return "\n".join(body)


class StackDocSectionTest(unittest.TestCase):

    def test_ac17_stack_doc_carries_the_models_section(self):
        """`docs/stack.md` несёт раздел «Модели: каталог, ярусы, тариф», и
        в нём названы все три слоя (каталог, локальный слой, ярусы ролей)
        и Оператор как тот, кто их меняет.

        Ловит мутацию: раздел добавлен заголовком со ссылкой «см. SPEC
        задачи» — документация стека продолжает описывать модель роли
        полем `model:` в `roles.yaml`, и Оператор, меняя модель, правит не
        тот файл.
        """
        body = section_body(STACK_DOC.read_text(encoding="utf-8"),
                            SECTION_TITLE)

        self.assertIsNotNone(body, f"раздела «{SECTION_TITLE}» нет в {STACK_DOC}")
        for mention in (_models.CATALOG_NAME, ".artel/models.yaml",
                        "model_tier", "Оператор"):
            with self.subTest(mention=mention):
                self.assertIn(mention, body)


class ExampleMatchesInitTemplateTest(CatalogSandbox):
    """Пример из `docs/reference/` против шаблона, который кладёт `init`."""

    def setUp(self):
        super().setUp()
        self.write_catalog()

    def test_ac17_example_file_matches_the_template_init_places(self):
        """`docs/reference/models-local.example.yaml` и файл, положенный
        `init`, описывают один и тот же локальный слой: те же ярусы с теми
        же моделями и такой же (пустой) раздел переопределений.

        Ловит мутацию: пример в документации разошёлся с шаблоном команды
        (ярусы указывают на разные модели) — Оператор, скопировавший
        пример, получает локальный слой, не совпадающий с тем, что пульт
        кладёт сам, и разбирается, какой из двух правильный.
        """
        self.assertTrue(EXAMPLE.is_file(), f"нет файла-примера {EXAMPLE}")
        with mock.patch.object(gitcmd, "git", fake_git):
            capture(catalog.cmd_init)
        self.assertTrue(self.local_path.is_file(),
                        f"init не положил шаблон: {self.local_path}")

        placed = yamlmini.mapping(self.local_path.read_text(encoding="utf-8"))
        example = yamlmini.mapping(EXAMPLE.read_text(encoding="utf-8"))

        self.assertEqual(_models.section(example, "tiers"),
                         _models.section(placed, "tiers"))
        self.assertEqual(_models.section(example, "overrides"),
                         _models.section(placed, "overrides"))


if __name__ == "__main__":
    unittest.main()
