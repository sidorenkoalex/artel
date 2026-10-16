---
task: 01M52EEDEYV14658X8VFNHCW8K
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: D0-1: профиль test_profile — подполя runner, workdir, env и фиксация мест запуска

## Фаза A: план
- Таблица покрытия полна: требования 1–5, 8 — шаг 1 (`targets.py`), 6 — шаг 2
  (`project_profile.py`), 7 — долгоживущий файл test_author, код мест запуска
  не трогается (SPEC «Не входит»).
- Шаги — единицы размера MR. Подход в рамках существующей архитектуры
  (новые виды `runner`/`mapping` в `_profile_value_error`, прежний шаблон
  отказа). Ленивый импорт `providers` обоснован циклом
  `providers → claude → runner → store → targets`.
- «Влияние на систему» = diff: тронуты только `orchestrator/targets.py`,
  `orchestrator/project_profile.py` (и карта кодовой базы). Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `runner`/`workdir`/`env` в `PROFILE_FIELDS` и `PROFILE_OPTIONAL` (`targets.py:52-60`); профиль без них проходит (AC-5 зелёный). |
| 2 | OK | Вид `runner`: `value not in PROFILE_RUNNERS` после проверки «непустая строка»; умолчание `PROFILE_RUNNER_DEFAULT`. |
| 3 | OK | `workdir` — существующий вид `dir`: ведущий `/`, сегмент `..`, пустой сегмент — отказ; `a..b` проходит. |
| 4 | OK | Вид `mapping`: не `dict` → отказ; значение не `str` (int/bool/None/float) → отказ; пересечение с `secret_env_names()` (реестр на момент вызова + `GITHUB_TOKEN`, `GH_TOKEN`), точное имя. `yamlmini.py` и `providers/` не тронуты. |
| 5 | OK | `profile.get("runner", PROFILE_RUNNER_DEFAULT) != pytest-own` + наличие `workdir`/`env` → отказ, в т.ч. без `runner`. |
| 6 | OK | `Profile.runner/workdir/env` с умолчаниями; `env` — `MappingProxyType`, `hash=False` (frozen-dataclass остаётся хэшируемым — проверено); построение kwargs без новых полей работает. |
| 7 | OK | `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`: все восемь мест, оба пути команды где требуются, argv/`cwd` литералами, окружение разницей с `os.environ`; правка `PYTHONUNBUFFERED` — по ANSWER-1 через `amend-tests`, ожидания не ослаблены. |
| 8 | OK | Все отказы — «подполе 'test_profile.<подполе>' — …»; `test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py` зелёный без правки. |

## Замечания

Блокеров и major нет. Наблюдения без влияния на вердикт:
- `orchestrator/targets.py:296` — при `runner: pult-pytest` и `env` с секретом
  отказ называет секрет, а не правило «только при pytest-own»: проверка
  значения идёт раньше правила требования 5. Отказ всё равно есть, текст
  называет `test_profile.env` — SPEC это допускает.
- `workdir: a/./b` проходит (как у прежнего вида `dir`) — SPEC такого
  отказа не требует.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний в этой итерации не заведено; прошлых итераций нет.

## Вердикт
approved

## Проверено исполнением
- `PYTHONUNBUFFERED=1 python3 -m pytest -q -p no:cacheprovider tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py tests/test_project_profile_gates.py tests/test_network_address_gate.py` — 38 passed, 103 subtests passed (с `PYTHONUNBUFFERED=1`, т.е. в окружении полного прогона, по ANSWER-1).
- `python3 -m pytest -q tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py tests/test_01m4s0jvb85w9ty1esgnbh97fp_targets_knowledge.py tests/test_01m4tvbt9zcrqdy669qv3s95ma_min_uses_field.py tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py tests/test_project_profile.py` — 26 passed, 177 subtests passed.
- `artel.py plank-run 01M52EEDEYV14658X8VFNHCW8K` — «планки нет: нет файлов test_*.py»; приёмка задачи целиком в долгоживущих файлах `tests/` (прогнаны выше).
- Граничные случаи `targets._check_profile` вручную: `env: None` при pytest-own → отказ «test_profile.env — не отображение»; `env: {GH_TOKEN: x}` при pult-pytest → отказ с `test_profile.env`; `runner: [a]` → отказ «test_profile.runner — не непустая строка»; `hash(Profile(...))` и `==` работают.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — разница только в `built_at_sha`, карта свежа (изменение откатил).
- Сверка неослабления: diff `tests/` вне долгоживущих файлов задачи пуст; существующие тесты не тронуты.

## Предложения системе
- Пакет ревью при пустой планке задачи (вся приёмка в долгоживущих `tests/`) мог бы сразу сказать «plank-run не применим», чтобы ревьювер не тратил вызов на отказ.
