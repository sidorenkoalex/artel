"""AC-8 (SPEC.md): по завершении прогона задачи механика сверяет
наличие машиночитаемого маркера «ожидается эскалация» в исходном
шаблоне ТЗ с фактическим исходом задачи (была ли эскалация);
расхождение отражается в отчёте прогона.

Маркер — `<!-- canary-expect-escalation: yes|no -->` в теле шаблона
(`_sandbox.MARK_EXPECT_ESCALATION_YES`/`_NO`, см. обоснование формата
в докстринге `_sandbox.py`: `catalog.cmd_new`/`_tz_document` кладёт
сырой текст шаблона ТЕЛОМ итогового `TZ.md`, фронтматтер самого
шаблона до задачи не доходит — HTML-комментарий читаем механикой и не
виден при рендере markdown).

Обе задачи этого теста устроены так, чтобы НЕ эскалировать фактически
(`_sandbox.SmartAgent` эскалирует только по `ESCALATE_TITLE_MARKER` в
имени файла — заголовке задачи, независимому сигналу, который здесь
не используется намеренно): одна несёт маркер «ожидается: нет»
(совпадает с фактом — не в отчёте), другая — «ожидается: да»
(расходится с фактом — обязана попасть в отчёт). Так тест целится
именно в СВЕРКУ маркер/факт, не смешивая её с механикой авто-ответа
(AC-6, отдельный тест).

Красен до реализации: `canary --k` падает на разборе аргументов,
эфемерных клонов не заводится, первая содержательная проверка
(наличие снимка клона) падает `AssertionError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (CanarySandbox, MARK_EXPECT_ESCALATION_NO,  # noqa: E402
                      MARK_EXPECT_ESCALATION_YES, _EphemeralDirTracker)

POOL_TEMPLATES = {
    "tikhaya-pravka-ne-ozhidaem.md":
        f"{MARK_EXPECT_ESCALATION_NO}\n"
        "Синтетическая тихая правка, эскалация не ожидается и не "
        "случается.",
    "tikhaya-pravka-ozhidali-eskalaciyu.md":
        f"{MARK_EXPECT_ESCALATION_YES}\n"
        "Синтетическая тихая правка — маркер ошибочно обещает "
        "эскалацию, которой не будет.",
}


class EscalationMarkerDiscrepancyTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)
        self.tracker = _EphemeralDirTracker()
        self.tracker.start(self, deep=True)

    def _title_to_task_id(self) -> dict:
        mapping = {}
        for snap in self.tracker.git_like_snapshots():
            for t in snap.get("tasks", []):
                mapping[t["title"]] = t["id"]
        return mapping

    def test_ac8_mismatch_between_marker_and_actual_outcome_is_reported(self):
        """N=2 шаблона (k=2, чтобы выборка не играла роли — оба всегда
        в прогоне), ни один фактически не эскалирует. Отчёт прогона
        обязан назвать несовпадение у задачи «ожидали эскалацию» (факт
        — не было) и НЕ поднимать его у задачи «не ожидали» (факт
        сошёлся).

        Ловит мутацию: разработчик читает маркер, но не сравнивает его
        с фактическим исходом (проставляет маркер как метаданные без
        сверки) — тогда ни для одной из задач в отчёте не появится
        слова, сигнализирующего расхождение, и первая проверка
        (наличие сигнала у task_id "ожидали") упадёт.
        """
        out = self.run_canary_pool(2)
        self.assertNotIn("[SystemExit]", out, out)

        title_to_id = self._title_to_task_id()
        expected_id = title_to_id.get("tikhaya-pravka-ozhidali-eskalaciyu")
        quiet_id = title_to_id.get("tikhaya-pravka-ne-ozhidaem")
        self.assertIsNotNone(
            expected_id, f"задача с маркером 'yes' не найдена в клонах: "
            f"{title_to_id}")
        self.assertIsNotNone(
            quiet_id, f"задача с маркером 'no' не найдена в клонах: "
            f"{title_to_id}")

        discrepancy_words = ("расхожд", "несовпад", "mismatch")

        def _nearby_flags_discrepancy(task_id: str) -> bool:
            idx = out.find(task_id)
            if idx == -1:
                return False
            window = out[max(0, idx - 200):idx + 200].lower()
            return any(w in window for w in discrepancy_words)

        self.assertTrue(
            _nearby_flags_discrepancy(expected_id),
            f"отчёт не отметил расхождение маркер/факт для задачи "
            f"{expected_id} (ожидали эскалацию, её не случилось):\n{out}")
        self.assertFalse(
            _nearby_flags_discrepancy(quiet_id),
            f"отчёт ошибочно отметил расхождение у задачи {quiet_id}, "
            f"хотя маркер и факт совпали (не ожидали — не случилось):\n{out}")


if __name__ == "__main__":
    unittest.main()
