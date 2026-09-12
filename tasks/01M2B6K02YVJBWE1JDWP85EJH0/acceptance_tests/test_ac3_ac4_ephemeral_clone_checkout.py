"""Приёмочные тесты AC-3, AC-4 (SPEC 01M2B6K02YVJBWE1JDWP85EJH0):
эфемерный клон прогона делает checkout целевого sha (по умолчанию или
из `--sha`), и запись `canary_runs.main_sha` несёт именно этот целевой
sha, а не `gitcmd.head_sha()` главной копии, когда они расходятся.

Красен до реализации: `canary._run_one_task` сегодня клонирует `outer_
root` и ведёт задачу на его текущем HEAD (никакого `git checkout
<target_sha>` внутри `_ephemeral_clone`/`_run_one_task` нет) и пишет
`main_sha = gitcmd.head_sha()` главной копии безусловно — оба
`assert`'а ниже сравнивают с явно ДРУГИМ (предковым) sha, поэтому
падают на текущем коде.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import TargetShaCanarySandbox  # noqa: E402


class EphemeralCloneChecksOutTargetShaTest(TargetShaCanarySandbox):

    def _explicit_ancestor_sha(self) -> str:
        return self.root_sha

    def test_ac3_clone_checkout_matches_explicit_sha_diverging_from_local_head(self):
        """`--sha` явно отличается от HEAD главной копии (предок текущего
        main) — checkout эфемерного клона В МОМЕНТ вождения задачи
        обязан стоять именно на этом sha, не на HEAD, который получил бы
        обычный `git clone` без явного checkout.

        Ловит мутацию: `_ephemeral_clone`/`_run_one_task` клонирует
        `outer_root` и НЕ делает `git checkout <target_sha>` внутри
        клона — checkout остался бы на HEAD главной копии независимо от
        переданного `--sha` (эта же мутация — «клон остаётся на HEAD
        главной копии вместо целевого sha» — прямо названа в AC-4).
        """
        explicit_sha = self._explicit_ancestor_sha()
        local_head = self.head_sha()
        self.assertNotEqual(explicit_sha, local_head)

        _out, captured = self.run_cmd_canary(sha=explicit_sha,
                                             capture_clone_head=True)

        self.assertEqual(captured["clone_head"], explicit_sha)

    def test_ac4_canary_run_main_sha_is_target_sha_not_local_pin_head(self):
        """Тот же расходящийся `--sha` — запись `canary_runs.main_sha`
        обязана нести именно целевой sha, а не `gitcmd.head_sha()`
        главной копии.

        Ловит мутацию: `main_sha` в `store.insert_canary_run` по-прежнему
        читает `gitcmd.head_sha()` (снятый ПОСЛЕ выхода из клона — HEAD
        главной копии) вместо переменной, хранящей целевой sha прогона —
        записанный `main_sha` совпал бы с локальным HEAD вместо явного
        `--sha`.
        """
        explicit_sha = self._explicit_ancestor_sha()
        local_head = self.head_sha()
        self.assertNotEqual(explicit_sha, local_head)

        self.run_cmd_canary(sha=explicit_sha)

        row = self.latest_canary_run()
        self.assertEqual(row["main_sha"], explicit_sha)
        self.assertNotEqual(row["main_sha"], local_head)

if __name__ == "__main__":
    import unittest
    unittest.main()
