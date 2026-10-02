---
task: 01M3XTF1CEBXT4J7P0EKG5J342
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Эскалация разработчика через PLAN.md не зацикливается после ответа и approve

# ТЗ: Эскалация разработчика через PLAN.md не зацикливается после ответа и approve

Источник: строка копилки `docs/backlog.md` от 30.09 (П1) «Эскалация
разработчика через PLAN.md зацикливается…» и строка 28.09 (П2) того же
содержания; ревизия 02.10. Срочность: с 02.10 разработчик обязан
эскалировать до сдачи шага, если нужно удалить или переименовать тестовый
метод (задача 01M3XR84299TD6V6E16D2PNXH4), — эскалация через PLAN.md
станет частым путём.

Факты (origin/main 83a9c96e):
- `orchestrator/fsm_advance.py:434-452` (`_in_dev_plan_escalate`): при
  `PLAN.md status: escalate` пульт поднимает `answer_baseline` и переводит
  задачу `in_dev -> escalated` с detail «эскалация от разработчика: …».
  Записи-признака «ответ Оператора должен дойти до роли»
  (`fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER`, `orchestrator/fsm.py:66-68`)
  эта функция не пишет.
- Тот же признак уже пишут три другие эскалации по содержимому артефакта
  роли через `_mark_artifact_escalation` (`fsm_advance.py:60-75`):
  аналитик — батч `QUESTIONS.md` (`fsm_advance.py:127`, `:151`),
  ревьювер — `REVIEW.md status: escalate` (`fsm_advance.py:237`, SPEC
  01M31JWD10728N5YGWVQGWYACW), автор тестов — пометка `AC-n: escalate`
  (`fsm_advance.py:378`, SPEC 01M2XFSJ1Z7BS6HR69SAT1D81Y).
- Как признак работает: `orchestrator/auto.py:387`
  (`_ROLE_STEP_REQUIRED_MARKERS`) и `auto.py:391`
  (`_role_step_since_state_entry`) — запись возврата из эскалации
  «эскалация разрешена, продолжаем» (`orchestrator/fsm.py:999-1002`,
  `_approve_escalated`; без `escalated_from` возврат идёт в `in_dev`),
  перед которой стоит признак, становится опорной; без признака она
  пропускается (`auto.py:375`, `_ESCALATED_RETURN_DETAILS`).
  `auto.py:738` (`_rework_gate_blocks`) для состояний
  `_REWORK_GATE_STATES = ("in_dev", "spec_writing", "tests_writing")`
  (`auto.py:258`) запрещает переход по готовым артефактам, пока после
  опорной записи нет завершённого шага роли; вызов — `auto.py:1114`.
  `in_dev` в перечне уже есть — не хватает только признака.
- Без признака опорной остаётся более ранний вход в `in_dev`, после
  которого шаг developer уже был, и `auto.py:813` (`_pre_advance_step`)
  вызывает `fsm.cmd_advance`: `fsm_advance.in_dev` (`:512`, ветка
  `status == "escalate"` около `:537`) читает прежний `PLAN.md` и снова
  эскалирует; `auto.py:865-868` пишет «шаг developer не нужен: переход
  выполнен по готовым артефактам in_dev -> escalated». Повторная эскалация
  снова поднимает `answer_baseline`, и следующий `approve` требует ещё
  один ANSWER.
- Журнал (таблица `steps`, время UTC):
  01M3S9HFDDS9S4274W6TBQJBH7 — эскалация 15:06:22Z, ANSWER-1 и approve
  15:14:58–59Z, `auto старт` и повторная эскалация в ту же секунду
  15:14:59Z, `approve отклонён: нет ANSWER` 15:15:36Z, ANSWER-2 и шаг
  developer через `run` 15:16:04Z;
  01M3KHQS7EQTHDT1RGCNH4KGTW — approve 09:28:41Z, повторная эскалация
  09:28:45Z, ANSWER-3 09:29:44Z;
  01M3SE87R3M7HGWX8HG1ANAKR0 — после approve 18:45:18Z шаг developer
  запущен через `run` (обход).
  Эскалация автора тестов в 01M3S9HRZYT0C6TC1CZJPNYKZ1 тем же путём
  прошла штатно (копилка 30.09) — у неё признак есть.
- Ревьювер: отдельного риска нет. Эскалация ревьювера уже пишет признак
  и возвращает задачу в `in_dev` (обязателен шаг developer). Когда задача
  снова доходит до `review`, прежний `REVIEW.md status: escalate` не
  срабатывает повторно: `reviewed_iter` уже записан
  (`fsm_advance.py:281`), и проверка свежести вердикта
  (`orchestrator/advance_gates/tests_writing.py:12`,
  `_freshness_refuses`) отказывает до нового прогона ревьювера; поэтому
  `review` намеренно не входит в `_REWORK_GATE_STATES` (`auto.py:254`).
- Сторонний читатель того же механизма:
  `orchestrator/advance_gates/review.py:348` (`_review_rework_gate`)
  вызывает `_role_step_since_state_entry(…, "in_dev", "developer")` —
  после правки опорной для него тоже станет возврат из эскалации
  разработчика; это совпадает с его смыслом (шаг developer после возврата
  обязателен).
- Комментарии-перечни точек записи признака устарели уже сейчас:
  `fsm_advance.py:69-73` («Точек вызова три», вызовов четыре),
  `fsm.py:50-65` и `auto.py:378-386` называют только аналитика и автора
  тестов.

Требуется:
1. `_in_dev_plan_escalate` (`orchestrator/fsm_advance.py`) сразу после
   `store.set_state(…, "escalated", …)` пишет признак
   `_mark_artifact_escalation(conn, task_id, detail)` с тем же `detail`,
   что у записи `state -> escalated`, — тем же способом, что
   `_review_escalate`. Признак пишет только эта функция: эскалации из
   `in_dev` по другим основаниям (бюджет, инцидент целостности, провал
   агента, конфликт подтяжки со своим признаком) признака
   `ARTIFACT_ESCALATION_ROLE_STEP_MARKER` не получают.
2. После `answer` и `approve` на такой эскалации цикл `auto` первым шагом
   запускает developer (с ANSWER в брифе), а не переход по готовым
   артефактам: в журнале между `state -> in_dev` («эскалация разрешена,
   продолжаем») и следующей записью `state -> escalated` обязательно
   стоит `agent run finished` роли developer; записи «шаг developer не
   нужен: переход выполнен по готовым артефактам in_dev -> escalated» до
   шага роли нет.
3. Новая эскалация не подавляется: если после шага developer `PLAN.md`
   по-прежнему (или заново) имеет `status: escalate`, задача эскалирует
   штатно, как сейчас. Правило «не считать escalate готовым, если ANSWER
   новее» (предложение копилки) не вводится — используется существующий
   признак.
4. Комментарии-перечни точек записи признака приводятся к коду:
   докстринг `_mark_artifact_escalation` (`fsm_advance.py`) называет все
   пять точек (аналитик ×2, автор тестов, ревьювер, разработчик).
   Комментарии в `orchestrator/fsm.py` и `orchestrator/auto.py` в этой
   задаче не меняются (решение Оператора 02.10: не занимать их зоны ради
   комментариев).
5. Тесты в `tests/test_artifact_escalation_marker.py` (по образцу
   `MarkerWrittenByTheEscalationPointsTest` и
   `RoleStepAnchorAfterTheMarkerTest`):
   а) `PLAN.md status: escalate` в `in_dev` → `cmd_advance` переводит в
      `escalated`, следующей записью журнала идёт признак с тем же
      `detail` и `actor = fsm`. «Ловит мутацию: `_in_dev_plan_escalate`
      не пишет признак или пишет его до перехода».
   б) Сквозной сценарий цикла `auto` (основа `AutoCycleTest`):
      эскалация разработчика через PLAN.md, ANSWER, `approve`, запуск
      `auto` с `PLAN.md`, оставшимся в `status: escalate`, — первым
      действием выполняется шаг developer (сценарий агента), повторной
      эскалации до него нет. «Ловит мутацию: признак убран из
      `_in_dev_plan_escalate` либо `in_dev` исключён из
      `_REWORK_GATE_STATES`».
   в) Продолжение сценария б): шаг developer оставил `PLAN.md` со
      `status: escalate` — задача снова уходит в `escalated` (требование
      3). «Ловит мутацию: исправление сделано подавлением escalate при
      наличии ANSWER новее эскалации — новая эскалация роли теряется».
   г) Эскалация из `in_dev` по бюджету (`budget.enforce_budget`) признака
      не пишет. «Ловит мутацию: признак вынесен в общий узел перехода в
      `escalated` (`store.set_state` или начало `fsm_advance.in_dev`)».
6. Существующие тесты не ослабляются и не удаляются; полный набор
   `tests/` зелёный.
7. `skills/escalation-rules.md`, раздел «Как эскалировать» — пункт:
   после ответа Оператора (ANSWER) роль, продолжая работу, снимает
   `status: escalate` в своём артефакте (PLAN.md) — сдаёт `ready` либо,
   если вопрос не снят, новую эскалацию с новым батчем; оставленный
   прежний `status: escalate` пульт читает как новую эскалацию.
   Правка — приложением PLAN (защищённый путь).

Зоны: orchestrator/fsm_advance.py, tests/test_artifact_escalation_marker.py, docs/codebase-map.md.
Приложением: skills/escalation-rules.md (защищённый путь, применяет пульт на мерже).

Только чтение (не менять): orchestrator/advance_gates/ (в том числе
review.py, tests_writing.py, zones.py), orchestrator/pull.py,
orchestrator/runner.py, orchestrator/answer.py, orchestrator/budget.py,
orchestrator/brief.py, orchestrator/config.py, orchestrator/store.py,
orchestrator/fsm.py, orchestrator/auto.py,
scripts/guard.py, tests/test_auto_cycle.py, tests/sandbox.py,
остальные файлы tests/, остальные файлы skills/, docs/backlog.md,
tasks/.

Не входит: изменение механизма проверки свежести вердикта ревьювера и
добавление `review` в `_REWORK_GATE_STATES`; ограничитель «две
эскалации разработчика подряд без изменения PLAN.md» (аналог
`_pull_conflict_marker_streak`); правка комментариев в
`orchestrator/fsm.py` и `orchestrator/auto.py`; изменение
`_approve_escalated` и правил `answer_baseline`; команда пульта для
обхода через `run`.

Рамка: $15.
