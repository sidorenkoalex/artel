---
task: 01M5AA5TS90RDJ2AFXB882WTPD
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: G2б-1 — долгоживущие файлы компонента по шаблону `long_lived`, строка группы и «Ловит мутацию:» у файлов с меткой `AC-<n>: `

## Фаза A: план
- Таблица покрытия полна (требования 1–11 → шаги 1–5); шаги размера MR.
- Подход (признак `Profile.long_lived_template`, `project_profile.long_lived_rule` → `None` у явной пары/`test_profile`/артели) держит границу задачи из решения Оператора №1 и не расходится с архитектурой: `zones.py`, `checkpoint.py`, `acceptance.py`, `plank_run.py` не тронуты.
- «Влияние на систему» сходится с диффом: 10 модулей зоны, плюс `tests/test_01m58fnwbv25ff26e7az9q9912_components.py` (правку разрешает требование 1) и новый `tests/test_long_lived_template_shape.py`. Вне зон ничего нет. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets._check_component_rules`: порядок «форма → шаблон или пара → наличие»; `_long_lived_shape_error` проверяет `<id>`/`<name>`, `<dir>`, корень и маски у правила-метки; повторы `_mask_segment_matches`/`_is_pytest_command` совпадают с `guard.py:2590` и `acceptance.py:709` построчно; подслучай G1а приведён к `tests/test_<id>_<name>.py`, утверждения те же |
| 2 | OK | `_with_long_lived_pairs` работает только с копией (`load`/`target`), `check` не мутирует словарь (AC-16 зелёный); `long_lived_template` с `compare=False` заполняется в `_with_component_fields` |
| 3 | OK | `<dir>/` → `(?:[A-Za-z0-9_-][A-Za-z0-9_.-]*/)*`; `guard.long_lived_example`; `Profile.long_lived_example` вызывает её. Для явной пары результат тот же, что у прежней склейки |
| 4 | OK | `Profile.long_lived_hint`: при шаблоне — пример пути, иначе прежняя склейка `prefix+<имя>.py`; runner, 2а (с пояснением `<каталог>`), 5, developer, `long_lived_plank_errors` — тексты дословно сверены тестами AC-15/AC-13 |
| 5 | OK | `plank_file_group(source, labelled)` читает `first_comment` без ведущей « * »; гейт групп и `preflight._groups` идут по правилу планки, гейт долгоживущих и `preflight._long_lived` — по `long_lived_group_errors` (одна функция на оба места); отказ `LONG_LIVED_UNCHECKABLE` срабатывает только при `rule is not None` |
| 6 | OK | `_labelled_long_lived_errors`: `tasks/` и id без учёта регистра в каждой строке; «Ловит мутацию:» через `_comment_above`; строка головы — из `_test_calls` (`TEST_CALL_HEAD` привязан к началу строки, поэтому номер — строка `.each(`) |
| 7 | OK | Пары (путь, текст) идут только при шаблоне (`fsm_advance.tests_writing`, `preflight._traceability`); `scan_ac_content` строки разбирает как Python при любом `rule` (`guard.py:614`), поэтому у явной пары исход прежний |
| 8 | OK | `_refuse_labelled` в обоих режимах стоит до записей; в рабочей копии — снимок до ∪ после правки; в `--from-branch` — снимки ∪ перечень и голова. AC-11 проверяет неизменность ветки документов, кодовой ветки, лока и журнала |
| 9 | OK | Зоны, перечень и сверка идут через `Profile.is_long_lived` без правки модулей; сторож предпроверки зелёный, файл сторожа не тронут |
| 10 | OK | Тексты артели, sled и явной пары закреплены тестами AC-13 (зелёные) |
| 11 | OK | Тесты детерминированы зерном, без Node и сети (`subprocess.Popen` подменён шпионом) |

## Замечания
Ни одного blocker/major/minor по коду. Наблюдение о времени долгоживущего файла (72.9 с при пороге 60 с) — в «Предложениях системе»: файл под локом, его правка — не предмет этого MR.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M5AA5TS90RDJ2AFXB882WTPD` — 1 passed (`test_ac14_preflight_sentry.py`), код выхода 0.
- `python3 -m pytest -q -p no:xdist tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py tests/test_long_lived_template_shape.py tests/test_01m58fnwbv25ff26e7az9q9912_components.py` — 31 passed, 180 subtests passed.
- `python3 -m pytest -q -p no:xdist tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py` — 28 passed, 57 subtests passed (60.8 с).
- Временная мутация `orchestrator/targets.py:479` (`if masks and not _is_pytest_command(...)` → `if masks:`) — `test_long_lived_template_shape.py::test_pytest_component_template_not_checked_against_masks` красный, как заявлено; код возвращён, `git status` чистый.
- `git diff 2a281643...HEAD -- tests/` вне долгоживущих файлов задачи: изменена одна строка входа подслучая G1а (основание — требование 1), утверждения не тронуты; удалённых и ослабленных ассертов нет.
- Сверка повторов в `targets.py` с `guard._mask_segment_matches` (`scripts/guard.py:2590`) и `acceptance.is_pytest_command` (`orchestrator/acceptance.py:709`) — тела совпадают.
- `grep` вызывающих `targets.load`/`targets.target`: ни один не прогоняет загруженную запись повторно через `check` и не пишет её обратно в `targets.yaml`, поэтому производная пара в копии отказа «либо шаблон, либо пара полей» не вызовет.

## Предложения системе
- Долгоживущий `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py` идёт 72.9 с при пороге 60 с: каждый метод заново поднимает песочницу настоящего git и делает полный `advance`. Скил test-authoring не советует общий стенд класса для таких сценариев (`setUpClass`), и после мержа это время ляжет на CI каждого пуша.
