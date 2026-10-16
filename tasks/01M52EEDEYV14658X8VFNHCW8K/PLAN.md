---
task: 01M52EEDEYV14658X8VFNHCW8K
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: D0-1: профиль test_profile — подполя runner, workdir, env и фиксация мест запуска

## Подход
- `orchestrator/targets.py`: в `PROFILE_FIELDS` три новых необязательных
  подполя (`PROFILE_OPTIONAL`): `runner` — вид `runner` (ровно
  `PROFILE_RUNNERS = ("pult-pytest", "pytest-own")`), `workdir` — вид
  `dir` (существующая проверка: ведущий `/`, сегмент `..`, пустой сегмент —
  отказ; `a..b` проходит), `env` — новый вид `mapping` (отображение,
  значения — строки, имя не из перечня секретов). Текст отказа — тот же
  шаблон `подполе 'test_profile.<подполе>' — <причина>`
  (`_check_profile`). После проверки значений — условие требования 5:
  `workdir`/`env` при действующем `runner` (по умолчанию `pult-pytest`)
  отличном от `pytest-own` — отказ с именем подполя.
- Перечень секретов — публичная функция `targets.secret_env_names()`
  (читатели — следующие части D0): `secret_env_names()`
  всех провайдеров `providers.PROVIDERS` в момент вызова плюс
  `GITHUB_TOKEN`, `GH_TOKEN`; сверка по точному имени. Импорт
  `providers` — внутри функции: `providers` → `claude` → `runner` →
  `store` → `targets`, импорт на уровне модуля даёт цикл.
- `orchestrator/project_profile.py`: `Profile` получает поля
  `runner = "pult-pytest"`, `workdir = ""`, `env` — неизменяемое
  отображение (`MappingProxyType`, по умолчанию пустое, исключено из
  хэша — `dict` в frozen-dataclass нехэшируем); `from_values` переносит
  подполя с теми же умолчаниями. Построение именованными аргументами без
  новых полей не меняется.
- Требование 7 (фиксация мест запуска) закрыто долгоживущим файлом
  test_author `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`;
  места запуска не меняются (SPEC «Не входит»).

## Шаги
1. `targets.py` — подполя, вид `mapping`, вид `runner`, условие
   `pytest-own`, перечень секретов из реестра.
2. `project_profile.py` — поля `Profile` и `from_values`.
3. Карта `python3 scripts/codebase_map.py`; прогон долгоживущих файлов
   задачи и затронутых тестов (`test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`,
   `test_project_profile_gates.py`, `test_network_address_gate.py`,
   `test_targets*.py`), полный набор — `suite-run`.

Итог: эскалация расхождения с долгоживущим `..._launch_places.py`
(`PYTHONUNBUFFERED` из окружения полного прогона) закрыта ANSWER-1,
вариант А — тест поправлен `amend-tests` (планка 68a5addc → 155dfad3),
код задачи не менялся. Оба долгоживущих файла зелёны с
`PYTHONUNBUFFERED=1`; `suite-run` №2 — зелёный: прошло 5525, упало 0,
пропущено 2.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 2 |
| 7 | 3 (долгоживущий файл test_author, код мест запуска не меняется) |
| 8 | 1 |

## Влияние на систему
- Профиль без новых подполей проверяется как раньше: новые подполя в
  `PROFILE_OPTIONAL`, обязательность прежних не меняется. Отказ
  неизвестному подполю остаётся для всех прочих имён; `runner: x` теперь
  отказывается по значению с тем же `test_profile` и `runner` в тексте
  (матрица неослабления SPEC).
- Потребители `Profile` не меняются: новые поля имеют умолчания, хэш
  `Profile` от `env` не зависит.
- `targets.check` теперь импортирует реестр провайдеров при проверке
  записи с `env` — только в этом случае (ленивый импорт), цикла нет.
- Откат — revert коммита задачи.

## Риски
- Ленивый импорт `providers` из `targets` при разборе `targets.yaml` в
  контексте, где реестр не импортируется (scripts/CI) — импорт идёт только
  при наличии `env`, у артели его нет.

## Предложения системе
- Класс «фиксирующий тест окружения считает разницу с `os.environ`
  пульта и не снимает переменные, которые выставляет сам прогон пульта»:
  тест зелёный в одиночку и красный внутри `suite-run`/гейта. Предпроверке
  test_author стоило бы гонять долгоживущие файлы с окружением полного
  прогона (`PYTHONUNBUFFERED=1`) — `orchestrator/preflight.py`.
