"""Приёмочные тесты AC-7 задачи 01M1TQ0X14Y5B3C87WC0Q31PK2: `doctor`
несёт проверку «CI артефактной ветки» для нетерминальных задач target
artel — зелёный последний прогон CI ветки `artifact/<id>` (через `gh run
list`, как уже делает `verifying` в `orchestrator/ci.py`) — `ok`;
красный — `warn` с sha и именем упавшей джобы; `gh`/сеть недоступны —
`skip`; проверка информационная и не блокирует ни один гейт (эта часть
критерия — не про доктор-проверку конкретно, помечена отдельно ниже).

Красен до реализации: `orchestrator/doctor.py` сегодня не содержит
функции `check_artifact_branch_ci` — каждый вызов
`doctor.check_artifact_branch_ci(...)` ниже падает `AttributeError` ещё
до какого-либо ассерта.

`gh` не вызывается по-настоящему нигде в тестах (сеть в песочницах
запрещена) — подменяется `orchestrator.ci.gh`, та же точка входа, что уже
использует `orchestrator/ci.py::run_list` (единственная реальная точка
`subprocess`, за которой в проде стоит настоящий `gh`); проверка сама
читает локальный sha артефактной ветки настоящим git (`gitcmd.
branch_head_sha`) — песочница `PultOriginSandbox` заводит ветку
плотницки, без workspace роли.

Последняя часть формулировки критерия («проверка информационная — гейты
не блокирует») — не отдельный AC и не отдельная пометка: она описывает
свойство «эта функция никем не вызывается из кода гейтов», то есть
отсутствие факта, а не наблюдаемое поведение с детерминированным
входом/выходом — доказывается ревью зоны `orchestrator/*.py` на предмет
нового `import doctor`, а не unit-тестом с фикстурой. Наблюдаемая часть
критерия (сама проверка — `ok`/`warn` с sha и джобой/`skip`) покрыта
тестами этого файла полностью.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch, ci, doctor, gitcmd, store  # noqa: E402
from _sandbox import PultOriginSandbox  # noqa: E402

JOB_NAME = "protected-paths"


def _fake_gh(branch: str, payload):
    """`orchestrator.ci.gh` — отвечает на `run list --branch <branch>`
    заготовленным `payload` (список entries `gh run list --json`), на
    любую другую команду/ветку — путём отказа (недоступность gh)."""
    def fake(*args, timeout=None):
        if (len(args) >= 2 and args[0] == "run" and args[1] == "list"
                and "--branch" in args):
            requested = args[args.index("--branch") + 1]
            body = payload if requested == branch else []
            return subprocess.CompletedProcess(list(args), 0,
                                               json.dumps(body), "")
        return subprocess.CompletedProcess(list(args), 1, "",
                                           "gh: неожиданная команда в тесте")
    return fake


def _gh_unavailable(*args, timeout=None):
    return subprocess.CompletedProcess(list(args), 1, "",
                                       "gh: command not found")


class DoctorArtifactBranchCiTest(PultOriginSandbox):

    def setUp(self):
        super().setUp()
        self.TASK = "01ACDOCTORCIOKKKKK1"
        self.branch = self.new_artel_task(self.TASK)
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/SPEC.md": "спека\n"},
            f"{self.TASK}: спека")
        self.sha = gitcmd.branch_head_sha(self.branch)
        self.assertTrue(self.sha)

    def checks(self):
        return doctor.check_artifact_branch_ci(store.db())

    def test_ac7_ok_when_the_last_run_is_green(self):
        """Последний прогон CI ветки `artifact/<id>` зелёный
        (`status=completed`, `conclusion=success`) — проверка обязана
        дать `ok`.

        Ловит мутацию: проверка засчитывает `ok` без реальной сверки
        `conclusion` (например, по одному факту, что `gh run list`
        ответил без ошибки) — тест ниже (`test_ac7_warn_when_red`) с
        тем же самым «ответ есть» поймал бы такую мутацию по неверному
        статусу; здесь фиксируется положительный эталон, симметрично."""
        payload = [{"headBranch": self.branch, "status": "completed",
                   "conclusion": "success", "name": JOB_NAME,
                   "workflowName": JOB_NAME}]
        with mock.patch.object(ci, "gh", _fake_gh(self.branch, payload)):
            checks = self.checks()

        mine = [c for c in checks if self.TASK in c.detail]
        self.assertTrue(mine, checks)
        self.assertTrue(all(c.status == "ok" for c in mine), checks)

    def test_ac7_warn_when_the_last_run_is_red_names_sha_and_job(self):
        """Последний прогон CI ветки `artifact/<id>` красный — проверка
        обязана дать `warn`, называющий sha ветки и имя упавшей джобы.

        Ловит мутацию: `warn` формируется без имени джобы (только факт
        «CI красный») — тест краснеет на `assertIn(JOB_NAME, ...)`;
        мутация «sha не назван» — на соседнем `assertIn(self.sha, ...)`.
        """
        payload = [{"headBranch": self.branch, "status": "completed",
                   "conclusion": "failure", "name": JOB_NAME,
                   "workflowName": JOB_NAME, "displayTitle": JOB_NAME}]
        with mock.patch.object(ci, "gh", _fake_gh(self.branch, payload)):
            checks = self.checks()

        warn = [c for c in checks if c.status == "warn" and self.TASK in c.detail]
        self.assertEqual(len(warn), 1, checks)
        self.assertIn(self.sha, warn[0].detail)
        self.assertIn(JOB_NAME, warn[0].detail)

    def test_ac7_skip_when_gh_is_unavailable(self):
        """`gh`/сеть недоступны — проверка обязана дать `skip`, не
        засчитывать зелёный/красный по несуществующему ответу.

        Ловит мутацию: недоступность `gh` трактуется как «зелёный по
        умолчанию» (fail-open) — тест краснеет на проверке статуса,
        символизируя ровно тот способ, каким красный CI мог бы остаться
        незамеченным (инцидент 06.09, «CI... был красный... и это ни на
        что не повлияло»/QUESTIONS «gh не ответил»)."""
        with mock.patch.object(ci, "gh", _gh_unavailable):
            checks = self.checks()

        mine = [c for c in checks if self.TASK in c.detail]
        self.assertTrue(mine, checks)
        self.assertTrue(all(c.status == "skip" for c in mine), checks)
        self.assertTrue(all(c.detail.strip() for c in mine), checks)

    def test_ac7_excludes_terminal_and_non_artel_target_tasks(self):
        """Задача в терминальном состоянии (`killed`) и задача другого
        target — обе с красным CI по данным `gh` — не имеют права
        породить `warn`: проверка касается только нетерминальных задач
        target artel.

        Ловит мутацию: фильтр по состоянию/target снят или неполон —
        тогда среди `checks()` найдётся `warn`, упоминающий id одной из
        исключённых задач."""
        killed_id = "01ACDOCTORCIKILLED1"
        killed_branch = self.new_artel_task(killed_id, state="killed")
        artifact_branch.commit_files(
            killed_id, {f"tasks/{killed_id}/SPEC.md": "спека\n"},
            f"{killed_id}: спека")

        external_id = "01ACDOCTORCIEXTERN1"
        self.new_external_task(external_id)
        external_branch = artifact_branch.branch_name(external_id)
        artifact_branch.commit_files(
            external_id, {f"tasks/{external_id}/SPEC.md": "спека\n"},
            f"{external_id}: спека")

        payload = [{"headBranch": self.branch, "status": "completed",
                   "conclusion": "failure", "name": JOB_NAME}]

        def fake(*args, timeout=None):
            if (len(args) >= 2 and args[0] == "run" and args[1] == "list"
                    and "--branch" in args):
                requested = args[args.index("--branch") + 1]
                if requested in (killed_branch, external_branch):
                    body = payload
                else:
                    body = []
                return subprocess.CompletedProcess(list(args), 0,
                                                   json.dumps(body), "")
            return subprocess.CompletedProcess(list(args), 1, "", "нет gh")

        with mock.patch.object(ci, "gh", fake):
            checks = self.checks()

        offending = [c for c in checks
                    if c.status != "ok"
                    and (killed_id in c.detail or external_id in c.detail)]
        self.assertEqual(offending, [],
                         f"терминальная/чужого target задача не должна "
                         f"порождать предупреждение: {checks}")


if __name__ == "__main__":
    unittest.main()
