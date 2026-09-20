"""AC-2 (tasks/01M2YWRB9HWW99R57HWGP2M7MQ/SPEC.md): после возврата AC-1
`review_iters` и `accept_rejects` задачи равны значениям до команды.

Счётчики берутся НЕНУЛЕВЫМИ до команды: на нулях «остались прежними» и
«обнулены» неотличимы, и тест пропустил бы реализацию, которая сбрасывает
чужой цикл вместо того, чтобы его не трогать.

Красен до реализации: reject на `spec_gate` ещё отказывает целиком
(`_cmd_reject`, ветка «reject применим только в acceptance, merge_gate или
verifying») — предпосылка критерия «после возврата AC-1» не наступает,
задача остаётся в `spec_gate`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import config  # noqa: E402

# Ненулевой снимок счётчиков до команды: задача уже прошла две итерации
# ревью и один отказ приёмки в прошлой жизни.
REVIEW_ITERS_BEFORE = 2
ACCEPT_REJECTS_BEFORE = 1


class CountersUntouchedByTheSpecGateReturnTest(_sandbox.SpecGateRejectSandbox):

    def test_ac2_review_iters_and_accept_rejects_survive_the_return(self):
        """У задачи на `spec_gate` уже есть история чужих циклов
        (`review_iters=2`, `accept_rejects=1`); возврат аналитику с
        причиной — оба счётчика остаются ровно теми же: гейт SPEC не
        расходует ни лимит итераций ревью, ни лимит отказов приёмки.

        Ловит мутацию: ветка `spec_gate` поставлена ПОСЛЕ проверки
        `state != "acceptance"` (или вовсе слита с ней) — исполнение
        доходит до `rejects = t["accept_rejects"] + 1` и
        `store.update_task(..., accept_rejects=rejects)`, и
        `accept_rejects` станет 2.
        """
        self.set_columns(review_iters=REVIEW_ITERS_BEFORE,
                         accept_rejects=ACCEPT_REJECTS_BEFORE)
        before = self.counters()

        out = self.reject_from("spec_gate", _sandbox.REASON)

        self.assertEqual(
            self.state(), "spec_writing",
            f"возврат AC-1 не состоялся — предпосылка AC-2 не проверена; "
            f"вывод команды: {out!r}")
        self.assertEqual(
            self.counters(), before,
            "(review_iters, accept_rejects) изменились возвратом с гейта SPEC")

    def test_ac2_the_return_does_not_consume_the_accept_rejects_limit(self):
        """Тот же возврат, повторённый столько раз, сколько всего отказов
        приёмки разрешает `config.LIMIT_ACCEPT_REJECTS` плюс один: ни один
        из них не эскалирует задачу по исчерпанному лимиту — счётчик
        отказов приёмки этим гейтом не расходуется вовсе.

        Число повторов считается от `config.LIMIT_ACCEPT_REJECTS`, не
        литералом: потолок — крутилка Оператора.

        Ловит мутацию: возврат считает себя отказом приёмки (растит
        `accept_rejects` и сверяет его с лимитом, как ветка `acceptance`)
        — на повторе сверх лимита задача уйдёт в `escalated` вместо
        `spec_writing`.
        """
        for attempt in range(config.LIMIT_ACCEPT_REJECTS + 1):
            with self.subTest(возврат=attempt + 1):
                out = self.reject_from("spec_gate", _sandbox.REASON)
                self.assertEqual(
                    self.state(), "spec_writing",
                    f"возврат №{attempt + 1} не вернул задачу аналитику; "
                    f"вывод команды: {out!r}")
                self.assertEqual(self.counters()[1], 0,
                                 "accept_rejects вырос на возврате с гейта SPEC")


if __name__ == "__main__":
    unittest.main()
