---
task: 01M41W15BK20WBTD9TMBTSXNZA
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: plank-run работает в шаге роли — путь планки, который признаёт сторож роли

## Подход
`orchestrator/plank_run.py::cmd_plank_run` собирал позиционный аргумент pytest
абсолютным (`str(tests_dir / selected)` / `str(tests_dir)`), а сторож роли
`conftest.py::_is_targeted_path` признаёт целевым только путь с первым
сегментом `tasks` (или `tests`). Правка: путь каталога планки берётся
относительным от `code_dir` — того же каталога, что `cwd` процесса pytest в
`acceptance.run_plank` (`tdir` — всегда `code_dir / "tasks" / <id>`, см.
`acceptance.materialize_files`/`materialize_from_branch`), — то есть
`tasks/<id>/acceptance_tests` для всей планки и
`tasks/<id>/acceptance_tests/<файл>[::узел]` для одного файла. Для pytest без
окружения роли относительный путь от `cwd` эквивалентен абсолютному: тот же
состав, код выхода и итоговая строка (AC-4). `conftest.py` не меняется.

## Шаги
1. `orchestrator/plank_run.py`: аргумент pytest —
   `(tdir / "acceptance_tests").relative_to(code_dir).as_posix()` плюс
   `/<selected>` для одного файла; комментарий «почему». Регенерирована
   карта `docs/codebase-map.md` (`python3 scripts/codebase_map.py`).
2. Сквозной сторож — долгоживущий файл test_author
   `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py` (зафиксирован,
   не правился). Своих новых тестов не добавлял: свойства AC-1…AC-4 этот файл
   покрывает целиком (вся планка, три формы аргумента файла, позиционный путь
   из `sys.argv` pytest, поведение без роли).

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (проверка — `test_ac4_without_role_same_tests_exit_code_and_summary`) |
| 3 | 2 |
| 4 | 1 — существующие тесты не правились |

Правки существующих тестов (требование 4, AC-4): нет. В
`tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py` и
`tests/test_plank_run_edges.py` ни одно утверждение не закрепляет абсолютную
форму позиционного пути; оба файла зелёные без изменений.

Прогоны (передний план, `-p no:cacheprovider -p timeout -o timeout=120`):
- `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py
  tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py
  tests/test_plank_run_edges.py tests/test_conftest_role_guard.py` —
  `21 passed, 26 subtests passed`.
- Мутация «вернуть абсолютную форму» (`tests_rel = str(tdir /
  "acceptance_tests")`) — долгоживущий сторож красный: `8 failed, 3 passed`
  (AC-1, AC-2, AC-3 по всем подслучаям); код возвращён.
- `artel.py plank-run 01M41W15BK20WBTD9TMBTSXNZA` пульта в этом шаге — отказ
  «Сторож роли …», код pytest 2: пульт работает на коде пина, где ещё
  абсолютный путь, — ровно дефект этой задачи. Планка задачи
  (`test_ac4_existing_tests_and_plan.py`) проверяет неизменность методов двух
  существующих файлов (их diff с базой пуст) и их зелёный прогон — оба
  условия подтверждены прогоном выше.

## Влияние на систему
Меняется только форма аргумента pytest в команде `plank-run` (только чтение
для пульта, без журнала и состояний). Сторож роли `conftest.py`, гейты,
прогон планки пультом на гейтах (`acceptance.run` — свои пути, без окружения
роли) не затронуты; ни одна проверка не ослаблена — относительный путь
проходит тот же `_is_targeted_path`, что и любой ручной вызов роли.
Откат — revert одного коммита.

## Риски
`relative_to` бросит `ValueError`, если `tdir` окажется вне `code_dir`; по
устройству `acceptance.materialize_*` (`code_dir / "tasks" / task_id`) это
невозможно, оба пути строятся от одного объекта `code_dir`.

## Предложения системе
- Самопроверка `plank-run` в шаге роли невозможна, пока пин пульта не
  включает исправление: команда пульта исполняется кодом пина, а не кодом
  ветки. Для задач, чинящих сам `plank-run`/прогон планки, миссии стоит
  явно называть замену (прогон затронутых модулей `tests/`), иначе роль
  встаёт перед выбором между запретом ручной выкладки и отсутствием прогона.
