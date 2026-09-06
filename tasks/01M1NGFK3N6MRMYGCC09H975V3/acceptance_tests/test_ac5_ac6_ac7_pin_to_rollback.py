"""AC-5, AC-6, AC-7 (tasks/01M1NGFK3N6MRMYGCC09H975V3/SPEC.md): откат
пина `pin --to <sha>` / `pin --to` (без аргумента — на sha последнего
зелёного прогона канарейки) и журналирование каждого вызова.

Контракт — ANSWER-1 (Оператор, ответ на эскалацию этой задачи), п.5:
функция `orchestrator/pin.py::cmd_pin_to(sha: str | None)`. `<sha>`
обязан существовать и быть предком текущего HEAD (`git reset --hard
<sha>` в `config.ROOT`; main пульта на origin НЕ трогается — ни `fetch`,
ни `push`). Без `<sha>` — цель — `main_sha` самого свежего зелёного
прогона ПО `created_at`; отказы: «pin --to: в журнале нет зелёного
прогона канарейки» (нет ни одного зелёного) и «pin --to: пин уже на sha
последнего зелёного прогона» (цель совпадает с текущим HEAD). Журнал
(AC-7, п.5): `store.journal` с `task_id=config.PIN_UPDATE_JOURNAL_
TASK_ID`, actor=`operator`; успех — действие «pin откатан», detail «pin
откатан: <старый> -> <новый>; причина: ...»; любой отказ — действие «pin
откат отклонён», HEAD не меняется; каждый вызов — ровно одна запись.

Красен до реализации: `orchestrator.pin` сегодня не несёт `cmd_pin_to` —
`AttributeError` на первом же вызове в каждом тесте этого файла.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import pin  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import CanaryPinSandbox  # noqa: E402


class PinToExplicitShaTest(CanaryPinSandbox):

    def test_ac5_pin_to_explicit_sha_resets_root_and_leaves_main_untouched(self):
        """`pin --to <sha>`, `<sha>` — предок текущего HEAD (sha до серии
        последующих мержей): HEAD `config.ROOT` откатывается именно на
        него, main пульта на origin не меняется (ни `fetch`, ни `push`).

        Ловит мутацию: `git reset --hard` перепутан направлением/целью
        (например, применяется к origin вместо локального ROOT), либо
        реализация попутно зовёт `fetch`/`push` — `origin_main_sha`
        изменился бы, хотя контракт это прямо запрещает.
        """
        old_sha = self.root_head_sha()
        self.merge_commit(count=2)
        origin_before = self.origin_main_sha()

        pin.cmd_pin_to(old_sha)

        self.assertEqual(self.root_head_sha(), old_sha)
        self.assertEqual(self.origin_main_sha(), origin_before)

    def test_ac5_pin_to_explicit_non_ancestor_sha_is_refused(self):
        """`<sha>` из ветки, никогда не смерженной в main, — не предок
        текущего HEAD: контракт требует «обязан быть предком» — команда
        обязана отказать именованно (`SystemExit`), не выполнять `reset
        --hard` на произвольную несвязанную историю.

        Ловит мутацию: отсутствие проверки предка — `reset --hard`
        применяется к любому существующему sha независимо от того, лежит
        ли он вообще в истории main.
        """
        abandoned_sha = self.branch_off_without_merging()
        before = self.root_head_sha()

        with self.assertRaises(SystemExit):
            pin.cmd_pin_to(abandoned_sha)

        self.assertEqual(self.root_head_sha(), before)


class PinToDefaultTest(CanaryPinSandbox):

    def test_ac6_pin_to_default_targets_latest_green_run_ignoring_red_and_older_green(self):
        """Журнал несёт: старый зелёный прогон, затем более свежий
        КРАСНЫЙ, затем ещё более свежий зелёный — `pin --to` без
        аргумента обязан откатить пин именно на `main_sha` последнего из
        них ЗЕЛЁНОГО, не на самый свежий по журналу вообще и не на первый
        зелёный.

        Ловит мутацию: выбор «последней записи журнала» без фильтра по
        verdict — красный прогон, будучи самым свежим по времени, ложно
        стал бы целью отката.
        """
        old_green = self.root_head_sha()
        self.insert_run(old_green, "green", created_at="2026-01-01 00:00:00Z")
        red_sha = self.merge_commit(count=1)
        self.insert_run(red_sha, "red", created_at="2026-01-02 00:00:00Z")
        latest_green = self.merge_commit(count=1)
        self.insert_run(latest_green, "green", created_at="2026-01-03 00:00:00Z")
        self.merge_commit(count=1)  # HEAD уходит дальше latest_green

        pin.cmd_pin_to(None)

        self.assertEqual(self.root_head_sha(), latest_green)

    def test_ac6_pin_to_default_refuses_when_no_green_run_exists(self):
        """Журнал несёт только красный прогон (зелёного нет ни одного) —
        `pin --to` без аргумента отказывает именованным сообщением «pin
        --to: в журнале нет зелёного прогона канарейки», HEAD не
        двигается.

        Ловит мутацию: при отсутствии зелёного прогона команда откатывает
        на sha ЛЮБОГО (в т.ч. красного) прогона вместо явного отказа.
        """
        red_sha = self.root_head_sha()
        self.insert_run(red_sha, "red")
        self.merge_commit(count=1)
        before = self.root_head_sha()

        with self.assertRaises(SystemExit) as cm:
            pin.cmd_pin_to(None)

        self.assertTrue(str(cm.exception).startswith(
            "pin --to: в журнале нет зелёного прогона канарейки"))
        self.assertEqual(self.root_head_sha(), before)

    def test_ac6_pin_to_default_refuses_when_already_at_latest_green_sha(self):
        """Последний зелёный прогон записан НА ТЕКУЩЕМ HEAD (пин уже там,
        куда откат бы направил) — `pin --to` без аргумента отказывает
        именованным сообщением «pin --to: пин уже на sha последнего
        зелёного прогона», HEAD не двигается.

        Ловит мутацию: команда всё равно выполняет `reset --hard` на тот
        же sha, что уже под HEAD, вместо явного отказа «нечего
        откатывать».
        """
        current = self.root_head_sha()
        self.insert_run(current, "green")

        with self.assertRaises(SystemExit) as cm:
            pin.cmd_pin_to(None)

        self.assertTrue(str(cm.exception).startswith(
            "pin --to: пин уже на sha последнего зелёного прогона"))
        self.assertEqual(self.root_head_sha(), current)


class PinToJournalTest(CanaryPinSandbox):

    def test_ac7_explicit_sha_success_journals_old_and_new_sha_with_reason(self):
        """Успешный `pin --to <sha>` пишет журнальную запись
        (`task_id=config.PIN_UPDATE_JOURNAL_TASK_ID`, actor=`operator`,
        действие «pin откатан») с прежним и новым sha и явной причиной
        отката.

        Ловит мутацию: HEAD откатывается, но вызов не журналируется —
        `steps_mentioning` не найдёт ни одной подходящей строки.
        """
        old_sha = self.root_head_sha()
        head_before_rollback = self.merge_commit(count=1)

        pin.cmd_pin_to(old_sha)

        matches = self.steps_mentioning(
            old_sha[:7], head_before_rollback[:7], "причина",
            action="pin откатан")
        self.assertTrue(matches, "ожидалась журнальная запись отката с обоими sha")
        self.assertEqual(matches[0]["actor"], "operator")

    def test_ac7_default_success_journals_run_stamp_as_reason(self):
        """Успешный `pin --to` без аргумента журналирует причину, ссылаясь
        на конкретный `run_stamp` того зелёного прогона, sha которого стал
        новым пином.

        Ловит мутацию: причина отката не называет прогон-источник цели
        (например, только голые sha без ссылки на журнал канарейки) —
        Оператор не смог бы проверить, ПОЧЕМУ откат ушёл именно туда.
        """
        green_sha = self.root_head_sha()
        run_stamp = self.insert_run(green_sha, "green")
        self.merge_commit(count=1)

        pin.cmd_pin_to(None)

        matches = self.steps_mentioning(run_stamp, action="pin откатан")
        self.assertTrue(
            matches, f"причина отката обязана называть run_stamp {run_stamp}")

    def test_ac7_refusal_also_journals_rejection_without_moving_head(self):
        """Отказ `pin --to` (журнал без единого зелёного прогона) тоже
        получает запись журнала — действие «pin откат отклонён», HEAD
        `config.ROOT` при этом не двигается.

        Ловит мутацию: отказ завершается `sys.exit` раньше, чем успевает
        отжурналировать причину, — Оператор терял бы след неудачной
        попытки отката (AC-7 требует запись на КАЖДЫЙ вызов, не только на
        успешный).
        """
        before = self.root_head_sha()

        with self.assertRaises(SystemExit):
            pin.cmd_pin_to(None)

        matches = self.steps_mentioning(action="pin откат отклонён")
        self.assertTrue(matches, "отказ обязан журналироваться отдельным действием")
        self.assertEqual(self.root_head_sha(), before)


if __name__ == "__main__":
    import unittest
    unittest.main()
