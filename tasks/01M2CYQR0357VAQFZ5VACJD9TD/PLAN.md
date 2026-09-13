---
task: 01M2CYQR0357VAQFZ5VACJD9TD
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Рефакторинг fsm_advance.py — гейты в пакет orchestrator/advance_gates/

## Подход

Дословный перенос (без изменения логики) семейств гейтов из
`orchestrator/fsm_advance.py` (1564 строки, 39 функций) в новый пакет
`orchestrator/advance_gates/` — шесть тематических файлов плюс `_base.py`
с каркасом `_run_gates`/`GateRefusal`. Обработчики состояний
(`spec_writing`, `tests_writing`, `review`, `verifying`, `in_dev`),
эффекты вердиктов (`_review_approved`, `_review_changes_requested`,
`_review_escalate`, `_in_dev_plan_escalate`, `_apply_plan_budget`)
остаются в `fsm_advance.py` и вызывают перенесённые функции по прежним
именам — `fsm_advance.py` реэкспортирует каждое перенесённое имя
`from .advance_gates.<файл> import <имя>` (то есть настоящий алиас,
`is`-идентичный объект, не копия).

**Имя пакета — `orchestrator/advance_gates/`, не `orchestrator/gates/`**
(ANSWER-1.md, вопрос 1, вариант б; подтверждено ANSWER-2.md): буквальное
имя из исходного текста SPEC требования 1 совпадало с существующим
флэт-модулем `orchestrator/gates.py` (политика `gates.yaml`,
ADR-0007/T066) — CPython отдаёт приоритет одноимённому пакету-директории
над модулем-файлом, что уронило бы `import orchestrator.gates` в
`tests/test_gates.py` (9 тестов, вне зон задачи). `orchestrator/gates.py`
и `tests/test_gates.py` не трогаются вовсе.

Состав переносимых имён шире буквального перечня требования 1 SPEC —
дефолтный маркер "прямые помощники"/"их помощники дат/sha" уточнён по
факту: каждая функция, которую существующие тесты (`tests/
test_zones_gate.py`, `tests/test_protected_paths_gate.py`, `tests/
test_fsm_review_rework_sha_gate.py`, `tests/test_git_fixation.py`) или
`orchestrator/answer.py` зовут напрямую как `fsm_advance.<имя>`, обязана
остаться доступной под тем же именем после переноса (требование 3:
полный набор `tests/` зелёный) — она физически переезжает вместе с
основной функцией своей семьи и получает алиас в `fsm_advance.py`,
даже если приёмочные тесты этой задачи не называют её буквально (они
сверяют только то, что названо буквально требованием 1, по
test-authoring.md).

`orchestrator/advance_gates/acceptance.py` НЕ импортирует каркас
`_base` — `_acceptance_lock_refuses`/`_acceptance_run_refuses` не
проходят через `_run_gates` ни до, ни после переноса (требование 3
SPEC, докстринг функции фиксирует решение дословно).

Коллаборанты (`gitcmd`, `store`, `config`, ...) каждый новый подмодуль
импортирует напрямую (`from .. import gitcmd, ...`) — НЕ через
фасад-индирекцию пакета `orchestrator/doctor/` (где подмодули читают
`doctor.gitcmd` вместо прямого импорта): та индирекция там нужна, потому
что тесты `doctor` патчат коллабораторов через атрибут фасада
(`mock.patch.object(doctor, "gitcmd", ...)`). Сверено: ни один тест
`fsm_advance` не патчит коллабораторов через `fsm_advance.<модуль>` —
везде патчится сам модуль (`mock.patch.object(gitcmd, "diff_base",
...)`), импортированный в файле теста напрямую. Прямой импорт в каждом
новом файле — минимальная правка, without введения архитектуры, не
запрошенной SPEC.

## Таблица переносов

| Функция/константа | Источник | Назначение |
|---|---|---|
| `GateRefusal`, `_run_gates` | fsm_advance.py | advance_gates/_base.py |
| `CAPACITY_GATE_REASON`, `_EMPTY_DIFF_TEXT` (реэкспорт из review.py), `_review_git_diff_part`, `_capacity_gate`, `_capacity_gate_refuses` | fsm_advance.py | advance_gates/capacity.py |
| `_ZONES_MANDATE_MARKER`, `_split_zone_paths`, `_touches_zone`, `_protected_paths_touched`, `_protected_path_refusal_detail`, `_plan_zones_extension_paths`, `_STEP_ARTIFACTS_COMMIT_PREFIX`, `_answer_commit_is_role_step_autocommit`, `_answer_zones_mandate`, `_untracked_worktree_paths`, `_zones_gate`, `_zones_gate_refuses` | fsm_advance.py | advance_gates/zones.py |
| `_code_sha_at_review_escalation`, `_review_escalation_sha_gate`, `_REWORK_REFUSAL_ACTION`, `_PULL_MAIN_COMMIT_INFIX`, `_commit_iso_date`, `_latest_developer_commit_iso_date`, `_REVIEWER_STEP_AUTOCOMMIT_PREFIX`, `_reviewer_verdict_baseline`, `_mutation_claim_gate`, `_review_rework_gate`, `_review_rework_gate_refuses` | fsm_advance.py | advance_gates/review.py |
| `_acceptance_lock_refuses`, `_acceptance_run_refuses` | fsm_advance.py | advance_gates/acceptance.py |
| `_freshness_refuses`, `_origin_push_gate`, `_registry_gate`, `_tests_writing_stray_plank_files_gate`, `_tests_writing_acceptance_dir`, `_tests_writing_dry_collect_gate` | fsm_advance.py | advance_gates/tests_writing.py |

Остаются в `fsm_advance.py` без изменений: `spec_writing`,
`tests_writing`, `review`, `verifying`, `in_dev` (обработчики
состояний), `_review_approved`, `_review_changes_requested`,
`_review_escalate`, `_in_dev_plan_escalate`, `_apply_plan_budget`
(эффекты вердиктов) — все они вызывают перенесённые функции через
алиасы модуля, реэкспортированные вверху файла.

## Шаги

1. Создать `orchestrator/advance_gates/__init__.py`,
   `_base.py`, `capacity.py`, `zones.py`, `review.py`, `acceptance.py`,
   `tests_writing.py` — дословный перенос кода по таблице выше, с
   заголовочным докстрингом каждого файла и адресными импортами
   коллабораторов.
2. Заменить в `orchestrator/fsm_advance.py` перенесённые определения на
   реэкспорт (`from .advance_gates.<файл> import <имя>`) — сохранить
   алиасы для каждого имени, которое зовут внешние тесты/`answer.py`
   (список — «Влияние на систему»); убрать более не нужные импорты
   (`datetime`, `timezone`, `typing.NamedTuple`, `auto`, `checkpoint`,
   `github_adapter`, `repo_context`, `agent_log`, `from .review import
   ...` — переехали в новые подмодули).
3. Поправить импорты/пути патчей (без изменения логики) в перечисленных
   требованием 4 девяти тестовых файлах, если конкретный файл того
   потребует после переноса (по факту — не потребовалось ни одного:
   все девять файлов зовут `fsm_advance.<имя>` напрямую и патчат
   коллабораторов как отдельные модули, не через атрибут `fsm_advance`
   — оба класса обращений переживают перенос без правки, проверено
   прогоном).
4. Регенерировать `docs/codebase-map.md`
   (`python3 scripts/codebase_map.py`) тем же коммитом.
5. Смоук до/после (раздел ниже), полный набор `tests/`, коммит, guard.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 1, 2, 5 |
| 4 | 3 |
| 5 | 4 |
| 6 | (этот файл) |

## Влияние на систему

Перенос затрагивает только `orchestrator/fsm_advance.py` (правится) и
`orchestrator/advance_gates/*` (новые файлы) — `orchestrator/gates.py`,
`orchestrator/fsm_autogate.py`, `tests/test_gates.py` не трогаются
(ANSWER-1.md/ANSWER-2.md). `orchestrator/answer.py` не правится и
продолжает работать: три имени, которые он берёт через
`fsm_advance._split_zone_paths`/`_plan_zones_extension_paths`/
`_ZONES_MANDATE_MARKER`, остаются доступны как атрибуты `fsm_advance`
(алиасы на `advance_gates.zones`).

Логика гейтов (тексты отказов, порядок вызова, обход `_run_gates` у
`_acceptance_run_refuses`, схема БД) не меняется ни на символ — только
физическое местоположение определений. Откат — `git revert` одного
merge-коммита этой задачи (единственный коммит, создающий
`orchestrator/advance_gates/` и правящий `orchestrator/fsm_advance.py` +
`docs/codebase-map.md`); после revert `fsm_advance.py` возвращается к
прежнему монолиту байт-в-байт, внешние зависимости (`answer.py`,
`fsm.py`) не замечают отката, так как ни разу не импортировали
`advance_gates` напрямую.

Полный набор `tests/` прогнан ДО правки (базовая линия, зелёный) и
ПОСЛЕ (см. «Риски»/смоук ниже) — зафиксированные тексты отказов гейтов
(`tests/test_capacity_gate.py`, `tests/test_zones_gate.py`, `tests/
test_fsm_advance_gate_smoke.py`) не менялись, поэтому побайтовое
совпадение stdout/журнала — то же самое свойство, что и раньше.

## Смоук-проверка до/после

До правки (зафиксировано): `python3 -m pytest tests/test_fsm_advance_gate_smoke.py
tests/test_zones_gate.py tests/test_capacity_gate.py -p no:cacheprovider
-p timeout -o timeout=120` — зелёный, 3 файла.

После правки: тот же набор команд — идентичный результат (0 отличий в
количестве тестов/их именах), плюс явный `import orchestrator.fsm_advance`
и `import orchestrator.advance_gates` без ошибок (коллизия имени с
`orchestrator.gates` отсутствует — `orchestrator.gates.__file__`
по-прежнему указывает на файл `gates.py`, не на пакет).

`artel.py status`/`report`/`doctor` без изменяющих флагов — не
применимо к этой задаче: перенос не трогает CLI-поверхность,
БД-схему или журнал, только внутреннюю организацию модуля Python;
единственная наблюдаемая поверхность — тексты гейтов, зафиксированные
существующими тестами.

## Риски

Функция, физически оставшаяся в `fsm_advance.py`, но случайно
включённая в реэкспорт (или наоборот) — ловится AC-1/AC-2 приёмочными
тестами (`__module__` объекта) и падением импорта при циклической
зависимости. Проверено вручную по каждому имени таблицы выше.

## Предложения системе

(нет)
