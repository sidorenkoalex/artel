"""Приёмочные тесты 01M290PYPV5T2NFW1Y0HB8BD6E — AC-3, AC-5, AC-6: бриф
developer после возврата из эскалации по конфликту подтяжки несёт ANSWER
Оператора и список конфликтующих файлов (AC-3); отказы `_pre_advance_step`
класса «роль ещё не закончила» не попадают в блок «почини это»
`brief.advance_refusal_history`, а настоящие отказы (гейт/guard) — попадают
как прежде (AC-5/AC-6).

Песочница — `tests/test_brief.py::BriefUnitTest` напрямую (не полный цикл
`auto`/FSM, скил test-authoring «источник — только критерии SPEC»,
предмет этих трёх критериев — сборка брифа над УЖЕ СЛУЧИВШЕЙСЯ историей
журнала, не сама механика перехода/эскалации): та же сырая посевная
история журнала, каким тестирует соседний, уже принятый компонент того же
файла (`tests/test_brief.py::ReturnReasonComponentTest`, SPEC
01M1SAA2AZX3ERQ779QJ5TS9J4).

Разрез краснoты файла НЕОДНОРОДЕН (прогон перед сдачей подтвердил ровно
этот расклад):

Зелёный с рождения: `test_ac3_...` — раздел «Причина возврата» (`brief.
_return_reason_component`) уже несёт detail записи `state -> escalated`
целиком (включая «конфликтные файлы: …» из `pull._merge_conflict_note`)
и ссылку на последний ANSWER для ЛЮБОГО предшественника escalated —
механика существует до этой задачи и не меняется требованием 3, тест
фиксирует её для сценария конфликта подтяжки конкретно (регрессионный
страж, не проверка нового кода); то же верно для
`test_ac6_a_real_gate_refusal_is_still_included` — включение настоящих
отказов гейта/guard в блок уже работает (SPEC T078) и требованием 3 не
меняется, тест фиксирует, что фильтрация класса 3 не задевает этот путь.

Красен до реализации: `test_ac5_...` и
`test_ac6_no_developer_step_since_return_refusal_excluded` — `brief.
advance_refusal_history` сегодня включает ЛЮБУЮ запись с префиксом
`store.REFUSAL_ACTION_PREFIX` без разбора класса (требование 3 ещё не
реализовано) — оба отказа «роль ещё не закончила» проходят в блок
«почини это» целиком, `assertEqual(..., "")` падает.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import auto, brief, config, gitcmd, store  # noqa: E402
from tests.sandbox import fake_git  # noqa: E402
from tests.test_brief import BriefUnitTest  # noqa: E402

TASK = "T001"


class ReturnBriefCarriesAnswerAndConflictFilesTest(BriefUnitTest):
    """AC-3: бриф developer после возврата из escalated по основанию AC-1
    несёт ANSWER Оператора и перечень конфликтующих файлов подтяжки
    (`pull.Conflict.files`).

    Зелёный с рождения: раздел «Причина возврата» (`brief.
    _return_reason_component`, SPEC 01M1SAA2AZX3ERQ779QJ5TS9J4) уже несёт
    дословный `detail` записи `state -> escalated` (куда `pull.
    _merge_conflict_note`/`_handle_merge_failure` уже кладут «конфликтные
    файлы: …» — SPEC 01M1REVMB50SND1KJ3CYQMV2ST) и ссылку на последний
    ANSWER-n.md для ЛЮБОГО предшественника `escalated` — не только для
    оснований, которые заведёт эта задача; для основания AC-1 этот
    существующий механизм не требует правки, тест фиксирует его как
    регрессионный страж специально для конфликта подтяжки, которого
    сегодня в этом файле никто не проверяет.
    """

    def seed_state(self, actor: str, state: str, detail: str = "") -> None:
        store.journal(store.db(), TASK, actor, f"state -> {state}", detail)

    def test_ac3_developer_brief_after_pull_conflict_return_has_answer_and_files(self):
        """Возврат из escalated по конфликту подтяжки — бриф developer
        называет и конфликтующий файл, и путь к ANSWER Оператора.

        Ловит мутацию: раздел «Причина возврата» перестаёт нести detail
        ИМЕННО записи `state -> escalated` (например, откатывается на
        фиксированную фразу approve «эскалация разрешена, продолжаем») —
        `module.py`/строка «конфликтные файлы» пропадёт из текста, первый
        `assertIn` упадёт.
        """
        conn = store.db()
        self.seed_state("fsm", "in_dev", "приёмочные тесты готовы")
        self.seed_state("operator", "review", "готово к ревью")
        self.seed_state(
            "fsm", "escalated",
            "конфликт подтяжки origin/main в ветку task/x-1: конфликтные "
            "файлы: module.py; CONFLICT (content): Merge conflict in "
            "module.py")
        (config.TASKS / TASK / "ANSWER-1.md").write_text(
            "---\ntask: T001\ntype: answer\nauthor_role: operator\n"
            "schema_version: 1\n---\n\n# ANSWER-1\n\nКонфликт разобран "
            "руками, продолжаем.\n", encoding="utf-8")
        self.seed_state("operator", "in_dev", "эскалация разрешена, продолжаем")

        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, TASK)

        self.assertIn(brief.RETURN_REASON_HEADER, text)
        self.assertIn("конфликтные файлы: module.py", text,
                      "бриф не называет конфликтующий файл подтяжки")
        self.assertIn(f"tasks/{TASK}/ANSWER-1.md", text,
                      "бриф не несёт ссылку на ANSWER Оператора")


class RoleNotFinishedRefusalsExcludedFromBriefTest(BriefUnitTest):
    """AC-5/AC-6: отказы `_pre_advance_step` класса «роль ещё не
    закончила» (включая «нет шага роли после возврата», «дерево не на
    ветке задачи») не попадают в блок «почини это»
    `brief.advance_refusal_history`; настоящие отказы (гейт/guard) —
    попадают как прежде."""

    def seed_state(self, actor: str, state: str, detail: str = "") -> None:
        store.journal(store.db(), TASK, actor, f"state -> {state}", detail)

    def refusal_history_block(self) -> str:
        return brief.advance_refusal_history(store.db(), TASK, "developer",
                                              "in_dev")

    # ------------------------------------------------------------- AC-5

    def test_ac5_tree_not_on_task_branch_refusal_excluded(self):
        """Отказ «дерево не на ветке задачи» (класс «роль ещё не
        закончила», требование 3, П2 копилки: «PLAN.md ветки не прочитан
        … does not exist») не попадает в блок «почини это» — читать его
        роли нечего чинить, дерево просто ещё не на её ветке.

        Ловит мутацию: классификация требования 3 не распознаёт этот
        отказ (константа не расширена/не читается фильтром) — блок
        останется непустым, `assertEqual` на `""` упадёт.
        """
        self.seed_state("fsm", "in_dev", "приёмочные тесты готовы")
        store.journal(
            store.db(), TASK, "fsm", "переход отклонён: дерево не на ветке задачи",
            "дерево на ветке task/x-1 — PLAN.md ветки не прочитан "
            "(fatal: path 'tasks/T001/PLAN.md' does not exist)")

        self.assertEqual(
            self.refusal_history_block(), "",
            "отказ класса «роль ещё не закончила» попал в блок «почини это»")

    # ------------------------------------------------------------- AC-6

    def test_ac6_no_developer_step_since_return_refusal_excluded(self):
        """Отказ «нет шага developer после возврата» (журналируемый
        `auto._rework_gate_blocks`, `REWORK_REFUSAL_ACTION` — тот же
        класс, П2 копилки) не попадает в блок «почини это»: роль ничего
        не сдавала, чинить нечего — цикл просто просит её сходить ещё раз.

        Ловит мутацию: фильтр требования 3 не распознаёт ИМЕННО generic-
        текст `_rework_not_addressed_reason` («возврат не отработан: нет
        шага {role} после возврата», без номера итерации) — блок останется
        непустым.
        """
        self.seed_state("fsm", "in_dev", "приёмочные тесты готовы")
        store.journal(
            store.db(), TASK, "fsm", auto.REWORK_REFUSAL_ACTION,
            "возврат не отработан: нет шага developer после возврата")

        self.assertEqual(
            self.refusal_history_block(), "",
            "отказ «нет шага developer после возврата» попал в блок "
            "«почини это»")

    def test_ac6_a_real_gate_refusal_is_still_included(self):
        """Настоящий отказ гейта (guard артефакта-условия) — по-прежнему
        попадает в блок «почини это»: это ровно то, что роли действительно
        нужно почитать и исправить (требование 3, «настоящие отказы сдачи
        шага … включает как сейчас»).

        Ловит мутацию: фильтр требования 3 расширен слишком широко и
        глотает любой `REFUSAL_ACTION_PREFIX`, включая настоящий гейт, —
        блок окажется пустым вместо содержащего текст guard'а.
        """
        self.seed_state("fsm", "in_dev", "приёмочные тесты готовы")
        store.journal(
            store.db(), TASK, "fsm", "переход отклонён guard'ом",
            "PLAN.md: пуст обязательный раздел «Подход»")

        block = self.refusal_history_block()

        self.assertIn("Предыдущая попытка сдать шаг отклонена", block)
        self.assertIn("PLAN.md: пуст обязательный раздел «Подход»", block)


# AC-7: skip — «существующие тесты проходят без ослабления» проверяется
# прогоном самих названных файлов (`tests/test_auto_cycle.py`, `tests/
# test_pull.py`, тесты `orchestrator/fsm.py`, `tests/test_brief.py`), не
# новым unittest здесь — гоняет их CI на каждом коммите (скил
# test-authoring, «Полный набор tests/ в шаге не запускай»), а не пометка
# manual/skip этой планки. Тот же приём — `tasks/01M1REVMB50SND1KJ3CYQMV2ST/
# acceptance_tests/test_pull_conflict_detail.py`, конец файла.


if __name__ == "__main__":
    import unittest
    unittest.main()
