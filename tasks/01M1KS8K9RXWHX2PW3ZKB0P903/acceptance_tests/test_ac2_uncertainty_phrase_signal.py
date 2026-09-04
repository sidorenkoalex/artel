"""Приёмочные тесты 01M1KS8K9RXWHX2PW3ZKB0P903 — AC-2 (сигнал
«формулировки неопределённости»).

Единственная наблюдаемая точка сигнала — отказ `scripts.guard.
check_content` на SPEC с отсутствующей секцией «Оценка объёма и деление»
(AC-5 держит это как отдельный критерий; здесь секция всегда отсутствует,
меняется только триггерная фраза, чтобы изолированно проверить каждую из
трёх фраз требования 1/AC-2 по отдельности — общая механика «отказ +
пустая секция» не дублируется, она принадлежит test_ac5).

Красен до реализации: guard.py сегодня не знает ни о секции «Оценка
объёма и деление», ни о какой из трёх фраз — `check_content` возвращает
пустой список ошибок для любой фикстуры ниже, пока разработчик не добавит
сигнал «формулировки неопределённости» (требования 1, 3 SPEC).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import UNCERTAINTY_PHRASE_SENTENCES, check  # noqa: E402


class UncertaintyPhraseSignalTest(unittest.TestCase):
    """Каждая из трёх фраз требования 1/AC-2 («ориентировочно», «весь
    оркестратор», «по факту затронутых мест»), встреченная в тексте SPEC,
    самостоятельно вызывает отказ guard'а, когда секция «Оценка объёма и
    деление» отсутствует.

    Ловит мутацию: реализация распознаёт не все три фразы (например,
    список триггеров содержит только «ориентировочно» и «весь
    оркестратор», а «по факту затронутых мест» пропущен) — соответствующий
    subTest покраснеет вместо остальных.
    """

    def test_ac2_each_uncertainty_phrase_triggers_refusal(self):
        for phrase, sentence in UNCERTAINTY_PHRASE_SENTENCES.items():
            with self.subTest(phrase=phrase):
                errors = check(extra_requirement_sentence=sentence,
                               volume_section=None)

                self.assertTrue(
                    errors,
                    f"фраза «{phrase}» в тексте SPEC не вызвала отказ "
                    f"guard'а при отсутствующей секции «Оценка объёма и "
                    f"деление»")


if __name__ == "__main__":
    unittest.main()
