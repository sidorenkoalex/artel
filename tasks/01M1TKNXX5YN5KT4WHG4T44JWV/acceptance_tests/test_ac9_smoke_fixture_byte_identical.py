"""AC-9 (tasks/01M1TKNXX5YN5KT4WHG4T44JWV/SPEC.md): три сценария (отказ
гейта ёмкости, отказ гейта зон, отказ рубежа «замечания ревью не
отработаны» регрессий №13/№15) дают тот же журнал (`store.journal`) и
вывод stdout, байт-в-байт, что и ДО рефакторинга.

Фикстура (строки-константы `_EXPECTED_*` ниже) снята прогоном РОВНО этих
трёх сценариев на сегодняшнем (нерефакторенном) `orchestrator/
fsm_advance.py` — `_capacity_gate_refuses`/`_zones_gate_refuses`/
`_review_rework_gate_refuses` вызваны напрямую, теми же сигнатурами и
теми же данными, что уже используют `tests/test_capacity_gate.py::
CapacityGateTwoNumbersMessageTest.
test_refusal_message_names_code_size_and_artifacts_size_separately` и
`tests/test_fsm_review_rework_gate.py::ReviewReworkGateFallbackTest.
test_falls_back_to_last_review_md_commit_and_still_refuses` — не
изобретены заново, чтобы не разойтись со смыслом уже существующих
планок этих гейтов.

Зелёный с рождения: фикстура снята буквальным прогоном ЭТОГО ЖЕ кода
(требование 6/AC-9 «фикстура снимается до правки кода») — сравнение
результата с самим собой обязано совпасть уже сегодня; он становится
содержательной планкой только ПОСЛЕ рефакторинга — тогда он либо
останется зелёным (поведение сохранено байт-в-байт), либо покраснеет на
реальном расхождении.
"""
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm_advance, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

# `TmpRootTest` (не голый `unittest.TestCase` + `store.db()`) — изоляция во
# временный `config.DB` обязательна: без неё прогон пишет тестовые строки
# T001/T002 в РЕАЛЬНУЮ БД оркестратора этого воркспейса (найдено при
# написании этого файла — `store.db()` без патча путей `config`
# возвращает ту же БД, что ведёт настоящие задачи пульта).


def _run(fn) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        result = fn()
    return result, buf.getvalue()


class Ac9CapacityGateSmokeTest(TmpRootTest):
    """Сценарий 1 — отказ гейта ёмкости, тот же ввод, что `tests/
    test_capacity_gate.py::CapacityGateTwoNumbersMessageTest.
    test_refusal_message_names_code_size_and_artifacts_size_separately`."""

    _EXPECTED_DETAIL = (
        "снимок не помещается в один контекст ревью — разделить задачу "
        "(T001 «Тест двух цифр»): diff кода 300000 байт > потолка 262144 "
        "байт (исключённые артефакты tasks/T001/: 500 байт)")
    _EXPECTED_ACTION = "переход отклонён: гейт ёмкости diff"
    _EXPECTED_STDOUT = (
        "[T001] переход отклонён: снимок не помещается в один контекст "
        "ревью — разделить задачу (T001 «Тест двух цифр»): diff кода "
        "300000 байт > потолка 262144 байт (исключённые артефакты "
        "tasks/T001/: 500 байт)\n"
        "  дальше: решение Оператора — разделить задачу или поднять "
        "потолок (ADR-0002)\n")

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.t = {"title": "Тест двух цифр", "branch": "task/t001-x"}

    def test_ac9_capacity_gate_journal_and_stdout_match_the_pre_refactor_snapshot(self):
        """Ловит мутацию: рефакторинг переставил порядок «код»/«артефакты»
        в тексте отказа, изменил формулировку причины или обнулил
        подсказку — итоговые строки журнала/stdout разойдутся с фикстурой
        хотя бы одним символом.
        """
        code_body = "x" * 300_000
        artifacts_body = "y" * 500
        tasks_prefix = f"tasks/{self.task_id}/"

        def git_diff(*args):
            if args and args[0] == "diff":
                if f":!{tasks_prefix}" in args:
                    return subprocess.CompletedProcess(list(args), 0, code_body, "")
                if tasks_prefix in args:
                    return subprocess.CompletedProcess(list(args), 0, artifacts_body, "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", git_diff):
            refused, out = _run(lambda: fsm_advance._capacity_gate_refuses(
                self.conn, self.task_id, self.t, "in_dev"))

        self.assertTrue(refused)
        self.assertEqual(out, self._EXPECTED_STDOUT)
        rows = [(r["actor"], r["action"], r["detail"]) for r in self.conn.execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,))]
        self.assertEqual(
            rows, [("fsm", self._EXPECTED_ACTION, self._EXPECTED_DETAIL)])


class Ac9ZonesGateSmokeTest(TmpRootTest):
    """Сценарий 2 — отказ гейта зон: файл вне заявленных `zones` и
    `COMMON_ZONES`."""

    _EXPECTED_DETAIL = (
        "дифф трогает файлы вне заявленных zones и COMMON_ZONES: "
        "docs/other.py")
    _EXPECTED_ACTION = "переход отклонён: гейт зон"
    _EXPECTED_STDOUT = (
        "[T002] переход отклонён: дифф трогает файлы вне заявленных "
        "zones и COMMON_ZONES: docs/other.py\n"
        "  дальше: сократи дифф до заявленных zones либо оформи раздел "
        "«## Расширение зон» в PLAN.md с обоснованием и мандатом "
        "Оператора («Расширение зон разрешено: <пути>» в ANSWER-n.md), "
        "и повтори artel.py advance T002\n")

    def setUp(self):
        super().setUp()
        from orchestrator import config
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T002"
        store.insert_task(self.conn, self.task_id, "Тест гейта зон",
                          "in_dev", "task/t002-x", config.DEFAULT_TARGET, 10.0)
        self.t = {"title": "Тест гейта зон", "branch": "task/t002-x",
                 "zones": "orchestrator/store.py", "zones_extension": None}

    def test_ac9_zones_gate_journal_and_stdout_match_the_pre_refactor_snapshot(self):
        """Ловит мутацию: рефакторинг сменил формулировку списка
        нарушенных путей или подсказку про «## Расширение зон» —
        расхождение хотя бы одним символом провалит сравнение.
        """
        with mock.patch.object(gitcmd, "diff_names",
                              return_value=["docs/other.py"]):
            refused, out = _run(lambda: fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, self.t, "task/t002-x", "PLAN\n"))

        self.assertTrue(refused)
        self.assertEqual(out, self._EXPECTED_STDOUT)
        rows = [(r["actor"], r["action"], r["detail"]) for r in self.conn.execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,))]
        self.assertEqual(
            rows, [("fsm", self._EXPECTED_ACTION, self._EXPECTED_DETAIL)])


class Ac9ReviewReworkGateSmokeTest(TmpRootTest):
    """Сценарий 3 — отказ рубежа «замечания ревью не отработаны»
    (регрессии №13/№15), тот же ввод, что `tests/test_fsm_review_rework_
    gate.py::ReviewReworkGateFallbackTest.
    test_falls_back_to_last_review_md_commit_and_still_refuses`."""

    TASK_ID = "T001"
    BRANCH = "artifact/t001"
    CODE_BRANCH = "task/t001-x"
    REVIEW_MD_CHANGES_REQUESTED = (
        "---\ntask: T001\ntype: review\nauthor_role: reviewer\n"
        "status: changes_requested\niteration: 1\nschema_version: 1\n---\n\n"
        "# REVIEW\n")

    _EXPECTED_DETAIL = (
        "замечания ревью не отработаны: нет шага developer после "
        "итерации 1 (опорное время 2026-08-01T10:00:00+00:00 — последний "
        "коммит REVIEW.md; последний коммит developer "
        "2026-07-31T10:00:00+00:00)")
    _EXPECTED_ACTION = "переход отклонён: замечания ревью не отработаны"
    _EXPECTED_STDOUT = (
        "[T001] переход отклонён: замечания ревью не отработаны: нет "
        "шага developer после итерации 1 (опорное время "
        "2026-08-01T10:00:00+00:00 — последний коммит REVIEW.md; "
        "последний коммит developer 2026-07-31T10:00:00+00:00)\n"
        "  дальше: почини код (не спорь с ревью втихую) и повтори "
        "artel.py advance T001\n")

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.t = {"branch": self.CODE_BRANCH}

    @staticmethod
    def _log_reply(subject: str, when: str) -> str:
        return f"{when}\x1f{subject}\n"

    def _fake_git(self, developer_commit_line: str):
        def fake(*args):
            if args[0] == "log" and "-1" in args:
                return subprocess.CompletedProcess(
                    list(args), 0, "2026-08-01T10:00:00+00:00\n", "")
            if args[0] == "log" and "--" in args:
                return subprocess.CompletedProcess(
                    list(args), 0,
                    self._log_reply("T001: правка REVIEW.md вручную",
                                   "2026-08-03T10:00:00+00:00"), "")
            if args[0] == "log":
                return subprocess.CompletedProcess(
                    list(args), 0, developer_commit_line, "")
            return subprocess.CompletedProcess(list(args), 0, "", "")
        return fake

    def test_ac9_review_rework_gate_journal_and_stdout_match_the_pre_refactor_snapshot(self):
        """Ловит мутацию: рефакторинг потерял источник опорного времени
        («последний коммит REVIEW.md») из текста отказа, изменил порядок
        дат в сообщении или подсказку «почини код...» — расхождение хотя
        бы одним символом провалит сравнение.
        """
        developer_before_fallback = self._log_reply(
            "код фикса", "2026-07-31T10:00:00+00:00")

        with mock.patch.object(gitcmd, "show",
                              lambda *a: (self.REVIEW_MD_CHANGES_REQUESTED, "")), \
                mock.patch.object(gitcmd, "git",
                                  self._fake_git(developer_before_fallback)):
            refused, out = _run(lambda: fsm_advance._review_rework_gate_refuses(
                self.conn, self.TASK_ID, self.t, self.BRANCH))

        self.assertTrue(refused)
        self.assertEqual(out, self._EXPECTED_STDOUT)
        rows = [(r["actor"], r["action"], r["detail"]) for r in self.conn.execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK_ID,))]
        self.assertEqual(
            rows, [("fsm", self._EXPECTED_ACTION, self._EXPECTED_DETAIL)])


if __name__ == "__main__":
    unittest.main()
