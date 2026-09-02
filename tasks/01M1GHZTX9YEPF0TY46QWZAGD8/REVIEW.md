---
task: 01M1GHZTX9YEPF0TY46QWZAGD8
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 3
---

# REVIEW: approve — полный sha в подсказках и приём уникального префикса

## Фаза A: гейт плана

Таблица покрытия PLAN.md полна: требование 1 → шаги 1-3, требование 2 →
шаг 4, требование 3 → шаг 4. Шаги проверяемого размера (не микрооперации,
не «сделать всё»), подход переиспользует существующие узлы
(`fixation.py`, `fsm.py`, `fsm_autogate.py`, `auto.py`, `runner.py`,
`config.py`) без новых модулей. Явное и обоснованное решение НЕ трогать
`fsm_merge_gate.py` (повторные approve уже НА merge_gate — не одна из
трёх категорий требования 1) проверено отдельно ниже (см. «Соответствие
SPEC», требование 1) — обоснование подтвердилось: ни один из вызовов
`set_state(..., "escalated", ...)` вне `runner.py` не печатает hint с
`approve` вообще (проверено `grep` по всем сайтам эскалации в
`budget.py`, `fsm_advance.py`, `fsm.py`, `fsm_merge_gate.py` — там либо
нет команды-подсказки, либо это `artel.py budget`, не `approve`), так
что расширять точки вставки требования 1 было некуда. Замечаний к плану
нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Все три категории (auto-stop `config.AUTO_STOP`/`auto.auto_stop_advice`, вход в `merge_gate` из `fsm._cmd_approve` и `fsm_autogate._maybe_autogate_acceptance`, обе эскалации `runner._cmd_run`) печатают зафиксированный sha; подтверждено юнит- и приёмочными тестами (AC-1) и ручной проверкой полноты — других мест, печатающих `artel.py approve <id>` без sha для перехода из этих трёх категорий, не осталось. |
| 2 | OK | `fsm.confirm_fixation` сравнивает через `current.startswith(sha)` после проверки длины; полный sha и префикс от 8 символов проходят одинаково (AC-2, тесты `test_ac2_prefix_accepted.py`, `ApproveAcceptsFixedShaPrefixTest`). |
| 3 | OK | Несовпадающий префикс/значение той же или большей длины отклоняется прежним текстом «не совпадает с зафиксированным {current}» (AC-3); префикс короче 8 символов — отдельным именованным отказом до сравнения (AC-4), с текстом, не содержащим «не совпадает». |

## Замечания

- major — `tests/test_git_fixation.py:881,885,914,921,928,953,984,1001,1026,1035,1048` —
  11 из 13 новых тестовых методов в этом файле не несут в докстринге
  заявку `Ловит мутацию: …` (review-checklist, п. «Тесты»; skills/test-authoring.md,
  раздел «Чувствительность»): `ApproveShaHintTest.test_empty_when_fixation_not_available`
  (881), `ApproveShaHintTest.test_leading_space_and_sha_when_fixed` (885),
  `AutoStopHintIncludesShaOnEveryApproveNeedsShaStateTest.test_spec_gate_auto_stop_hint_includes_full_fixed_sha`
  (914) и `...test_acceptance_auto_stop_hint_includes_full_fixed_sha` (921) —
  без докстринга вовсе; `...test_escalated_auto_stop_hint_includes_full_fixed_sha`
  (928) — докстринг есть, но это пояснение объёма теста, не заявка о
  мутации; `AutogateMergeGateHintIncludesShaTest.test_autogate_transition_hint_includes_full_fixed_sha`
  (953), `RunnerEscalationHintsIncludeShaTest.test_integrity_incident_hint_includes_full_fixed_sha`
  (984), `...test_agent_failure_escalation_hint_includes_full_fixed_sha` (1001),
  `ApproveAcceptsFixedShaPrefixTest.test_prefix_of_fixed_sha_transitions_like_the_full_value`
  (1026), `...test_value_of_min_length_not_a_prefix_is_refused_with_fixed_sha`
  (1035), `...test_value_shorter_than_min_length_is_refused_by_name` (1048) —
  без докстринга вовсе. Для сравнения — все пять файлов в
  `tasks/01M1GHZTX9YEPF0TY46QWZAGD8/acceptance_tests/` эту конвенцию
  соблюдают полностью, так что разрыв — не пробел в понимании конвенции,
  а систематический пропуск именно в этом файле. Без явной заявки
  ревьювер не может свериться с тем, какую мутацию каждый тест обязан
  ловить (сам список тестов выглядит содержательным, но это не заменяет
  требуемую форму). Предложение: добавить каждому из перечисленных
  методов докстринг со сценарием и строкой `Ловит мутацию: …` (по образцу
  уже оформленных тестов этого же MR, например `test_prefix_of_fixed_sha_transitions_like_the_full_value`
  логично ловит мутацию «сравнение снова стало строгим `==`, а не
  `startswith` после среза», `test_value_shorter_than_min_length_is_refused_by_name`
  — мутацию «проверка длины убрана/перепутана местами с проверкой
  совпадения»).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_git_fixation.py:881,885,914,921,928,953,984,1001,1026,1035,1048 | 11 новых тестовых методов без докстринга с заявкой `Ловит мутацию: …` | ревьювер не может проверить заявленную чувствительность теста при следующих итерациях; конвенция test-authoring нарушена систематически | добавить докстринг со сценарием и строкой `Ловит мутацию: …` каждому перечисленному методу |

## Вердикт

changes_requested — единственное замечание (R1-F1): добавить докстринги
с заявкой `Ловит мутацию: …` перечисленным 11 тестовым методам в
`tests/test_git_fixation.py`. Сама реализация (обе части SPEC) корректна,
проверена запуском полного набора тестов и приёмочных тестов задачи —
исправление ожидается точечным, без изменения логики.

## Проверено исполнением

- `python3 -m pytest tests/test_git_fixation.py -q` — 38 passed.
- `python3 -m pytest tasks/01M1GHZTX9YEPF0TY46QWZAGD8/acceptance_tests/ -q` — 6 passed (AC-1..AC-5, один файл даёт 2 теста на AC-1).
- `python3 -m pytest tests/ -q` — 1235 passed, 408 subtests passed, без регрессий.
- `python3 scripts/codebase_map.py` (прогнан и сверен построчно с `docs/codebase-map.md` из diff через `grep -v '^built_at_sha:'`) — расхождение только в строке `built_at_sha` (текущий HEAD после подтяжки main новее коммита, которым карта в диффе была собрана) — не дефект (см. review-checklist, built_at_sha); рабочее дерево возвращено в чистое состояние (`git checkout -- docs/codebase-map.md`) после проверки.
- Ручной обзор всех сайтов `set_state(..., "escalated", ...)` (`grep -rn '"escalated"' orchestrator/*.py`) вне `runner.py` — ни один не печатает hint `artel.py approve` без sha, подтверждает полноту покрытия требования 1 и обоснованность решения PLAN не трогать `fsm_merge_gate.py`.

## Предложения системе
