"""Приёмочные тесты 01M1TQ0TRCZPRZX22C4084NCPB — AC-13: ревью-пакет несёт
строку статуса CI головы (sha, число проверок, идентификатор прогона),
построенную из данных, которые состояние `verifying` уже журналирует.

Красен до реализации: `orchestrator/review.py::review_package` сегодня
не читает журнал `fsm.VERIFYING_STATUS_ACTION` вовсе и не несёт ни
одного упоминания CI (проверено чтением всего тела функции,
строки 190-339) — собранный пакет не содержит ни sha, ни число
проверок, ни идентификатор прогона из journal-записи verifying.

Тест намеренно не зависит от того, реализован ли уже новый порядок
переходов (AC-1/AC-9 из соседнего файла): запись `fsm.
VERIFYING_STATUS_ACTION` в журнал делает уже СЕГОДНЯШНИЙ
`fsm_advance.verifying` (строки 307-309), независимо от того, в какое
состояние он ведёт дальше — здесь только читается сам факт, что эта
запись попадает в собранный ревью-пакет.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FsmOrderScenarioTest, green_ci  # noqa: E402
from orchestrator import review, store  # noqa: E402

# Три узнаваемых, не встречающихся больше нигде в пакете значения — sha
# (8 hex, формат уже реального `ci.verifying_status`), число проверок и
# идентификатор прогона CI (длинное число, чтобы не совпасть случайно с
# чем-то ещё в SPEC/PLAN/diff).
_FAKE_SHA = "01234567"
_FAKE_RUN_ID = "9988776655"
_FAKE_CHECKS = 4
_FAKE_NOTE = (f"CI коммита {_FAKE_SHA} зелёный "
             f"({_FAKE_CHECKS} проверок, run {_FAKE_RUN_ID})")


class ReviewPackageCiStatusLineTest(FsmOrderScenarioTest):

    def test_ac13_review_package_carries_verifying_ci_status_line(self):
        """Ревью-пакет, собранный ПОСЛЕ прохождения `verifying` с зелёным
        CI, несёт sha, число проверок и идентификатор прогона из записи
        журнала `fsm.VERIFYING_STATUS_ACTION` этого же прохода.

        Ловит мутацию: `review_package` продолжает не читать журнал
        verifying вовсе — ни одна из трёх подстрок (sha/run id/число
        проверок) не попадёт в собранный текст пакета.
        """
        self.set_state("verifying")
        with green_ci(note=_FAKE_NOTE):
            self.advance()

        t = self.task_row()
        pkg = review.review_package(store.db(), self.TASK, t["title"],
                                    t["branch"], iteration=1, prev_sha="")

        self.assertIn(_FAKE_SHA, pkg["text"],
                     "sha головы CI не попал в ревью-пакет")
        self.assertIn(_FAKE_RUN_ID, pkg["text"],
                     "идентификатор прогона CI не попал в ревью-пакет")
        self.assertIn(str(_FAKE_CHECKS), pkg["text"],
                     "число проверок CI не попало в ревью-пакет")


if __name__ == "__main__":
    import unittest
    unittest.main()
