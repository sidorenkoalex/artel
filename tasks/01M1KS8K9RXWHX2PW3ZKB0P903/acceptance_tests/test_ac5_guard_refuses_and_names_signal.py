"""Приёмочные тесты 01M1KS8K9RXWHX2PW3ZKB0P903 — AC-5 (guard отказывает
при сработавшем сигнале и незаполненной секции; отказ называет сигнал).

Триггер — фраза «ориентировочно» из требования 1/AC-2 (сама широта
распознавания фраз — предмет test_ac2, не дублируется здесь): AC-5
проверяет свойство отказа как такового (missing/empty секция, называние
сигнала), а не то, сколько фраз guard умеет узнавать.

Красен до реализации: guard.py сегодня не знает о секции «Оценка объёма и
деление» и ни об одном сигнале — `check_content` возвращает пустой список
ошибок для обеих фикстур ниже (секция отсутствует / секция пуста), пока
разработчик не добавит проверку требования 3 SPEC.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import check  # noqa: E402

TRIGGER_SENTENCE = "Список затронутых файлов оценён ориентировочно."

# Буквальное имя сигнала из AC-2 — самый прямой, не изобретённый текст,
# которым сообщение отказа может «назвать сработавший сигнал» (AC-5).
SIGNAL_NAME = "формулировки неопределённости"


class GuardRefusesWithUnfilledSectionTest(unittest.TestCase):
    """Сигнал сработал (фраза-триггер в тексте SPEC), секция «Оценка
    объёма и деление» отсутствует ЛИБО присутствует, но пустая — оба
    случая отклоняются guard'ом.

    Ловит мутацию: проверка срабатывает только для полностью
    отсутствующей секции, но не для секции с пустым телом (или наоборот)
    — соответствующий subTest покраснеет.
    """

    def test_ac5_missing_or_empty_section_is_refused_when_signal_fires(self):
        for label, volume_section in (("отсутствует", None), ("пустая", "")):
            with self.subTest(section=label):
                errors = check(extra_requirement_sentence=TRIGGER_SENTENCE,
                               volume_section=volume_section)

                self.assertTrue(
                    errors,
                    f"guard принял SPEC со сработавшим сигналом "
                    f"«формулировки неопределённости» и секцией «Оценка "
                    f"объёма и деление», которая {label}")


class RefusalMessageNamesTheSignalTest(unittest.TestCase):
    """Сообщение отказа называет сработавший сигнал по имени, данному
    самим SPEC («формулировки неопределённости», AC-2), а не абстрактной
    фразой вроде «критерий не пройден».

    Ловит мутацию: guard отказывает молча/общей фразой без указания,
    КАКОЙ сигнал сработал — assertion на присутствие имени сигнала в
    тексте ошибок покраснеет, даже если сам факт отказа (предыдущий тест)
    остаётся зелёным.
    """

    def test_ac5_refusal_message_names_the_fired_signal(self):
        errors = check(extra_requirement_sentence=TRIGGER_SENTENCE,
                       volume_section=None)

        self.assertTrue(errors, "guard принял SPEC со сработавшим сигналом "
                                "и без секции «Оценка объёма и деление» — "
                                "нечего сверять на называние сигнала")
        combined = " ".join(errors)
        self.assertIn(
            SIGNAL_NAME, combined,
            f"сообщение отказа не называет сработавший сигнал «{SIGNAL_NAME}»"
            f" (AC-2): {errors}")


if __name__ == "__main__":
    unittest.main()
