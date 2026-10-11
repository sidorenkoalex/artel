"""AC-21, AC-22 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md): сборка брифа,
пропустившая ВСЕГДА включаемый компонент (`docs/codebase-map.md`) по
потолку размера файла, поднимает открытый алерт с указанием компонента,
его размера и потолка (AC-21); сборка того же брифа при компоненте,
вновь помещающемся в потолок, закрывает этот алерт автоматически
(AC-21, паттерн авто-закрытия T035/T088); пропуск по потолку файла
АРТЕФАКТА КОНКРЕТНОЙ ЗАДАЧИ (здесь — SPEC.md) алерт не поднимает —
фиксируется только записью в описи пакета (AC-22).

SPEC называет источник сигнала только по смыслу («существующий механизм
orchestrator/alerts.py»), не по конкретному `source`-ключу — тест
поэтому не завязан на конкретную строку `source`, только на содержимое
сообщения алерта (компонент/размер/потолок) и на факт открытия/
авто-закрытия через `alerts.open_alerts`.

Красен до реализации: сегодня переполнение потолка размера файла вообще
не существует как условие (потолок ещё не заведён), алертов о нём брифы
не поднимают ни при каких обстоятельствах.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import alerts  # noqa: E402
from _sandbox import BriefSandbox, TASK  # noqa: E402

FILE_CAP_BYTES = 131072  # AC-2/AC-3


class Ac21MapAlertTest(BriefSandbox):

    def test_ac21_oversized_always_included_map_raises_an_open_alert(self):
        big_map = "я" * (FILE_CAP_BYTES + 1000)
        (self.root / "docs" / "codebase-map.md").write_text(
            big_map, encoding="utf-8")

        self.build_brief()

        rows = alerts.open_alerts(self.conn, "incident")
        messages = "\n".join(r["message"] for r in rows)
        self.assertIn("codebase-map.md", messages,
                      "алерт обязан назвать пропущенный компонент")
        self.assertIn(str(len(big_map.encode("utf-8"))), messages,
                      "алерт обязан назвать его размер")
        self.assertIn(str(FILE_CAP_BYTES), messages,
                      "алерт обязан назвать потолок")

    def test_ac21_alert_auto_closes_once_the_map_fits_the_cap_again(self):
        big_map = "я" * (FILE_CAP_BYTES + 1000)
        (self.root / "docs" / "codebase-map.md").write_text(
            big_map, encoding="utf-8")
        self.build_brief()
        opened = alerts.open_alerts(self.conn, "incident")
        opened_ids = {r["id"] for r in opened
                     if "codebase-map.md" in (r["message"] or "")}
        self.assertTrue(opened_ids, "алерт не завёлся — не с чем сравнивать")

        # Карта снова маленькая — тот же built_at_sha, свежесть не при чём,
        # только размер.
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
            "---\n\n# Карта\n", encoding="utf-8")

        self.build_brief()

        still_open = {r["id"] for r in alerts.open_alerts(self.conn, "incident")}
        self.assertFalse(
            opened_ids & still_open,
            "алерт о переполнении карты обязан закрыться автоматически, "
            "когда карта снова умещается в потолок (AC-21, паттерн "
            "T035/T088)")


class Ac22TaskArtifactNoAlertTest(BriefSandbox):

    def test_ac22_oversized_task_artifact_does_not_raise_an_alert(self):
        big_spec = "Маркер-текста-SPEC.\n" + ("я" * (FILE_CAP_BYTES + 1000))
        (self.root / "tasks" / TASK / "SPEC.md").write_text(
            big_spec, encoding="utf-8")
        before = len(alerts.open_alerts(self.conn))

        text = self.build_brief()

        self.assertNotIn("Маркер-текста-SPEC.", text,
                         "SPEC.md крупнее потолка — сам факт пропуска "
                         "проверен test_ac2, здесь важно отсутствие алерта")
        after = alerts.open_alerts(self.conn)
        self.assertEqual(
            len(after), before,
            "пропуск артефакта конкретной задачи (SPEC/TZ/PLAN/REVIEW/"
            "ANSWER) по потолку размера не должен поднимать алерт — "
            "только запись в описи (AC-22)")


if __name__ == "__main__":
    unittest.main()
