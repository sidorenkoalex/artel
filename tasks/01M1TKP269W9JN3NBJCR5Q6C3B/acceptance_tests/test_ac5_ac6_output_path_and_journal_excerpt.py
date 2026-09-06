"""AC-5/AC-6 (SPEC.md):

AC-5. Путь сохранённой диагностики (AC-1..AC-3) печатается в выводе
команды `canary`.
AC-6. Вывод `canary` несёт для каждой задачи набора выдержку журнала
(переходы состояний и записи «эскалация»/«переход отклонён»/«auto
остановлен»), не более 20 строк на задачу, вместо одной итоговой строки
исхода.

Сценарий — тот же класс «не сошлась», что и `test_ac1_ac2_ac3_
diagnostics_on_inconclusive_outcome.py`: ревью один раз запрашивает
доработку, повторный вход в `in_dev` держит rework-гейт (`orchestrator/
auto.py::_role_step_since_state_entry`, «регрессия №13» — тестовая
заглушка агента не журналирует `agent run finished`), три холостых
прохода без прогресса убивают задачу «не сошлась». Гарантированно даёт
и путь диагностики (AC-5 без диагностики нечего было бы печатать), и
как минимум одну запись «переход отклонён» в журнале (AC-6 — сама
запись rework-гейта: «переход отклонён: замечания ревью не
отработаны»).

Красен до реализации: вывод `canary` — прежний однострочный формат
(`шагов=... исход=...`) без пути диагностики вовсе — обе проверки этого
файла ищут то, чего в старом выводе нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox, extract_run_stamp, extract_task_ids  # noqa: E402

TITLE_NEVER_APPROVED = "vyvod-nikogda-ne-odobrennaya-pravka"


class OutputPathAndJournalExcerptTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            f"{TITLE_NEVER_APPROVED}.md":
                "Синтетическая правка, ревью которой никогда не "
                "одобряется.",
        })
        self.agent.extra_review_rounds_default = 1

    def _per_task_lines(self, out: str, task_id: str) -> list:
        """Строки вывода СТРОГО между объявлением задачи («заведена») и
        концом прогона (либо следующей задачей набора — здесь k=1, так
        что граница — финальная строка «прогон ... завершён»)."""
        lines = out.splitlines()
        start = next(i for i, l in enumerate(lines)
                    if f"] {task_id} заведена из" in l)
        end = next(i for i, l in enumerate(lines) if "завершён" in l)
        self.assertLess(start, end, out)
        return lines[start + 1:end]

    def test_ac5_diagnostics_path_is_printed(self):
        """Путь `.artel/canary/<run_stamp>/<task_id>/`, под которым
        реально сохранена диагностика, встречается в выводе команды
        буквально (не пересказан словами) — Оператор должен суметь
        скопировать его из вывода.

        Ловит мутацию: разработчик сохраняет диагностику (AC-1..AC-3),
        но не печатает её путь — каталог на диске существует, но его
        полный путь нигде не встречается в тексте вывода.
        """
        out = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out, out)
        run_stamp = extract_run_stamp(out)
        task_ids = extract_task_ids(out)
        self.assertEqual(len(task_ids), 1, out)
        diag_dir = self.root / ".artel" / "canary" / run_stamp / task_ids[0]
        self.assertTrue(diag_dir.is_dir(), out)

        self.assertIn(
            str(diag_dir), out,
            f"путь сохранённой диагностики не встречается в выводе "
            f"команды:\n{out}")

    def test_ac6_output_is_a_multiline_journal_excerpt_not_one_summary_line(self):
        """Вывод по задаче — несколько строк выдержки журнала (переходы
        состояний, запись «переход отклонён» rework-гейта), не одна
        финальная строка «шагов=... исход=...»; выдержка укладывается в
        потолок 20 строк на задачу.

        Ловит мутацию: разработчик оставляет старый однострочный формат
        v2 (`  {task_id}: шагов=... исход=...`) — per-task часть вывода
        сжимается до 1 строки, тест на «больше одной строки» и на
        присутствие «переход отклонён»/«state ->» (которых в
        однострочном итоге нет вовсе) не проходит.
        """
        out = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out, out)
        task_ids = extract_task_ids(out)
        self.assertEqual(len(task_ids), 1, out)
        task_id = task_ids[0]

        per_task = self._per_task_lines(out, task_id)
        non_empty = [l for l in per_task if l.strip()]

        self.assertGreater(
            len(non_empty), 1,
            f"вывод по задаче {task_id} — одна строка вместо выдержки "
            f"журнала:\n{per_task}")
        self.assertLessEqual(
            len(non_empty), 20,
            f"выдержка журнала задачи {task_id} превышает потолок 20 "
            f"строк: {len(non_empty)}\n{per_task}")

        excerpt_text = "\n".join(per_task)
        self.assertTrue(
            any(marker in excerpt_text
               for marker in ("эскалация", "переход отклонён",
                              "auto остановлен", "state ->")),
            f"выдержка журнала задачи {task_id} не несёт ни одной "
            f"узнаваемой записи перехода/эскалации:\n{excerpt_text}")


if __name__ == "__main__":
    unittest.main()
