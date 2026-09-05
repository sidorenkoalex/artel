"""AC-6 (tasks/01M1REVP9WGRHDDNVEVE8BBH0Z/SPEC.md): «Если `git ls-remote
--heads origin 'artifact/*'` не отвечает или возвращает ошибку, `doctor
--fix` не удаляет ни одной ветки и сообщает FAIL с именованной причиной
(«origin недоступен» или аналогичной, отличимой от прочих FAIL).»

`origin` указывает на несуществующий локальный путь (`_sandbox.
make_origin_unreachable`) — настоящий отказ git (`fatal: ... does not
appear to be a git repository`), не сеть и не заглушка: единственный
способ добросовестно проверить требование «принцип целостности» —
недоступность origin обязана остановить уборку целиком, а заглушка
`gitcmd.git`, отвечающая фиксированным провалом на ЛЮБУЮ команду,
остановила бы её тоже, но не доказала бы, что остановил именно ОТКАЗ
СВЕРКИ С ORIGIN, а не что-то иное.

Красен до реализации: сегодня `sweep_orphan_artifact_branches` не знает
об origin вовсе — недоступность origin (несуществующий remote-путь) не
мешает существующему коду посчитать `artifact/t777` сиротой по старому
критерию (только БД) и удалить её; тест ожидает обратное.
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, doctor, store  # noqa: E402

from _sandbox import ArtifactOriginSandbox  # noqa: E402


class Ac6OriginUnavailableBlocksFixTest(ArtifactOriginSandbox):

    def test_ac6_unreachable_origin_blocks_deletion_with_a_distinct_fail(self):
        """origin недоступен: ни одна ветка не удалена, вывод содержит
        FAIL с упоминанием origin/недоступности, incident уборки не
        заведён, процесс завершается ненулевым кодом.

        Ловит мутацию: `sweep_orphan_artifact_branches` трактует
        неответивший `git ls-remote` как «на origin ничего нет» (тот же
        приём вырождения, что и не глядя на `res is None` — как у
        `gitcmd.list_branches`/`remote_branch_sha`, где ЭТО корректно, но
        здесь означало бы считать сиротой ЛЮБУЮ локальную ветку) — тогда
        `artifact/t777` была бы удалена как «сирота», хотя на самом деле
        критерий просто не вычислим.
        """
        self.local_only_artifact_branch("t777")
        self.make_origin_unreachable()

        buf = io.StringIO()
        with mock.patch.object(doctor, "all_checks", lambda conn: []):
            with self.assertRaises(SystemExit) as cm:
                with redirect_stdout(buf):
                    doctor.cmd_doctor(fix=True)
        out = buf.getvalue()

        self.assertEqual(cm.exception.code, 1)
        self.assertIn("[FAIL]", out)
        self.assertIn("origin", out)
        self.assertIn("недоступ", out)
        self.assertTrue(
            self.branch_exists_locally("artifact/t777"),
            "origin недоступен — уборка не должна была тронуть ни одну ветку")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == doctor.ORPHAN_ARTIFACT_BRANCH_SOURCE]
        self.assertEqual(incidents, [],
                         "уборка не выполнялась вовсе — заводить incident не о чем")


if __name__ == "__main__":
    unittest.main()
