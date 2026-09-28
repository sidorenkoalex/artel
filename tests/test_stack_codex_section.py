"""Сторож раздела `docs/stack.md` о провайдере `codex` — абзац про
`CODEX_HOME` эфемерного клона канарейки (SPEC
01M3M55070T5NJFYM3QQJH4B9V, требование 7, AC-8).

Тем же приёмом, что `tests/test_stack_zones_pull_section.py` и
`tests/test_stack_parity_table.py`: документ читается как данные, а якоря
берутся ИЗ КОДА (имена переменных окружения, каталог клиента, имя строки
`doctor`), не переписаны сюда литералами — иначе переименование в коде
оставляло бы документ обещать механику, которой нет, на зелёном тесте.

Сторож нужен именно в `tests/`: до него абзац был закрыт только
приёмочной планкой задачи, а её после мержа не гоняет ни CI, ни автогейт
приёмки (замечание R1-F1 ревью итерации 1) — абзац мог бы исчезнуть или
разойтись с кодом без единой красной строки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, doctor  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402

#: Раздел ищется по подстроке заголовка, а не по точной формулировке:
#: предмет требования — наличие раздела о провайдере, не его имя.
SECTION_MARKERS = ("Провайдер", codex_provider.CLI_NAME)


def stack_md_text() -> str:
    return config.ROOT.joinpath("docs", "stack.md").read_text(encoding="utf-8")


def section_body(text: str) -> str:
    """Тело раздела `## …`, чей заголовок несёт все `SECTION_MARKERS` —
    до следующего заголовка того же уровня; пустая строка, если такого
    раздела нет."""
    body: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = all(marker in line for marker in SECTION_MARKERS)
            continue
        if inside:
            body.append(line)
    return "\n".join(body)


class StackCodexCloneHomeSectionTest(unittest.TestCase):

    def setUp(self):
        # Пробелы нормализуются: документ свёрнут по ~72 символа, и любая
        # искомая фраза может быть разорвана переносом строки — сторож
        # проверяет наличие формулировки, не её раскладку по строкам.
        self.body = " ".join(section_body(stack_md_text()).split())

    def test_section_says_the_login_record_is_keyed_by_the_codex_home_path(self):
        """Раздел объясняет, что запись входа клиент ищет по ПУТИ
        `CODEX_HOME`, и называет строку `doctor`, которой этот вход
        проверяется.

        Ловит мутацию: из раздела исчезает причина подмены (остаётся одна
        механика «клон получает путь пульта») — следующий читатель,
        увидев в коде переопределение модульного состояния провайдера,
        не нашёл бы, зачем оно, и снял бы его как лишнюю связность,
        вернув прогон канарейки к отказу предполёта.
        """
        self.assertTrue(self.body,
                        "в docs/stack.md нет раздела о провайдере codex")
        self.assertIn(codex_provider.HOME_ENV, self.body)
        self.assertIn("ПУТИ", self.body)
        self.assertIn(doctor.CODEX_AUTH_CHECK, self.body)

    def test_section_says_the_clone_gets_the_pult_client_directory(self):
        """Раздел называет, что в блоке клона `CODEX_HOME` — каталог
        клиента дома роли ПУЛЬТА, а `HOME` и `ZDOTDIR` остаются
        клоновскими.

        Ловит мутацию: документ обещает, что в клон уезжает весь дом роли
        пульта (перечень имён из раздела исчез) — Оператор читал бы
        изоляцию канарейки шире, чем она есть, и не понял бы, почему
        `.zshenv` проверяемого sha под канарейкой всё ещё проверяется.
        """
        for anchor in (codex_provider.DEPLOYED_HOME_DIR,
                       codex_provider.ZDOTDIR_ENV, "ПУЛЬТА"):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, self.body)

    def test_section_names_both_refusals_of_the_run(self):
        """Раздел называет ОБА отказа прогона: несделанный однократный
        шаг Оператора (рецепт `codex login`) и дефект пульта, повторным
        входом не чинящийся.

        Ловит мутацию: из раздела исчезает второй отказ — Оператор,
        получив «дефект пульта», не нашёл бы в документе ни того, что
        такой исход штатно различается, ни того, что входить повторно
        бессмысленно, и потратил бы на повторный вход ровно тот шаг,
        который отказ и просил не делать.
        """
        lowered = self.body.lower()
        self.assertIn("дефект пульта", lowered)
        self.assertIn("codex login", lowered)


if __name__ == "__main__":
    unittest.main()
