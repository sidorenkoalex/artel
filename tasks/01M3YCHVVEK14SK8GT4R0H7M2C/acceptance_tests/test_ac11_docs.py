"""Документация пробного периода набора и приостановки пары в `docs/stack.md`.

Группа: разовый

Красен до реализации: в разделах `docs/stack.md` о наборах моделей задач нет ни команды `pair-resume`, ни причины «пробная задача набора», ни возвратов ревью и алерта как триггера и следствия приостановки пары.

AC-1…AC-10 и AC-12 покрыты долгоживущим файлом
`tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py` (методы
`test_ac<n>_…`). Документация — код репозитория, не артефакт задачи:
страница читается из корня кодовой ветки, рядом с пакетом `orchestrator`,
которым идёт прогон.

Провалидирован временной правкой страницы (зелёный; правка удалена).
"""
import re
import unittest
from pathlib import Path

from orchestrator import config

CODE_ROOT = Path(config.__file__).resolve().parent.parent


def model_set_sections(text: str) -> str:
    """Разделы `###` о наборах моделей задач: заголовок говорит о наборе,
    но не о наборе ролей канарейки; раздел — до следующего заголовка
    `##`/`###`."""
    parts = re.split(r"(?m)^(?=#{2,3} )", text)
    return "\n".join(part for part in parts
                     if part.startswith("### ")
                     and "набор" in part.splitlines()[0].lower()
                     and "канарейк" not in part.splitlines()[0].lower())


class TrialAndSuspensionDocsTest(unittest.TestCase):

    def test_ac11_stack_describes_trial_period_and_pair_suspension(self):
        """Разделы о наборах задач описывают пробный период и приостановку.

        Сценарий: из `docs/stack.md` берутся разделы `###` о наборах
        моделей задач (не о наборе ролей канарейки); в них есть: пробный
        период (слово «пробн», три задачи, счётчик по составу из БД,
        причина ручного гейта «пробная задача набора»); приостановка пары
        (возвраты ревью и отказ автогейта как триггеры, запись в БД поверх
        `model_sets.yaml`, алерт, шаг на боевой модели, команда
        `pair-resume`).

        Ловит мутацию: документация не дописана либо дописана вне разделов
        о наборах моделей задач — нужного фрагмента в них нет."""
        sections = model_set_sections(
            (CODE_ROOT / "docs" / "stack.md").read_text(encoding="utf-8"))
        self.assertTrue(sections.strip(),
                        "docs/stack.md: нет разделов о наборах моделей задач")
        low = sections.lower()
        for needle in ("пробн", "пробная задача набора", "состав", "бд",
                       "возврат", "автогейт", "model_sets.yaml", "алерт",
                       "боев", "pair-resume"):
            self.assertTrue(needle in low, f"docs/stack.md, разделы о "
                                           f"наборах задач: нет «{needle}»")
        self.assertTrue(re.search(r"\bтр[её]х\b|\bтри\b|\b3\b", low),
                        "docs/stack.md: не названо число пробных задач (три)")


if __name__ == "__main__":
    unittest.main()
