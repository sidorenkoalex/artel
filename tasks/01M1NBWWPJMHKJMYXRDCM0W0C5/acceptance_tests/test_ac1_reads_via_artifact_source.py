"""AC-1 (SPEC): `_autogate_conditions` определяет наличие
`acceptance_tests/*.py` и разбирает AC-пометки (manual/skip/escalate)
через источник артефактов задачи (`artifact_source.resolve` +
`gitcmd.ls_tree_files`/`gitcmd.show`), не через путь на диске рабочей
копии (`acc_tdir`).

Красен до реализации: сегодняшний код (`orchestrator/fsm_autogate.py`,
`_autogate_conditions`) читает `acc_tdir.glob("*.py")`/
`guard.scan_acceptance_tests(acc_tdir)` — путь на диске, не ветку.
`test_ac1_disk_manual_marker_is_ignored...` покраснеет именно потому,
что до правки кода функция видит manual-маркер ДИСКА (реализация ещё
не переключилась на ветку); `test_ac1_ls_tree_and_show_are_called...`
покраснеет потому, что до правки `gitcmd.ls_tree_files`/`gitcmd.show`
не вызываются вовсе (функция даже не пытается читать ветку) — оба по
причине, названной в критерии, не по случайной.

Провалидировано временным стабом (см. `test-authoring`, обязательная
самопроверка): реализация, которая внутри `_autogate_conditions`
резолвит `branch, _ = artifact_source.resolve(conn, task_id)` и читает
маркеры через `gitcmd.ls_tree_files(branch, ...)` +
`gitcmd.show(branch, ...)` + `guard.scan_ac_content(sources)` вместо
`guard.scan_acceptance_tests(acc_tdir)`, зеленит оба теста файла.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateBranchSandbox, CLEAN_PLANKA, MANUAL_PLANKA  # noqa: E402
from orchestrator import artifact_source, gitcmd  # noqa: E402


class AutogateReadsViaArtifactSourceTest(AutogateBranchSandbox):

    def test_ac1_disk_manual_marker_is_ignored_when_branch_planka_is_clean(self):
        """Диск (`acc_tdir`) несёт планку с manual-критерием, артефактная
        ветка — чистую (без manual/skip); автогейт обязан решать по
        ВЕТКЕ, не по диску.

        Ловит мутацию: если `_autogate_conditions` останется на старом
        чтении `guard.scan_acceptance_tests(acc_tdir)` (диск), он увидит
        manual-маркер диска и откажет условие «а», хотя реальная планка
        задачи (в ветке) чистая — `reason` перестанет быть `None`.
        """
        acc_tdir = self.stale_disk_dir()
        acc_tdir_tests = acc_tdir / "acceptance_tests"
        acc_tdir_tests.mkdir(parents=True)
        (acc_tdir_tests / "test_disk_marker.py").write_text(
            MANUAL_PLANKA, encoding="utf-8")
        self.seed_planka(CLEAN_PLANKA)

        ok, reason = self.conditions(acc_tdir=acc_tdir)

        self.assertIsNone(
            reason,
            f"диск нёс manual-маркер, но планка ВЕТКИ чистая — автогейт "
            f"обязан пройти условие «а» по ветке: {reason!r}")
        self.assertIn("0 manual, 0 skip критериев", "; ".join(ok))

    def test_ac1_ls_tree_and_show_are_called_with_the_artifact_branch(self):
        """`_autogate_conditions` обращается к ветке через
        `artifact_source.resolve` + `gitcmd.ls_tree_files`/`gitcmd.show`
        — диск (`acc_tdir`) в этом тесте указывает на несуществующий
        каталог, так что чтение с диска сразу провалилось бы молча
        (пустой каталог), а не совпало бы с ожидаемым «условие а
        пройдено» случайно.

        Ловит мутацию: если разработчик уберёт вызов
        `artifact_source.resolve`/`gitcmd.ls_tree_files`/`gitcmd.show` и
        оставит чтение `acc_tdir` с диска — оба спая ниже останутся
        незваны, `assert_called()` упадёт.
        """
        self.seed_planka(CLEAN_PLANKA)
        missing_disk_dir = self.root / "нет-такого-каталога"

        with mock.patch.object(artifact_source, "resolve",
                               wraps=artifact_source.resolve) as resolve_spy, \
             mock.patch.object(gitcmd, "ls_tree_files",
                               wraps=gitcmd.ls_tree_files) as ls_spy, \
             mock.patch.object(gitcmd, "show",
                               wraps=gitcmd.show) as show_spy:
            ok, reason = self.conditions(acc_tdir=missing_disk_dir)

        self.assertIsNone(reason, reason)
        resolve_spy.assert_called()
        self.assertEqual(resolve_spy.call_args.args[-1], self.TASK)
        ls_spy.assert_called()
        for call in ls_spy.call_args_list:
            self.assertEqual(call.args[0], self.artifact_branch)
        show_spy.assert_called()
        for call in show_spy.call_args_list:
            self.assertEqual(call.args[0], self.artifact_branch)


if __name__ == "__main__":
    unittest.main()
