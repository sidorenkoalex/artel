"""Юнит-тесты гейта зон на `in_dev -> review` (tasks/
01M1P9QCHPHSCEA6TK13PV85SP): чистые функции разбора (`_split_zone_paths`,
`_touches_zone`, `_plan_zones_extension_paths`) и fail-closed на сбое git —
тот же класс, что `tests/test_capacity_gate.py` закрывает для соседнего
гейта ёмкости, а его собственная приёмочная планка (`tasks/
01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/`) намеренно не бьёт: там git
всегда отвечает.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm_advance, gitcmd, store  # noqa: E402
from orchestrator.advance_gates import zones  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


def _git_log_subject(subject: str, returncode: int = 0):
    """`gitcmd.git("log", "-1", "--format=%s", ...)` отвечающий `subject`
    ровно на подкоманду `log`; всё остальное — заглушка успехом (в
    тестах этого файла ей не пользуются)."""
    def fake(*args):
        if args and args[0] == "log":
            return subprocess.CompletedProcess(list(args), returncode,
                                               f"{subject}\n", "")
        return subprocess.CompletedProcess(list(args), 0, "", "")
    return fake


class SplitZonePathsTest(unittest.TestCase):

    def test_comma_separated_paths_are_trimmed(self):
        """Ловит мутацию: `.strip()` на элементе убран/сломан — вокруг
        пути остаются пробелы (` b.py `), и он не совпадает с реальным
        путём диффа при сверке зон."""
        self.assertEqual(
            fsm_advance._split_zone_paths("a.py, b.py ,c/"),
            ["a.py", "b.py", "c/"])

    def test_none_gives_empty_list(self):
        """Ловит мутацию: `None` (поле не заполнено) трактуется как список
        из одного пустого пути, а не как «зон нет»."""
        self.assertEqual(fsm_advance._split_zone_paths(None), [])

    def test_empty_string_gives_empty_list(self):
        """Ловит мутацию: проверка `if not raw` убрана/ослаблена — пустая
        строка идёт в `"".split(",")` и даёт список из одного пустого
        пути вместо пустого списка (та же ловушка, что и `None`)."""
        self.assertEqual(fsm_advance._split_zone_paths(""), [])

    def test_blank_entries_are_dropped(self):
        """Ловит мутацию: фильтр `if p.strip()` убран — двойная запятая
        (пустой элемент между `a.py` и `b.py`) попадает в список как
        пустая строка, и пустой путь ложно матчит любой файл диффа
        (`_touches_zone` — `path.startswith("")` истинно всегда)."""
        self.assertEqual(fsm_advance._split_zone_paths("a.py,, b.py"),
                         ["a.py", "b.py"])


class TouchesZoneTest(unittest.TestCase):

    def test_exact_file_match(self):
        """Ловит мутацию: сравнение `path == z` убрано (осталось только
        `startswith`, испорченное, например, разворотом операндов) —
        путь, буквально совпадающий с зоной-файлом, обязан матчиться."""
        self.assertTrue(
            fsm_advance._touches_zone("orchestrator/store.py",
                                      ["orchestrator/store.py"]))

    def test_directory_zone_matches_file_under_it(self):
        """Ловит мутацию: `startswith` заменён на строгое равенство —
        зона-директория несёт trailing `/` (COMMON_ZONES: `"tests/"`) —
        путь под ней обязан матчиться префиксом, не только листингом
        каталога буквально."""
        self.assertTrue(
            fsm_advance._touches_zone("tests/test_x.py", ["tests/"]))

    def test_unrelated_path_does_not_match(self):
        """Ловит мутацию: сравнение ослаблено до подстроки где угодно
        (`in`), не префикса — `docs/x.py` не обязан матчить зону
        `orchestrator/`."""
        self.assertFalse(
            fsm_advance._touches_zone("docs/x.py", ["orchestrator/"]))

    def test_file_zone_matches_as_prefix_of_unrelated_file(self):
        """Ловит мутацию: намеренное поведение (тот же `startswith`, что и
        `config.PROTECTED_PATHS`/`_touches_protected_path`) заменено на
        точное сравнение путей — зона-файл без trailing `/`
        (`orchestrator/store.py`) СОВПАДАЕТ по префиксу с чужим файлом
        того же имени (`orchestrator/store.py.bak`); список зон
        намеренно не эксклюзивный, а не баг, который стоит чинить здесь."""
        self.assertTrue(
            fsm_advance._touches_zone("orchestrator/store.py.bak",
                                      ["orchestrator/store.py"]))


class PlanZonesExtensionPathsTest(unittest.TestCase):

    def test_no_section_gives_none(self):
        """Ловит мутацию: `guard.section_body` на отсутствующей секции
        возвращает не пустую строку, а весь текст (или проверка `is
        None` заменена на falsy-проверку) — исключение AC-3 открылось бы
        для PLAN, вовсе не заявлявшего расширение зон."""
        text = "# PLAN\n\n## Подход\n\nтекст\n"
        self.assertIsNone(fsm_advance._plan_zones_extension_paths(text))

    def test_section_without_paths_line_gives_none(self):
        """Ловит мутацию: раздел «## Расширение зон» сам по себе (без
        строки `Пути:`) ошибочно открывал бы исключение AC-3."""
        text = "## Расширение зон\n\nОбоснование без строки Пути.\n"
        self.assertIsNone(fsm_advance._plan_zones_extension_paths(text))

    def test_section_with_paths_line_is_parsed(self):
        """Ловит мутацию: срез `line[len("Пути:"):]` сдвинут (обрезает
        первый символ пути или оставляет сам префикс `Пути:`) — список
        путей исключения AC-3 выходит искажённым, и мандат Оператора на
        реальные пути перестаёт совпадать."""
        text = ("## Расширение зон\n\nПути: docs/a.md, docs/b.md\n\n"
               "Обоснование ниже.\n")
        self.assertEqual(
            fsm_advance._plan_zones_extension_paths(text),
            ["docs/a.md", "docs/b.md"])


class ZonesGateGitFailureTest(TmpRootTest):
    """Fail-closed на сбое git (тот же принцип ADR-0002, что
    `_capacity_gate_refuses`/лок `acceptance_tests/`): список файлов диффа
    не получен — сверка с зонами невозможна, переход отказывает, не
    пропускает молча."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.t = {"title": "Тест гейта зон", "branch": "task/t001-x",
                 "zones": "orchestrator/store.py", "zones_extension": None}

    def test_git_not_answering_diff_names_refuses(self):
        """Ловит мутацию: проверка `if files is None: ... return True`
        убрана/заменена на `return False` — `diff_names`, не ответивший
        списком файлов, молча пропустил бы переход вместо явного отказа
        (fail-open вместо fail-closed, ADR-0002).

        `diff_base` замокан отдельно на успешный sha (R1-F1, REVIEW.md
        итерация 1): без этого в песочнице `TmpRootTest` (без настоящего
        git-репозитория) `_zones_gate_refuses` отказывал бы РАНЬШЕ, на
        собственной проверке `base is None` (fsm_advance.py, ветка
        `diff_base`), и выполнение не доходило бы до мокнутого
        `diff_names` вовсе — тест был бы зелёным, но не ловил заявленную
        мутацию."""
        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names", return_value=None):
            refuses = fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, self.t, "task/t001-x", "PLAN\n")
        self.assertTrue(refuses)
        details = [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.task_id,))]
        self.assertTrue(any("гейт зон" in d for d in details))


class ZonesGateNoDeclaredZoneSkipsTest(TmpRootTest):
    """Задача без заявленной зоны вовсе (`zones`/`zones_extension` оба
    пусты — SPEC старой версии до `guard.requires_zones`, либо тестовая
    фикстура, заведённая мимо гейта SPEC) — гейт не звонится (AC-7,
    `PLAN.md`, «Риски»): опт-ин механики, не ретроактивный запрет.

    Ловит мутацию: гейт считает пустой `zones` как «зона пуста, всё вне
    зоны» вместо «зона не декларировалась вовсе» — любой существующий
    тест, заводящий задачу в обход гейта SPEC (без `zones`), начал бы
    отказывать на первом же файле вне `COMMON_ZONES`."""

    def test_no_zones_and_no_extension_skips_the_gate(self):
        store.create_schema(store.db())
        conn = store.db()
        task_id = "T001"
        store.insert_task(conn, task_id, "Тест", "in_dev", "task/t001-x",
                          config.DEFAULT_TARGET, 10.0)
        t = {"title": "Тест", "branch": "task/t001-x", "zones": None,
            "zones_extension": None}

        def boom(*args, **kwargs):
            raise AssertionError("гейт зон не обязан звать diff_names без "
                                 "заявленной зоны")

        with mock.patch.object(gitcmd, "diff_names", boom):
            refuses = fsm_advance._zones_gate_refuses(
                conn, task_id, t, "task/t001-x", "PLAN\n")
        self.assertFalse(refuses)


class ZonesGateExternalTargetSkipsTest(TmpRootTest):
    """Внешний (не self) target — гейт не проверяется вовсе (тот же довод,
    что `_capacity_gate_refuses`: diff в `config.ROOT` не видит код
    внешнего target)."""

    def test_external_target_never_calls_diff_names(self):
        store.create_schema(store.db())
        conn = store.db()
        task_id = "T001"
        store.insert_task(conn, task_id, "Тест", "in_dev", "task/t001-x",
                          "some-external-target", 10.0)
        self.assertNotEqual(store.task_target(conn, task_id),
                            config.DEFAULT_TARGET)
        t = {"title": "Тест", "branch": "task/t001-x", "zones": None,
            "zones_extension": None}

        def boom(*args, **kwargs):
            raise AssertionError("гейт зон не обязан звать diff_names "
                                 "для внешнего target")

        with mock.patch.object(gitcmd, "diff_names", boom):
            refuses = fsm_advance._zones_gate_refuses(
                conn, task_id, t, "task/t001-x", "PLAN\n")
        self.assertFalse(refuses)


class UntrackedWorktreePathsTest(TmpRootTest):
    """`fsm_advance._untracked_worktree_paths` (SPEC
    01M290PVYG2VJK6442H5BAX9MA, AC-6): разбор `git status --porcelain`
    рабочего дерева self-target — изолированно от полного `_zones_gate`
    (сценарий «нетрекенный файл вне зоны отказывает переходу» целиком уже
    несёт залоченная планка приёмки tasks/01M290PVYG2VJK6442H5BAX9MA/
    acceptance_tests/test_ac6_zones_gate_untracked_files.py)."""

    def test_git_status_failure_degrades_to_empty_list(self):
        """Ловит мутацию: отказ `git status` трактуется как «путей нет»
        и одновременно роняет исключение/отказывает переходу отдельно —
        committed-дифф `_zones_gate` уже fail-closed на СВОИХ отказах,
        этот довесок обязан молча деградировать, не падать."""
        with mock.patch.object(gitcmd, "in_repo", return_value=None):
            paths = fsm_advance._untracked_worktree_paths("T001")
        self.assertEqual(paths, [])

    def test_parses_untracked_staged_and_renamed_entries(self):
        """Ловит мутацию: разбор строки `git status --porcelain` не
        снимает трёхсимвольный код статуса (`assertEqual` ниже увидел бы
        `"?? docs/new_note.md"` целиком вместо `"docs/new_note.md"`) либо
        не берёт путь НАЗНАЧЕНИЯ переименования после ` -> `."""
        porcelain = ("?? docs/new_note.md\n"
                    " M orchestrator/checkpoint.py\n"
                    "R  old_name.py -> new_name.py\n")
        with mock.patch.object(
                gitcmd, "in_repo",
                return_value=subprocess.CompletedProcess([], 0, porcelain, "")):
            paths = fsm_advance._untracked_worktree_paths("T001")
        self.assertEqual(
            set(paths),
            {"docs/new_note.md", "orchestrator/checkpoint.py", "new_name.py"})


class ZonesGateOwnTaskDirTest(TmpRootTest):
    """SPEC 01M2B6JNFD381MZT70CVB5NJQC, AC-1/AC-2: собственный каталог
    задачи — своя зона для довеска неотслеживаемых файлов, тем же
    правилом (`checkpoint.task_dir_zone`), что уже применяет
    `checkpoint._zone_paths` к WIP-чекпоинтам. Committed-дифф пуст в обоих
    тестах — предмет проверки строго довесок untracked-путей
    (`_untracked_worktree_paths`), не остальной гейт."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        store.insert_task(self.conn, self.task_id, "Тест", "in_dev",
                          "task/t001-x", config.DEFAULT_TARGET, 10.0)
        store.update_task(self.conn, self.task_id, zones="orchestrator/store.py")
        self.t = {"title": "Тест", "branch": "task/t001-x",
                 "zones": "orchestrator/store.py", "zones_extension": None}

    def _status_in_repo(self, porcelain: str):
        def fake(repo, *args):
            if args[:1] == ("status",):
                return subprocess.CompletedProcess(list(args), 0, porcelain, "")
            return subprocess.CompletedProcess(list(args), 0, "", "")
        return fake

    def test_untracked_file_under_own_task_dir_does_not_refuse(self):
        """AC-1: неотслеживаемый `tasks/<id>/acceptance_tests/test_x.py`
        (материализованная планка после подтяжки, SPEC «Контекст») —
        гейт зон пропускает переход, коммиченный дифф строго в
        заявленных зонах.

        Ловит мутацию: фильтр `task_dir_zone` в `_zones_gate` убран —
        планка приёмки снова считалась бы файлом вне зон, регрессия
        12.09 (четыре ложных отказа волны 3)."""
        porcelain = f"?? tasks/{self.task_id}/acceptance_tests/test_x.py\n"
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names", return_value=[]), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._status_in_repo(porcelain)):
            refuses = fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, self.t, "task/t001-x", "PLAN\n")
        self.assertFalse(refuses)

    def test_untracked_file_outside_own_task_dir_still_refuses(self):
        """AC-2: неотслеживаемый файл кода вне `tasks/<id>/` и вне
        заявленных zones — прежний отказ гейта зон сохраняется
        байт-в-байт (01M290PVYG, AC-6).

        Ловит мутацию: фильтр `task_dir_zone` расширен неверно (например,
        сверяет подстрокой вместо префикса пути) и случайно накрывает
        посторонний путь — регрессия по AC-2, гейт молча пропускал бы
        код вне зон."""
        porcelain = "?? docs/stray_note.md\n"
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names", return_value=[]), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._status_in_repo(porcelain)):
            refuses = fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, self.t, "task/t001-x", "PLAN\n")
        self.assertTrue(refuses)
        details = [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.task_id,))]
        self.assertTrue(any("docs/stray_note.md" in d for d in details))


class AnswerCommitIsRoleStepAutocommitTest(unittest.TestCase):
    """R2-F1 (REVIEW.md 01M1P9QCHPHSCEA6TK13PV85SP итерация 2, blocker):
    `_answer_commit_is_role_step_autocommit` — единственный узел,
    отличающий настоящий `cmd_answer` от подделки роли через автокоммит
    шага."""

    def test_role_step_autocommit_subject_is_detected(self):
        """Ловит мутацию: префикс `own_commit_marker` (`checkpoint.py`)
        не распознан — поддельный `ANSWER-99.md`, занесённый автокоммитом
        шага developer, засчитывался бы мандатом Оператора."""
        fake = _git_log_subject(
            "T001: артефакты шага developer (автокоммит оркестратора)")
        with mock.patch.object(gitcmd, "git", fake):
            self.assertTrue(fsm_advance._answer_commit_is_role_step_autocommit(
                "task/t001-x", "T001", "tasks/T001/ANSWER-99.md"))

    def test_role_step_timeout_autocommit_subject_is_also_detected(self):
        """Ловит мутацию: распознаётся только точная формулировка без
        пометки таймаута — вариант `commit_timeout_checkpoint`
        («WIP после таймаута», тот же префикс) проходил бы как настоящий
        `cmd_answer`."""
        fake = _git_log_subject(
            "T001: артефакты шага developer (автокоммит оркестратора, "
            "WIP после таймаута)")
        with mock.patch.object(gitcmd, "git", fake):
            self.assertTrue(fsm_advance._answer_commit_is_role_step_autocommit(
                "task/t001-x", "T001", "tasks/T001/ANSWER-99.md"))

    def test_cmd_answer_commit_subject_is_not_detected(self):
        """Ловит мутацию: префикс сверяется настолько широко, что
        совпадает и с настоящим сообщением `cmd_answer` — легитимный
        мандат Оператора отклонялся бы как подделка."""
        fake = _git_log_subject("T001: ANSWER-1 — ответ Оператора")
        with mock.patch.object(gitcmd, "git", fake):
            self.assertFalse(fsm_advance._answer_commit_is_role_step_autocommit(
                "task/t001-x", "T001", "tasks/T001/ANSWER-1.md"))

    def test_git_not_answering_is_not_treated_as_role_autocommit(self):
        """Ловит мутацию: неответ git (`returncode != 0`, либо лёгкая
        песочница без реального коммита — так отвечает акцептная планка
        этой задачи, `_sandbox.py::write_answer_mandate`) трактуется как
        доказанный автокоммит роли — легитимный мандат в такой песочнице
        отклонялся бы всегда, ломая уже зелёный сценарий AC-3."""
        fake = _git_log_subject("", returncode=1)
        with mock.patch.object(gitcmd, "git", fake):
            self.assertFalse(fsm_advance._answer_commit_is_role_step_autocommit(
                "task/t001-x", "T001", "tasks/T001/ANSWER-1.md"))


class AnswerZonesMandateOriginTest(unittest.TestCase):
    """R2-F1: `_answer_zones_mandate` не засчитывает маркер из ANSWER-файла,
    чей последний коммит — доказанный автокоммит шага роли."""

    def test_marker_from_role_step_autocommit_is_not_counted(self):
        """Ловит мутацию: проверка происхождения не подключена в цикле
        перебора файлов — `_answer_zones_mandate` вернулся бы к прежнему
        поведению R2-F1, засчитывая ЛЮБОЙ `ANSWER-*.md` с маркером."""
        answer_text = ("---\ntype: answer\n---\n\n"
                       "Расширение зон разрешено: docs/extra_module.md\n")
        git_fake = _git_log_subject(
            "T001: артефакты шага developer (автокоммит оркестратора)")
        with mock.patch.object(gitcmd, "ls_tree_files",
                               return_value=["tasks/T001/ANSWER-99.md"]), \
                mock.patch.object(gitcmd, "show",
                                  return_value=(answer_text, "")), \
                mock.patch.object(gitcmd, "git", git_fake):
            mandate = fsm_advance._answer_zones_mandate("task/t001-x", "T001")
        self.assertEqual(mandate, set())

    def test_marker_from_genuine_cmd_answer_commit_is_counted(self):
        """Ловит мутацию: узел происхождения отклоняет ЛЮБОЙ ANSWER,
        включая настоящий `cmd_answer` — исключение AC-3 стало бы
        недостижимым даже с реальным мандатом Оператора."""
        answer_text = ("---\ntype: answer\n---\n\n"
                       "Расширение зон разрешено: docs/extra_module.md\n")
        git_fake = _git_log_subject("T001: ANSWER-1 — ответ Оператора")
        with mock.patch.object(gitcmd, "ls_tree_files",
                               return_value=["tasks/T001/ANSWER-1.md"]), \
                mock.patch.object(gitcmd, "show",
                                  return_value=(answer_text, "")), \
                mock.patch.object(gitcmd, "git", git_fake):
            mandate = fsm_advance._answer_zones_mandate("task/t001-x", "T001")
        self.assertEqual(mandate, {"docs/extra_module.md"})


class ZonesGateMandateWithoutPlanSectionTest(TmpRootTest):
    """SPEC 01M2XFSNVGWA2VX5XFEYR93Y4Z, требования 1-2 (AC-1/AC-2): гейт
    зон различает «мандат Оператора покрывает все пути вне зон, раздел
    «## Расширение зон» PLAN.md не оформлен» (своё действие
    `ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION`, перечень путей мандата в
    тексте, подсказка «оформи раздел PLAN») и обычный отказ «вне зон»
    (мандата нет / покрыты не все пути — прежние действие, текст и
    подсказка байт-в-байт). Мандат подменяется на уровне
    `_answer_zones_mandate` — происхождение ANSWER-файла проверяют
    `AnswerZonesMandateOriginTest` выше и планка приёмки задачи."""

    OUT_OF_ZONE = "docs/extra_module.md"
    PLAN_WITH_SECTION = ("PLAN\n\n## Расширение зон\n\nПути: {paths}\n\n"
                         "Обоснование: нужно.\n")
    OLD_ACTION = "переход отклонён: гейт зон"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        store.insert_task(self.conn, self.task_id, "Тест", "in_dev",
                          "task/t001-x", config.DEFAULT_TARGET, 10.0)
        store.update_task(self.conn, self.task_id, zones="orchestrator/store.py")
        self.t = {"title": "Тест", "branch": "task/t001-x",
                 "zones": "orchestrator/store.py", "zones_extension": None}

    def _gate(self, plan_text: str, mandate: set, files: list) -> tuple:
        """(отказал ли гейт, stdout, последняя запись (action, detail))."""
        empty_status = subprocess.CompletedProcess([], 0, "", "")
        result = []
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_base_source",
                               return_value="локальной main"), \
             mock.patch.object(gitcmd, "diff_names", return_value=list(files)), \
             mock.patch.object(gitcmd, "in_repo", return_value=empty_status), \
             mock.patch.object(zones, "_answer_zones_mandate",
                               return_value=set(mandate)):
            out = self.capture(lambda: result.append(
                fsm_advance._zones_gate_refuses(
                    self.conn, self.task_id, self.t, "task/t001-x", plan_text)))
        rows = [(r["action"], r["detail"]) for r in self.conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,))]
        last = rows[-1] if rows else (None, None)
        return result[0], out, last

    def _old_detail(self, files: list) -> str:
        return (f"дифф трогает файлы вне заявленных zones и COMMON_ZONES "
                f"(база сравнения deadbeef от локальной main): "
                f"{', '.join(files)}")

    def _old_hint(self) -> str:
        return (f"  дальше: сократи дифф до заявленных zones либо оформи раздел "
                f"«## Расширение зон» в PLAN.md с обоснованием и мандатом "
                f"Оператора («Расширение зон разрешено: <пути>» в ANSWER-n.md), "
                f"и повтори artel.py advance {self.task_id}")

    def test_missing_plan_section_with_full_mandate_refuses_with_named_action(self):
        """Раздела «## Расширение зон» нет, мандат покрывает единственный
        путь вне зон — действие отказа отдельное, в тексте перечислены
        пути мандата и причина «отсутствует», подсказка называет раздел
        PLAN.md со строкой «Пути:» мандата.

        Ловит мутацию: чтение мандата оставлено внутри ветки
        `if extension_paths is not None` — без раздела гейт вовсе не
        читает `_answer_zones_mandate` и журналирует прежнее «переход
        отклонён: гейт зон» (инцидент 13.09)."""
        refuses, out, (action, detail) = self._gate(
            "PLAN\n", {self.OUT_OF_ZONE}, [self.OUT_OF_ZONE])

        self.assertTrue(refuses)
        self.assertEqual(action, zones.ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION)
        self.assertNotEqual(action, self.OLD_ACTION)
        self.assertIn(f"Расширение зон разрешено: {self.OUT_OF_ZONE}", detail)
        self.assertIn("отсутствует", detail)
        self.assertIn(f"  дальше: оформи раздел «## Расширение зон» в PLAN.md: "
                      f"строка «Пути: {self.OUT_OF_ZONE}»", out)

    def test_plan_section_mismatching_the_mandate_refuses_with_named_action(self):
        """Раздел есть, но его `Пути:` называют другой путь — тот же
        именованный отказ, в тексте — и путь мандата, и пути раздела.

        Ловит мутацию: различение прикручено только к `extension_paths
        is None` — опечатка в строке `Пути:` снова давала бы отказ класса
        «нужны руки Оператора»."""
        refuses, out, (action, detail) = self._gate(
            self.PLAN_WITH_SECTION.format(paths="docs/another.md"),
            {self.OUT_OF_ZONE}, [self.OUT_OF_ZONE])

        self.assertTrue(refuses)
        self.assertEqual(action, zones.ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION)
        self.assertIn("не совпадает с мандатом (в разделе: docs/another.md)",
                      detail)
        self.assertIn(self.OUT_OF_ZONE, detail)
        self.assertIn("оформи раздел «## Расширение зон» в PLAN.md", out)

    def test_mandate_by_directory_prefix_covers_the_file(self):
        """Мандат на директорию `docs/` покрывает файл под ней — та же
        формула префикса `_touches_zone`, что у исключения AC-3.

        Ловит мутацию: покрытие мандатом сверяется равенством строк
        вместо префикса — мандат на директорию не засчитывался бы, и
        отказ уходил бы в прежний класс."""
        refuses, _out, (action, _detail) = self._gate(
            "PLAN\n", {"docs/"}, [self.OUT_OF_ZONE])

        self.assertTrue(refuses)
        self.assertEqual(action, zones.ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION)

    def test_named_refusal_leaves_zones_extension_untouched(self):
        """Именованный отказ не легализует пути в БД: `zones_extension`
        обновляется по-прежнему только совпадающим разделом PLAN.

        Ловит мутацию: новая ветка «заодно» пишет `zones_extension` по
        мандату — следующий advance прошёл бы без раздела PLAN вовсе."""
        self._gate("PLAN\n", {self.OUT_OF_ZONE}, [self.OUT_OF_ZONE])

        row = self.conn.execute("SELECT zones_extension FROM tasks WHERE id=?",
                                (self.task_id,)).fetchone()
        self.assertIsNone(row["zones_extension"])

    def test_no_mandate_keeps_the_old_refusal_byte_for_byte(self):
        """Мандата нет — прежние действие, текст и подсказка дословно.

        Ловит мутацию: новая ветка срабатывает на одном факте «раздела
        нет» (без сверки покрытия мандатом) — задача без мандата
        получала бы мягкий отказ и гоняла бы developer по кругу."""
        refuses, out, (action, detail) = self._gate(
            "PLAN\n", set(), [self.OUT_OF_ZONE])

        self.assertTrue(refuses)
        self.assertEqual(action, self.OLD_ACTION)
        self.assertEqual(detail, self._old_detail([self.OUT_OF_ZONE]))
        self.assertIn(self._old_hint(), out)

    def test_mandate_covering_only_part_of_the_paths_keeps_the_old_refusal(self):
        """Мандат покрывает один из двух путей вне зон — прежний отказ
        байт-в-байт, оба пути в тексте.

        Ловит мутацию: покрытие сверяется `any` вместо `all` —
        непокрытый путь молча получал бы мягкий класс отказа."""
        files = [self.OUT_OF_ZONE, "docs/uncovered.md"]

        refuses, out, (action, detail) = self._gate(
            "PLAN\n", {self.OUT_OF_ZONE}, files)

        self.assertTrue(refuses)
        self.assertEqual(action, self.OLD_ACTION)
        self.assertEqual(detail, self._old_detail(files))
        self.assertIn(self._old_hint(), out)

    def test_matching_plan_section_with_mandate_still_passes(self):
        """Контроль: раздел совпадает с мандатом — исключение AC-3 как и
        раньше пропускает переход и легализует путь в `zones_extension`.

        Ловит мутацию: новая ветка стоит ДО исключения AC-3 и
        перехватывает уже оформленный раздел — задача не выходила бы из
        `in_dev` даже после честно оформленного раздела."""
        refuses, _out, _row = self._gate(
            self.PLAN_WITH_SECTION.format(paths=self.OUT_OF_ZONE),
            {self.OUT_OF_ZONE}, [self.OUT_OF_ZONE])

        self.assertFalse(refuses)
        row = self.conn.execute("SELECT zones_extension FROM tasks WHERE id=?",
                                (self.task_id,)).fetchone()
        self.assertEqual(row["zones_extension"], self.OUT_OF_ZONE)


if __name__ == "__main__":
    unittest.main()
