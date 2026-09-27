"""AC-13 — 01M3GKJ84XM5QPC6TK5EE307Q9: `docs/stack.md` несёт раздел о
предупреждении `new`, пометке `status` и о том, что подтяжка main
сливает сама, а что эскалирует.

Источник — SPEC.md, «Критерии приёмки»:

AC-13. `docs/stack.md` несёт раздел, называющий предупреждение `new` о
пересечении зон, пометку `status`, перечень того, что подтяжка main
сливает сама, и перечень того, что эскалирует.

Тема опознаётся набором альтернатив (каждая — набор подстрок, которые
обязаны встретиться в одном разделе), а не точной формулировкой:
критерий называет ПРЕДМЕТ, а планка не вправе диктовать разработчику
слова. Исключение — «зона занята»: этот текст пометки `status`
зафиксирован требованием 3 SPEC буквально, поэтому его альтернативы
включают сам литерал.

Документ читается из `config.ROOT` — того же корня, которым пульт
адресует свои файлы (на прогоне гейта это рабочая копия задачи); это
файл кода, а не артефакт задачи, и правило «артефакты только из
артефактной ветки» его не касается.

Красен до реализации: сегодня `docs/stack.md` не несёт раздела ни о
подтяжке main, ни о `new` (SPEC требование 10 говорит об этом прямо) —
ни одна тема не покрыта, и тест падает с перечнем непокрытых тем.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

STACK_MD = config.ROOT / "docs" / "stack.md"

#: {тема: альтернативы опознания}; альтернатива срабатывает, когда в
#: тексте раздела есть ВСЕ её подстроки (текст приведён к нижнему
#: регистру).
TOPICS = {
    "предупреждение new о пересечении зон": (
        ("new", "пересеч", "зон"),
        ("заведени", "пересеч", "зон"),
    ),
    "пометка status «зона занята»": (
        ("status", "зона занята"),
        ("статус", "зона занята"),
    ),
    "что подтяжка main сливает сама": (
        ("подтяж", "аддитив"),
        ("подтяж", "сливает сама"),
    ),
    "что подтяжка main эскалирует": (
        ("эскалир", "не-документ"),
        ("эскалац", "не-документ"),
        ("эскалир", "не документ"),
        ("эскалир", "удал"),
        ("эскалир", "измен"),
    ),
}

#: Темы, которые SPEC требование 10 относит к подтяжке main — они
#: обязаны жить в ОДНОМ разделе («раздел о подтяжке main добавляется»).
PULL_TOPICS = ("что подтяжка main сливает сама",
               "что подтяжка main эскалирует")
NEW_TOPICS = ("предупреждение new о пересечении зон",
              "пометка status «зона занята»")


def sections(text: str) -> list:
    """Разделы документа: каждый — заголовок `## …` со своим телом до
    следующего заголовка того же уровня."""
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


def covered(block: str) -> set:
    lowered = block.lower()
    return {topic for topic, alternatives in TOPICS.items()
            if any(all(part in lowered for part in alt)
                   for alt in alternatives)}


class StackDocDescribesNewBehaviourTest(unittest.TestCase):

    def setUp(self):
        self.blocks = sections(STACK_MD.read_text(encoding="utf-8"))
        self.coverage = [covered(block) for block in self.blocks]

    def test_ac13_stack_md_names_all_four_subjects(self):
        """Все четыре предмета критерия названы в документе.

        Ловит мутацию: разработчик описал только новую механику подтяжки
        (как более «кодовую») и не тронул предупреждение `new` и пометку
        `status` — непокрытые темы будут названы поимённо.
        """
        union = set().union(*self.coverage) if self.coverage else set()
        missing = sorted(set(TOPICS) - union)

        self.assertEqual(
            [], missing,
            f"{STACK_MD} не называет: " + "; ".join(missing))

    def test_ac13_pull_and_zone_subjects_each_live_in_one_section(self):
        """Обе темы подтяжки названы одним разделом, обе темы зон —
        одним разделом (возможно, тем же): критерий говорит о РАЗДЕЛЕ,
        а не о словах, рассыпанных по документу.

        Ловит мутацию: «сливает сама» дописано в один раздел, а «что
        эскалирует» — в другой, далеко от него; читатель, нашедший
        первый перечень, не узнает, когда подтяжка всё-таки остановится.
        """
        for group in (PULL_TOPICS, NEW_TOPICS):
            self.assertTrue(
                any(set(group) <= hit for hit in self.coverage),
                f"ни один раздел {STACK_MD} не называет разом: "
                + "; ".join(group))


if __name__ == "__main__":
    unittest.main()
