"""Приёмочный тест AC-7 (tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/SPEC.md):
`artel report` на той же копии БД пульта в песочнице даёт тот же вывод
(тот же HTML) до и после рефакторинга `store.py`/`schema.py`.

Тот же приём, что и `test_ac6_status_output_smoke.py` (см. его
докстринг про буквальную «копию живой БД» — не воспроизводима в
детерминированном юнит-тесте, заменена фикстурой): здесь предмет
сравнения — не короткая строка `stdout`, а весь файл `report.html`
(`cmd_report` печатает в stdout только путь к файлу, само «тот же
вывод» относится к его СОДЕРЖИМОМУ). Полный HTML — несколько
килобайт разметки, поэтому сравнение идёт по SHA-256 всего файла, а
не по вставленному в тест куску текста: хэш ловит ЛЮБОЕ отличие
байт-в-байт, не только то, что автор теста решил процитировать явно.

Три источника недетерминизма зафиксированы явно, чтобы хэш был
воспроизводим независимо от момента запуска:
- `store.now` — иначе `created_at`/`updated_at`/`ts` журнала несли бы
  реальное время запуска теста;
- `config.LIMIT_REVIEW_ITERS` — крутилка Оператора, встроенная в
  разметку (`_gate_queue_html`) — тест не должен спонтанно покраснеть
  от смены потолка ревью, не имеющей отношения к этому рефакторингу
  (урок T062: нельзя намертво впаивать значение дозволенной крутилки —
  здесь оно намертво впаяно осознанно, но ТОЛЬКО НА ВРЕМЯ ЭТОГО
  ЗАМОРОЖЕННОГО теста, отдельным `mock.patch`, а не литералом внутри
  кода приложения);
- фикстура использует состояния `done`/`escalated` (не `in_dev`) и не
  создаёт `leases`/собственных файлов `.artel/logs/*.log` — тот же
  приём отказа от зонных/lease-путей, что и в `test_ac6_...` (там же
  объяснение, почему это безопасно и не «подгонка под тест»: `report`
  по этим данным попросту не читает).

Зелёный с рождения: хэш снят с сегодняшнего (дорефакторингового)
`report.cmd_report()` на этой же фикстуре — обязан остаться тем же
после переноса схемы/миграций в `schema.py` (AC-1) и группировки
запросов (AC-3), поскольку поведение не меняется (SPEC, требование 6).
"""
import hashlib
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, report, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

# SHA-256 `.artel/report.html`, сгенерированного `report.cmd_report()` на
# фикстуре ниже сегодняшним (дорефакторинговым) `orchestrator/report.py` +
# `orchestrator/store.py`.
_EXPECTED_SHA256 = (
    "920f2ac5c41e17525a0845cfdf97ef5c44bf7d5093df2538d00c420af40fee68")


class ReportOutputByteParityTest(TmpRootTest):

    def test_ac7_report_html_matches_golden_sha256(self):
        """`report.cmd_report()` на детерминированной фикстуре (две
        задачи, четыре записи журнала) пишет `.artel/report.html`,
        SHA-256 которого совпадает с хэшем, снятым на той же фикстуре
        до рефакторинга.

        Ловит мутацию: перенос схемы/миграций в `schema.py` (AC-1) или
        группировка запросов (AC-3), которые по пути незаметно изменили
        любую метрику отчёта (например, порядок задач/журнала, влияющий
        на `_friction_html`/`_gate_ratio`, или потерянное поле
        `spent_usd` из-за опечатки при переносе) — хэш файла меняется
        при малейшем отличии хотя бы одного байта HTML.
        """
        with mock.patch.object(store, "now", lambda: "2020-01-01 00:00:00Z"), \
                mock.patch.object(config, "LIMIT_REVIEW_ITERS", 3):
            conn = store.db()
            store.create_schema(conn)

            store.insert_task(
                conn, "T001", "Обычная задача", "done", "task/t001",
                config.DEFAULT_TARGET, 10.0, is_canary=False)
            store.update_task(conn, "T001", spent_usd=2.5, review_iters=1)
            store.journal(conn, "T001", "developer", "state -> in_dev", "",
                         session_id="s-test")
            store.journal(conn, "T001", "operator", "state -> merge_gate", "",
                         session_id="s-test")

            store.insert_task(
                conn, "T002", "Эскалированная задача", "escalated",
                "task/t002", config.DEFAULT_TARGET, 8.0, is_canary=False)
            store.update_task(conn, "T002", spent_usd=1.25)
            store.journal(conn, "T002", "developer", "escalate", "вопрос",
                         session_id="s-test")

            report.cmd_report()

            html = (config.ROOT / ".artel" / "report.html").read_text(
                encoding="utf-8")

        actual_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()
        self.assertEqual(
            actual_sha256, _EXPECTED_SHA256,
            "report.html отличается от золотого снимка — длина текущего "
            f"вывода {len(html)} байт")


if __name__ == "__main__":
    unittest.main()
