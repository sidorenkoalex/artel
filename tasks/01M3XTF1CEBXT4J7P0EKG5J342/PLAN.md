---
task: 01M3XTF1CEBXT4J7P0EKG5J342
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Эскалация разработчика через PLAN.md не зацикливается после ответа и approve

## Подход
Одна строка вызова: `_in_dev_plan_escalate` (`orchestrator/fsm_advance.py`)
сразу после `store.set_state(…, "escalated", …)` пишет
`_mark_artifact_escalation(conn, task_id, detail)` с тем же `detail` —
ровно как `_review_escalate`. Чтение признака уже есть
(`auto._role_step_since_state_entry` через `_ROLE_STEP_REQUIRED_MARKERS`,
`in_dev` в `_REWORK_GATE_STATES`): запись возврата `approve` за признаком
становится анкером рубежа, и пред-advance `auto` держится до шага
developer. Новая эскалация не подавляется — после шага developer
пред-advance читает PLAN.md как прежде (требование 3), никакого правила
«ANSWER новее» не вводится. Признак пишет только эта функция — общий узел
перехода (`store.set_state`, начало `fsm_advance.in_dev`) не трогается.

Тесты: AC-1..AC-4 кроет долгоживущий файл задачи
`tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py` (test_author,
ADR-0020; залочен — не правлю). По скилу coding-standards свои тесты — только
на непокрытые свойства, поэтому в `tests/test_artifact_escalation_marker.py`
(зона требования 5) добавлен один тест на сам гейт рубежа `in_dev` по
журналу, собранному руками (по образцу `RoleStepAnchorAfterTheMarkerTest`),
и модульный докстринг называет пятую точку и долгоживущий файл.

## Шаги
1. `orchestrator/fsm_advance.py`: вызов признака в `_in_dev_plan_escalate`
   + абзац «почему» в её докстринге; докстринг `_mark_artifact_escalation`
   — «Точек вызова пять», перечень с `_in_dev_plan_escalate`.
2. `tests/test_artifact_escalation_marker.py`:
   `RoleStepAnchorAfterTheMarkerTest.test_marked_developer_escalation_holds_the_in_dev_pre_advance`
   (заявка «Ловит мутацию: `in_dev` исключён из `auto._REWORK_GATE_STATES`»).
3. `python3 scripts/codebase_map.py` — `docs/codebase-map.md` тем же коммитом.
4. Приложение к `skills/escalation-rules.md` (ниже) — требование 6.

Проверки (передний план, `-p no:cacheprovider -p timeout -o timeout=120`):
- `tests/test_artifact_escalation_marker.py`,
  `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`,
  `acceptance_tests/test_ac5_marker_docstring.py` — 18 passed;
- плюс `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`,
  `tests/test_fsm_advance_gate_smoke.py`, `tests/test_answer_gate.py`,
  `tests/test_pull_conflict_marker_states.py` — вместе 101 passed, 30 subtests.
- Мутации (временно, код возвращён): убран вызов признака из
  `_in_dev_plan_escalate` → краснеют AC-1 (оба subTest), AC-3, AC-4
  долгоживущего файла; `in_dev` убран из `_REWORK_GATE_STATES` → краснеет
  новый тест `test_marked_developer_escalation_holds_the_in_dev_pre_advance`.
- `acceptance_tests/test_ac6_skill_appendix.py` читает PLAN.md из
  артефактной ветки — до автокоммита шага прогнать нельзя; приложение
  проверено `git apply --check` на чистом дереве (см. ниже).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (проверка — долгоживущий файл, AC-3) |
| 3 | 1 (не вводится подавления; проверка — AC-4) |
| 4 | 1 |
| 5 | 2 + долгоживущий файл задачи (а–г = AC-1..AC-4) |
| 6 | 4 |

## Влияние на систему
- Затрагивается только эскалация `in_dev` по `PLAN.md status: escalate`:
  после `answer` + `approve` пред-advance `auto` требует шаг developer
  (как уже для review/test_author/analyst). Бюджетная, целостности,
  провала агента и конфликта подтяжки эскалации признака не получают
  (AC-2 долгоживущего файла держит это).
- Сторонний читатель признака `advance_gates/review.py::_review_rework_gate`
  — смена опорной записи совпадает с его смыслом (SPEC «Материалы»).
- Гейты, лимиты, тесты не ослабляются; существующие тесты не правлены.
- Откат — revert merge-коммита задачи.

## Риски
- Роль, оставившая после ANSWER прежний `status: escalate`, эскалирует
  повторно (сознательно, требование 3) — пункт 4 скила (приложение)
  объясняет ролям, что escalate надо снимать.

## Приложение: skills/escalation-rules.md
Пункт 4 раздела «Как эскалировать» (требование 6). `git apply --check` на
чистом дереве ветки (`skills/escalation-rules.md` = main) — проходит.

```diff
diff --git a/skills/escalation-rules.md b/skills/escalation-rules.md
index 5470ce7a..d92c35b7 100644
--- a/skills/escalation-rules.md
+++ b/skills/escalation-rules.md
@@ -26,6 +26,11 @@
    (У ролей со своим носителем батча — например QUESTIONS.md у
    analyst — действует механика их скила, правило то же: один батч.)
 3. Останься в рамках сделанного — не откатывай работу.
+4. Продолжая работу после ответа Оператора (ANSWER), сними
+   `status: escalate` в своём артефакте (PLAN.md): сдай `ready` либо,
+   если вопрос не снят, новую эскалацию с новым батчем. Оставленный
+   прежний `status: escalate` пульт читает как новую эскалацию — задача
+   снова встанет, не продвинувшись.
 
 ## Чего не делать
 - Не выбирать интерпретацию «на свой вкус» при неоднозначности SPEC.
```

## Предложения системе
- Требование 5 SPEC («тесты добавляются в `tests/test_artifact_escalation_marker.py`»)
  расходится с ADR-0020: те же AC уже лежат в долгоживущем файле test_author,
  а coding-standards запрещает дублировать — analyst-скилу стоит не называть
  файл тестов для AC, которые уйдут в долгоживущую планку.
