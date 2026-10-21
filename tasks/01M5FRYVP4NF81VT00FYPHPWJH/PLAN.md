---
task: 01M5FRYVP4NF81VT00FYPHPWJH
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: G3а-2б-2: запрет повторов через плагины pytest и переносы из приёмок

## Подход
Новое поведение включается одним условием `acceptance._bans_rerun_plugins`
(повтор `in_outcome_bounds` — `reported` и `from_components` — плюс команда
pytest не Vitest): им пользуются и `_report_argv` (флаги
`-p no:rerunfailures -p no:flaky` дописываются к `head` сразу за `command`,
до подмножества/целей/`--ignore`/`-p no:cacheprovider`/`report_args`), и
`_report_suite_result_key` (поле `"no_rerun_plugins": true`). Импорт
`in_outcome_bounds` не нужен — круговой импорт исключён. У артели и
`test_profile` условие ложно, argv и ключ побайтно прежние.

`targets.check` получает `_check_rerun_ban` в цикле `_check_components`:
только компонент с `report` и командой pytest (обёртка — граница «Не
входит»); поля `command`/`report_args`/`select`, `env.PYTEST_ADDOPTS`
через `shlex.split` (`ValueError` → `TargetsError` «PYTEST_ADDOPTS не
разбирается»), `env.PYTEST_PLUGINS` по запятой со `strip`. Запись
`test_profile` идёт другой веткой `check` и не проверяется.

Переносы — точечно: деталь гейта SPEC из
`tests_writing.SPEC_GATE_PASSED_DETAIL` импортом внутри функции `fsm.py`;
`liveness.GATE_OWNER_MARKER` пишется в каталог выписки первой строкой
`try` в `_gate` и `two_sided.run` (сбой записи — отказ подготовки, не
пропуск); `doctor/orphans.py` — ветка `artel-outcome-*`/`artel-two-sided-*`
в `_temp_owner_alive` до общего маркера канарейки, префиксы в
`_orphan_temp_dirs`, `git worktree prune` в каждом `_project_clones()`
только если удалена хотя бы одна выписка; `mandate._component_covered`
признаёт токен, только если `strip("*_")`-токен целиком совпадает с
`[\w][\w./-]*\.\w+(:\d+)?` и путь в области; тексты действий мержа гейта
исходов — из `refusal_classes`, новая `OUTCOME_MERGE_PREPARE_ACTION` с
классом «чинит Оператор».

Бюджет SPEC ($40) не пересматривается.

## Шаги
1. `orchestrator/acceptance.py`: `NO_RERUN_PLUGINS_ARGS`, `_bans_rerun_plugins`, правка `_report_argv` и `_report_suite_result_key` (требования 1–2).
2. `orchestrator/targets.py`: `RERUN_FLAGS`, `RERUN_PLUGINS`, `_rerun_argument`, `_check_rerun_ban` (требование 3); свой тест `tests/test_targets_rerun_ban_wrapper.py` (граница обёртки, похожие флаги, `-p` в конце).
3. `orchestrator/fsm.py`: деталь из константы (требование 4).
4. `orchestrator/liveness.py`, `advance_gates/outcome_integrity.py`, `advance_gates/two_sided.py`: маркер владельца (требование 5).
5. `orchestrator/doctor/orphans.py`: сироты выписок и prune (требование 6).
6. `orchestrator/advance_gates/mandate.py`: `_FILE_PATH_TOKEN_RE` в `_component_covered` (требования 7–8).
7. `advance_gates/refusal_classes.py`, `advance_gates/outcome_integrity.py`: тексты действий (требования 9–10).
8. `python3 scripts/codebase_map.py`; планка (`plank-run`) и тесты затронутых модулей (требование 11).
9. Ревью R1-F1: сторожа разработчика в `tests/` на требования 1, 2, 5, 6, 8 (планка — `Группа: разовый`): `tests/test_report_argv_rerun_ban.py`, `tests/test_gate_owner_marker.py`, `tests/test_mandate_file_path_token.py`; каждая заявка «Ловит мутацию» проверена временной мутацией кода (12 мутаций — все красные).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 9 |
| 2 | 1, 9 |
| 3 | 2 |
| 4 | 3 |
| 5 | 4, 9 |
| 6 | 5, 9 |
| 7 | 6 |
| 8 | 6, 9 |
| 9 | 7 |
| 10 | 7 |
| 11 | 8 |

## Влияние на систему
- Прогон компонента с `report`: argv длиннее на четыре элемента; если в
  проекте плагин не установлен, `-p no:<имя>` pytest принимает молча.
  Ключ итога компонента сменился — кэш итогов компонентов один раз
  пересчитается (намеренно: итог до запрета не переиспользуется).
- `targets.check` строже только для компонентов с `report` и командой
  pytest; запись с повторами раньше загружалась — теперь отказ записи с
  именем поля (`targets.yaml` — зона Оператора; отказ называет компонент,
  поле и аргумент, чинится по тексту).
- `doctor`: `orphans-temp` начинает называть брошенные выписки гейтов
  (ожидаемое изменение вывода); `--fix` удаляет их и делает
  `git worktree prune` в клонах проектов — prune убирает только записи
  с отсутствующим каталогом, живые выписки (маркер живого pid) не
  трогаются. Выписки процессов, начатых до задачи (без маркера), —
  сироты (принятая цена по SPEC).
- Мандат: признание при профиле в границе только уже — ничего, что было
  отказом, не стало покрытием; правило `*.py` и id компонента прежние.
- Гейты, лимиты, инварианты не ослабляются; существующие тесты не
  правились. Откат — revert merge-коммита.

## Риски
- Окно между `mkdtemp` и записью маркера: параллельный `doctor --fix`
  в эту долю миллисекунды удалит каталог — `worktree add` упадёт отказом
  подготовки (fail-closed), тот же приём и окно, что
  `canary._owned_temp_dir`.

## Предложения системе
- Прогон «тестов затронутых модулей» последовательно по ~30 файлам
  занимает >10 минут, а `-n` с явным списком файлов роняет воркеры —
  команде пульта не хватает режима «suite-run по списку модулей».
