---
task: 01M5N9V4S984GRRXSMBK5JX7V1
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: ADR-0027, часть А1 — общие фикстуры-песочницы в стиле pytest

## Фаза A: план
- Таблица покрытия полна (требования 1–9 → шаги 1–3); шаги размера MR.
- Подход (переходник `_sandbox` + собственная уборка по `_cleanups`) согласуется
  с решением Оператора на гейте SPEC (не опираться на `doCleanups()`).
- В `tests/sandbox.py` нет `setUpClass`/`tearDownClass`/`addClassCleanup`/
  `enterContext` (проверил grep): `cls()` + `setUp()` воспроизводит всю
  подготовку классов, ничего классового не теряется.
- Приложение 1 отличается от текста SPEC (условное подключение через
  `importlib.util.find_spec`). PLAN ссылается на решение Оператора 24.10.2026
  при возврате из `verifying` (CI 40028534489). ANSWER-файла в каталоге
  документов нет, текст причины возврата я в пакете не нашёл. Поэтому сверить
  дословность не могу. Приложение исполняет сам Оператор и увидит его целиком.
  Замечанием это не завожу.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `tests/fixtures.py` — шесть фикстур с нужными именами; AC-1 зелёный по всем шести |
| 2 | OK | `_run_cleanups`: `pop()` с конца, исключения собираются, цикл не прерывается; `RuntimeError` с `cls.__name__` и `repr` каждой ошибки |
| 3 | OK | `except BaseException` вокруг `setUp`, уборка, `add_note` тем же `_cleanup_message`, голый `raise` |
| 4 | OK | `tests/sandbox.py` в диффе нет; импорт внутри тел фикстур; AC-6 зелёный |
| 5 | OK | настройки классов не трогаются, экземпляр — ровно класс sandbox |
| 6 | OK (с оговоркой) | Приложение 1 условное, по решению Оператора 24.10 (см. Фазу A); `git apply --check` — применяется |
| 7 | OK | долгоживущий файл импортирует `tests.fixtures` явно; AC-7 — временный проект подпроцессом |
| 8 | OK | долгоживущий файл — функции pytest, `parametrize`, «Ловит мутацию:» у каждой функции; новый `tests/test_fixtures_plugin_conditional.py` тоже |
| 9 | OK | существующие файлы `tests/` в диффе не тронуты; адресный прогон по классам зелёный (см. ниже) |

## Замечания

Блокирующих и major-замечаний нет.

- Наблюдение, не замечание: `_run_cleanups` ловит `Exception`, а не `BaseException`.
  Если действие уборки поднимет `KeyboardInterrupt`/`SystemExit`, остальные действия
  не выполнятся. `doCleanups()` ведёт себя так же, и SPEC этого не требует.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_01m5n9v4s984grrxsmbk5jx7v1_fixtures.py tests/test_fixtures_plugin_conditional.py -p no:cacheprovider -p timeout -o timeout=120 -q`:
  45 passed.
- `artel.py plank-run 01M5N9V4S984GRRXSMBK5JX7V1`: 2 passed, код выхода pytest 0.
- Приложение 1 извлечено из PLAN.md. `git apply --check` на чистом дереве ветки — применяется.
- Приложение временно наложено (`git apply`). Затем один прогон:
  `tests/test_fsm_advance_tests_writing_test_groups.py`,
  `tests/test_fixtures_plugin_conditional.py`, файл задачи и адресные файлы по
  классам (`..._pycache.py`, `..._launch_hint.py`, `..._zone_lock_projects.py`,
  `..._canary_acceptance.py`, `..._sandbox_copies.py`). Итог: 84 passed,
  51 subtests passed. После прогона `git checkout conftest.py`, дерево чистое.
- Временные мутации `tests/fixtures.py` (каждая — прогон файла задачи, затем откат,
  дерево чистое):
  - «прямой порядок» (`pop(0)`): 6 failed, `test_ac4_cleanup_runs_in_reverse_registration_order[*]`;
  - «нет RuntimeError»: 6 failed, `test_ac4_failed_cleanup_raises_runtime_error[*]`;
  - «нет уборки при сбое setUp»: 12 failed, `test_ac5_*`;
  - «нет add_note»: 6 failed, `test_ac5_*[True-*]`;
  - «импорт tests.sandbox на уровне модуля»: 1 failed, `test_ac6_*[tests.fixtures]`;
  - «стоп на первом упавшем действии»: 12 failed (`test_ac4_failed_cleanup_*`, `test_ac5_*[True-*]`).

  Заявки «Ловит мутацию» подтверждены.
- `python3 scripts/codebase_map.py`: после регенерации отличается только строка
  `built_at_sha`, карта свежая. Регенерация откачена `git checkout`.

## Предложения системе
- Песочница Bash ревьювера отказывает в `$?` и в `cd … && git …`, а `ls` в ней
  не найден. Поэтому `git apply --check` по приложению PLAN пришлось делать
  через временный скрипт в каталоге документов. Команда пульта
  `appendix-check <id>` (её же предлагает PLAN) сняла бы этот обход у обеих ролей.
- Решение Оператора при возврате из `verifying` (причина возврата) не попадает
  в ревью-пакет как ANSWER. Ревьювер не может сверить дословность приложения,
  которое PLAN называет «текстом из причины возврата». Стоит класть причину
  возврата в пакет ревьювера.
