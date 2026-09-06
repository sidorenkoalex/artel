"""Общая песочница приёмочных тестов задачи 01M1SAA2AZX3ERQ779QJ5TS9J4
(«бриф роли после возврата цитирует причину возврата первым пунктом»).

Не сканируется guard'ом на AC-маркеры/тест-методы (только test_*.py,
SPEC T081) — файлы test_ac*.py этого каталога делят с ним фикстуры.

Реализация раздела «Причина возврата» ещё не существует (эта задача её
вводит) — фикстуры ниже строят историю журнала `steps` НАПРЯМУЮ
(`seed_state`), тем же текстом действия `state -> <state>`, что пишет
`store.set_state` (store.py:654), но без CAS/строки `tasks`: журналу
она не нужна (`store.journal`/`store.task_target` терпят отсутствие
строки задачи — тот же приём, каким уже пользуется весь `tests/
test_brief.py`, ни разу не зовущий `insert_task`). Детали `detail`,
которые сеет `seed_state`, — не выдумка теста, а дословные форматы
существующих вызовов `store.set_state` в `orchestrator/fsm.py`/
`fsm_advance.py` (например `f"замечания ревью, итерация {iters}"` —
`fsm_advance.py:281`, `f"приёмка отклонена: {reason}"` — `fsm.py:958`,
`"эскалация разрешена, продолжаем"` — `fsm.py:899`), чтобы фикстура
была неотличима от того, что реально пишет FSM.
"""
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import brief, config, gitcmd, store  # noqa: E402
from tests.sandbox import (TmpRootTest, disk_backed_ls_tree_files,  # noqa: E402
                           disk_backed_show, fake_git)

TASK = "T001"

MAP_FRESH = ("---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
            "---\n\n# Карта\n\nМаркер-текста-карты.\n")
SPEC_SMALL = "# SPEC\n\nМаркер-текста-SPEC.\n"
CONVENTIONS_SMALL = "# Конвенции проекта\n\nМаркер-текста-CLAUDE.\n"

# Дословные фразы существующих переходов FSM (см. докстринг модуля) —
# константы, чтобы опечатка в фикстуре не разошлась молча с опечаткой в
# ассерте того же теста.
DETAIL_REVIEW_CHANGES_REQUESTED = "замечания ревью, итерация 1"
DETAIL_REJECT_ACCEPTANCE = "приёмка отклонена: регресс в модуле экспорта отчётов"
DETAIL_REJECT_VERIFYING = ("возврат из verifying: test_ac3_foo, "
                          "test_ac9_bar упали на раннере")
DETAIL_REJECT_MERGE_GATE = "возврат из merge_gate: конфликт с main, перебазируй ветку"
DETAIL_ESCALATED_APPROVE = "эскалация разрешена, продолжаем"
DETAIL_ESCALATED_LIMIT = ("потолок ожидания CI в verifying исчерпан (10800с) — "
                         "последний статус: CI зависла без ответа")
DETAIL_ESCALATED_ANALYST = ("analyst: батч вопросов по ТЗ — "
                           f"tasks/{TASK}/QUESTIONS.md")
DETAIL_ESCALATED_TEST_AUTHOR = ("test_author: критерий неисполним тестом — "
                               "AC-7: формулировка требует внешний стенд")
DETAIL_NORMAL_TESTS_WRITING_DONE = ("приёмочные тесты готовы — трассируемость "
                                   "AC пройдена")
DETAIL_NORMAL_SPEC_GATE_TO_TESTS_WRITING = ("гейт SPEC пройден — приёмочные "
                                           "тесты до кода")
RETURN_REASON_HEADER = "Причина возврата"
RETURN_REASON_CLOSING = "шаг без правки, закрывающей причину, не засчитывается"


class BriefSandbox(TmpRootTest):
    """docs/codebase-map.md + CLAUDE.md + tasks/<TASK>/SPEC.md на диске —
    тот же минимум, что `tests/test_brief.py::BriefUnitTest`, плюс
    `seed_state` для истории журнала."""

    def setUp(self):
        super().setUp()
        (self.root / "docs").mkdir(parents=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            MAP_FRESH, encoding="utf-8")
        (self.root / "CLAUDE.md").write_text(
            CONVENTIONS_SMALL, encoding="utf-8")
        (config.TASKS / TASK).mkdir(parents=True)
        (config.TASKS / TASK / "SPEC.md").write_text(
            SPEC_SMALL, encoding="utf-8")
        store.create_schema(store.db())
        self.conn = store.db()

        # Тот же приём, что `tests/test_brief.py::BriefUnitTest` (см.
        # докстринг там): `artifact_source.resolve` всегда `foreign=True`
        # (A7) — без этой подмены `disk_backed_show`/`disk_backed_
        # ls_tree_files` читают SPEC/QUESTIONS/ANSWER/REVIEW/PLAN с диска
        # `config.TASKS`, а не с фиктивного ответа заглушки `git`.
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

    def seed_state(self, state: str, actor: str, detail: str = "") -> None:
        """Сырая запись журнала `state -> <state>` — тот же текст
        действия, что пишет `store.set_state` (store.py:654), без CAS и
        без строки `tasks` (`store.journal` её не требует)."""
        store.journal(self.conn, TASK, actor, f"state -> {state}", detail)

    def write_review(self, marker_text: str) -> None:
        (config.TASKS / TASK / "REVIEW.md").write_text(
            "---\ntask: " + TASK + "\ntype: review\nstatus: changes_requested\n"
            "iteration: 1\n---\n\n# REVIEW\n\n## Замечания\n\n"
            f"{marker_text}\n",
            encoding="utf-8")

    def write_answer(self, n: int, marker_text: str) -> None:
        (config.TASKS / TASK / f"ANSWER-{n}.md").write_text(
            "---\ntask: " + TASK + "\ntype: answer\nauthor_role: operator\n"
            "status: ready\nschema_version: 2\n---\n\n"
            f"# ANSWER-{n}: ответ Оператора\n\n## Ответы\n\n{marker_text}\n",
            encoding="utf-8")

    def write_questions(self, marker_text: str) -> None:
        (config.TASKS / TASK / "QUESTIONS.md").write_text(
            "---\ntask: " + TASK + "\ntype: questions\nauthor_role: analyst\n"
            "status: draft\nschema_version: 2\n---\n\n# QUESTIONS\n\n"
            f"## Вопросы\n\n1. **Вопрос?** — {marker_text} — дефолт: A.\n",
            encoding="utf-8")

    def build_developer_brief(self) -> str:
        with mock.patch.object(gitcmd, "git", fake_git):
            return brief.developer_brief(self.conn, TASK)

    def build_analyst_brief(self) -> str:
        with mock.patch.object(gitcmd, "git", fake_git):
            return brief.analyst_map_component(self.conn, TASK)

    def build_test_author_brief(self):
        with mock.patch.object(gitcmd, "git", fake_git):
            return brief.test_author_answer_component(self.conn, TASK)
