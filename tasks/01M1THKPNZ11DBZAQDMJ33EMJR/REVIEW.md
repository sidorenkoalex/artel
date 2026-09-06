---
task: 01M1THKPNZ11DBZAQDMJ33EMJR
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: стоп-кран волны, часть 1 — счётчик класса отказа по волне и алерт

## Замечание к пакету ревью (диагностика перед вердиктом)

Ревью-пакет не показал ни SPEC.md, ни PLAN.md этой задачи («не найден
ни в ветке, ни в дереве»), а инкрементальный diff (от sha
447286df6bccc43ef839d7564d91c9050ce81e3b до HEAD) состоял целиком из
подтяжек main, несущих содержимое ДВУХ чужих задач
(01M1RFVWV6WWTXRC5F40K61632 — наблюдатель роста карты кодовой базы;
01M1SHJTT0V516BWHYXWS50F3G — автогейт приёмки по CI) — ни строкой не
относящихся к предмету этой задачи. Тот же класс ложного сигнала уже
independent зафиксирован ревью 01M1SAA2AZX3ERQ779QJ5TS9J4/
01M1SCQ6WZHMQVK1AHP9F392JZ и описан в review-checklist.md
(«Инкрементальный diff пакета — пустой не значит «без изменений»»).

Корень в этот раз конкретнее: `447286df` — не «автокоммит роли,
лежащий позже коммита-вердикта» (уже описанный в skill класс), а
сам developer-коммит, ЗАКРЫВШИЙ замечание R1-F1 итерации 1 (см. ниже) —
то есть выбранная точка отсчёта уже включает саму правку, которую и
предстоит проверить в этой итерации, поэтому diff «от неё до HEAD»
закономерно пуст по зоне задачи и показывает только последующий шум
подтяжек main.

Восстановил фактический материал вручную:
- `git show artifact/01m1thkpnz11dbzaqdmj33emjr:tasks/01M1THKPNZ11DBZAQDMJ33EMJR/{SPEC,PLAN,REVIEW}.md`
  — прочитаны напрямую из артефактной ветки.
- `git log --oneline --all --grep=01M1THKPNZ11DBZAQDMJ33EMJR` (по
  времени коммитов) — восстановлена хронология: `10c291a0` (08:40:21,
  исходная реализация developer), `8d9ab90b` (08:45:56, автокоммит
  артефактов reviewer — вердикт итерации 1, changes_requested),
  `447286df` (08:48:42, ЧЕРЕЗ 3 минуты — фикс R1-F1: докстринги «Ловит
  мутацию» во всех 13 методах `tests/test_alerts_wave_breaker.py`),
  `52d16fb1` (08:49:00, автокоммит артефактов developer), далее только
  подтяжки main (`c0af044a`, `1a01c4ec` — обе с меткой этой задачи, но
  без единой строки в её зоне) и чужие задачи.
- `git diff 10c291a0..HEAD --stat -- orchestrator/alerts.py
  orchestrator/runner.py orchestrator/config.py
  tests/test_alerts_wave_breaker.py` — единственное отличие от
  исходной реализации: `tests/test_alerts_wave_breaker.py` (+43/-5,
  ровно фикс R1-F1) и `orchestrator/config.py` (+12 строк) —
  построчная проверка (`git diff 10c291a0..447286df -- config.py` —
  пусто; `git diff 447286df..HEAD -- config.py` — все 12 строк) показала,
  что прирост `config.py` целиком — три константы `MAP_GROWTH_*` чужой
  задачи 01M1RFVWV6WWTXRC5F40K61632, пришедшие подтяжкой main, не
  работа этой задачи. `orchestrator/alerts.py`/`orchestrator/runner.py`
  не изменились ни байтом с `10c291a0`.

## Фаза A: проверка плана

PLAN.md не менялся с итерации 1 (фикс R1-F1 — только тесты, не код
подхода/шагов). Подход (счётчик и дедуп в `alerts.py`, две точки вызова
в `runner.py`, константы в `config.py`, Python-фильтр по
`store.all_tasks`/`task_steps` без нового SQL) соответствует
конвенции (SQL только в `store.py`, ADR-0003 3ж) и не конфликтует с
существующей архитектурой (`raise_token_rate_divergence_alert` —
прямой прецедент дедупа по префиксу сообщения). Покрытие требований
таблицей плана полное. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (константы `config.py`) | OK | Без изменений с итерации 1 — `WAVE_BREAKER_WINDOW_SEC=900`, `WAVE_BREAKER_TASKS=3` (orchestrator/config.py:143-144), проверено повторно. |
| 2 (подсчёт по журналу, классы + «таймаут шага») | OK | Без изменений — `_wave_breaker_task_count` (orchestrator/alerts.py:183-207). |
| 3 (алерт на пороге, две точки вызова, дедуп) | OK | Без изменений — вызовы `orchestrator/runner.py:859` (после `"agent run TIMEOUT"`) и `runner.py:884` (после `_record_failure_classification`), проверено повторно чтением. |
| 4 (hung_test_runs не считается) | OK | Без изменений. |
| 5 (только target self) | OK | Без изменений. |

Единственное содержательное изменение этой итерации — закрытие R1-F1
(докстринги «Ловит мутацию» в `tests/test_alerts_wave_breaker.py`),
функциональность кода не тронута.

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_alerts_wave_breaker.py | 7/13 тестов без обязательной заявки `Ловит мутацию: …` (2 — вовсе без докстринга) | ревью не может свериться с заявленной мутацией | Проверил все 7 методов (`test_three_distinct_tasks_reach_threshold`, `test_non_transient_class_is_ignored`, `test_none_failure_class_is_ignored`, `test_message_names_the_configured_window_in_minutes`, `test_three_distinct_timeouts_raise_incident_naming_timeout`, `test_two_distinct_timeouts_below_threshold_no_alert`, `test_timeout_is_not_summed_with_failure_classes`) — каждый несёт содержательную заявку, описывающую конкретную мутацию и наблюдаемый провал (не пересказ имени метода). Прогнал файл — 13/13 зелёные. Закрыто. |

Реестр закрыт целиком.

## Вердикт

approved

## Проверено исполнением

- `git show artifact/01m1thkpnz11dbzaqdmj33emjr:tasks/01M1THKPNZ11DBZAQDMJ33EMJR/{SPEC,PLAN,REVIEW}.md` — восстановлены реальные артефакты задачи (пакет их не показал).
- `git log --oneline --all --grep=01M1THKPNZ11DBZAQDMJ33EMJR` + `git log -1 --format="%h %ci %s" <sha>` по каждому коммиту — восстановлена хронология, подтверждено: `447286df` — фикс R1-F1, сделанный ПОСЛЕ вердикта итерации 1 (`8d9ab90b`), не «автокоммит роли» и не посторонний коммит.
- `git diff 10c291a0..HEAD --stat -- orchestrator/alerts.py orchestrator/runner.py orchestrator/config.py tests/test_alerts_wave_breaker.py` и `git diff 10c291a0..447286df`/`git diff 447286df..HEAD` по каждому файлу зоны — восстановлен фактический предмет ревью: единственное изменение с итерации 1 — `tests/test_alerts_wave_breaker.py` (+43/-5); прирост `config.py` (+12 строк) целиком — чужие константы `MAP_GROWTH_*`, пришедшие подтяжкой main (задача 01M1RFVWV6WWTXRC5F40K61632), не работа этой задачи.
- `python3 -m pytest tests/test_alerts_wave_breaker.py -q` — 13 passed, 3 subtests passed.
- `python3 -m pytest tasks/01M1THKPNZ11DBZAQDMJ33EMJR/acceptance_tests/ -q` — 13 passed (AC-1..AC-9, без manual/skip).
- `python3 -m pytest tests/test_failure_classification.py tests/test_agent_failure.py tests/test_stall_alerts.py tests/test_diff_not_collected_alerts.py -q` — 59 passed, 13 subtests passed (модули, соседствующие с точками вызова в runner.py/alerts.py).
- `grep -n "WAVE_BREAKER" orchestrator/config.py`, `grep -n "wave_breaker" orchestrator/alerts.py`, `grep -n "check_wave_breaker" orchestrator/runner.py` — построчно сверены с PLAN/SPEC, расхождений нет.
- `python3 scripts/guard.py tasks/01M1THKPNZ11DBZAQDMJ33EMJR/SPEC.md tasks/01M1THKPNZ11DBZAQDMJ33EMJR/PLAN.md` — «GUARD: ок».
- `python3 scripts/codebase_map.py` + сверка diff `docs/codebase-map.md` — расхождение только в строке `built_at_sha` (не дефект); откачено `git checkout -- docs/codebase-map.md`, `git status --short` — чисто (кроме материализованного `tasks/01M1THKPNZ11DBZAQDMJ33EMJR/`).
- Полный набор `tests/` не гонял (решение Оператора 05.09 — гоняет CI на каждый пуш) — прогнаны планка задачи и все модули, реально пересекающиеся с диффом со времени предыдущего вердикта, плюс соседние модули, названные проверкой итерации 1.

## Предложения системе

- Baseline инкрементального diff (`review.previous_verdict_sha`) на
  этой задаче указал на `447286df` — коммит, которым РАЗРАБОТЧИК сам
  закрыл замечание предыдущей итерации (R1-F1), а не на код,
  который РЕВЬЮВЕР действительно рецензировал в прошлый раз: diff «от
  этой точки до HEAD» закономерно пуст по зоне задачи и показывает
  только шум последующих подтяжек main. Отличается от уже описанного в
  skills/review-checklist.md класса («sha указывает на автокоммит
  роли, лежащий позже коммита-вердикта») тем, что здесь sha — не
  автокоммит артефактов, а содержательный код-коммит фикса; тот же
  практический эффект (пустой/бесполезный diff, реальный материал
  приходится восстанавливать вручную по `git log --grep`). Стоит
  учесть этот вариант в работе над задачей о трёхточечном diff'е
  (01M1SG9T96, уже в работе).
