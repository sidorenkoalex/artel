"""Граница срока записи строки «оборвана сигналом» дочерним параллельного
прогона канарейки: все попытки записи и снятие группы ведения укладываются в
срок родителя до SIGKILL.

Группа: долгоживущий
Красен до реализации: константы `CHILD_ROW_WRITE_ATTEMPTS` в `orchestrator/canary.py` ещё нет — обращение к ней падает `AttributeError`.

Модель срока: на одну попытку записи — не более трёх ожиданий блокировки
соединения по 5 с (миграция при открытии соединения, обновление таблиц
канарейки, вставка).
"""
import unittest

from orchestrator import canary, liveness

LOCK_WAITS_PER_ATTEMPT = 3
LOCK_WAIT_SEC = 5


class RowWriteDeadlineTest(unittest.TestCase):
    def test_ac5_write_attempts_fit_parent_stop_grace(self):
        """Худший срок записи строки дочерним меньше срока родителя до SIGKILL.

        Сценарий: `CHILD_ROW_WRITE_ATTEMPTS` — целое не меньше 1; величина
        `CHILD_ROW_WRITE_ATTEMPTS × 3 × 5 + GROUP_TERMINATE_GRACE_SEC`
        строго меньше `PARALLEL_STOP_GRACE_SEC`.

        Ловит мутацию: число попыток поднято до 4 (60 + 3 ≥ 60) либо срок
        `PARALLEL_STOP_GRACE_SEC` снижен до 45 — дочерний снимается SIGKILL
        посреди повторов, строки «оборвана сигналом» нет; либо константа
        нулевая — повторов нет вовсе.
        """
        attempts = canary.CHILD_ROW_WRITE_ATTEMPTS
        self.assertIsInstance(attempts, int)
        self.assertGreaterEqual(attempts, 1)
        worst = (attempts * LOCK_WAITS_PER_ATTEMPT * LOCK_WAIT_SEC
                 + liveness.GROUP_TERMINATE_GRACE_SEC)
        self.assertLess(worst, canary.PARALLEL_STOP_GRACE_SEC,
                        f"попыток {attempts}, худший срок {worst} с, срок "
                        f"родителя {canary.PARALLEL_STOP_GRACE_SEC} с")
