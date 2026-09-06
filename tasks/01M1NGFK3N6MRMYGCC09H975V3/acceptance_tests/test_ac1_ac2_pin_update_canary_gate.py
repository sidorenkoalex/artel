"""AC-1, AC-2 (tasks/01M1NGFK3N6MRMYGCC09H975V3/SPEC.md): `pin-update`
отказывает без достаточно свежего зелёного прогона канарейки и
продолжает работать как прежде, когда такой прогон есть.

Контракт полей журнала (`main_sha`, `verdict`), именованная константа
`config.CANARY_MAX_MERGES_SINCE_GREEN` и точная формулировка отказа —
ANSWER-1 (Оператор, ответ на эскалацию этой задачи, п.1, п.3, п.4):
прогон «не старше N» ⇔ возраст (`git rev-list --count --merges S..T` в
`config.ROOT`) < N; `main_sha` прогона обязан быть предком целевого sha
(`git merge-base --is-ancestor`), иначе прогон не считается; отказ
начинается словами `pin-update: нет зелёного прогона канарейки` и несёт
команду запуска канарейки (`python3 orchestrator/artel.py canary --k`);
проверка — до `fetch`/`merge`.

Фикстура (`_sandbox.py::CanaryPinSandbox.merge_commit`) держит `origin`
синхронным с локальным main на каждом шаге — настоящий `git fetch`
внутри `pin.cmd_pin_update` остаётся безопасным no-op независимо от
того, вычисляет ли guard возраст относительно аргумента `sha` или
относительно локального HEAD (ANSWER-1 не уточняет это буквально до
байта реализации — здесь оба совпадают).

Красен до реализации: `store.insert_canary_run` в `orchestrator/store.py`
сегодня не принимает `main_sha=`/`verdict=` — `_sandbox.py::insert_run`
падает `TypeError` на первом же вызове; `config.
CANARY_MAX_MERGES_SINCE_GREEN` не существует — `AttributeError` там, где
тест ссылается на неё напрямую. `pin.cmd_pin_update` сегодня безусловно
делает `fetch`+`merge --ff-only` без единой проверки канарейки, так что
даже без журнала (AC-1) она бы прошла до `merge`.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, pin  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import CanaryPinSandbox  # noqa: E402


class PinUpdateCanaryGateTest(CanaryPinSandbox):

    def test_ac1_no_green_run_in_journal_refuses_and_preserves_pin(self):
        """Журнал канарейки пуст (ни одного прогона) — `pin-update`
        отказывает именованным сообщением с командой запуска канарейки,
        HEAD `config.ROOT` не двигается.

        Ловит мутацию: guard проверяет только «журнал не пуст» без учёта
        verdict/возраста — при пустом журнале должен отказать так же, как
        и при устаревшем прогоне, а не считать «нечего сравнивать» за ОК.
        """
        target = self.merge_commit(count=1)
        before = self.root_head_sha()

        with self.assertRaises(SystemExit) as cm:
            pin.cmd_pin_update(target)

        message = str(cm.exception)
        self.assertTrue(
            message.startswith("pin-update: нет зелёного прогона канарейки"),
            message)
        self.assertIn("python3 orchestrator/artel.py canary --k", message)
        self.assertEqual(self.root_head_sha(), before)

    def test_ac1_only_stale_green_run_refuses_and_preserves_pin(self):
        """Зелёный прогон есть, но его `main_sha` ровно на `config.
        CANARY_MAX_MERGES_SINCE_GREEN` мержей старше целевого sha (граница
        «устарел») — `pin-update` отказывает тем же именованным
        сообщением, пин не двигается.

        Ловит мутацию: guard считает «зелёный прогон существует» вообще,
        не сверяя его возраст с порогом N (off-by-one или отсутствие
        сравнения) — устаревший ровно на границе прогон ложно считался бы
        достаточно свежим.
        """
        stale_sha = self.root_head_sha()
        self.insert_run(stale_sha, "green")
        target = self.merge_commit(count=config.CANARY_MAX_MERGES_SINCE_GREEN)
        before = self.root_head_sha()

        with self.assertRaises(SystemExit) as cm:
            pin.cmd_pin_update(target)

        self.assertTrue(str(cm.exception).startswith(
            "pin-update: нет зелёного прогона канарейки"))
        self.assertEqual(self.root_head_sha(), before)

    def test_ac1_non_ancestor_green_run_is_not_considered(self):
        """Зелёный прогон в журнале ссылается на `main_sha` из ТУПИКОВОЙ
        ветки, никогда не смерженной в main, — он не предок целевого sha
        и обязан считаться отсутствующим: `pin-update` отказывает так же,
        как при пустом журнале.

        Ловит мутацию: guard берёт verdict/возраст любого попавшегося
        зелёного прогона, не проверяя `git merge-base --is-ancestor`, —
        прогон с чужой, несвязанной историей ложно считался бы валидным
        основанием для обновления пина.
        """
        abandoned_sha = self.branch_off_without_merging()
        self.insert_run(abandoned_sha, "green")
        target = self.merge_commit(count=1)
        before = self.root_head_sha()

        with self.assertRaises(SystemExit) as cm:
            pin.cmd_pin_update(target)

        self.assertTrue(str(cm.exception).startswith(
            "pin-update: нет зелёного прогона канарейки"))
        self.assertEqual(self.root_head_sha(), before)

    def test_ac2_recent_green_run_allows_pin_update_as_before(self):
        """Зелёный прогон в журнале младше `config.
        CANARY_MAX_MERGES_SINCE_GREEN` мержей относительно целевого sha
        (граница «свежий», на единицу меньше порога отказа AC-1) —
        `pin-update` выполняет обновление пина как прежде: HEAD `config.
        ROOT` продвигается до целевого sha, журнал получает запись «pin
        обновлён».

        Ловит мутацию: новый guard отказывает вообще ЛЮБОМУ вызову
        (регресс существующего поведения, `tasks/
        01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests/
        test_ac14_pin_update_command.py`) независимо от наличия свежего
        зелёного прогона.
        """
        stale_sha = self.root_head_sha()
        self.insert_run(stale_sha, "green")
        target = self.merge_commit(
            count=config.CANARY_MAX_MERGES_SINCE_GREEN - 1)

        pin.cmd_pin_update(target)

        self.assertEqual(self.root_head_sha(), target)
        matches = self.steps_mentioning(target[:7], action="pin обновлён")
        self.assertTrue(matches, "журнал обязан получить запись «pin обновлён»")


if __name__ == "__main__":
    import unittest
    unittest.main()
