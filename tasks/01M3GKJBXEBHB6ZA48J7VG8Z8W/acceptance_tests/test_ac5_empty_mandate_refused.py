"""AC-5 — 01M3GKJBXEBHB6ZA48J7VG8Z8W: маркер мандата без элементов
отказывает.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. `answer` с маркером мандата, после которого нет ни одного непустого
элемента, отказывает именованно; ANSWER не создаётся.

Критерий говорит «маркером мандата», не называя который из двух, — планка
проверяет оба (требование «Не входит»: видов мандата ровно два) и обе
формы пустого списка: маркер без ничего и маркер с одними запятыми.

Красен до реализации: для задачи в `escalated` содержимое файла ответа не
разбирается вовсе (`orchestrator/answer.py:124-125`) — файл с голым
маркером коммитится, и мандат уходит в артефактную ветку пустым: оба
гейта прочитают его как «мандата нет», а Оператор будет считать, что
выдал его.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402


class EmptyMandateRefusedTest(_sandbox.AnswerMandateSandbox):

    def test_ac5_zones_marker_without_any_element_refuses(self):
        """Строка мандата зон — один маркер и ничего после него. `answer`
        отказывает, назвав строку; ANSWER не создаётся.

        Ловит мутацию: пустой список элементов после маркера трактуется как
        «строка мандатом не является» и молча пропускается (ровно так
        сегодня ведёт себя `_zones_mandate_marker_paths`: пустой список —
        законный ответ) — Оператор, забывший дописать пути, получил бы
        ANSWER без мандата и узнал бы об этом только по отказу гейта зон
        через шаг роли.
        """
        line = _sandbox.ZONES_MARKER

        message = self.refuse_answer(_sandbox.answer_text(line))

        self.assertIn(line, message, "отказ обязан назвать строку мандата")

    def test_ac5_zones_marker_with_only_empty_elements_refuses(self):
        """Строка мандата зон, где после маркера только запятые и пробелы —
        непустого элемента нет ни одного.

        Ловит мутацию: пустота проверяется по сырому остатку строки
        (`if not line[len(marker):].strip()`) ДО деления по запятым — строка
        «маркер:  ,  , » непустая, проверка её пропустила бы, а список
        элементов всё равно вышел бы пустым.
        """
        line = _sandbox.zones_mandate_line("  ,  , ")

        message = self.refuse_answer(_sandbox.answer_text(line))

        self.assertIn(_sandbox.ZONES_MARKER, message,
                      "отказ обязан назвать строку мандата")

    def test_ac5_weakening_marker_without_any_element_refuses(self):
        """То же для маркера мандата ослабления тестов: маркер без
        элементов — отказ, ANSWER не создаётся.

        Ловит мутацию: проверка пустого списка написана только для мандата
        зон (ветка `answer`, где мандат зон уже разбирался) — второй маркер
        остался бы без неё, хотя требование 2г названо для обоих.
        """
        line = _sandbox.WEAKENING_MARKER

        message = self.refuse_answer(_sandbox.answer_text(line))

        self.assertIn(line, message, "отказ обязан назвать строку мандата")


if __name__ == "__main__":
    unittest.main()
