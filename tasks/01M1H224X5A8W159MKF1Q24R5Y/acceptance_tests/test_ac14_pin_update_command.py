"""AC-14: Отдельная операторская команда обновляет пин (продвигает рабочее
дерево и HEAD `config.ROOT` до нового sha main) и пишет журнальную запись
с операторской идентичностью, старым и новым sha, временем обновления;
`doctor` эту команду сам не вызывает.

Допущение интерфейса (см. `test_ac13_doctor_pin_drift_check.py` — тот же
файл допущений): команда — `artel.py pin-update <sha main>`, диспетчер
`orchestrator/artel.py::main()` (дефис-конвенция существующих команд:
`target-init`, `alert-ack`, `acceptance-dry-run`). `<sha>` — sha main
артели, который печатает doctor-проверка AC-13 (явное подтверждение
Оператора, не безусловный fast-forward «докуда получится»). Операторская
идентичность — литерал `"operator"`, тот же, каким уже журналирует любое
другое операторское действие (`orchestrator/budget.py::_cmd_budget`,
`store.journal(conn, task_id, "operator", ...)`). Журнал — таблица
`steps` (то же значение термина «журнал», что и везде в системе,
инвариант 11 «журнал шагов пишется всегда»); тест ищет запись по
СОДЕРЖИМОМУ (actor=operator, оба sha в detail), не по конкретному
`task_id` — команда не привязана к задаче.

Красен до реализации: команды `pin-update` не существует — `artel.main()`
с `argv=["artel.py", "pin-update", <sha>]` сегодня падает на разборе
неизвестной команды, HEAD `config.ROOT` не двигается никуда.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import artel, doctor, store  # noqa: E402
from tests.sandbox import capture  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ArtelSelfTargetSandbox  # noqa: E402


class PinUpdateCommandTest(ArtelSelfTargetSandbox):

    def run_pin_update(self, sha: str) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", "pin-update", sha]):
            return capture(artel.main)

    def steps_mentioning(self, *substrings: str) -> list:
        conn = store.db()
        rows = conn.execute(
            "SELECT actor, action, detail FROM steps").fetchall()
        return [r for r in rows
               if all(s in (r["detail"] or "") for s in substrings)]

    def test_ac14_pin_update_advances_root_worktree_and_head_to_new_main_sha(self):
        """`pin-update <sha main артели>` продвигает рабочее дерево и HEAD
        `config.ROOT` до этого sha — файл, который принёс продвинутый
        main (`external-change.txt`, см. `advance_origin_main_without_
        touching_root`), появляется в рабочем дереве `config.ROOT` после
        команды, HEAD совпадает с запрошенным sha.

        Ловит мутацию: команда `pin-update` не реализована (или
        реализована, но не двигает реальный чекаут `config.ROOT`) — файл
        не появится, `root_head_sha()` останется на старом sha.
        """
        new_sha = self.advance_origin_main_without_touching_root()
        self.assertNotEqual(self.root_head_sha(), new_sha)

        self.run_pin_update(new_sha)

        self.assertEqual(self.root_head_sha(), new_sha)
        self.assertTrue((self.root / "external-change.txt").exists(),
                        "рабочее дерево config.ROOT обязано получить "
                        "содержимое продвинутого main")

    def test_ac14_pin_update_journals_operator_identity_and_both_shas(self):
        """После `pin-update` в журнале (таблица `steps`) обязана
        появиться запись операторской идентичности со старым и новым sha
        (по 7-значному префиксу каждого).

        Ловит мутацию: команда двигает HEAD, но не журналирует ничего —
        `steps_mentioning` не найдёт ни одной подходящей строки.
        """
        old_sha = self.root_head_sha()
        new_sha = self.advance_origin_main_without_touching_root()

        self.run_pin_update(new_sha)

        matches = self.steps_mentioning(old_sha[:7], new_sha[:7])
        self.assertTrue(matches,
                        f"ни одна запись журнала не назвала оба sha "
                        f"({old_sha[:7]}, {new_sha[:7]})")
        self.assertTrue(any(r["actor"] == "operator" for r in matches),
                        "запись обязана нести операторскую идентичность "
                        "(actor='operator')")

    def test_ac14_doctor_never_advances_the_pin_on_its_own(self):
        """Контроль: прогон `doctor` (даже когда он видит расхождение
        пина, AC-13) не двигает HEAD/рабочее дерево `config.ROOT` сам —
        `doctor` только СООБЩАЕТ о расхождении, продвигает пин ТОЛЬКО
        `pin-update`.

        Ловит мутацию: реализация AC-13, которая по ошибке сама
        обновляет пин как побочный эффект прогона `doctor` (авто-починка
        вместо информационного сообщения)."""
        before = self.root_head_sha()
        self.advance_origin_main_without_touching_root()

        doctor.all_checks(store.db())

        self.assertEqual(self.root_head_sha(), before,
                         "doctor не имеет права сам продвигать пин")


if __name__ == "__main__":
    unittest.main()
