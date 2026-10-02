---
task: 01M3XTF1CEBXT4J7P0EKG5J342
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm_advance.py, tests/test_artifact_escalation_marker.py, docs/codebase-map.md
budget_usd: 40
---

# SPEC: Эскалация разработчика через PLAN.md не зацикливается после ответа и approve

## Контекст
`_in_dev_plan_escalate` (`orchestrator/fsm_advance.py:434-452`) переводит
задачу `in_dev -> escalated` по `PLAN.md status: escalate`, но, в отличие
от трёх других эскалаций по содержимому артефакта роли (батч
`QUESTIONS.md` аналитика, `AC-n: escalate` автора тестов, `REVIEW.md
status: escalate` ревьювера), не пишет признак
`fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER` через
`_mark_artifact_escalation`. Без признака после `answer` + `approve` цикл
`auto` берёт опорной более ранний вход в `in_dev`, выполняет переход по
готовым артефактам, читает прежний `PLAN.md` и снова эскалирует, требуя
новый ANSWER (журнал задач 01M3S9HFDDS9S4274W6TBQJBH7,
01M3KHQS7EQTHDT1RGCNH4KGTW, обход через `run` в 01M3SE87R3M7HGWX8HG1ANAKR0).
С 02.10 эскалация разработчика через PLAN.md становится частым путём
(задача 01M3XR84299TD6V6E16D2PNXH4), поэтому цикл нужно убрать.

## Требования
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
   новее» не вводится — используется существующий признак.
4. Докстринг `_mark_artifact_escalation` (`orchestrator/fsm_advance.py`)
   называет все пять точек записи признака: аналитик ×2 (батч
   `QUESTIONS.md`, оба пути), автор тестов, ревьювер, разработчик.
5. Тесты добавляются в `tests/test_artifact_escalation_marker.py` по
   образцу `MarkerWrittenByTheEscalationPointsTest` и
   `RoleStepAnchorAfterTheMarkerTest` (сквозной сценарий — на основе
   `AutoCycleTest`), каждый с заявкой «Ловит мутацию: …» из ТЗ:
   а) признак после эскалации через PLAN.md (мутация: признак не пишется
      или пишется до перехода);
   б) сквозной сценарий `auto` — первым действием шаг developer (мутация:
      признак убран из `_in_dev_plan_escalate` либо `in_dev` исключён из
      `_REWORK_GATE_STATES`);
   в) продолжение б): повторная эскалация после шага developer (мутация:
      исправление сделано подавлением escalate при наличии ANSWER новее
      эскалации);
   г) эскалация из `in_dev` по бюджету признака не пишет (мутация:
      признак вынесен в общий узел перехода в `escalated` — `store.set_state`
      или начало `fsm_advance.in_dev`).
6. `skills/escalation-rules.md`, раздел «Как эскалировать», получает
   пункт: после ответа Оператора (ANSWER) роль, продолжая работу,
   снимает `status: escalate` в своём артефакте (PLAN.md) — сдаёт `ready`
   либо, если вопрос не снят, новую эскалацию с новым батчем;
   оставленный прежний `status: escalate` пульт читает как новую
   эскалацию. Путь защищённый — правка оформляется приложением PLAN
   (unified-диф), применяет пульт на мерже.

## Критерии приёмки

AC-1. Задача в `in_dev` с `PLAN.md status: escalate`: `cmd_advance`
переводит её в `escalated`, и следующей записью журнала после
`state -> escalated` идёт запись `fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER`
с тем же `detail`, что у записи перехода, и `actor = fsm`. Проверено
тестом в `tests/test_artifact_escalation_marker.py` с заявкой «Ловит
мутацию: `_in_dev_plan_escalate` не пишет признак или пишет его до
перехода».

AC-2. Эскалация из `in_dev` по бюджету (`budget.enforce_budget`) признака
`ARTIFACT_ESCALATION_ROLE_STEP_MARKER` не пишет. Проверено тестом в
`tests/test_artifact_escalation_marker.py` с заявкой «Ловит мутацию:
признак вынесен в общий узел перехода в `escalated` (`store.set_state`
или начало `fsm_advance.in_dev`)».

AC-3. Сквозной сценарий цикла `auto`: эскалация разработчика через
PLAN.md, ANSWER, `approve`, запуск `auto` с `PLAN.md`, оставшимся в
`status: escalate`, — первым действием выполняется шаг developer: в
журнале между `state -> in_dev` («эскалация разрешена, продолжаем») и
следующей записью `state -> escalated` стоит `agent run finished` роли
developer, а записи «шаг developer не нужен: переход выполнен по готовым
артефактам in_dev -> escalated» до шага роли нет. Проверено тестом в
`tests/test_artifact_escalation_marker.py` с заявкой «Ловит мутацию:
признак убран из `_in_dev_plan_escalate` либо `in_dev` исключён из
`_REWORK_GATE_STATES`».

AC-4. Продолжение сценария AC-3: шаг developer оставил `PLAN.md` со
`status: escalate` — задача снова уходит в `escalated`. Проверено тестом
в `tests/test_artifact_escalation_marker.py` с заявкой «Ловит мутацию:
исправление сделано подавлением escalate при наличии ANSWER новее
эскалации — новая эскалация роли теряется».

AC-5. Докстринг `_mark_artifact_escalation` в `orchestrator/fsm_advance.py`
перечисляет все пять точек записи признака: `spec_writing` ×2 (батч
`QUESTIONS.md` — ветка-источник и диск), `tests_writing`
(`AC-n: escalate`), `_review_escalate` и `_in_dev_plan_escalate`; фразы
«Точек вызова три» в нём нет.

AC-6. PLAN.md несёт приложение — unified-диф к `skills/escalation-rules.md`,
добавляющий в раздел «Как эскалировать» пункт по требованию 6 (после
ANSWER роль снимает `status: escalate` в PLAN.md: `ready` либо новая
эскалация с новым батчем; оставленный прежний `status: escalate` пульт
читает как новую эскалацию); диф применяется `git apply --check` на
чистом дереве.

## Оценка объёма и деление
Сработавшие сигналы guard: «число затрагиваемых модулей/файлов»,
«затронут инвариантный механизм», «прогноз диффа не дан». Первые два —
следствие того, что текст SPEC упоминает модули только для чтения
(`orchestrator/auto.py`, `orchestrator/fsm.py`, `orchestrator/store.py`,
`orchestrator/budget.py` и др. — в «Контексте», «Материалах» и перечне
«Не входит»); guard считает пути по всему тексту. Фактическая зона —
три файла: `orchestrator/fsm_advance.py` (одна строка вызова в
`_in_dev_plan_escalate` и докстринг `_mark_artifact_escalation`),
`tests/test_artifact_escalation_marker.py` (четыре теста),
`docs/codebase-map.md` (регенерация), плюс приложение к
`skills/escalation-rules.md`.

Прогноз диффа: 12 КиБ (основной объём — сквозной тест цикла `auto`).

Обоснование монолита (для решения Оператора на гейте SPEC): исправление
— одна строка вызова в одном модуле, и его тесты (AC-1..AC-4) проверяют
именно эту строку; часть «только код» осталась бы без регресс-тестов
поведения, часть «только тесты» — красной на main. Докстринг (AC-5) и
приложение к скилу (AC-6) описывают ту же точку записи признака и
отдельно смысла не имеют. Режущей границы по зонам нет.

## Не входит
- Изменение механизма проверки свежести вердикта ревьювера и добавление
  `review` в `_REWORK_GATE_STATES`.
- Ограничитель «две эскалации разработчика подряд без изменения PLAN.md»
  (аналог `_pull_conflict_marker_streak`).
- Правка комментариев в `orchestrator/fsm.py` и `orchestrator/auto.py`
  (решение Оператора 02.10: их зоны не занимаются ради комментариев).
- Изменение `_approve_escalated` и правил `answer_baseline`.
- Команда пульта для обхода через `run`.
- Любые правки файлов только для чтения: `orchestrator/advance_gates/`
  (в том числе `review.py`, `tests_writing.py`, `zones.py`),
  `orchestrator/pull.py`, `orchestrator/runner.py`, `orchestrator/answer.py`,
  `orchestrator/budget.py`, `orchestrator/brief.py`, `orchestrator/config.py`,
  `orchestrator/store.py`, `orchestrator/fsm.py`, `orchestrator/auto.py`,
  `scripts/guard.py`, `tests/test_auto_cycle.py`, `tests/sandbox.py`,
  остальные файлы `tests/` и `skills/`, `docs/backlog.md`, `tasks/`.
- Неослабление существующих тестов и зелёный полный набор `tests/`
  (требование 6 ТЗ) — её держит пульт.

## Материалы
- ТЗ: `tasks/01M3XTF1CEBXT4J7P0EKG5J342/TZ.md` (факты по origin/main
  83a9c96e, номера строк — оттуда).
- Источник: `docs/backlog.md`, строки копилки 28.09 и 30.09 (П1, П2).
- Механика признака: `orchestrator/auto.py` (`_ROLE_STEP_REQUIRED_MARKERS`,
  `_role_step_since_state_entry`, `_rework_gate_blocks`,
  `_REWORK_GATE_STATES`); сторонний читатель —
  `orchestrator/advance_gates/review.py` (`_review_rework_gate`), для
  него смена опорной записи совпадает с его смыслом.
- Бюджет: «Рамка: $15» ТЗ ниже пола калибровки
  (`config.BUDGET_CALIBRATION_FLOOR_USD` = $25); `budget_usd: 40` — уровень
  `config.BUDGET_CALIBRATION_TABLE` для 6 критериев и 3 файлов зоны (≤10 /
  ≤4), ниже дефолта оркестратора $50, с запасом на две итерации ревью.
