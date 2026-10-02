"""AC-6: `docs/stack.md` описывает предполёт шага задачи с набором.

Группа: разовый

Красен до реализации: в `docs/stack.md` нет раздела, говорящего о предполёте шага задачи с набором, — раздел «Набор задачи: `new --set`, …» называет провайдера, CLI и вход модели набора, но слова «предполёт», версии CLI и строки `doctor` о наборах задач в работе в нём нет.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. `docs/stack.md` содержит описание предполёта шага задачи с набором:
предполёт проверяет CLI, версию и вход провайдера шага (модели набора), а
не боевого провайдера роли; `doctor` дополнительно проверяет провайдеров
наборов задач в работе.

Провалидирован временным разделом в `docs/stack.md` (абзац о предполёте
шага задачи с набором и абзац о `doctor`): оба метода зелёные; раздел
удалён. Без правки документа первый метод краснеет, хотя раздел «Провайдер
codex» и несёт все слова врозь, — поэтому утверждение ищется в одном
абзаце.

AC-1…AC-5 покрыты долгоживущим файлом
`tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`
(AC-1 — в прочтении ANSWER-1: CLI `claude` есть, токена Claude нет).

Раздел — текст между заголовком любого уровня и следующим заголовком:
место описания критерий не называет, поэтому тест ищет его по всему
документу, а не под заданным заголовком.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STACK_DOC = REPO_ROOT / "docs" / "stack.md"

HEADING = re.compile(r"^#{1,6}\s")


def sections(text: str) -> list:
    """Тексты разделов: каждый — от заголовка до следующего заголовка."""
    found, current = [], []
    for line in text.splitlines():
        if HEADING.match(line) and current:
            found.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        found.append("\n".join(current))
    return found


def paragraphs(section: str) -> list:
    """Абзацы раздела — блоки строк между пустыми строками (пункты одного
    списка без пустых строк между ними — один абзац)."""
    return [block for block in re.split(r"\n\s*\n", section) if block.strip()]


def has_all(section: str, *alternatives) -> list:
    """Группы слов, ни одно из которых не встречается в разделе (без учёта
    регистра); пустой список — каждая группа представлена."""
    low = section.lower()
    return [group for group in alternatives
            if not any(word.lower() in low for word in group)]


class StackDocSetPreflightTest(unittest.TestCase):

    def setUp(self):
        self.text = STACK_DOC.read_text(encoding="utf-8")
        self.sections = sections(self.text)

    def test_ac6_doc_describes_step_preflight_of_a_task_with_set(self):
        """Раздел о предполёте шага задачи с набором называет CLI, версию,
        вход провайдера шага и противопоставляет его боевому провайдеру.

        Сценарий: в `docs/stack.md` есть абзац, где в одном тексте стоят
        предполёт, набор, провайдер шага (модели набора) и боевой
        провайдер роли, а раздел этого абзаца называет CLI, версию и вход.

        Ловит мутацию: документ дополнен общей фразой «предполёт учитывает
        набор» без перечня проверок (CLI, версия, вход) либо без
        противопоставления боевому провайдеру роли — Оператор не узнает,
        почему шаг задачи с набором не спрашивает CLI Claude."""
        claim = (("предполёт", "предполет"), ("набор",),
                 ("провайдер шага", "провайдера шага", "провайдеру шага",
                  "модели набора", "модель набора"),
                 ("боев",))
        checks = (("CLI",), ("верси",), ("вход",))
        found = [section for section in self.sections
                 if not has_all(section, *checks)
                 and any(not has_all(paragraph, *claim)
                         for paragraph in paragraphs(section))]
        self.assertTrue(found,
                        f"в {STACK_DOC} нет абзаца о предполёте шага задачи с "
                        f"набором (провайдер шага — модели набора, а не "
                        f"боевой провайдер роли) в разделе, называющем CLI, "
                        f"версию и вход")

    def test_ac6_doc_says_doctor_checks_providers_of_live_task_sets(self):
        """Документ говорит, что `doctor` проверяет и провайдеров наборов
        задач в работе.

        Сценарий: среди разделов `docs/stack.md` есть раздел, где в одном
        тексте стоят `doctor`, набор и задачи в работе (незакрытые).

        Ловит мутацию: добавка `doctor` реализована, но в документе не
        описана либо описана без оговорки «задачи в работе» — Оператор
        ждёт строк Codex и от закрытых задач."""
        groups = (("doctor",), ("набор",),
                  ("в работе", "незакрыт", "живых задач", "живой задач"))
        self.assertTrue(
            any(not has_all(section, *groups) for section in self.sections),
            f"в {STACK_DOC} нет раздела, где `doctor` проверяет провайдеров "
            f"наборов задач в работе")


if __name__ == "__main__":
    unittest.main()
