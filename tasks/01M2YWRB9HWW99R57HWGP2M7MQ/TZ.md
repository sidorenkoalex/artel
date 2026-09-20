---
task: 01M2YWRB9HWW99R57HWGP2M7MQ
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: reject на гейте SPEC: возврат аналитику с причиной, гейт переделки и бриф «Причина возврата»

Источник: инцидент 20.09 на гейте SPEC задачи 01M2YSHDKW и строка
копилки П2 11.09 «Нет команды пульта для операторской правки SPEC на
гейте spec_gate». Решение Оператора 20.09: заводить сейчас.

Факты:
- Протокол гейта SPEC (docs/operator-gates.md, раздел «Гейт SPEC»)
  называет два исхода помимо approve: «отказ (reject) или редактура
  Оператором». Но `orchestrator/fsm.py::_cmd_reject` принимает только
  `acceptance`, `merge_gate` и `verifying`; на `spec_gate` команда
  отвечает «reject применим только в acceptance, merge_gate или
  verifying». Редактура тоже без команды: 11.09 и 20.09 сессия писала
  SPEC в артефактную ветку функциями пульта (`artifact_branch.
  commit_files`/`push`) сценарием — обход, дважды записанный в копилку.
- 20.09: SPEC 01M2YSHDKW расходился с кодом (класс отказа в auto.py
  требовал зоны, которой не было); единственным рычагом Оператора
  оказалась ручная редактура текста аналитика.
- Механика возврата с причиной уже есть для других состояний:
  `_cmd_reject` из `verifying`/`merge_gate` переводит в `in_dev` записью
  `state -> in_dev` с detail «возврат из <state>: <причина>»; гейт
  переделки `orchestrator/auto.py::_rework_gate_blocks` держит
  предварительный advance до шага роли состояния, а бриф роли получает
  раздел «Причина возврата» (`orchestrator/brief.py`,
  `RETURN_REASON_HEADER`) и историю отказов. `spec_writing` уже входит в
  `_REWORK_GATE_STATES` auto.py.

Требуется:
1. `reject <id> "<причина>"` на `spec_gate`: переход `spec_gate ->
   spec_writing` записью `state -> spec_writing` с detail «возврат из
   spec_gate: <причина>» (тем же приёмом, что возврат из verifying),
   без роста `review_iters`/`accept_rejects`; `tasks.zones` и
   `budget_usd` от отклонённого SPEC не пишутся (они пишутся только на
   approve). Пустая причина — отказ команды, как у остальных состояний.
2. Аналитик после возврата получает причину: раздел «Причина возврата»
   брифа несёт текст detail (сверить, что `brief.py` строит его для
   `spec_writing` по записи `state -> spec_writing` так же, как для
   `in_dev`; если нет — это правка brief.py, зона задачи).
3. Гейт переделки: после `state -> spec_writing` с основанием возврата
   предварительный advance по готовому SPEC (status: ready в ветке) не
   уводит задачу обратно на `spec_gate` до завершённого шага analyst —
   сверить с `auto._role_step_since_state_entry`, что запись возврата
   становится анкером (detail не входит в `_ESCALATED_RETURN_DETAILS`);
   при необходимости дополнить.
4. Документация: docs/operator-gates.md, раздел «Гейт SPEC» — фраза
   «отказ (reject)» получает форму команды и порядок: `reject` с
   причиной → `auto` → аналитик переписывает SPEC → новый approve;
   редактура Оператором остаётся законным ходом для правок в одну-две
   строки.
5. Тесты (tests/): reject на spec_gate переводит в spec_writing с
   причиной в журнале и не пишет zones/budget; пустая причина — отказ;
   auto после возврата запускает analyst (не переходит по готовому SPEC)
   и бриф несёт «Причина возврата» с текстом; reject в прочих состояниях
   — поведение как сегодня; существующие тесты reject/auto зелёные.

Зоны: orchestrator/fsm.py, orchestrator/auto.py, orchestrator/brief.py,
docs/operator-gates.md, tests/.

Только чтение (не менять): orchestrator/fsm_advance.py (обработчик
`spec_writing` не меняется), orchestrator/artifact_branch.py (обход
редактуры — не легализуется этой задачей), docs/backlog.md (источник).

Не входит: команда редактуры SPEC Оператором (правка текста остаётся
ручной, обход при необходимости — записью в копилку); reject на
`escalated` (там `answer`); изменение шаблона SPEC.

Рамка: $30.
