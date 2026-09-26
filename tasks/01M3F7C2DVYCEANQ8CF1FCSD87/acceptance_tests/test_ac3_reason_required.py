"""AC-3: `--reason` обязателен — отказ до любого обращения к `gh`.

Красен до реализации: команды `ci-rerun` в пульте нет вовсе — `resolve_command`
не находит обработчика ни в таблице команд `orchestrator/artel.py`, ни по
очевидным адресам, и `run_ci_rerun` валит тест этим сообщением.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CiRerunSandbox  # noqa: E402


class ReasonRequiredTest(CiRerunSandbox):

    def test_ac3_missing_or_empty_reason_refuses_before_touching_gh(self):
        """Без основания (флага нет / основание пустое) — отказ без `gh`.

        Задача в `verifying`, CI ветки красный, голова совпадает — то есть
        все ОСТАЛЬНЫЕ предусловия выполнены, и единственная причина отказа —
        отсутствующее основание. Проверяется не только отказ, но и его
        место в порядке: ни одного обращения к подменённому `gh` после
        старта команды (ни опроса статуса, ни поиска прогона), ни одного
        вызова `ci.trigger_rerun`.

        Ловит мутацию: проверка основания стоит ПОСЛЕ опроса статуса CI и
        сверки с главной веткой (или основание проверяется только на
        непустоту, а `None` проваливается дальше) — команда успевает
        сходить в `gh`, и `gh_calls_since_command` перестаёт быть пустым.
        """
        self.enter_verifying_red()
        for label, reason in (("флага --reason нет", None),
                              ("основание пустое", "")):
            with self.subTest(reason=label):
                self.trigger_calls.clear()
                text = self.run_ci_rerun(reason)

                self.assertEqual(
                    self.gh_calls_since_command(), [],
                    f"{label}: отказ обязан случиться ДО любого обращения "
                    f"к gh; сказано: {text!r}")
                self.assertEqual(
                    self.trigger_calls, [],
                    f"{label}: ci.trigger_rerun не имеет права быть вызванной")
                self.assertTrue(
                    text.strip(),
                    f"{label}: отказ обязан быть именованным — команда "
                    f"промолчала")
                self.assertEqual(
                    self.state(), "verifying",
                    "команда не меняет состояние задачи (требование 9)")


if __name__ == "__main__":
    unittest.main()
