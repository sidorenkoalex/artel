"""AC-4 (tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md): «Служебное действие
пульта, вызванное явно Оператором, удаляет ветки artifact/<id>, для
которых нет задачи в БД, перечисляет удалённое в вывод и делает ровно
одну запись kind=incident в журнал алертов на весь прогон уборки; ветки
живых задач не удаляются, и без явного вызова Оператора уборка не
запускается.»

Локальный контракт (test_author, требование 4 SPEC явно оставляет
выбор разработчику: «`doctor --fix` либо команда» — планка фиксирует
ПЕРВЫЙ из двух названных в SPEC вариантов, минимальным расширением уже
существующей команды `doctor`, тем же приёмом, каким уже устроен
`--restore`):

- `doctor.sweep_orphan_artifact_branches(conn) -> list[str]` — находит
  ветки `artifact/<id>` (`gitcmd.list_branches("artifact/")`), для
  которых `<id>` НЕ встречается в `store.all_tasks(conn)` (сравнение
  без учёта регистра — `artifact_branch.branch_name` работает с
  `task_id.lower()`), удаляет их (`gitcmd.git("branch", "-D", …)`),
  заводит РОВНО ОДИН incident-алерт на весь прогон (source
  `doctor.cleanup.artifact_branches`, перечисление удалённого в
  сообщении) и возвращает список удалённых имён веток.
- `doctor.cmd_doctor(restore: bool = False, fix: bool = False)` — новый
  keyword `fix`: `True` вызывает `sweep_orphan_artifact_branches` и
  печатает список удалённого; по умолчанию (`False`, как и у всех
  существующих вызовов `cmd_doctor()`) уборка не запускается.
- CLI: `doctor --fix` (`orchestrator/artel.py`, таблица `main()`) —
  `"--fix" in rest` вторым позиционным в `doctor.cmd_doctor(...)`, тем
  же приёмом, что уже несёт `"--restore" in rest`.

Красен до реализации: ни `doctor.sweep_orphan_artifact_branches`, ни
keyword `fix` у `cmd_doctor`, ни разбор `--fix` в `artel.py` сегодня не
существуют — весь файл падает `AttributeError`/`TypeError` до
реализации требования 4.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import alerts, artel, catalog, config, doctor, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class _DoctorSandboxTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)


class Ac4SweepOrphanArtifactBranchesTest(_DoctorSandboxTest):

    def test_ac4_sweep_deletes_only_branches_without_a_db_row(self):
        """Ветки `artifact/<id>` без строки БД удаляются; ветка `artifact/
        <id>` живой задачи (строка в `tasks` есть) — нет. Ровно один
        incident-алерт заведён на весь прогон, с обеими удалёнными
        ветками в сообщении, без упоминания живой.

        Ловит мутацию: цикл удаления не фильтрует по БД (удаляет вообще
        все ветки `artifact/*`, включая живую) — `artifact/t001` попадёт
        в удалённые; либо код заводит алерт ВНУТРИ цикла удаления, один
        на каждую ветку, — тест увидит больше одной incident-записи
        вместо ровно одной.
        """
        store.insert_task(store.db(), "T001", "Живая задача", "in_dev",
                          "task/t001-zhivaya-zadacha", config.DEFAULT_TARGET, 25.0)
        existing_branches = ["artifact/t001", "artifact/t777", "artifact/t778"]
        deleted_via_git = []

        def fake_git(*args):
            import subprocess
            if len(args) >= 3 and args[0] == "branch" and args[1] == "-D":
                deleted_via_git.append(args[2])
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(doctor.gitcmd, "list_branches",
                               lambda prefix="": list(existing_branches)), \
                mock.patch.object(doctor.gitcmd, "git", fake_git):
            deleted = doctor.sweep_orphan_artifact_branches(store.db())

        self.assertEqual(sorted(deleted), ["artifact/t777", "artifact/t778"])
        self.assertEqual(sorted(deleted_via_git), ["artifact/t777", "artifact/t778"])

        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.cleanup.artifact_branches"]
        self.assertEqual(len(incidents), 1)
        self.assertIn("artifact/t777", incidents[0]["message"])
        self.assertIn("artifact/t778", incidents[0]["message"])
        self.assertNotIn("artifact/t001", incidents[0]["message"])

    def test_ac4_sweep_is_a_noop_when_no_orphans_exist(self):
        """Ни одной ветки `artifact/*` без строки БД — ветка не удаляется,
        incident-алерт не заводится, возвращается пустой список.

        Ловит мутацию: код заводит incident-алерт (или пустую запись в
        журнал) даже при пустом результате уборки — нарушает «ровно одна
        запись НА ПРОГОН уборки» в сторону «алерт всегда, даже без
        находок».
        """
        store.insert_task(store.db(), "T001", "Живая задача", "in_dev",
                          "task/t001-zhivaya-zadacha", config.DEFAULT_TARGET, 25.0)

        def fake_git(*args):
            import subprocess
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(doctor.gitcmd, "list_branches",
                               lambda prefix="": ["artifact/t001"]), \
                mock.patch.object(doctor.gitcmd, "git", fake_git):
            deleted = doctor.sweep_orphan_artifact_branches(store.db())

        self.assertEqual([], deleted)
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.cleanup.artifact_branches"]
        self.assertEqual([], incidents)


class Ac4CmdDoctorGatingTest(_DoctorSandboxTest):
    """`all_checks` подменена целиком (не предмет этого критерия — своя
    полная песочница живого/CLI-смоука не нужна): единственное, что
    проверяют эти тесты, — вызывается ли уборка и что попадает в вывод."""

    def test_ac4_default_call_does_not_run_the_sweep(self):
        """`doctor.cmd_doctor()` (без `fix`, как во всех существующих
        вызовах) не запускает уборку осиротевших веток.

        Ловит мутацию: уборка вызывается безусловно внутри `cmd_doctor`
        (не за флагом `fix`) — нарушает «без явного вызова Оператора
        уборка не запускается».
        """
        with mock.patch.object(doctor, "all_checks", lambda conn: []), \
                mock.patch.object(doctor, "sweep_orphan_artifact_branches") as sweep:
            capture(doctor.cmd_doctor)
        sweep.assert_not_called()

    def test_ac4_fix_flag_runs_the_sweep_and_lists_output(self):
        """`doctor.cmd_doctor(fix=True)` запускает уборку ровно один раз и
        печатает удалённые ветки в вывод.

        Ловит мутацию: `fix=True` не доходит до `sweep_orphan_artifact_
        branches` (например, параметр принят, но не использован), либо
        вывод не перечисляет удалённое — «перечисление удалённого в
        вывод» из AC-4 нарушено.
        """
        with mock.patch.object(doctor, "all_checks", lambda conn: []), \
                mock.patch.object(doctor, "sweep_orphan_artifact_branches",
                                  return_value=["artifact/t777"]) as sweep:
            out = capture(lambda: doctor.cmd_doctor(fix=True))
        sweep.assert_called_once()
        self.assertIn("artifact/t777", out)


class Ac4CliFixFlagWiringTest(unittest.TestCase):

    def test_ac4_cli_fix_flag_calls_cmd_doctor_with_fix_true(self):
        """`artel.py doctor --fix` вызывает `doctor.cmd_doctor` с
        `fix=True` (позиционно или по имени — сверяется по значению, не
        по форме вызова); голый `artel.py doctor` — с `fix=False`.

        Ловит мутацию: таблица команд `main()` не разбирает `--fix`
        вовсе (флаг молча игнорируется) — уборка окажется вызвать
        нечем ни при каком argv, критерий «служебное действие,
        вызванное явно Оператором» лишится входной точки.
        """
        calls = []

        def stub_cmd_doctor(restore=False, fix=False):
            calls.append((restore, fix))

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "argv", ["artel.py", "doctor", "--fix"]), \
                    mock.patch.object(artel.doctor, "cmd_doctor", stub_cmd_doctor), \
                    mock.patch.object(artel.config, "ROOT", Path(tmp)):
                artel.main()

            with mock.patch.object(sys, "argv", ["artel.py", "doctor"]), \
                    mock.patch.object(artel.doctor, "cmd_doctor", stub_cmd_doctor), \
                    mock.patch.object(artel.config, "ROOT", Path(tmp)):
                artel.main()

        self.assertEqual(calls, [(False, True), (False, False)])
