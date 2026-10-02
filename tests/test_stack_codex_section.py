"""Сторож раздела `docs/stack.md` о постоянном профиле Codex канарейки.

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
        """Раздел связывает отдельный CODEX_HOME со строкой проверки входа.

        Ловит мутацию: документ обещает только постоянство каталога без
        проверки входа — истёкшая подписка выглядела бы готовой к шагу.
        """
        self.assertTrue(self.body,
                        "в docs/stack.md нет раздела о провайдере codex")
        self.assertIn(codex_provider.HOME_ENV, self.body)
        self.assertIn("отдельный постоянный профиль", self.body.lower())
        self.assertIn(doctor.CODEX_AUTH_CHECK, self.body)

    def test_section_says_profile_is_separate_from_pult_and_clone(self):
        """Раздел называет адрес профиля и обе границы изоляции.

        Ловит мутацию: документ снова рекомендует боевой дом пульта либо
        временный дом клона — отдельный подписочный вход исчезает.
        """
        for anchor in ("~/.artel-canary-codex/.codex", "боевым домом пульта",
                       "временным клоном", "не изменяет боевой дом"):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, self.body)

    def test_section_names_both_refusals_of_the_run(self):
        """Раздел называет ОБА отказа входа — несделанный вход Оператора
        (рецепт `codex login`) и дефект пульта, повторным входом не
        чинящийся, — и отказ занятости профиля.

        Ловит мутацию: из раздела исчезает отказ «дефект пульта» или отказ
        занятости — Оператор повторял бы вход, который ничего не изменит,
        либо счёл бы параллельный платный прогон допустимым.
        """
        lowered = self.body.lower()
        self.assertIn("codex login", lowered)
        self.assertIn("дефект пульта", lowered)
        self.assertIn("отказ занятости", lowered)


if __name__ == "__main__":
    unittest.main()
