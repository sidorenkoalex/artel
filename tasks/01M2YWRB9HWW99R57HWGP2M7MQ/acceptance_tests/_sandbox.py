"""Тонкая надстройка `LightTransitionSandbox` (tests/sandbox.py) для планки
задачи 01M2YWRB9HWW99R57HWGP2M7MQ: сценарий один на все файлы — синтетическая
задача-песочница ставится в нужное состояние, после чего зовётся настоящий
`fsm.cmd_reject`, и наблюдается исход команды (состояние задачи, записи
журнала, колонки `tasks`).

`disk_backed_show`/`disk_backed_ls_tree_files`/`fake_git`/`set_state` здесь
не переопределяются — импортируются готовыми вместе с
`LightTransitionSandbox` (skills/test-authoring.md, «Лёгкая песочница
переходов — не копия, импорт»). Собственного здесь только то, чего
эталонная песочница не знает: перехват `SystemExit` именованного отказа
`_cmd_reject` (`run_reject`), вход в состояние С ЗАПИСЬЮ журнала
(`enter_state` — сырой `set_state` журнала не трогает), фикстуры
SPEC.md/TZ.md синтетической задачи и чтение журнала/колонок.

Почему `SystemExit` перехватывается, а не ожидается `assertRaises`: сегодня
`_cmd_reject` отказывает `sys.exit`, но требование 4 SPEC вводит НОВЫЙ отказ
(пустая причина на `spec_gate`), формы которого SPEC не называет — ни
критерий AC-4, ни требование 7 не обязывают реализацию к конкретному
механизму («команда отказывает», «прежний именованный отказ»). Наблюдаемое
по критериям — состояние задачи, отсутствие записи перехода и текст отказа;
`run_reject` приводит оба механизма (`sys.exit` с сообщением и `print` +
`return`) к одному тексту, чтобы планка не фиксировала произвольно выбранный
ею механизм.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, fsm, store  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402

# Причина Оператора — один текст на всю планку: фактура инцидента 20.09 из
# «Контекста» SPEC. Небуквенные символы (кавычки, двоеточие) в ней намеренно:
# detail записи и раздел брифа обязаны нести её дословно, а не «очищенной».
REASON = 'SPEC разошёлся с кодом: класс отказа в auto.py требует зоны, которой нет'

# Форма detail записи возврата (требование 1 SPEC, AC-1) — «возврат из
# <состояние>: <причина>», тем же приёмом, каким `_cmd_reject` возвращает
# задачу из `verifying`/`merge_gate` сегодня.
RETURN_DETAIL_TMPL = "возврат из {state}: {reason}"

# Действие журнала перехода: `store.set_state` пишет его как
# `state -> <новое состояние>`.
STATE_ACTION_TMPL = "state -> {state}"

# Detail, которым `fsm_advance.spec_writing` журналирует штатный вход
# задачи на гейт SPEC — им же входит в гейт песочница: без записи
# `state -> spec_gate` журнал был бы вырожден (задача «возникла» на гейте
# ниоткуда), а `brief._return_context` определяет возврат ИМЕННО по тому,
# из какого состояния пришла задача — по предыдущей записи `state -> X`.
SPEC_GATE_ENTRY_DETAIL = "SPEC готов — ждёт approve"

# Опорная часть текста отказа «reject здесь неприменим» (AC-5). Перечень
# состояний в нём НЕ фиксируется дословно: требование 1 SPEC само делает
# `spec_gate` применимым, и перечисление законно меняется вместе с ним —
# а «прежний именованный отказ» (требование 7) остаётся отказом ЭТОГО
# класса, называющим текущее состояние задачи.
INAPPLICABLE_REFUSAL_HEAD = "reject применим только"

# SPEC синтетической задачи: schema_version 1 (без AC-разметки) — минимум,
# который guard пропускает на переходе `spec_writing -> spec_gate`
# (`tests/test_advance_guard.py::SPEC_MD`, тот же набор секций). Значения
# `zones`/`budget_usd` подставляются тестом и заведомо отличаются от колонок
# задачи: reject не имеет права их подхватить (требование 3, AC-3).
SPEC_MD = """---
task: {task}
type: spec
author_role: analyst
status: ready
zones: {zones}
budget_usd: {budget}
schema_version: 1
---

# SPEC: отклонённый на гейте SPEC

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

# ТЗ синтетической задачи: без него `runner.step_role` не даёт `spec_writing`
# роль `analyst` вовсе (обратная совместимость «SPEC пишет Оператор»), и
# цикл `auto` не стал бы запускать шаг ни при какой реализации.
TZ_MD = """---
task: {task}
type: tz
author_role: operator
status: ready
schema_version: 1
---

# ТЗ: отклонённый на гейте SPEC

## Задача

Синтетическое ТЗ песочницы.
"""


class SpecGateRejectSandbox(LightTransitionSandbox):
    """Задача песочницы + настоящий `fsm.cmd_reject` из заданного состояния."""

    TASK_TITLE = "reject на гейте SPEC"

    def run_reject(self, reason: str) -> str:
        """Зовёт настоящий `fsm.cmd_reject` и отдаёт напечатанное им.

        `SystemExit` именованного отказа перехватывается, его сообщение
        дописывается к тексту — см. докстринг модуля."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                fsm.cmd_reject(self.TASK, reason)
            except SystemExit as exc:
                buf.write(f"{exc}\n")
        return buf.getvalue()

    def enter_state(self, state: str, detail: str = "") -> None:
        """Ставит состояние задачи И журналирует вход в него записью
        `state -> {state}` — тем же action/actor, каким её пишет
        `store.set_state` на настоящем переходе.

        Сырой `set_state` эталонной песочницы (UPDATE в обход переходов)
        журнала не трогает; без записи входа половина наблюдаемых
        свойств этой планки вырождается — `brief._return_context` и
        `auto._role_step_since_state_entry` читают ИМЕННО историю
        записей `state -> X`, и сценарий «пришла на гейт, отклонена с
        гейта» без первой из них не разыгрывается вовсе."""
        self.set_state(state)
        store.journal(store.db(), self.TASK, "fsm",
                      STATE_ACTION_TMPL.format(state=state), detail)

    def reject_from(self, state: str, reason: str) -> str:
        """Вводит задачу в состояние (с записью журнала) и отклоняет её
        из него."""
        detail = (SPEC_GATE_ENTRY_DETAIL if state == "spec_gate" else "")
        self.enter_state(state, detail)
        return self.run_reject(reason)

    # ---------------------------------------------------------- фикстуры

    def write_spec(self, zones: str = "orchestrator/auto.py",
                   budget: float = 0.0) -> None:
        """SPEC.md синтетической задачи на «ветке» (диск — источник
        артефактов этой песочницы, `disk_backed_show`)."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            SPEC_MD.format(task=self.TASK, zones=zones, budget=budget),
            encoding="utf-8")

    def write_tz(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "TZ.md").write_text(
            TZ_MD.format(task=self.TASK), encoding="utf-8")

    def set_columns(self, **fields) -> None:
        """Ставит колонки `tasks` в обход переходов (счётчики, зоны,
        потолок) — снимок «как было до команды»."""
        conn = store.db()
        for column, value in fields.items():
            conn.execute(f"UPDATE tasks SET {column}=? WHERE id=?",
                         (value, self.TASK))
        conn.commit()

    # ------------------------------------------------------------ чтение

    def journal_rows(self) -> list[tuple[str, str, str]]:
        return [(r["actor"], r["action"], r["detail"] or "")
                for r in store.db().execute(
                    "SELECT actor, action, detail FROM steps "
                    "WHERE task_id=? ORDER BY id", (self.TASK,))]

    def transition_details(self, state: str) -> list[str]:
        """Detail всех записей `state -> {state}` задачи, по порядку."""
        action = STATE_ACTION_TMPL.format(state=state)
        return [detail for _, act, detail in self.journal_rows()
                if act == action]

    def counters(self) -> tuple[int, int]:
        row = self.task_row()
        return row["review_iters"], row["accept_rejects"]

    def zones_and_budget(self) -> tuple:
        row = self.task_row()
        return row["zones"], row["budget_usd"]

    def spec_budget_value(self) -> float:
        """Потолок для фикстуры SPEC — заведомо отличный от текущего
        потолка задачи и заведомо применимый (`budget.spec_budget`
        отвергает всё выше `config.ROLE_BUDGET_CAP`).

        Считается от `config`, не литералом: потолки — крутилка
        Оператора (skills/test-authoring.md, урок 28.08)."""
        default = config.DEFAULT_BUDGET_USD
        raised = default + 1.0
        return raised if raised <= config.ROLE_BUDGET_CAP else default / 2.0
