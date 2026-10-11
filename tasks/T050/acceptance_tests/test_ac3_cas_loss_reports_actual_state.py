"""AC-3 (tasks/T050/SPEC.md): отказ проигравшего `set_state` называет
фактическое состояние задачи, прочитанное из БД («ожидалось X, в БД Y»).

Отказ может уйти исключением или возвратом (SPEC требование 3: «…
возвращается/бросается…», интерфейс сознательно не фиксирован) — тест
собирает весь наблюдаемый текст (stdout + текст исключения, если оно
было), тем же приёмом, что `_invoke` в
tasks/T044/acceptance_tests/test_lease_enforcement.py.
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK = "T001"


def _attempt(conn, state: str, actor: str, expected_state: str) -> str:
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            result = store.set_state(conn, task_id=TASK, state=state,
                                     actor=actor, expected_state=expected_state)
    except BaseException as exc:
        return buf.getvalue() + str(exc)
    return buf.getvalue() + ("" if result is None else str(result))


class CasLossReportsActualStateTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def test_ac3_refusal_names_the_expected_and_the_actual_state(self):
        conn = store.db()
        # Первый вызов побеждает и переводит задачу в review — второй
        # вызов ниже всё ещё ждёт in_dev, а фактическое состояние в БД
        # уже другое.
        store.set_state(conn, task_id=TASK, state="review", actor="winner",
                        expected_state="in_dev")
        self.assertEqual(store.get_task(conn, TASK)["state"], "review")

        response = _attempt(conn, state="review", actor="loser",
                            expected_state="in_dev")

        self.assertIn("in_dev", response,
                      f"отказ не назвал ожидаемое состояние: {response!r}")
        self.assertIn("review", response,
                      f"отказ не назвал фактическое состояние, прочитанное "
                      f"из БД: {response!r}")
        self.assertEqual(store.get_task(conn, TASK)["state"], "review",
                         "проигравший вызов не имеет права менять состояние")


if __name__ == "__main__":
    unittest.main()
