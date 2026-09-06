"""AC-4/AC-5/AC-6 (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0): автокоммит артефактов
шага (`checkpoint.commit_step_artifacts`, тот же путь, которым идут
чекпоинты таймаута/аварии/паузы) переносит в артефактную ветку только
файлы из белого списка требования 1 (AC-4); посторонние файлы первого
уровня `tasks/<id>/` не проваливают шаг роли, а отбрасываются с ОДНОЙ
записью в журнал на весь список отброшенных путей, не по записи на файл
(AC-5); критерий допустимости `checkpoint.py` берёт ИЗ `scripts/guard.py`
(AC-6) — не дублирует его независимой регуляркой, как уже сделано для
`acceptance_tests/` этим же модулем (`_is_stray_acceptance_test_file`,
которая, по докстрингу `guard.py` рядом, СОЗНАТЕЛЬНО дублирует список
независимо от guard'а — SPEC 01M1SAA01YRRTWAVADT2F81RRQ прямо разрешала
дублирование ради лёгкости guard'а; эта SPEC для НОВОГО правила прямо
требует обратного).

AC-6 разбита на два теста намеренно (см. докстринги классов): поведенческое
сравнение классификации guard/checkpoint НЕ может отличить «импортирует
общий список» от «независимо продублировал идентичный список» — в любой
ОДИН момент времени обе реализации дают одинаковое поведение, а различаются
только будущей устойчивостью к правке списка в одном месте. Факт импорта
поэтому проверяется отдельным тестом чтением дерева разбора (`ast`) — без
угадывания имени новой функции/константы (SPEC называет только ОБРАЗЕЦ
существующих имён, не имя новой сущности).

Красен до реализации: checkpoint сегодня фильтрует только посторонние файлы ВНУТРИ acceptance_tests/ и не содержит импорта scripts.guard — test_ac4/test_ac5/test_ac6_checkpoint_module_imports_scripts_guard падают по прямым наблюдаемым следствиям этого.

Подробности: `checkpoint._commit_external_step_artifacts` сегодня
фильтрует ТОЛЬКО `_is_stray_acceptance_test_file` (посторонние файлы ВНУТРИ
`acceptance_tests/`) — файл первого уровня `tasks/<id>/` вроде
`notes.txt`/`debug.tmp` сегодня благополучно уезжает в артефактную ветку
целиком, никакой записи в журнал про «посторонние» не появляется вовсе, а
`orchestrator/checkpoint.py` не содержит ни одного импорта `scripts.guard`
(проверено `grep`). `test_ac4_...` красный по присутствию постороннего
файла в артефактной ветке после коммита; `test_ac5_...` красный по нулю
подходящих записей журнала вместо одной; `Ac6ImportsFromGuardTest::
test_ac6_checkpoint_module_imports_scripts_guard` красный, потому что
такого импорта в дереве разбора `checkpoint.py` сегодня нет.

Зелёный с рождения: сегодня guard.py и checkpoint.py оба пропускают любое имя первого уровня без разбора, поэтому пустые множества классификации совпадают по построению, не по согласованности критерия.

Подробности: `Ac6ChecksAgreeOnClassificationTest::
test_ac6_checkpoint_drops_exactly_what_guard_calls_extraneous` — сегодня ОБЕ
стороны (guard.py и checkpoint.py) пропускают любое имя первого уровня без
разбора, оба множества пусты и совпадают по построению, не потому что
критерий уже согласован. После реализации это станет содержательной
проверкой согласованности классификации на смешанном наборе имён —
переписывать тест под сегодняшнюю вырожденность не нужно.

Провалидировано стабом (решение Оператора 03.09): временная реализация
критерия допустимости ОДНИМ списком, импортируемым `checkpoint.py` из
`scripts.guard` и применяемым в `_commit_external_step_artifacts` тем же
приёмом, что уже применяет `_is_stray_acceptance_test_file` (собрать
`stray`, исключить из `files`, одна запись `store.journal` на весь
список) — зеленила все тесты этого файла. Стаб убран, репозиторий не
тронут.

## AC-9: обнаружено противоречие AC-1/AC-4 с уже залоченным поведением
`tests/test_checkpoint_external_step_artifacts.py`

При валидации стаба выше тем же прогоном обнаружено: белый список AC-1
— БУКВАЛЬНОЕ перечисление (`SPEC.md`/`PLAN.md`/`REVIEW.md`/
`TEST_REPORT.md`/`QUESTIONS.md`/`TZ.md`/`ANSWER-<n>.md`/
`acceptance_tests/`/`*.patch`), без места для произвольных бинарных
приложений. Но `tests/test_checkpoint_external_step_artifacts.py`
(строка 180, `test_binary_file_is_not_lost`, и строка 206,
`test_all_files_binary_still_commits_and_clears_the_dir`) — уже
существующие, зелёные, никем не помеченные как подлежащие правке тесты
— ЖЁСТКО требуют, чтобы `screenshot.png`/`blob.bin`, лежащие в
`tasks/<id>/` роли ПРЯМО РЯДОМ с `PLAN.md`, доехали до артефактной
ветки как есть (`assertIn(".../screenshot.png", committed)`).

Буквальная реализация AC-1 + AC-4 (checkpoint отбрасывает всё вне
белого списка) неизбежно превращает `screenshot.png`/`blob.bin` в
«посторонние» и красит оба этих теста — не гипотетической мутацией, а
прямым следствием ЛЮБОЙ добросовестной реализации требования 1/2. Это
проверено тем же стабом, которым выше провалидированы `test_ac4_...`/
`test_ac5_...`/`test_ac6_...`: временно применённый к `checkpoint.py`
белый список AC-1 (без каких-либо специальных исключений под `.png`/
`.bin`) даёт `FAILED` именно на этих двух существующих тестах, прогнанных
`python3 -m unittest tests.test_checkpoint_external_step_artifacts` тем
же стабом.

AC-9 требует «остаются зелёными БЕЗ ПРАВКИ АССЕРТОВ» — а любой выход из
противоречия, который я вижу, требует либо ослабить буквальность AC-1
(разрешить произвольные бинарные приложения помимо перечня), либо
поправить ассерты двух существующих тестов (запрещено без ADR/решения
Оператора — conventions-core.md, ADR-0002). Ни то, ни другое не в праве
решить test_author единолично — маркер эскалации ниже, вне докстроки
(guard читает его текстом из `test_*.py` планки, сюда положен рядом с
файлами, чьи AC-4/AC-5/AC-6 он же и покрывает).
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, checkpoint, config, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

# Полный разбор находки — в докстринге модуля выше. Однострочный маркер
# ниже — то, что реально читает сканер AC-разметки (regex, без переноса
# причины на следующую строку, тот же формат, что REDNESS_MARKER).
# AC-9: escalate — буквальный белый список AC-1 (SPEC.md/PLAN.md/REVIEW.md/TEST_REPORT.md/QUESTIONS.md/TZ.md/ANSWER-<n>.md/acceptance_tests//*.patch) конфликтует с залоченными tests/test_checkpoint_external_step_artifacts.py::test_binary_file_is_not_lost (стр.180) и ::test_all_files_binary_still_commits_and_clears_the_dir (стр.206), требующими произвольных бинарных вложений (screenshot.png/blob.bin) в артефактной ветке — варианты: A (дефолт) расширить AC-1 правилом «произвольное вложение вне генераторных .md-паттернов инцидента 06.09 разрешено»; B — ADR на правку фикстур этих тестов; C — иное решение Оператора

TARGET = "extproj"

# Одновременно валидные (per AC-1) и заведомо посторонние имена первого
# уровня — общий набор для checkpoint- и guard-прогонов AC-6 ниже.
ALLOWED_NAMES = ("PLAN.md", "TZ.md", "ANSWER-3.md", "x.patch")
STRAY_NAMES = ("notes.txt", "junk.bin")


class _CheckpointTaskRootStrayTest(RealGitSandbox):

    TASK = "01CHKTASKROOTSTRAY0001"

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.insert_task(conn, self.TASK, "Задача внешнего target",
                          "in_dev", f"task/{self.TASK.lower()}-x", TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)

    def write(self, rel: str, text: str = "содержимое\n") -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def artifact_branch_files(self) -> list:
        branch = f"artifact/{self.TASK.lower()}"
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def journal_rows(self) -> list:
        return store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()


class Ac4StrayFilesExcludedFromCommitTest(_CheckpointTaskRootStrayTest):
    """AC-4: посторонние файлы первого уровня исключены из переноса,
    разрешённые — переносятся, шаг роли не проваливается."""

    def test_ac4_allowed_file_transferred_stray_file_dropped_step_does_not_fail(self):
        """`PLAN.md` (в белом списке AC-1) и `scratch.log` (посторонний)
        лежат в `tasks/<id>/` роли одновременно; после
        `commit_step_artifacts` артефактная ветка несёт `PLAN.md`, но не
        несёт `scratch.log`, и вызов не бросает исключение.

        Ловит мутацию: фильтр посторонних файлов первого уровня не
        реализован (сегодняшнее поведение) — `scratch.log` попадёт в
        артефактную ветку наравне с `PLAN.md`, `assertNotIn` ниже это
        поймает.
        """
        self.write("PLAN.md", "план")
        self.write("scratch.log", "мусор роли")

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertTrue(detail)
        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", files)
        self.assertNotIn(f"tasks/{self.TASK}/scratch.log", files)


class Ac5SingleJournalEntryForAllStrayPathsTest(_CheckpointTaskRootStrayTest):
    """AC-5: ровно ОДНА запись в журнал шага на весь список отброшенных
    путей, не по записи на файл."""

    def test_ac5_two_stray_files_produce_exactly_one_journal_entry_listing_both(self):
        """Два посторонних файла первого уровня (`scratch.log`,
        `debug.tmp`) рядом с одним разрешённым (`PLAN.md`) — журнал шага
        несёт РОВНО одну новую запись, упоминающую ОБА отброшенных пути,
        не две отдельные записи.

        Ловит мутацию: журналирование сделано ПО ФАЙЛУ (цикл вызывает
        `store.journal` на каждой итерации вместо накопления списка и
        одного вызова после цикла) — тогда записей, упоминающих
        `scratch.log`/`debug.tmp`, будет две, не одна, и `assertEqual(...,
        1)` ниже это поймает.
        """
        self.write("PLAN.md", "план")
        self.write("scratch.log", "мусор 1")
        self.write("debug.tmp", "мусор 2")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        rows = self.journal_rows()
        stray_rows = [r for r in rows
                     if "scratch.log" in (r["detail"] or "")
                     or "scratch.log" in (r["action"] or "")]
        self.assertEqual(len(stray_rows), 1, [dict(r) for r in rows])
        combined = stray_rows[0]["action"] + " " + stray_rows[0]["detail"]
        self.assertIn("scratch.log", combined)
        self.assertIn("debug.tmp", combined)


class Ac6ImportsFromGuardTest(_CheckpointTaskRootStrayTest):
    """AC-6, часть 1: `checkpoint.py` ОБЯЗАН импортировать из
    `scripts.guard` (статическая проверка исходника через `ast` —
    поведенческое сравнение AC-6 ниже структурно не может отличить
    «импортирует общий список» от «независимо продублировал идентичный
    список» — обе реализации в любой ОДИН момент времени дают одинаковое
    поведение; факт импорта отличим только чтением дерева разбора)."""

    def test_ac6_checkpoint_module_imports_scripts_guard(self):
        """`orchestrator/checkpoint.py` несёт импорт `scripts.guard`
        (`from scripts import guard` либо `from scripts.guard import
        ...` либо `import scripts.guard`) — единственный способ, которым
        модуль вообще может СОСЛАТЬСЯ на критерий допустимости guard'а,
        не переписывая его заново.

        Ловит мутацию: разработчик реализует фильтр `checkpoint.py`
        собственной независимой регуляркой/списком имён (ровно так, как
        уже сознательно сделано для `_is_stray_acceptance_test_file` —
        готовый шаблон под рукой, соблазн скопировать тот же приём
        велик) — тогда в дереве разбора `checkpoint.py` не найдётся ни
        одного импорта `scripts.guard`, и `assertTrue` ниже это поймает.
        """
        import ast
        checkpoint_path = (Path(__file__).resolve().parents[3]
                           / "orchestrator" / "checkpoint.py")
        tree = ast.parse(checkpoint_path.read_text(encoding="utf-8"))

        imports_guard = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "scripts.guard":
                    imports_guard = True
                elif node.module == "scripts" and any(
                        alias.name == "guard" for alias in node.names):
                    imports_guard = True
            elif isinstance(node, ast.Import):
                if any(alias.name == "scripts.guard" for alias in node.names):
                    imports_guard = True

        self.assertTrue(
            imports_guard,
            "orchestrator/checkpoint.py не импортирует scripts.guard — "
            "критерий допустимости первого уровня tasks/<id>/ обязан "
            "жить одним списком в guard.py (AC-6)")


class Ac6ChecksAgreeOnClassificationTest(_CheckpointTaskRootStrayTest):
    """AC-6, часть 2 (дополнительная, регресс-контроль): при ОБОИХ уже
    реализованных сторонах — guard.py и checkpoint.py — они обязаны
    классифицировать один и тот же набор имён одинаково; если
    checkpoint.py импортирует список guard'а (часть 1 выше), это верно
    по построению, но при независимом дублировании способно молча
    разойтись ПОЗЖЕ, когда список guard'а поменяется, а checkpoint —
    нет. До готовности ОБЕИХ сторон это сравнение вырождено (обе стороны
    сегодня пропускают всё подряд, поэтому пустые множества совпадают
    независимо от импорта) — часть 1 выше остаётся единственным тестом
    этого файла, красным именно по AC-6 до реализации."""

    def guard_extraneous_names(self, names: list) -> set:
        """Имена первого уровня, которые `guard.py --all` называет
        «посторонний файл в каталоге задачи» — на изолированном временном
        дереве `tasks/<TASK>/`, git не нужен (тот же приём, что
        `test_ac1_ac2_guard_task_root_whitelist.py::run_guard`)."""
        import io
        import os
        from contextlib import redirect_stdout
        from unittest import mock
        from scripts import guard

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            task_dir = tmp_root / "tasks" / self.TASK
            task_dir.mkdir(parents=True)
            for name in names:
                (task_dir / name).write_text("x\n", encoding="utf-8")
            orig_cwd = Path.cwd()
            os.chdir(tmp_root)
            try:
                buf = io.StringIO()
                with mock.patch.object(sys, "argv", ["scripts/guard.py", "--all"]):
                    with redirect_stdout(buf):
                        guard.main()
                out = buf.getvalue()
            finally:
                os.chdir(orig_cwd)

        reason = "посторонний файл в каталоге задачи"
        flagged = set()
        for line in out.splitlines():
            if reason not in line:
                continue
            for name in names:
                if name in line:
                    flagged.add(name)
        return flagged

    def test_ac6_checkpoint_drops_exactly_what_guard_calls_extraneous(self):
        """Один и тот же набор имён (валидные + посторонние вперемешку)
        классифицируется ОДИНАКОВО guard'ом и checkpoint'ом: множество
        имён, отброшенных `commit_step_artifacts`, совпадает с
        множеством, которое `guard --all` называет посторонним, — ни
        одним именем больше, ни одним меньше.

        Ловит мутацию: `checkpoint.py` реализует критерий НЕЗАВИСИМОЙ
        регуляркой, разошедшейся со списком guard'а (например, забывает
        разрешить `TZ.md` или ошибочно разрешает `.log`) — тогда множество
        отброшенных checkpoint'ом имён разойдётся с множеством,
        помеченным guard'ом, и сравнение множеств ниже упадёт.
        """
        names = list(ALLOWED_NAMES) + list(STRAY_NAMES)
        for name in names:
            self.write(name)

        guard_stray = self.guard_extraneous_names(names)

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")
        kept = {Path(f).name for f in self.artifact_branch_files()}

        checkpoint_dropped = set(names) - kept
        self.assertEqual(
            checkpoint_dropped, guard_stray,
            f"checkpoint отбросил {checkpoint_dropped}, guard посторонним "
            f"назвал {guard_stray} — критерий допустимости разошёлся между "
            f"checkpoint.py и guard.py (AC-6 требует единого источника)")


if __name__ == "__main__":
    import unittest
    unittest.main()
