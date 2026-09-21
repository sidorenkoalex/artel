---
task: 01M31JWD10728N5YGWVQGWYACW
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Возврат из эскалации ревьювера: маркер «ответ должен дойти до роли»

Источник: строка копилки П1 20.09 «Возврат из эскалации РЕВЬЮВЕРА снова
уводит задачу мимо роли» и её повтор 21.09 на 01M31DRD81. Решение
Оператора 21.09: заводить задачу на фикс.

Факты:
- Два случая за три дня, одна механика. 20.09, 01M2XJKKPH: reviewer
  поднял `status: escalate`, Оператор `answer` + `approve` → `in_dev`,
  `auto` через 16 с перевёл задачу в `verifying` по готовым артефактам
  без шага developer. 21.09, 01M31DRD81: то же — `state -> in_dev |
  эскалация разрешена, продолжаем` в 08:52:09, в 08:52:22 журнал «шаг
  developer не нужен: переход выполнен по готовым артефактам | in_dev
  -> verifying», код тот же (64399a0d), ANSWER-1 до роли не дошёл.
  Оба раза обход: `stop` + `reject` из `verifying` с причиной — запись
  возврата становится анкером гейта переделки, и он держит advance до
  шага developer.
- Механика дефекта. Возврат из `escalated` пишет detail «эскалация
  разрешена, продолжаем» (`orchestrator/fsm.py::_approve_escalated`,
  `back = t["escalated_from"] or "in_dev"`). `orchestrator/auto.py::
  _role_step_since_state_entry` пропускает такие записи как анкер
  (`_ESCALATED_RETURN_DETAILS`): это возврат к работе, прерванной
  эскалацией, а не новое основание переделки. Исключение —
  `_ROLE_STEP_REQUIRED_MARKERS`: если непосредственно перед возвратом
  в журнале стоит маркер «ответ Оператора должен дойти до роли»
  (`fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER` или
  `pull.PULL_CONFLICT_ROLE_STEP_MARKER`), запись возврата становится
  анкером, и шаг роли обязателен.
- Маркер пишет `orchestrator/fsm_advance.py::_mark_artifact_escalation`
  сразу после `state -> escalated` — для эскалаций по артефакту роли в
  `spec_writing` и `tests_writing` (SPEC 01M2XFSJ1Z7BS6HR69SAT1D81Y).
  Эскалация ревьювера `_review_escalate` (там же) пишет только
  `state -> escalated | эскалация от ревьювера` и маркера НЕ пишет.
  SPEC 01M2XFSJ1Z счёл случай review невоспроизводимым —
  воспроизводится стабильно.
- Возврат эскалации ревьювера идёт в `in_dev` (`escalated_from`
  `_review_escalate` не выставляет). Шаг developer до эскалации уже был
  (задача дошла до ревью), поэтому без анкера гейт переделки его и
  засчитывает.

Требуется:
1. Эскалация ревьювера (`REVIEW.md status: escalate`,
   `fsm_advance._review_escalate`) пишет маркер «ответ Оператора должен
   дойти до роли» тем же вызовом `_mark_artifact_escalation`, что
   эскалации spec_writing/tests_writing, сразу после `state ->
   escalated`. После `answer` + `approve` возврат в `in_dev` становится
   анкером, и предварительный advance не переводит задачу дальше до
   завершённого шага developer, бриф которого несёт ANSWER.
2. Вариант возврата — в `in_dev` с обязательным шагом developer (как
   сегодня возвращается задача, только теперь с анкером). Альтернатива
   из копилки — возврат в `review` с обязательным шагом reviewer — не
   выбирается: ответ Оператора на вопрос ревьювера почти всегда меняет
   трактовку требования, а значит код; developer, которому правок не
   нужно, подтверждает PLAN и выходит дешёвым шагом. Если аналитик
   найдёт довод против — обосновать в SPEC, решение на гейте SPEC.
3. Возвраты из эскалации БЕЗ основания переделки (бюджет, лимит сессии,
   провал агента) ведут себя как сегодня: запись возврата анкером не
   становится, шаг роли, отработанный до эскалации, засчитывается.
4. Тесты (tests/): эскалация ревьювера → answer → approve → auto
   запускает developer (не переходит в verifying по готовым
   артефактам), бриф developer несёт ANSWER; эскалация по бюджету из
   review — поведение прежнее; эскалации spec_writing/tests_writing —
   поведение прежнее. Сценарий 21.09 воспроизводится журналом задачи в
   песочнице. Существующие `tests/test_artifact_escalation_marker.py`,
   `tests/test_auto_escalated_return_rework_gate.py`,
   `tests/test_fsm_review_rework_gate.py`,
   `tests/test_fsm_review_rework_sha_gate.py` остаются зелёными.

Зоны: orchestrator/fsm_advance.py, tests/.

Только чтение (не менять): orchestrator/auto.py
(`_role_step_since_state_entry`, `_ROLE_STEP_REQUIRED_MARKERS` — маркер
уже распознаётся), orchestrator/fsm.py (`_approve_escalated`,
`ARTIFACT_ESCALATION_ROLE_STEP_MARKER`), orchestrator/pull.py,
orchestrator/brief.py (ANSWER в брифе developer уже есть),
docs/backlog.md (источник).

Не входит: изменение точки возврата эскалации ревьювера (остаётся
`in_dev`); правка других видов эскалаций; команда операторской
редактуры артефактов.

Рамка: $25.
