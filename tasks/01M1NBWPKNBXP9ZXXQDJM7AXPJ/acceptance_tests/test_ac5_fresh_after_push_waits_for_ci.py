"""AC-5 (tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md): Гейт `merge_gate`
после push головы ветки задачи в origin — включая случай, когда
`approve` этим же вызовом впервые публикует голову в origin
(`github_adapter.ensure_head_in_origin`) — ждёт появления и завершения
проверок CI тем же циклом (`_wait_for_branch_ci_green`), что и путь
«pulled», вместо немедленного отказа по статусу «нет ни одной
проверки».

Источник — tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md, «Критерии
приёмки», AC-5.

Красен до реализации: `_cmd_approve_merge_gate` на пути `"fresh"`
опрашивает `ci.branch_status` РОВНО один раз и, увидев не-красный,
не-зелёный статус («нет ни одной проверки CI — статус неизвестен»),
немедленно `sys.exit`'ит («merge отклонён: ...») — до второго опроса и
до контрольной точки `_origin_main_sha` (замоканной здесь на `None`
намеренно — см. докстринг теста) исполнение не доходит вовсе.
Проверено прогоном на немодифицированном коде при подготовке файла:
`SystemExit` с текстом «нет ни одной проверки», `ci.branch_status`
вызван 1 раз, `_origin_main_sha` не достигнута.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import GREEN, NOCHECKS, MergeGateFreshCiWaitSandbox  # noqa: E402


class Ac5FreshAfterPushWaitsForCiTest(MergeGateFreshCiWaitSandbox):

    def test_ac5_no_checks_yet_then_green_eventually_proceeds_past_wait(self):
        """CI ещё не появился на только что запушенной голове (первые
        два опроса — «нет ни одной проверки»), затем зеленеет. Гейт
        обязан дождаться зелёного тем же циклом, что и путь «pulled»,
        не отказать по первому ответу — контрольная точка ниже по телу
        гейта (`_origin_main_sha`, замокана на `None`) достигается,
        только если ожидание довело дело до зелёного статуса и передало
        управление дальше.

        Ловит мутацию: код, который на пути "fresh" опрашивает CI один
        раз и `sys.exit`'ит на первом не-зелёном ответе (сегодняшнее
        поведение) — тест не увидит второго/третьего вызова
        `ci.branch_status` и не долетит до контрольной точки
        `_origin_main_sha`; вместо этого `SystemExit` поднимется с
        текстом «нет ни одной проверки», не с «git fetch origin».
        """
        responses = [NOCHECKS, NOCHECKS, GREEN]
        calls = {"n": 0}

        def sequenced(branch):
            resp = responses[min(calls["n"], len(responses) - 1)]
            calls["n"] += 1
            return resp

        self.patch_branch_status(sequenced)
        self.patch_origin_main_sha(lambda: None)

        with self.assertRaises(SystemExit) as exit_:
            self.run_cycle()

        self.assertIn(
            "fetch origin", str(exit_.exception).lower(),
            f"ожидалась контрольная точка ПОСЛЕ успешного ожидания CI "
            f"(_origin_main_sha), получено: {exit_.exception}")
        self.assertGreaterEqual(
            calls["n"], 2,
            "гейт обязан опросить CI больше одного раза — ждать циклом, "
            "а не отказывать по первому статусу")
        self.assertGreaterEqual(
            self.ensure_head_in_origin.call_count, 1,
            "AC-5 явно включает случай, когда approve публикует голову "
            "в origin этим же вызовом (github_adapter.ensure_head_in_origin)")


if __name__ == "__main__":
    import unittest
    unittest.main()
