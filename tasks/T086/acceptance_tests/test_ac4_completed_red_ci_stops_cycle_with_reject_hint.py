"""AC-4 (tasks/T086/SPEC.md): завершённый красный CI (`ci.VERIFYING_RED`)
останавливает цикл `auto` на состоянии `verifying` с сообщением-
подсказкой, называющим `artel.py reject`; состояние задачи при этом
остаётся `verifying` (переход в `escalated`/`in_dev` `auto` сам не
выполняет).

Зелёный с рождения: сегодня `verifying` не входит в `STATE_ROLE`, поэтому `auto` останавливает цикл на входе в НЕГО ЖЕ, ни разу не опросив `ci.verifying_status` — случайное совпадение внешнего наблюдения с требованием AC-4 по вырожденной причине («не покидает verifying», потому что цикл вообще не входит в тело, а не потому что код различил именно завершённый красный CI); сегодняшний `config.AUTO_STOP["verifying"]` уже называет ОБЕ команды (`advance` и `reject`) в одной подсказке безусловно — `"artel.py reject"` в ней есть независимо от статуса CI, так что и вторая проверка проходит уже сейчас.

Тест не становится от этого бесполезным: он фиксирует ДВЕ вещи как
планку на будущее — 1) реализация требования 1 (новая ветка `verifying`
в `auto`) не имеет права позволить завершённому красному CI сдвинуть
задачу в `escalated`/`in_dev` НИ НА КАКОМ ЭТАПЕ цикла (не только на
первом опросе, но и после N-1 неудачных промежуточных при повторном
запуске функции с уже накопленным состоянием); 2) какой бы ни стала
точная логика остановки, подсказка обязана явно называть `artel.py
reject`, а не просто угадываться по старому многоцелевому тексту,
который эта задача с высокой вероятностью заменит на более точный.
Регресс здесь красит тест сразу же, а не открывает окно для нового бага.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto  # noqa: E402
from _sandbox import RED_RUNS, VerifyingTest  # noqa: E402


class VerifyingRedCiStopsCycleWithRejectHintTest(VerifyingTest):

    def test_ac4_red_ci_stays_in_verifying_not_escalated_not_in_dev(self):
        self.enter_verifying(RED_RUNS, "[]")

        auto.cmd_auto(self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "завершённый красный CI сам по себе не имеет права сдвинуть "
            "задачу ни в escalated, ни в in_dev — только Оператор через "
            "reject (ADR-0009, «Последствия»)")

    def test_ac4_stop_hint_names_reject(self):
        self.enter_verifying(RED_RUNS, "[]")

        out = self.capture(auto.cmd_auto, self.TASK)

        self.assertIn(
            "artel.py reject", out,
            "остановка цикла на завершённом красном CI обязана назвать "
            "artel.py reject Оператору")


if __name__ == "__main__":
    unittest.main()
