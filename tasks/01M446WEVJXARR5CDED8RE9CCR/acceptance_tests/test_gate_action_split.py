"""Причины разных классов у одного гейта журналируются разными действиями.

Гейт заявки мутации, прогон приёмки на выходе `in_dev`, проверка
долгоживущих файлов на выходе `tests_writing` и узлы чтения документов с
ветки разводят причину, которую чинит роль, и причину, которую чинит
Оператор (сбой git, рабочая копия, чужой документ), по разным действиям
журнала. Класс действия виден по реакции цикла `auto`: на причине роли он
запускает шаг роли с текстом отказа в брифе, на причине Оператора —
останавливается на первом же отказе без шага роли, называя действие.

Группа: разовый
Красен до реализации: сегодня сбой git гейта заявки мутации, «рабочая копия задачи не заведена» прогона приёмки, сбой git проверки долгоживущих файлов и непрочитанный QUESTIONS.md/ANSWER-*.md/SPEC.md журналируются тем же действием, что и причина роли, а `auto` в `in_dev` не запускает developer на «гейт заявки мутации»/«приёмочные тесты» — AC-5, AC-6, AC-7, AC-8 падают.

Публичная поверхность: переход — настоящий `fsm.cmd_advance` в лёгкой
песочнице переходов (`tests/sandbox.py::LightTransitionSandbox`); git
задачи — подменённые публичные `gitcmd.diff_base`/`diff_names`/
`diff_name_status`/`branch_exists`/`show`/`ls_tree_files`; рабочая копия —
`workspace.ensure`/`workspace.on_task_branch`; прогон планки —
`acceptance.run`. Цикл — `auto.cmd_auto(<id>)` с подменённым шагом роли
(`runner.cmd_run` журналирует `agent run finished` под ролью шага и
запоминает блок истории отказов брифа `brief.advance_refusal_history`).
Имена файлов, хвосты и причины сбоев случайны; зерно печатается и входит в
текст провала.

Файл подменяет примитивы git задачи (`gitcmd`) — правило долгоживущих
файлов `tests/` отводит такие файлы в разовую группу планки, хотя предмет
проверки — поведение гейтов.

Сбой git гейта заявки мутации берётся на чтении файла теста: сбой базы
сравнения или списка файлов диффа раньше отказывает гейт ёмкости diff (он
стоит перед гейтом заявки мутации и читает тот же дифф).
"""
import random
import signal
import unittest
from unittest import mock

from orchestrator import (acceptance, auto, brief, config, fsm, github_adapter,
                          gitcmd, runner, store, workspace)
from tests.sandbox import (LightTransitionSandbox, capture,
                           disk_backed_ls_tree_files, disk_backed_show,
                           make_project_repo)

PREFIX = "переход отклонён"
MUTATION = "переход отклонён: гейт заявки мутации"
ACCEPTANCE = "переход отклонён: приёмочные тесты"
LONG_LIVED = "переход отклонён: долгоживущие файлы tests/"
TREE = "переход отклонён: дерево не на ветке задачи"
STOP_ACTION = "auto остановлен"
BASE_SHA = "b" * 40

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: сценарий

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

QUESTIONS_READY = """---
task: {task}
type: questions
author_role: analyst
status: ready
schema_version: 2
---

# QUESTIONS: сценарий

## Вопросы
1. **Вопрос сценария** — варианты: A) да; B) нет — дефолт: A.
"""

#: Файл планки, проходящий трассируемость единственного AC-1 SPEC песочницы.
PLANK_FILE = '''"""Планка сценария.

Группа: разовый
Зелёный с рождения: заглушка сценария.
"""
import unittest


class PlankTest(unittest.TestCase):
    def test_ac1_scenario(self):
        """Сценарий.

        Ловит мутацию: заглушка.
        """
'''

TEST_WITHOUT_CLAIM = '''def {name}():
    """Сценарий без заявки."""
    assert True
'''


class RecordingStep:
    """Подмена `runner.cmd_run`: роль, состояние и блок истории отказов
    брифа на момент шага; журналирует успешное завершение шага."""

    def __init__(self, conn):
        self.conn = conn
        self.steps: list = []

    def __call__(self, task_id, *args, **kwargs) -> None:
        task_id = store.resolve_task_id(self.conn, task_id)
        if len(self.steps) > config.AUTO_MAX_STEPS:
            raise AssertionError("цикл не остановился")
        t = store.get_task(self.conn, task_id)
        role = runner.step_role(t)
        self.steps.append({"role": role, "brief": brief.advance_refusal_history(
            self.conn, task_id, role, t["state"])})
        store.journal(self.conn, task_id, role, "agent run finished",
                      "rc=0, тестовая заглушка шага роли")


class GateActionSplitSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.step = RecordingStep(self.conn)
        self.patch(runner, "cmd_run", self.step)
        self.tdir.mkdir(parents=True, exist_ok=True)
        # Чтения пути вне документов задачи (`tests/…`) и перечень `tests`
        # отвечают сценарию; остальное — диск, как у песочницы.
        self.test_tree: list = []
        self.unreadable: set = set()
        self.unlistable: set = set()
        self.patch(gitcmd, "show", self.show)
        self.patch(gitcmd, "ls_tree_files", self.ls_tree_files)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def note(self, extra: str) -> str:
        return f"зерно: {self.seed}; {extra}"

    def tail(self) -> str:
        return f"{self.rng.randrange(1 << 40):x}"

    def show(self, branch, rel, *, repo=None):
        if rel in self.unreadable:
            return None, "git не ответил"
        if rel.startswith("tests/"):
            if branch == BASE_SHA:
                return None, "пути нет в базе"
            path = config.ROOT / rel
            return (path.read_text(encoding="utf-8"), "") if path.is_file() \
                else (None, "пути нет")
        return disk_backed_show(branch, rel, repo=repo)

    def ls_tree_files(self, branch, rel, *, repo=None):
        if any(rel == item or rel.endswith("/" + item) for item in self.unlistable):
            return None
        if rel == "tests":
            return list(self.test_tree)
        return disk_backed_ls_tree_files(branch, rel, repo=repo)

    # ------------------------------------------------------------ сценарии

    def in_dev_with_diff(self, files: list) -> None:
        """`in_dev`, PLAN.md ready, зоны покрывают `tests/`, дифф кодовой
        ветки — `files` (лок `acceptance_tests/` видит пустой дифф)."""
        store.update_task(self.conn, self.TASK, zones="tests/")
        (self.tdir / "PLAN.md").write_text(PLAN_READY.format(task=self.TASK),
                                           encoding="utf-8")
        self.set_state("in_dev")
        self.patch(gitcmd, "diff_base", lambda branch, repo=None: BASE_SHA)
        self.patch(gitcmd, "diff_names",
                   lambda base, branch, *rest, repo=None: [] if rest else list(files))

    def new_test_file(self) -> str:
        name = f"test_scenario_{self.tail()}"
        rel = f"tests/{name}.py"
        (config.ROOT / "tests").mkdir(parents=True, exist_ok=True)
        (config.ROOT / rel).write_text(
            TEST_WITHOUT_CLAIM.format(name=f"test_{self.tail()}"), encoding="utf-8")
        self.test_tree.append(rel)
        return rel

    def write_spec_and_plank(self) -> None:
        self.write_acceptance_plank()
        (self.tdir / "acceptance_tests" / "test_stub.py").write_text(
            PLANK_FILE, encoding="utf-8")

    def enter_tests_writing(self, entries) -> None:
        self.write_spec_and_plank()
        self.set_state("tests_writing")
        self.patch(gitcmd, "branch_exists", lambda branch, repo=None: True)
        self.patch(gitcmd, "diff_base", lambda branch, repo=None: BASE_SHA)
        self.patch(gitcmd, "diff_name_status",
                   lambda base, branch, repo=None: entries)

    def spec_writing_with_questions(self) -> None:
        (self.tdir / "TZ.md").write_text("# ТЗ сценария\n", encoding="utf-8")
        (self.tdir / "QUESTIONS.md").write_text(
            QUESTIONS_READY.format(task=self.TASK), encoding="utf-8")
        self.set_state("spec_writing")

    # ------------------------------------------------------------ наблюдения

    def advance_once(self) -> tuple:
        """Один настоящий `advance`: (действие, подробность) первого отказа,
        журналированного этим вызовом, либо (None, None)."""
        before = len(store.task_steps(self.conn, self.TASK))
        out = capture(fsm.cmd_advance, self.TASK)
        for row in store.task_steps(self.conn, self.TASK)[before:]:
            if row["actor"] == "fsm" and row["action"].startswith(PREFIX):
                return row["action"], row["detail"] or "", out
        return None, None, out

    def run_auto(self) -> str:
        return capture(auto.cmd_auto, self.TASK)

    def stop_detail(self) -> str | None:
        details = [row["detail"] for row in store.task_steps(self.conn, self.TASK)
                   if row["action"] == STOP_ACTION]
        return details[-1] if details else None

    def assert_operator_class(self, action: str, why: str) -> None:
        """Цикл `auto` на этом отказе: ни одного шага роли, остановка,
        причина называет действие."""
        state = self.state()
        out = self.run_auto()
        self.assertEqual(len(self.step.steps), 0, self.note(
            f"{why}: на отказе «{action}» запущен шаг роли\n{out}"))
        detail = self.stop_detail()
        self.assertIsNotNone(detail, self.note(f"{why}: цикл не остановлен\n{out}"))
        self.assertIn(action, detail, self.note(
            f"{why}: причина остановки {detail!r}\n{out}"))
        self.assertEqual(self.state(), state, self.note(why))

    def assert_role_class(self, action: str, needle: str, role: str, why: str) -> None:
        """Цикл `auto` на этом отказе: запущен шаг `role`, бриф первого шага
        несёт действие и `needle` из подробности."""
        out = self.run_auto()
        self.assertGreaterEqual(len(self.step.steps), 1, self.note(
            f"{why}: на отказе «{action}» шаг роли не запущен\n{out}"))
        first = self.step.steps[0]
        self.assertEqual(first["role"], role, self.note(why))
        self.assertIn(action, first["brief"], self.note(
            f"{why}: бриф шага не несёт действие отказа"))
        self.assertIn(needle, first["brief"], self.note(
            f"{why}: бриф шага не несёт подробность отказа"))

    def assert_split_action(self, action, base: str, why: str, out: str) -> None:
        self.assertIsNotNone(action, self.note(f"{why}: отказа нет\n{out}"))
        self.assertTrue(action.startswith(PREFIX + ":"), self.note(
            f"{why}: действие {action!r} без префикса «{PREFIX}:»"))
        self.assertNotEqual(action, base, self.note(
            f"{why}: причина Оператора журналирована действием причины роли"))


class MutationClaimGateSplitTest(GateActionSplitSandbox):

    def test_ac5_missing_claim_runs_the_developer_with_the_refusal(self):
        """Тест в `tests/` без заявки «Ловит мутацию» — прежнее действие, шаг developer с ним в брифе.

        Сценарий: `in_dev`, PLAN.md ready, дифф кодовой ветки несёт новый
        файл `tests/test_scenario_<случайно>.py` с тестом без заявки.
        Настоящий `advance` журналирует «переход отклонён: гейт заявки
        мутации» с путём файла; цикл `auto` запускает developer, и бриф шага
        несёт это действие и путь файла.

        Ловит мутацию: отказ гейта заявки мутации остался в классе «чинит
        Оператор» — цикл останавливается без шага developer (прецедент
        04.10.2026); либо причина роли переименована вместе со сбоем git —
        действие отказа другое.
        """
        rel = self.new_test_file()
        self.in_dev_with_diff([rel])
        action, detail, out = self.advance_once()
        self.assertEqual(action, MUTATION, self.note(f"действие {action!r}\n{out}"))
        self.assertIn(rel, detail, self.note(detail))
        self.assert_role_class(MUTATION, rel, "developer", f"нет заявки, {rel}")

    def test_ac5_git_failure_is_another_action_and_stops_auto(self):
        """Сбой git гейта заявки мутации — другое действие, `auto` стоит без шага developer.

        Сценарий: `in_dev`, PLAN.md ready, дифф несёт файл
        `tests/test_scenario_<случайно>.py`, он есть в дереве ветки, но git
        не отвечает на его чтение. Настоящий `advance` журналирует отказ
        «переход отклонён: …» с действием, отличным от «гейт заявки
        мутации», с путём файла в подробности; цикл `auto` останавливается
        на первом отказе без шага developer, причина называет действие.

        Ловит мутацию: сбой git оставлен под прежним действием гейта
        заявки мутации — действие совпадает с причиной роли, и `auto`
        жжёт шаг developer на сбое, которого роль не чинит.
        """
        rel = self.new_test_file()
        self.unreadable.add(rel)
        self.in_dev_with_diff([rel])
        action, detail, out = self.advance_once()
        why = f"сбой чтения {rel}"
        self.assert_split_action(action, MUTATION, why, out)
        self.assertIn(rel, detail, self.note(detail))
        self.assert_operator_class(action, why)


class AcceptanceRunSplitTest(GateActionSplitSandbox):

    def test_ac6_red_plank_is_role_class(self):
        """Красная планка на выходе `in_dev` — «переход отклонён: приёмочные тесты», класс «чинит роль».

        Сценарий: `in_dev`, PLAN.md ready, планка в источнике есть, прогон
        `acceptance.run` красный со случайным хвостом. Настоящий `advance`
        журналирует «переход отклонён: приёмочные тесты» с хвостом прогона;
        цикл `auto` запускает developer, и бриф шага несёт это действие и
        хвост.

        Ловит мутацию: красная планка осталась в классе «чинит Оператор» —
        `auto` останавливается без шага developer; либо красная планка
        получила новое действие вместо прежнего.
        """
        tail = f"FAILED test_ac1_scenario {self.tail()}"
        self.write_acceptance_plank()
        self.in_dev_with_diff([])
        self.patch(acceptance, "run", lambda *args, **kwargs: (False, tail))
        action, detail, out = self.advance_once()
        self.assertEqual(action, ACCEPTANCE, self.note(f"действие {action!r}\n{out}"))
        self.assertIn(tail, detail, self.note(detail))
        self.assert_role_class(ACCEPTANCE, tail, "developer", "красная планка")

    def test_ac6_missing_code_copy_is_another_operator_action(self):
        """Рабочая копия задачи не заведена — другое действие класса «чинит Оператор».

        Сценарий: задача внешнего проекта в `in_dev`, PLAN.md ready, планка
        в источнике есть, `workspace.ensure` отказывает случайной причиной.
        Настоящий `advance` журналирует отказ «переход отклонён: …» с
        действием, отличным от «приёмочные тесты», с причиной `ensure` в
        подробности; прогон планки не запускается; цикл `auto`
        останавливается на первом отказе без шага developer.

        Ловит мутацию: «рабочая копия задачи не заведена» осталась под
        действием красной планки — `auto` запускает developer, который
        рабочую копию не заведёт.
        """
        reason = f"клон проекта не заведён: {self.tail()}"
        make_project_repo("ext-scenario")
        store.update_task(self.conn, self.TASK, target="ext-scenario")
        self.write_acceptance_plank()
        self.in_dev_with_diff([])
        self.patch(github_adapter, "ensure_draft_mr", lambda *args, **kwargs: None)
        self.patch(workspace, "ensure",
                   lambda task_id, branch, target=None: (None, reason))
        runs = mock.Mock(return_value=(True, ""))
        self.patch(acceptance, "run", runs)
        action, detail, out = self.advance_once()
        why = "рабочая копия не заведена"
        self.assert_split_action(action, ACCEPTANCE, why, out)
        self.assertIn(reason, detail, self.note(detail))
        runs.assert_not_called()
        self.assert_operator_class(action, why)


class LongLivedFilesSplitTest(GateActionSplitSandbox):

    def test_ac7_rule_violation_is_role_class(self):
        """Правка/удаление/переименование файла `tests/` — прежнее действие, класс «чинит роль».

        Сценарий: `tests_writing`, планка проходит трассируемость, дифф
        кодовой ветки несёт запись случайного вида — правка, удаление или
        переименование существующего файла `tests/test_<случайно>.py`.
        Настоящий `advance` журналирует «переход отклонён: долгоживущие файлы
        tests/» с путём; цикл `auto` запускает test_author с этим отказом в
        брифе.

        Ловит мутацию: нарушение правила отнесено к классу «чинит Оператор»
        либо получило новое действие — `auto` останавливается без шага
        test_author.
        """
        rel = f"tests/test_existing_{self.tail()}.py"
        status = self.rng.choice(["M", "D", "R100"])
        entry = (status, rel, f"tests/test_renamed_{self.tail()}.py"
                 if status.startswith("R") else None)
        self.enter_tests_writing([entry])
        action, detail, out = self.advance_once()
        why = f"запись {entry}"
        self.assertEqual(action, LONG_LIVED, self.note(
            f"{why}: действие {action!r}\n{out}"))
        self.assertIn(rel, detail, self.note(detail))
        self.assert_role_class(LONG_LIVED, rel, "test_author", why)

    def test_ac7_git_failure_is_another_operator_action(self):
        """Сбой git той же проверки — другое действие класса «чинит Оператор».

        Сценарий: `tests_writing`, кодовая ветка есть, git не отвечает на
        дифф кодовой ветки против базы. Настоящий `advance` журналирует отказ
        «переход отклонён: …» с действием, отличным от «долгоживущие файлы
        tests/»; цикл `auto` останавливается на первом отказе без шага
        test_author.

        Ловит мутацию: сбой git оставлен под действием нарушения правила —
        `auto` запускает test_author на сбое, который роль не чинит.
        """
        self.enter_tests_writing(None)
        action, _detail, out = self.advance_once()
        why = "дифф кодовой ветки не прочитан"
        self.assert_split_action(action, LONG_LIVED, why, out)
        self.assert_operator_class(action, why)


class TreeNotOnBranchSplitTest(GateActionSplitSandbox):

    def test_ac8_own_artifact_unread_keeps_the_tree_action(self):
        """Артефакт роли текущего состояния не прочитан с ветки — «дерево не на ветке задачи».

        Сценарий: `in_dev`, PLAN.md на ветке нет. Настоящий `advance`
        журналирует «переход отклонён: дерево не на ветке задачи».

        Ловит мутацию: разделение действий задело и чтение артефакта своей
        роли — PLAN.md `in_dev` получил действие класса «чинит Оператор».
        """
        self.set_state("in_dev")
        action, detail, out = self.advance_once()
        self.assertEqual(action, TREE, self.note(f"действие {action!r}\n{out}"))
        self.assertIn("PLAN.md", detail, self.note(detail))

    def test_ac8_branch_listing_failure_is_operator_action(self):
        """git не ответил на перечисление ветки — другое действие, `auto` стоит без шага.

        Сценарий: `spec_writing` с ТЗ (роль analyst), git не отвечает на
        перечисление QUESTIONS.md на ветке. Настоящий `advance` журналирует
        отказ «переход отклонён: …» с действием, отличным от «дерево не на
        ветке задачи»; цикл `auto` останавливается на первом отказе без шага
        analyst.

        Ловит мутацию: сбой перечисления оставлен под действием «дерево не
        на ветке задачи» — подкласс «роль ещё не закончила» запускает
        analyst на сбое git.
        """
        (self.tdir / "TZ.md").write_text("# ТЗ сценария\n", encoding="utf-8")
        self.set_state("spec_writing")
        self.unlistable.add("QUESTIONS.md")
        action, _detail, out = self.advance_once()
        why = "перечисление QUESTIONS.md"
        self.assert_split_action(action, TREE, why, out)
        self.assert_operator_class(action, why)

    def test_ac8_answer_count_failure_is_operator_action(self):
        """git не ответил на подсчёт `ANSWER-*.md` — другое действие, `auto` стоит без шага.

        Сценарий: `spec_writing`, батч QUESTIONS.md готов, git не отвечает
        на перечисление каталога задачи (подсчёт ANSWER-*.md перед
        эскалацией). Настоящий `advance` журналирует отказ «переход отклонён:
        …» с действием, отличным от «дерево не на ветке задачи», задача не
        эскалирует; цикл `auto` останавливается без шага analyst.

        Ловит мутацию: сбой подсчёта ANSWER-*.md оставлен под действием
        «дерево не на ветке задачи» — `auto` запускает analyst.
        """
        self.spec_writing_with_questions()
        self.unlistable.add(self.TASK)
        action, _detail, out = self.advance_once()
        why = "подсчёт ANSWER-*.md"
        self.assert_split_action(action, TREE, why, out)
        self.assertEqual(self.state(), "spec_writing", self.note(out))
        self.assert_operator_class(action, why)

    def test_ac8_foreign_document_unread_is_operator_action(self):
        """Не прочитан документ другой роли (SPEC.md на выходе `in_dev`) — другое действие.

        Сценарий: `in_dev`, PLAN.md ready, рабочая копия на ветке задачи,
        планки в источнике нет и SPEC.md на ветке нет — поиск планки читает
        SPEC.md. Настоящий `advance` журналирует отказ «переход отклонён: …»
        с действием, отличным от «дерево не на ветке задачи», с SPEC.md в
        подробности; цикл `auto` останавливается без шага developer.

        Ловит мутацию: чтение чужого документа оставлено на общем узле с
        действием «дерево не на ветке задачи» — `auto` запускает developer,
        который SPEC не пишет.
        """
        self.in_dev_with_diff([])
        self.patch(workspace, "on_task_branch", lambda *args, **kwargs: True)
        action, detail, out = self.advance_once()
        why = "SPEC.md на выходе in_dev"
        self.assert_split_action(action, TREE, why, out)
        self.assertIn("SPEC.md", detail, self.note(detail))
        self.assert_operator_class(action, why)


if __name__ == "__main__":
    unittest.main()
