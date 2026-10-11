"""AC-4 (tasks/T085/SPEC.md): `alerts.ack` для алерта `kind=threshold`
не требует непустого `resolution` — как и сейчас.

Зелёный с рождения: SPEC требование 2 прямо запрещает менять это
поведение («`kind=threshold` по-прежнему без ack-обязательств»).
`orchestrator/alerts.py::ack` уже сегодня требует непустой `resolution`
только для `kind == "trigger"` — для `threshold` подтверждение с пустой
строкой проходит без отказа.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import alerts, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class ThresholdAckWithoutResolutionTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()

    def test_ac4_ack_with_empty_resolution_succeeds_for_threshold(self):
        alerts.raise_alert(self.conn, None, "threshold", "budget.program_spend",
                           "суммарно по всем задачам $1401.00 из $2000.00 — "
                           "пересечён порог 70% расхода программы")
        alert_id = alerts.open_alerts(self.conn, "threshold")[0]["id"]

        error = alerts.ack(self.conn, alert_id, "operator", resolution="")

        self.assertIsNone(
            error,
            f"AC-4: ack алерта kind=threshold не обязан нести resolution; "
            f"получен отказ: {error!r}")
        self.assertEqual(alerts.open_alerts(self.conn, "threshold"), [],
                         "AC-4: подтверждённый алерт больше не открыт")


if __name__ == "__main__":
    unittest.main()
