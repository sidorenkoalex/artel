"""AC-4: sha красного статуса разошёлся с текущей головой ветки задачи.

Красен до реализации: команды `ci-rerun` в пульте нет вовсе — `resolve_command`
не находит обработчика ни в таблице команд `orchestrator/artel.py`, ни по
очевидным адресам, и `run_ci_rerun` валит тест этим сообщением.

Фикстура отличается от штатного пути РОВНО одним: после записи журнала о
красном CI коммита `BRANCH_HEAD` голова ветки уезжает на `MOVED_HEAD`
(разработчик успел допушить). Статус CI новой головы в фикстуре тоже
красный — иначе отказ мог бы объясняться требованием 2, а не сверкой головы.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import BRANCH_HEAD, MOVED_HEAD, REASON, CiRerunSandbox  # noqa: E402


class HeadMovedSinceRedStatusTest(CiRerunSandbox):

    def test_ac4_head_moved_refuses_naming_both_shas(self):
        """Голова уехала после красного статуса — отказ с обоими sha.

        Цикл остановился на красном CI коммита `BRANCH_HEAD` (запись
        журнала об этом пишет настоящий `fsm_advance.verifying`), после чего
        голова ветки стала `MOVED_HEAD`. Красный статус относится уже не к
        тому коммиту — повторять по нему нечего: команда обязана отказать,
        назвав оба sha, и не звать `ci.trigger_rerun`.

        Ловит мутацию: сверка головы пропущена (sha берётся заново из
        `ci.head_sha` и сравнивается сам с собой, либо запись журнала не
        читается вовсе) — тогда команда пошла бы перезапускать прогон уже
        неактуального красного статуса, и `trigger_calls` перестал бы быть
        пустым.
        """
        self.enter_verifying_red()
        self.head = MOVED_HEAD
        before = self.last_step_id()

        text = self.run_ci_rerun(REASON)

        self.assertEqual(
            self.trigger_calls, [],
            "при разошедшейся голове ветки повтор не запускается")
        self.assertIn(
            BRANCH_HEAD[:8], text,
            f"отказ обязан называть sha красного статуса; сказано: {text!r}")
        self.assertIn(
            MOVED_HEAD[:8], text,
            f"отказ обязан называть текущую голову ветки; сказано: {text!r}")
        self.assertEqual(
            self.state(), "verifying",
            "команда не меняет состояние задачи (требование 9)")
        self.assertEqual(
            self.state_transitions_since(before), [],
            "отказ не имеет права журналировать переход состояния")


if __name__ == "__main__":
    unittest.main()
