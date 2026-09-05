---
task: 01M1SC40NT8T1WFKKKJ67CK96Z
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: R1 — разбор цикла `auto` на шаги с явным контрактом

## Фаза A: гейт плана

PLAN.md (`tasks/01M1SC40NT8T1WFKKKJ67CK96Z/PLAN.md`, артефактная ветка,
коммит `edcf5d28`) покрывает все 5 требований SPEC одной строкой шага 1
(таблица «Покрытие требований») — задача монолитная (budget $25, зона
два пути), дробление не требовалось и SPEC явно фиксирует это в разделе
«Оценка объёма и деление». Подход (dataclass-исходы верхнего уровня +
mutable `_CycleState`, владение которым закреплено за одной функцией)
не конфликтует с конвенциями — не вводит новых внешних зависимостей,
не трогает `orchestrator/fsm_advance.py` (запрещено разделом «Не
входит»), не меняет `docs/invariants.md`. Секция «Влияние на систему»
и «Риски» PLAN соответствуют фактическому дифу — проверено ниже
построчным сравнением diff. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (пять именованных функций (а)-(д)) | OK | `_rework_gate_blocks` (а, auto.py:406), `_pre_advance_step` (б, auto.py:429), `_role_run_step` (в, auto.py:545), `_step_limit_stop` (г, auto.py:386) — часть стоп-кранов (г) внутри (б), как и заявлено в PLAN; (д) `auto_stop` не менялся. `_cmd_auto` (auto.py:600) — 83 строки (порог AC-1 — 100), не несёт литералов `runner.cmd_run(`, `_REWORK_GATE_STATES`, `>= config.AUTO_MAX_STEPS`, `>= config.AUTO_STALL_STEPS_LIMIT` (проверено `grep`/AST — см. «Проверено исполнением»). |
| 2 (явные исходы, без локальных флагов) | OK | `Advanced`/`RoleRan`/`Refused`/`Stop` — frozen dataclass верхнего уровня (auto.py:348-384); `_CycleState` (auto.py:336) создаётся один раз в `_cmd_auto` (auto.py:617) и мутируется только внутри `_pre_advance_step` (`grep -n "cycle\."` — все 6 вхождений в диапазоне строк 429-543). Тело `_cmd_auto` не содержит голых имён `idle_steps`/`prev_refusal`. |
| 3 (тексты журнала/подсказок/print буквальны) | OK | Диф — построчный перенос f-строк без единой правки формулировки (сверено вручную по diff); байт-в-байт подтверждено AC-3/AC-6 тестами на трёх сценариях, задевающих все пять шагов. |
| 4 (смоук байт-в-байт до/после) | OK | Закрыт залоченным `acceptance_tests/test_ac3_ac6_output_matches_pre_refactor_fixture.py` — 6 тестов (2 на сценарий × 3 сценария), все зелёные. |
| 5 (`tests/test_auto_cycle.py` и приёмочные 01M1R8B3ZKXQT0Z0G6QQQDV906/01M1RHFRQ2C0P4A57XJJ1WZV8N зелёные без правки утверждений) | OK | `tests/test_auto_cycle.py` — 41 тест, OK, диф этого файла в дереве этой ветки нулевой (файл не входит в `git diff --stat`, правка утверждений исключена структурно). 01M1RHFRQ2C0P4A57XJJ1WZV8N — 10 тестов через `acceptance_tests/test_ac5_...py`, OK. 01M1R8B3ZKXQT0Z0G6QQQDV906 обоснованно помечен `# AC-5: manual` (её `acceptance_tests/` не существует на этой ветке и её дереве — только на `origin/artifact/01m1r8b3zkxqt0z0g6qqqdv906`, которую CI и конвенция «не заводить сеть/чужие ветки из tests/» запрещают доставать отсюда; причина — отсутствие тестового контура в этой песочнице, легальный класс manual, не «сложно/долго»). |

## Замечания

- ...

Замечаний нет — все 6 залоченных приёмочных тестов, полный
`tests/test_auto_cycle.py` (41), `tests/test_stall_alerts.py` и
`tests/test_canary.py` (62) зелёные, поведение цикла подтверждено
байт-в-байт на трёх сценариях, покрывающих все пять шагов декомпозиции;
структурные ограничения AC-1/AC-2 проверены вручную построчно поверх
автоматических AST-тестов (см. «Проверено исполнением»). `docs/
codebase-map.md` перегенерирован тем же коммитом (содержимое совпадает
с `python3 scripts/codebase_map.py`, отличается только строка
`built_at_sha`, что не дефект). Diff не выходит за зону задачи
(`orchestrator/auto.py`, `tests/` — фактически только первый файл плюс
карта, `tests/` не тронут обоснованно, см. PLAN). Публичный контракт
модуля (`cmd_auto`, `auto_stop`, `auto_stop_advice`) не менялся —
`grep -rn "_cmd_auto"` вне `orchestrator/auto.py` показывает только
упоминания в докстрингах/комментариях других задач, ни одного внешнего
вызова приватной функции.

## Реестр замечаний

Пусто — итерация 1, замечаний не заведено.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M1SC40NT8T1WFKKKJ67CK96Z/acceptance_tests -v` — 12 тестов (AC-1, AC-2 ×2, AC-3 ×3, AC-6 ×3, AC-4, AC-5), все `ok`.
- `python3 -m unittest tests.test_auto_cycle` — 41 тест, OK.
- `python3 -m unittest tests.test_stall_alerts tests.test_canary` — 62 теста, OK (смежные модули, зависящие от поведения `_cmd_auto`).
- `python3 scripts/codebase_map.py` в рабочей копии + сравнение с закоммиченным `docs/codebase-map.md` построчно без `built_at_sha` (`grep -v '^built_at_sha:'`) — файлы идентичны, карта свежая; после проверки локальная перегенерация отменена (`git checkout -- docs/codebase-map.md`), в дереве чисто.
- AST-проверка вручную (`ast.parse` + обход): `_cmd_auto` — 83 строки, топ-уровневые функции/классы модуля после разбора — `_CycleState`, `Advanced`, `RoleRan`, `Refused`, `Stop`, `_step_limit_stop`, `_rework_gate_blocks`, `_pre_advance_step`, `_role_run_step` (полный список см. `grep -n "^def \|^class \|^@dataclass" orchestrator/auto.py`).
- `grep -n "cycle\." orchestrator/auto.py` — все мутации `_CycleState` (6 вхождений) лежат внутри `_pre_advance_step` (auto.py:429-543), `_cmd_auto` только создаёт объект и передаёт его дальше.
- `grep -rn "_cmd_auto" .` (за пределами `orchestrator/auto.py`) — только докстринги/комментарии сторонних задач, ни одного вызова приватной функции извне.
- Ручное построчное сравнение diff `_pre_advance_step`/`_role_run_step`/`_cmd_auto` с дорефакторинговым телом — порядок вызовов (`fsm.cmd_advance` → чтение состояния → анализ отказа → `runner.cmd_run`) и место инкремента `steps` не изменились; расхождение по инкременту `steps` в путях, ведущих к немедленному `return` из `_cmd_auto` (guard-отказ, два одинаковых отказа подряд, буксование N шагов), не наблюдаемо — `steps` нигде не читается после этих `return`, и `auto_stop`/`auto_stop_advice` его не принимают.

## Предложения системе

Пусто.
