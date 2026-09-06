"""AC-4/AC-5/AC-6 (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0), формулировка по
ANSWER-1 (tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/ANSWER-1.md, вариант A):
автокоммит артефактов шага (`checkpoint.commit_step_artifacts`, тот же
путь, которым идут чекпоинты таймаута/аварии/паузы) переносит в
артефактную ветку только `.md`-файлы из белого списка требования 1 плюс
ЛЮБЫЕ вложения других расширений (AC-4); посторонние `.md`-файлы первого
уровня `tasks/<id>/` (и скрытые файлы/`__pycache__`, ANSWER-1) не
проваливают шаг роли, а отбрасываются с ОДНОЙ записью в журнал на весь
список отброшенных путей, не по записи на файл (AC-5); критерий
допустимости `checkpoint.py` берёт ИЗ `scripts/guard.py` (AC-6) — не
дублирует его независимой регуляркой, как уже сделано для
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

## История: конфликт AC-9 эскалирован и разрешён ANSWER-1

Первый заход этой планки использовал `scratch.log`/`debug.tmp`/
`junk.bin` как примеры «посторонних» файлов первого уровня и
эскалировал AC-9: буквальный белый список AC-1 (без понятия «вложение»)
конфликтовал с уже залоченными `tests/
test_checkpoint_external_step_artifacts.py::test_binary_file_is_not_lost`
(стр.180) и `::test_all_files_binary_still_commits_and_clears_the_dir`
(стр.206), которые требуют, чтобы `screenshot.png`/`blob.bin` доезжали
до артефактной ветки как есть. ANSWER-1 (вариант A) разрешил конфликт:
белый список AC-1 действует ТОЛЬКО для `.md` первого уровня; вложения
любого другого расширения проходят молча, без ограничения имени.
Следствие для этой планки: `.log`/`.tmp`/`.bin` бывшие «посторонние»
фикстуры сами становятся легальными вложениями по новому правилу — они
заменены на посторонние `.md`-копии (`_head_map.md`/`compare.md`, тот
же класс инцидента 06.09), а `screenshot.png` теперь фигурирует как
ПОЗИТИВНЫЙ пример (обязан доехать, не быть отброшенным) — см.
`test_ac4_non_md_attachment_is_transferred_not_dropped` ниже, прямой
регресс-тест против повторения того же конфликта.

Красен до реализации: checkpoint сегодня фильтрует только посторонние файлы ВНУТРИ acceptance_tests/ и не содержит импорта scripts.guard — test_ac4/test_ac5/test_ac6_checkpoint_module_imports_scripts_guard падают по прямым наблюдаемым следствиям этого.

Подробности: `checkpoint._commit_external_step_artifacts` сегодня
фильтрует ТОЛЬКО `_is_stray_acceptance_test_file` (посторонние файлы ВНУТРИ
`acceptance_tests/`) — файл первого уровня `tasks/<id>/` вроде
`_head_map.md`/`compare.md` сегодня благополучно уезжает в артефактную
ветку целиком, никакой записи в журнал про «посторонние» не появляется
вовсе, а `orchestrator/checkpoint.py` не содержит ни одного импорта
`scripts.guard` (проверено `grep`). `test_ac4_...` красный по
присутствию постороннего файла в артефактной ветке после коммита;
`test_ac5_...` красный по нулю подходящих записей журнала вместо одной;
`Ac6ImportsFromGuardTest::test_ac6_checkpoint_module_imports_scripts_guard`
красный, потому что такого импорта в дереве разбора `checkpoint.py`
сегодня нет.

Зелёный с рождения: test_ac4_non_md_attachment_is_transferred_not_dropped проходит уже сегодня (checkpoint переносит любой файл диска без разбора расширения) — регресс-контроль на будущее правило AC-1/AC-4/ANSWER-1, не тавтология: как только правило появится, ему запрещено начать отбрасывать вложение только по «странному» расширению/имени.

Подробности: `Ac6ChecksAgreeOnClassificationTest::
test_ac6_checkpoint_drops_exactly_what_guard_calls_extraneous` — сегодня ОБЕ
стороны (guard.py и checkpoint.py) пропускают любое имя первого уровня без
разбора, оба множества пусты и совпадают по построению, не потому что
критерий уже согласован. После реализации это станет содержательной
проверкой согласованности классификации на смешанном наборе имён —
переписывать тест под сегодняшнюю вырожденность не нужно.

Провалидировано стабом (решение Оператора 03.09): временная реализация
критерия допустимости ОДНИМ списком (только `.md`-имена AC-1, ANSWER-1),
импортируемым `checkpoint.py` из `scripts.guard` и применяемым в
`_commit_external_step_artifacts` тем же приёмом, что уже применяет
`_is_stray_acceptance_test_file` (собрать `stray`, исключить из `files`,
одна запись `store.journal` на весь список) — зеленила все тесты этого
файла, включая `test_ac4_non_md_attachment_is_transferred_not_dropped`
(вложения `.png`/`.bin` переносились как есть). Стаб убран, репозиторий
не тронут.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, checkpoint, config, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

# AC-9: manual — критерий требует, чтобы отдельные уже существующие
# tests/test_guard*.py, tests/test_checkpoint*.py, tests/test_fsm_merge_gate*.py
# остались зелёными на реализации разработчика; skill test-authoring
# запрещает test_author гонять полный tests/ в шаге (эту работу делает
# CI/ревью), поэтому это не отдельный тест acceptance_tests/. Вторая
# половина AC-9 (каждый новый тест ловит заявленную мутацию) обеспечена
# докстринками «Ловит мутацию:» тестов AC-1/AC-2/AC-4/AC-5/AC-6/AC-7/AC-8
# этой планки, отдельного теста не требует. Конфликт, из-за которого
# предыдущий заход эскалировал именно AC-9 (буквальный белый список
# ломал test_binary_file_is_not_lost/test_all_files_binary_still_commits_and_clears_the_dir),
# разрешён ANSWER-1 и закрыт регресс-тестом
# test_ac4_non_md_attachment_is_transferred_not_dropped ниже.

TARGET = "extproj"

# Валидные (per AC-1/ANSWER-1) и заведомо посторонние `.md`-имена первого
# уровня — общий набор для checkpoint- и guard-прогонов AC-6 ниже.
# `.log`/`.tmp`/`.bin` НЕ используются как посторонние примеры — по
# ANSWER-1 это легальные вложения (см. «История» в докстринге модуля).
ALLOWED_NAMES = ("PLAN.md", "TZ.md", "ANSWER-3.md", "x.patch")
STRAY_NAMES = ("_head_map.md", "compare.md")


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
    """AC-4: посторонние `.md`-файлы первого уровня исключены из
    переноса, разрешённые и любые вложения — переносятся, шаг роли не
    проваливается."""

    def test_ac4_allowed_file_transferred_stray_md_file_dropped_step_does_not_fail(self):
        """`PLAN.md` (в белом списке AC-1) и `_head_map.md` (посторонняя
        копия карты кодовой базы, инцидент 06.09) лежат в `tasks/<id>/`
        роли одновременно; после `commit_step_artifacts` артефактная
        ветка несёт `PLAN.md`, но не несёт `_head_map.md`, и вызов не
        бросает исключение.

        Ловит мутацию: фильтр посторонних `.md`-файлов первого уровня не
        реализован (сегодняшнее поведение) — `_head_map.md` попадёт в
        артефактную ветку наравне с `PLAN.md`, `assertNotIn` ниже это
        поймает.
        """
        self.write("PLAN.md", "план")
        self.write("_head_map.md", "черновая копия карты кодовой базы")

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertTrue(detail)
        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", files)
        self.assertNotIn(f"tasks/{self.TASK}/_head_map.md", files)

    def test_ac4_non_md_attachment_is_transferred_not_dropped(self):
        """Вложение `screenshot.png` (расширение, не входящее в `.md`
        белого списка) рядом с `PLAN.md` — доезжает до артефактной ветки
        как есть, не отбрасывается фильтром постороннего (ANSWER-1: белый
        список AC-1 действует только для `.md`; регресс-тест против
        конфликта, из-за которого предыдущий заход эскалировал AC-9 —
        буквальный белый список ломал залоченные `tests/
        test_checkpoint_external_step_artifacts.py::test_binary_file_is_not_lost`).

        Ловит мутацию: разработчик реализует фильтр `checkpoint.py`
        буквальным списком AC-1 ДО правки ANSWER-1 (без понятия
        «вложение», отбрасывающим всё вне перечисленных `.md`-имён и
        `*.patch`) — тогда `screenshot.png` попадёт в `stray` наравне с
        `_head_map.md`, и `assertIn` ниже это поймает.
        """
        self.write("PLAN.md", "план")
        self.write("screenshot.png", "не настоящий png, но не суть")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/screenshot.png", files)


class Ac5SingleJournalEntryForAllStrayPathsTest(_CheckpointTaskRootStrayTest):
    """AC-5: ровно ОДНА запись в журнал шага на весь список отброшенных
    путей, не по записи на файл."""

    def test_ac5_two_stray_md_files_produce_exactly_one_journal_entry_listing_both(self):
        """Два посторонних `.md`-файла первого уровня (`_head_map.md`,
        `compare.md`) рядом с одним разрешённым (`PLAN.md`) — журнал шага
        несёт РОВНО одну новую запись, упоминающую ОБА отброшенных пути,
        не две отдельные записи.

        Ловит мутацию: журналирование сделано ПО ФАЙЛУ (цикл вызывает
        `store.journal` на каждой итерации вместо накопления списка и
        одного вызова после цикла) — тогда записей, упоминающих
        `_head_map.md`/`compare.md`, будет две, не одна, и
        `assertEqual(..., 1)` ниже это поймает.
        """
        self.write("PLAN.md", "план")
        self.write("_head_map.md", "черновая копия карты 1")
        self.write("compare.md", "")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        rows = self.journal_rows()
        stray_rows = [r for r in rows
                     if "_head_map.md" in (r["detail"] or "")
                     or "_head_map.md" in (r["action"] or "")]
        self.assertEqual(len(stray_rows), 1, [dict(r) for r in rows])
        combined = stray_rows[0]["action"] + " " + stray_rows[0]["detail"]
        self.assertIn("_head_map.md", combined)
        self.assertIn("compare.md", combined)


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
        """Один и тот же набор имён (валидные + посторонние `.md`
        вперемешку) классифицируется ОДИНАКОВО guard'ом и checkpoint'ом:
        множество имён, отброшенных `commit_step_artifacts`, совпадает с
        множеством, которое `guard --all` называет посторонним, — ни
        одним именем больше, ни одним меньше.

        Ловит мутацию: `checkpoint.py` реализует критерий НЕЗАВИСИМОЙ
        регуляркой, разошедшейся со списком guard'а (например, забывает
        разрешить `TZ.md` или ошибочно считает посторонним любой `.md`,
        не входящий в буквальный перечень, включая корректно
        сформированный `ANSWER-3.md`) — тогда множество отброшенных
        checkpoint'ом имён разойдётся с множеством, помеченным guard'ом,
        и сравнение множеств ниже упадёт.
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
