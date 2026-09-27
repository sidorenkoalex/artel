"""AC-5 (первые две половины) — 01M3H1Z489CKJ8FHSRS4TYTPX2:
`docs/stack.md` говорит о подзадачах деления в разделе о заведении задач
и прогнозе очереди зон, а набор `tests/` покрывает сценарии AC-1–AC-3.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. В `docs/stack.md` в разделе о заведении задач и прогнозе очереди
зон есть одно предложение о подзадачах деления; покрыты сценарии
AC-1--AC-3, а существующие `tests/test_catalog_spawn_subtask.py`,
`tests/test_catalog_zone_overlap.py` и `tests/test_zone_lock_forecast.py`
остаются зелёными без ослабления проверок.

Третью половину критерия (существующие наборы не ослаблены) проверяет
`test_ac5_existing_suites_stay_intact.py`.

Документ и тесты читаются из `config.ROOT` — того же корня, которым пульт
адресует свои файлы (на прогоне гейта это рабочая копия задачи); это
файлы кода, а не артефакты задачи, и правило «артефакты только из
артефактной ветки» их не касается.

Раздел опознаётся ПРЕДМЕТОМ (заведение задач и/или прогноз очереди зон),
а предложение о подзадачах — словами «подзадач» и «делени»: критерий
называет тему, а планка не вправе диктовать разработчику формулировку.
Покрытие сценариев в `tests/` опознаётся так же по предмету: модуль,
который ЗОВЁТ `spawn_subtask`, обязан говорить о колонке `zones` (сценарии
AC-1/AC-2) и о пересечении зон (сценарий AC-3) — тест, покрывающий эти
сценарии, не может не делать и того, и другого.

Красен до реализации: сегодня `docs/stack.md` о подзадачах деления не
говорит вовсе, а единственный модуль `tests/`, зовущий `spawn_subtask`
(`tests/test_catalog_spawn_subtask.py`), не упоминает ни колонки `zones`,
ни пересечения зон — падают оба теста файла.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

STACK_DOC = config.ROOT / "docs" / "stack.md"
TESTS_DIR = config.ROOT / "tests"

#: Признаки раздела «о заведении задач и прогнозе очереди зон»:
#: альтернатива срабатывает, когда в тексте раздела есть ВСЕ её подстроки
#: (текст приведён к нижнему регистру).
SECTION_ALTERNATIVES = (
    ("завед", "зон"),
    ("прогноз", "зон"),
    ("очеред", "зон"),
    ("new", "зон"),
)

#: Признаки предложения о подзадачах деления.
SUBTASK_MARKERS = ("подзадач", "делени")

#: Предметы, которые обязан называть модуль `tests/`, зовущий
#: `spawn_subtask`: колонка зон (AC-1/AC-2) и пересечение зон (AC-3).
SPAWN_CALL = "spawn_subtask"
ZONES_COLUMN_MARKERS = ("zones",)
OVERLAP_MARKERS = ("zone_overlap", "пересеч")


def sections(text: str) -> list:
    """Разделы документа: заголовок `## …` со своим телом до следующего
    заголовка того же уровня."""
    blocks, current = [], []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                blocks.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def is_about_new_and_zone_forecast(block: str) -> bool:
    lowered = block.lower()
    return any(all(part in lowered for part in alternative)
               for alternative in SECTION_ALTERNATIVES)


def sentences_about_subtasks(block: str) -> list:
    """Предложения раздела, называющие подзадачи деления."""
    flat = " ".join(block.split())
    return [sentence for sentence in re.split(r"(?<=[.!?])\s+", flat)
            if all(marker in sentence.lower() for marker in SUBTASK_MARKERS)]


def module_sources() -> dict:
    """{путь модуля `tests/test_*.py`: его текст в нижнем регистре}."""
    sources = {}
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        sources[path.name] = path.read_text(encoding="utf-8").lower()
    return sources


class StackDocMentionsDivisionSubtasksTest(unittest.TestCase):

    def test_ac5_stack_doc_names_division_subtasks_where_zones_are_described(self):
        """В `docs/stack.md` есть раздел о заведении задач и прогнозе
        очереди зон, и в нём — предложение, называющее подзадачи деления.

        Ловит мутацию: разработчик дописал фразу о подзадачах в
        посторонний раздел (например, в раздел о делении SPEC) — читатель,
        разбирающийся с прогнозом очереди зон, о подзадачах деления так и
        не узнает, а именно его неведение и есть «Контекст» SPEC.
        """
        blocks = [block for block in sections(
            STACK_DOC.read_text(encoding="utf-8"))
            if is_about_new_and_zone_forecast(block)]
        self.assertTrue(
            blocks,
            f"{STACK_DOC} не несёт раздела о заведении задач и прогнозе "
            f"очереди зон — дописывать предложение некуда")

        with_subtasks = [block for block in blocks
                         if sentences_about_subtasks(block)]
        self.assertTrue(
            with_subtasks,
            f"ни один раздел {STACK_DOC} о заведении задач и прогнозе "
            f"очереди зон не несёт предложения о подзадачах деления "
            f"(слова: {', '.join(SUBTASK_MARKERS)})")


class TestsCoverSubtaskZonesAndOverlapTest(unittest.TestCase):

    def test_ac5_tests_cover_subtask_preliminary_zones_and_overlap(self):
        """Среди модулей `tests/test_*.py` есть такой, что зовёт
        `spawn_subtask` и говорит о колонке `zones`, и такой, что зовёт
        `spawn_subtask` и говорит о пересечении зон.

        Ловит мутацию: разработчик внёс механику в `catalog.py`, а
        проверки оставил приёмочной планке («её же и так прогонят») — зона
        `tests/` осталась бы без покрытия сценариев AC-1–AC-3, и после
        снятия планки с задачи регрессию ловить стало бы нечем.
        """
        sources = module_sources()
        spawners = {name: text for name, text in sources.items()
                    if SPAWN_CALL in text}
        self.assertTrue(
            spawners,
            f"ни один модуль {TESTS_DIR} не зовёт {SPAWN_CALL} — сценарии "
            f"подзадач деления в наборе tests/ не покрыты вовсе")

        gaps = []
        for subject, markers in (("колонка zones подзадачи", ZONES_COLUMN_MARKERS),
                                 ("пересечение зон подзадачи", OVERLAP_MARKERS)):
            if not any(any(marker in text for marker in markers)
                       for text in spawners.values()):
                gaps.append(subject)

        self.assertEqual(
            [], gaps,
            f"модули tests/, зовущие {SPAWN_CALL} ({', '.join(sorted(spawners))}), "
            f"не покрывают: " + "; ".join(gaps))


if __name__ == "__main__":
    unittest.main()
