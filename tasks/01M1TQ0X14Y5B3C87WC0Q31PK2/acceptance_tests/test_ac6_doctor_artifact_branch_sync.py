"""Приёмочные тесты AC-6 задачи 01M1TQ0X14Y5B3C87WC0Q31PK2: `doctor`
несёт проверку «артефактная ветка синхронна» для нетерминальных задач
target artel — сравнивает локальный `artifact/<id>` и
`origin/artifact/<id>`; `ok` при совпадении; `warn` с обоими sha и
направлением расхождения (локальный отстаёт / origin отстаёт /
разошлись) при несовпадении; `skip` с причиной, если origin недоступен.

Красен до реализации: `orchestrator/doctor.py` сегодня не содержит
функции `check_artifact_branch_sync` вовсе (`grep` по модулю — SPEC
относит эту проверку к требованию 3/новой зоне `doctor.py` этой же
задачи) — каждый вызов `doctor.check_artifact_branch_sync(...)` ниже
падает `AttributeError` ещё до какого-либо ассерта.

Песочница — `PultOriginSandbox` (`_sandbox.py` рядом): задачи заводятся
напрямую через `new_artel_task` (target `config.DEFAULT_TARGET`, без
рабочего каталога — проверка читает только git-ветки), артефактная ветка
— плотницкой записью `artifact_branch.commit_files` (не через
чекпоинт — предмет проверки здесь только сверка sha, не автокоммит).
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch, doctor, gitcmd, store  # noqa: E402
from _sandbox import PultOriginSandbox  # noqa: E402


class DoctorArtifactBranchSyncTest(PultOriginSandbox):

    def setUp(self):
        super().setUp()
        self.add_origin()

    def commit(self, task_id: str, text: str) -> str:
        return artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/SPEC.md": text},
            f"{task_id}: правка")

    def push(self, task_id: str) -> None:
        branch = artifact_branch.branch_name(task_id)
        self.git("push", "-q", "-f", "origin",
                 f"refs/heads/{branch}:refs/heads/{branch}")

    def checks(self):
        return doctor.check_artifact_branch_sync(store.db())

    def test_ac6_ok_when_local_and_origin_match(self):
        """Локальный `artifact/<id>` и `origin/artifact/<id>` совпадают —
        проверка обязана дать `ok`, без единого `warn`/`fail` по этой
        задаче.

        Ловит мутацию: проверка сравнивает НЕ ТЕ ветки (например, только
        факт существования `artifact/<id>` на origin, без сверки sha) —
        тогда синхронный случай ничем не отличался бы от расхождения,
        соседний тест ниже (`test_ac6_warn_local_behind`) поймал бы это,
        а этот тест страховал бы от обратной мутации «всегда warn»."""
        task_id = "01ACDOCTORSYNCOK0001"
        branch = self.new_artel_task(task_id)
        self.commit(task_id, "спека\n")
        self.push(task_id)

        checks = self.checks()
        mine = [c for c in checks if task_id in c.detail]
        self.assertTrue(mine, f"нет ни одной записи про {task_id}: {checks}")
        self.assertTrue(all(c.status == "ok" for c in mine), checks)

    def test_ac6_warn_when_origin_is_ahead_of_the_local_ref(self):
        """Origin ушёл вперёд локального ref (Оператор коммитил прямо в
        origin, как в инциденте 06.09) — проверка обязана дать `warn` с
        обоими sha и направлением «локальный отстаёт».

        Ловит мутацию: направление расхождения перепутано местами
        («origin отстаёт» вместо «локальный отстаёт») — тест краснеет на
        `assertIn("локальный отстаёт", ...)`."""
        task_id = "01ACDOCTORSYNCLBHD01"
        branch = self.new_artel_task(task_id)
        self.commit(task_id, "спека v1\n")
        self.push(task_id)
        self.push_external_commit(
            task_id, f"tasks/{task_id}/EXTERNAL.md", "внешний коммит\n")

        local_sha = gitcmd.branch_head_sha(branch)
        origin_sha = self.origin_branch_sha(branch)
        self.assertNotEqual(local_sha, origin_sha)

        warn = [c for c in self.checks()
               if c.status == "warn" and task_id in c.detail]
        self.assertEqual(len(warn), 1, self.checks())
        self.assertIn(local_sha, warn[0].detail)
        self.assertIn(origin_sha, warn[0].detail)
        self.assertIn("локальный отстаёт", warn[0].detail)

    def test_ac6_warn_when_the_local_ref_is_ahead_of_origin(self):
        """Локальный ref ушёл вперёд origin (роль закоммитила, push ещё
        не случился/отказал) — проверка обязана дать `warn` с обоими sha
        и направлением «origin отстаёт».

        Ловит мутацию: то же перепутанное направление, что и в тесте
        выше, только в другую сторону — если оба теста проходят
        одновременно с одинаковым (неверным) направлением, только один
        из двух покраснеет."""
        task_id = "01ACDOCTORSYNCOBHD01"
        branch = self.new_artel_task(task_id)
        self.commit(task_id, "спека v1\n")
        self.push(task_id)
        self.commit(task_id, "спека v2, не запушена\n")

        local_sha = gitcmd.branch_head_sha(branch)
        origin_sha = self.origin_branch_sha(branch)
        self.assertNotEqual(local_sha, origin_sha)

        warn = [c for c in self.checks()
               if c.status == "warn" and task_id in c.detail]
        self.assertEqual(len(warn), 1, self.checks())
        self.assertIn(local_sha, warn[0].detail)
        self.assertIn(origin_sha, warn[0].detail)
        self.assertIn("origin отстаёт", warn[0].detail)

    def test_ac6_warn_when_local_and_origin_diverged_in_different_directions(self):
        """Локальный ref и origin разошлись КАЖДЫЙ своим коммитом от
        общего предка (ни один не является предком другого) — проверка
        обязана дать `warn` с направлением «разошлись», не спутав его ни
        с «локальный отстаёт», ни с «origin отстаёт».

        Ловит мутацию: сверка расхождения смотрит только на неравенство
        sha и всегда называет одно из двух однонаправленных состояний —
        третий, действительно двусторонний случай, останется
        неотличимым, тест поймает это по отсутствию слова «разошлись»."""
        task_id = "01ACDOCTORSYNCDIVR01"
        branch = self.new_artel_task(task_id)
        self.commit(task_id, "спека v1\n")
        self.push(task_id)
        self.push_external_commit(
            task_id, f"tasks/{task_id}/EXTERNAL.md", "внешний коммит\n")
        self.commit(task_id, "локальная правка, не запушена\n")

        local_sha = gitcmd.branch_head_sha(branch)
        origin_sha = self.origin_branch_sha(branch)
        self.assertNotEqual(local_sha, origin_sha)

        warn = [c for c in self.checks()
               if c.status == "warn" and task_id in c.detail]
        self.assertEqual(len(warn), 1, self.checks())
        self.assertIn(local_sha, warn[0].detail)
        self.assertIn(origin_sha, warn[0].detail)
        self.assertIn("разошлись", warn[0].detail)

    def test_ac6_skip_without_origin_with_a_reason(self):
        """Origin пульта недоступен вовсе (не настроен) — проверка
        обязана дать `skip` с непустой причиной, не молча пропасть и не
        отрапортовать `ok`/`warn` по несуществующим данным.

        Ловит мутацию: недоступность origin трактуется как «совпадает» и
        засчитывается `ok` (fail-open вместо честного `skip`) — тест
        краснеет на проверке статуса."""
        self.git("remote", "remove", "origin")
        task_id = "01ACDOCTORSYNCSKIP01"
        self.new_artel_task(task_id)
        self.commit(task_id, "спека\n")

        checks = self.checks()
        self.assertTrue(checks)
        self.assertTrue(all(c.status == "skip" for c in checks), checks)
        self.assertTrue(all(c.detail.strip() for c in checks), checks)

    def test_ac6_excludes_terminal_and_non_artel_target_tasks(self):
        """Задача в терминальном состоянии (`done`) и задача другого
        target — обе с настоящим расхождением веток — не имеют права
        породить `warn`: проверка касается только НЕТЕРМИНАЛЬНЫХ задач
        target artel (требование 3).

        Ловит мутацию: фильтр по состоянию/target снят или неполон
        (например, отфильтрован только `killed`, но не `done`, либо
        target не проверяется вовсе) — тогда среди `checks()` найдётся
        `warn`, упоминающий id одной из исключённых задач."""
        done_id = "01ACDOCTORSYNCDONE01"
        self.new_artel_task(done_id, state="done")
        self.commit(done_id, "спека v1\n")
        self.push(done_id)
        self.push_external_commit(
            done_id, f"tasks/{done_id}/EXTERNAL.md", "внешний коммит\n")

        external_id = "01ACDOCTORSYNCEXT01"
        self.new_external_task(external_id)
        self.commit(external_id, "спека v1\n")
        self.push(external_id)
        self.push_external_commit(
            external_id, f"tasks/{external_id}/EXTERNAL.md", "внешний коммит\n")

        checks = self.checks()
        offending = [c for c in checks
                    if c.status != "ok"
                    and (done_id in c.detail or external_id in c.detail)]
        self.assertEqual(offending, [],
                         f"терминальная/чужого target задача не должна "
                         f"порождать предупреждение: {checks}")


if __name__ == "__main__":
    unittest.main()
