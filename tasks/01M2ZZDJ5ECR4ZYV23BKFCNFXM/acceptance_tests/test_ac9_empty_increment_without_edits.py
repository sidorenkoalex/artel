"""AC-9 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: пустой инкремент без правок —
штатный исход, без алерта.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Инкрементальный diff пуст И diff от базы вердикта пуст — текст
пакета прямо сообщает, что правок с предыдущего вердикта нет; алерт не
заводится, а открытый ранее алерт того же источника закрывается.

Красен до реализации: пакет сегодня показывает пустой diff плейсхолдером «(изменений нет)» и ничего не говорит о том, что с предыдущего вердикта правок не было (`orchestrator/review.py::review_package` — заметка итерации > 1 называет только диапазон и команду полного diff).

Два других теста файла (алерт не заводится, ранее открытый —
закрывается) зелены и до правки намеренно: критерий требует, чтобы
новая ветка «штатная пустота» НЕ сломала уже работающую механику
алертов, — они сторожат её от потери вместе с откатом требования 7.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import alerts  # noqa: E402


class EmptyIncrementWithoutEditsTest(_sandbox.ReviewPackagePlankSandbox):

    def setUp(self):
        super().setUp()
        # Голова ветки совпадает с базой вердикта: правок нет ни
        # собственных, ни пришедших подтяжкой.
        self.verdict_sha = self.developer_commit(f"{_sandbox.DEV_MARK}-база\n")
        self.journal_verdict_anchor(self.verdict_sha, iteration=1)
        # Лишние записи фиксации между итерациями (автокоммит артефактов и
        # сам переход) кодовую ветку не двигают: `код=` у них тот же.
        self.journal_fixation(self.verdict_sha)
        self.journal_transition("review")
        self.journal_fixation(self.verdict_sha)

    def open_warnings(self) -> list:
        return [row for row in alerts.open_alerts(self.conn, "warning")
                if row["target"] == self.TASK]

    def test_ac9_package_says_there_are_no_edits_since_the_verdict(self):
        """Правок с предыдущего вердикта нет — текст пакета обязан
        сказать это прямо, а не оставить ревьювера с одним лишь
        плейсхолдером пустого diff.

        Ловит мутацию: ветка «инкремент пуст» одна на оба случая и
        всегда печатает причину отката требования 7 — штатная пустота
        станет неотличима от дефекта, и обе проверки покраснеют.
        """
        text = self.build_prompt(reviewed_iter=1)

        tail = _sandbox.after_diff(text)
        self.assertRegex(
            tail, r"(?si)правок.{0,80}нет|нет.{0,80}правок",
            "заметка пакета не говорит, что правок с предыдущего вердикта нет")
        self.assertNotIn(
            _sandbox.FALLBACK_REASON, text,
            "штатная пустота — не откат при непустых правках")

    def test_ac9_no_alert_is_raised_for_a_normal_empty_increment(self):
        """Штатный исход алерта не заводит.

        Ловит мутацию: алерт заводится по одному лишь признаку «diff
        пуст», без проверки, пуст ли diff от базы вердикта — Оператор
        получит warning на каждую итерацию без правок.
        """
        self.build_prompt(reviewed_iter=1)

        self.assertEqual(
            [row["message"] for row in self.open_warnings()], [],
            "пустой инкремент без правок — не повод для алерта")

    def test_ac9_previously_open_alert_of_the_same_source_is_closed(self):
        """Алерт того же источника, открытый прошлым сбором пакета,
        закрывается прежним механизмом.

        Ловит мутацию: новая ветка штатной пустоты возвращается из
        сборки промпта раньше закрытия открытых алертов (или обходит
        его) — старый warning останется висеть у Оператора, и
        assertEqual покраснеет.
        """
        alerts.raise_diff_not_collected_alert(self.conn, self.TASK,
                                              "прошлый сбор: git не ответил")
        self.assertTrue(self.open_warnings(), "алерт не заведён — фикстура "
                                              "ничего не проверяет")

        self.build_prompt(reviewed_iter=1)

        self.assertEqual(
            [row["source"] for row in self.open_warnings()], [],
            "ранее открытый алерт того же источника обязан закрыться")


if __name__ == "__main__":
    unittest.main()
