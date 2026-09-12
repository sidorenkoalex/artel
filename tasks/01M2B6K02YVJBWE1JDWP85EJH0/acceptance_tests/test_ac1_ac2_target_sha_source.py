"""Приёмочные тесты AC-1, AC-2 (SPEC 01M2B6K02YVJBWE1JDWP85EJH0): без
`--sha` целевой sha прогона — голова `origin/<config.MAIN_BRANCH>`, не
`gitcmd.head_sha()` главной копии; с явным `--sha` — именно он, без
обращения к `origin`.

Красен до реализации (3 из 4 тестов): `canary.cmd_canary` сегодня не
принимает параметр `sha` вовсе (`orchestrator/canary.py`, `def
cmd_canary(*, k: int)`) — вызов `canary.cmd_canary(k=1, sha=...)`
падает `TypeError` раньше, чем дойдёт до какого-либо `assert`; это
ловит `test_ac2_explicit_sha_is_used_verbatim`/`..._does_not_require_
origin_remote` напрямую (оба зовут `run_cmd_canary(sha=<явный sha>)`);
`test_ac1_default_target_sha_is_origin_main_head_not_local_pin_head`
красный по другой причине — вызов идёт БЕЗ `sha` (`cmd_canary(k=1)`,
сигнатура сегодня это принимает), но `_run_one_task` пишет `main_sha =
gitcmd.head_sha()` (строка ~1161) безусловно, поэтому записанный
`main_sha` совпадает со старым локальным HEAD, а не с головой
`origin/<MAIN_BRANCH>`, которая в этом сценарии намеренно другая.

Зелёный с рождения (1 из 4): `test_ac1_default_target_sha_matches_
origin_head_when_pin_is_in_sync` не расходится с сегодняшним
поведением — стенд синхронен (`origin/<MAIN_BRANCH>` == локальный
HEAD == HEAD, из которого сегодня берётся `main_sha`), поэтому
`gitcmd.head_sha()` уже сейчас совпадает с ожидаемым значением; тест
остаётся в файле как позитивный образец из формулировки AC-1, не как
дефект «неловящего» теста — расходящийся сценарий той же АС ловится
соседним `test_ac1_default_target_sha_is_origin_main_head_not_local_
pin_head` выше.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import TargetShaCanarySandbox  # noqa: E402


class DefaultTargetShaTest(TargetShaCanarySandbox):

    def test_ac1_default_target_sha_is_origin_main_head_not_local_pin_head(self):
        """`origin/<MAIN_BRANCH>` уходит вперёд локального `main` (главной
        копии/пина) — прогон без `--sha` обязан записать в `canary_runs.
        main_sha` голову `origin/<MAIN_BRANCH>`, а не `gitcmd.head_sha()`
        локального `main`, который в этом сценарии другой sha.

        Ловит мутацию: `main_sha`/целевой sha по-прежнему берётся из
        `gitcmd.head_sha()` главной копии (старое поведение, требование 1)
        — записанный `main_sha` совпал бы со старым локальным HEAD вместо
        головы `origin/<MAIN_BRANCH>`.
        """
        old_local_head = self.head_sha()
        new_origin_head = self.advance_origin_only()
        self.assertNotEqual(old_local_head, new_origin_head)
        self.assertEqual(self.head_sha(), old_local_head,
                         "локальный main не должен был сдвинуться")

        self.run_cmd_canary(sha=None)

        row = self.latest_canary_run()
        self.assertEqual(row["main_sha"], new_origin_head)

    def test_ac1_default_target_sha_matches_origin_head_when_pin_is_in_sync(self):
        """Стенд с bare `origin`, синхронным с локальным main (обычное
        состояние) — целевой sha по умолчанию совпадает с головой
        `origin/<MAIN_BRANCH>` этого стенда (что здесь равно и локальному
        HEAD, раз они синхронны) — образец из формулировки AC-1.

        Ловит мутацию: источник целевого sha — случайный/пустой sha
        (например, забытый `git rev-parse --verify` без реального
        `fetch`) — записанный `main_sha` разошёлся бы с настоящей головой
        `origin/<MAIN_BRANCH>` стенда.
        """
        expected = self.origin_head_sha()

        self.run_cmd_canary(sha=None)

        row = self.latest_canary_run()
        self.assertEqual(row["main_sha"], expected)


class ExplicitTargetShaTest(TargetShaCanarySandbox):

    def test_ac2_explicit_sha_is_used_verbatim(self):
        """`--sha <sha>` с явным sha, отличным и от локального HEAD, и от
        головы `origin/<MAIN_BRANCH>` (предок текущего main — первый
        коммит песочницы) — записанный `main_sha` обязан быть ИМЕННО этим
        явным sha.

        Ловит мутацию: явный `sha` игнорируется, целевой sha всё равно
        вычисляется через `origin`/локальный HEAD — записанный `main_sha`
        не совпал бы с переданным явно значением.
        """
        explicit_sha = self.root_sha
        self.assertNotEqual(explicit_sha, self.head_sha())

        self.run_cmd_canary(sha=explicit_sha)

        row = self.latest_canary_run()
        self.assertEqual(row["main_sha"], explicit_sha)

    def test_ac2_explicit_sha_does_not_require_origin_remote(self):
        """Ни один remote `origin` вообще не заведён (`git remote add
        origin` не вызывался) — прогон с явным `--sha` всё равно обязан
        успешно завершиться и записать этот sha: обращение к `origin`
        (сеть/fetch) для явного `--sha` — requirement 1 запрещает его.

        Ловит мутацию: реализация безусловно зовёт `gitcmd.fetch_ref_sha`/
        `git fetch origin` независимо от того, передан ли явный `--sha` —
        без единого настроенного `origin` эта команда не ответит, и
        прогон упал бы `SystemExit`/subprocess-отказом ещё до checkout,
        вместо того чтобы записать явный sha.
        """
        self.git("remote", "remove", "origin")
        explicit_sha = self.root_sha

        self.run_cmd_canary(sha=explicit_sha)

        row = self.latest_canary_run()
        self.assertEqual(row["main_sha"], explicit_sha)


if __name__ == "__main__":
    import unittest
    unittest.main()
