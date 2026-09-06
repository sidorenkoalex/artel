---
task: 01M1THKPNZ11DBZAQDMJ33EMJR
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: стоп-кран волны, часть 1 — счётчик класса отказа по волне и алерт

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (константы `config.py`) | OK | `WAVE_BREAKER_WINDOW_SEC=900`, `WAVE_BREAKER_TASKS=3` (orchestrator/config.py:137-144); счётчик и порог читают их через `config.` на каждом вызове, не копируют. |
| 2 (подсчёт по журналу `steps`, классы + «таймаут шага») | OK | `_wave_breaker_task_count` (orchestrator/alerts.py:183-207) фильтрует по `action`/`detail_contains`/окну/target, схлопывает в `set(task_id)`. |
| 3 (алерт на пороге, две точки вызова, дедуп) | OK | `check_wave_breaker_failure`/`check_wave_breaker_timeout` вызваны из `orchestrator/runner.py:856` (после `store.journal(..., "agent run TIMEOUT", ...)`) и `runner.py:882` (после `_record_failure_classification`); дедуп по префиксу сообщения через `open_alerts(conn, "incident")` (alerts.py:225-232), проверено тестом `test_reaching_the_threshold_again_does_not_duplicate_the_alert`. |
| 4 (hung_test_runs не считается) | OK | `doctor.check_hung_test_runs`/`_find_hung_test_runs` пишут только через `alerts.raise_alert`, ни разу не журналируют `steps.action` из `WAVE_BREAKER_FAILURE_ACTION`/`WAVE_BREAKER_TIMEOUT_ACTION` — счётчик их физически не видит; акцептанс AC-7 зелёный. |
| 5 (только target self) | OK | `_wave_breaker_task_count` пропускает задачи с `target != config.DEFAULT_TARGET` (alerts.py:187-188); AC-9 зелёный. |

Критерии приёмки AC-1..AC-9 — все реализованы, приёмочная планка задачи (`tasks/01M1THKPNZ11DBZAQDMJ33EMJR/acceptance_tests/`) прогнана целиком и зелёная (13/13), без пометок `manual`/`skip`.

## Замечания

- major — `tests/test_alerts_wave_breaker.py:66-68,166-169,180-182,212-214,230,243,253-255` — 7 из 13 тестовых методов нового файла не несут обязательную заявку `Ловит мутацию: …` в докстринге (skills/test-authoring.md, раздел «Чувствительность: у теста — заявленная мутация», требование — «для КАЖДОГО тестового метода»); два метода (`test_three_distinct_timeouts_raise_incident_naming_timeout` — строка 230, `test_two_distinct_timeouts_below_threshold_no_alert` — строка 243) не несут докстринга вовсе. Для сравнения: все 13 методов приёмочной планки (`tasks/01M1THKPNZ11DBZAQDMJ33EMJR/acceptance_tests/test_ac*.py`) заявку несут — значит приём применим и достижим здесь же. Последствие: ревьювер следующей итерации/будущий читатель не может свериться с заявленной мутацией по правилу review-checklist («сверяй тест С НЕЙ, а не мысленным мутационным тестом по наитию»); риск, что часть этих 7 тестов тавтологична, не проверен. Предложение: дописать `Ловит мутацию: …` каждому из 7 методов (для двух без докстринга — докстринг целиком, по образцу уже оформленных соседних тестов в том же файле, например `test_two_distinct_tasks_below_threshold_no_alert`).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_alerts_wave_breaker.py:66-68,166-169,180-182,212-214,230,243,253-255 | 7/13 тестов файла без обязательной заявки `Ловит мутацию: …` (2 из них — вовсе без докстринга) | ревью не может свериться с заявленной мутацией; риск тавтологичности не проверен | дописать заявку `Ловит мутацию: …` во все 7 методов (двум добавить докстринг целиком) |

## Вердикт

changes_requested — единственное замечание R1-F1 (major, нарушение обязательного правила skills/test-authoring.md — заявка `Ловит мутацию: …` для КАЖДОГО тестового метода — на 7 из 13 методов нового юнит-теста). Функционально код и приёмочная планка корректны и зелёные; после исправления докстрингов — готово к approve.

## Проверено исполнением

- `python3 -m pytest tests/test_alerts_wave_breaker.py -q` — 13 passed, 3 subtests passed.
- `python3 -m pytest tasks/01M1THKPNZ11DBZAQDMJ33EMJR/acceptance_tests/ -q` — 13 passed (все AC-1..AC-9, без `manual`/`skip`).
- `python3 -m pytest tests/test_failure_classification.py tests/test_agent_failure.py tests/test_doctor.py tests/test_stall_alerts.py tests/test_diff_not_collected_alerts.py -q` — 172 passed, 16 subtests passed (модули, затронутые диффом: точки вызова в runner.py, соседние алерты `alerts.py`, hung-test-runs сторож `doctor.py`).
- `git diff -- tests/` вручную сверен построчно — только добавления (новый файл `test_alerts_wave_breaker.py`), ни один существующий тест/ассерт не ослаблен и не удалён.
- Регенерация `docs/codebase-map.md` (`python3 scripts/codebase_map.py`) сверена с закоммиченной версией: расхождение только в строке `built_at_sha` (не признак дефекта, см. codebase-map.md — built_at_sha); рабочее дерево возвращено в исходное состояние (`git checkout -- docs/codebase-map.md`) после сверки.
- Зона диффа сверена с `zones:` SPEC (`orchestrator/alerts.py, orchestrator/runner.py, orchestrator/config.py, tests/`) — фактический diff (`orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `tests/test_alerts_wave_breaker.py`, `docs/codebase-map.md`) в зону укладывается, посторонних side effects нет.
- Прочитаны `orchestrator/failure_classification.py` (подтверждён модульный импорт `alerts` — обоснование отложенного импорта в `alerts.py` реальное, не мнимое) и `orchestrator/doctor.py` (участок `check_hung_test_runs`/`_find_hung_test_runs` — подтверждено требование 4).

## Предложения системе

(пусто)
