---
task: 01M1SHK3MD4ZF9NYXSCT67J8AP
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: пульт не зависит от профиля оболочки — самовыбор интерпретатора при старте

## Подход

Точка входа `orchestrator/artel.py` проверяет версию интерпретатора ДО
безусловного `from orchestrator import (..., doctor, ...)` — эта строка
тянет модули с синтаксисом 3.10+ (`X | None`), и под системным `python3`
(ниже `REQUIRED_PYTHON`) падает `TypeError` из глубины импорта, а не
именованным отказом. Проверка живёт как top-level код модуля (не внутри
`main()`), потому что крах происходит уже при самом импорте `orchestrator.
artel` — верно для всех трёх способов столкнуться с этим файлом (`python3
orchestrator/artel.py`, `python3 -m orchestrator.artel`, `from orchestrator
import artel`).

Порог читается ПРЯМЫМ импортом `orchestrator.stack.REQUIRED_PYTHON`, не
дублируется копией-константой: фактическая проверка (`ast`-обход,
`tasks/01M1SHK3MD4ZF9NYXSCT67J8AP/acceptance_tests/test_python_bootstrap.
py::test_ac2_stack_module_has_no_39_incompatible_syntax`) требует, чтобы
`stack.py` (и `config.py`, от которого он зависит) не несли синтаксиса
3.10+ вовсе — тогда прямой импорт безопасен и не образует второй источник
истины. В `stack.py` был ровно один такой случай — `_main_copy_root() ->
Path | None` — заменён на `Optional[Path]` (`typing`, 3.9-совместимо,
семантика та же). Дублирование константы (второй вариант SPEC, «если
фактическая проверка покажет обратное») не понадобилось.

Если текущий интерпретатор ниже порога: маркер-переменная окружения
(`ARTEL_PYTHON_REEXEC`) уже стоит — именованный отказ, код 2, без повторной
попытки; иначе `.artel/venv/bin/python` — если файл существует и его
версия (снятая отдельным `subprocess`-вызовом) не ниже порога, точка входа
переисполняет тот же вызов через `os.execv` под ним, с теми же аргументами
и добавленным (не построенным заново) окружением; иначе — тот же
именованный отказ.

`doctor`/`stack.check_stack()` дополняют существующую проверку `python`
(не заводят новую) строкой про фактический `sys.executable` и наличие
`.artel/venv` — статус (ok/warn) остаётся функцией только версии, как и
до этой задачи; `doctor/*.py` не тронуты вовсе — `checks.extend(doctor.
stack.check_stack())` уже прокидывает расширенную деталь без изменений в
самом пакете doctor.

`agent_log.py` не трогается — строка «окружение: python=…» не меняет
формат (требование 6).

## Шаги

1. `orchestrator/artel.py`: `_ensure_supported_interpreter()` и помощники
   (`_venv_python_path`, `_venv_python_version`,
   `_refuse_unsupported_interpreter`) — top-level вызов до риск-импорта;
   `orchestrator/stack.py`: `_main_copy_root` избавлен от `Path | None`
   (делает прямой импорт `REQUIRED_PYTHON` безопасным); тесты
   `tests/test_artel_bootstrap.py` (перманентная регрессия — переживает
   закрытие `acceptance_tests/`).
2. `orchestrator/stack.py::_python_check`: строка про `sys.executable` и
   `.artel/venv` в `detail`, статус не меняется; тест
   `tests/test_stack.py::PythonCheckProvenanceTest`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 (проверено — `agent_log.py` не тронут) |
| 7 | 2 |
| 8 | 1, 2 |

## Влияние на систему

Зона ограничена `orchestrator/artel.py`, `orchestrator/stack.py`,
`orchestrator/doctor.py` (не тронут), `tests/`. Единственное изменение
вне «нового» кода — замена `Path | None` на `Optional[Path]` в
`stack._main_copy_root`: чисто синтаксическая правка аннотации без
изменения поведения (сама функция не меняется), покрыта существующим
`tests/test_stack.py::MainCopyRootTest`, который остался зелёным без
правок.

Никакой существующий гейт/лимит/инвариант не ослаблен: `check_stack()`
по-прежнему возвращает 6 проверок с теми же статусами при тех же входах
(`tests/test_stack.py::CheckStackTest::test_ok_scenario_reports_ok_for_
every_tool` зелёный без изменений), `doctor`-пакет не тронут вовсе.
`_refuse_if_worktree()` (инвариант T056) и остальной `main()` — после
нашей проверки, поведение не меняется для современного интерпретатора
(требование 6, подтверждено `python3 orchestrator/artel.py` и `python3 -m
orchestrator.artel` вручную — оба доходят до того же отказа инварианта
T056, что и до этой задачи).

Откат: правки локальны (два файла + новые тесты), `git revert` без
побочных эффектов — новых таблиц/колонок/файлов на диске не заводится,
маркер-переменная живёт только в окружении одного вызова процесса.

## Риски

- `os.execv` необратимо заменяет образ процесса — не воспроизводится
  реальным запуском под другим интерпретатором в этой песочнице (нет
  Python 3.9/3.10 в PATH); все сценарии проверены подменой
  `sys.version_info`/`os.execv`/`importlib.reload`, тем же приёмом, что
  уже несёт зафиксированный `acceptance_tests/test_python_bootstrap.py`.
- Порог читается динамически (`stack.REQUIRED_PYTHON`) — при будущей
  правке `stack.py`, вносящей туда `X | None`/`match`, прямой импорт из
  `artel.py` снова станет небезопасным; `tests/test_artel_bootstrap.py`
  и локальный `acceptance_tests/` это не ловят напрямую (ловит AST-тест
  в `acceptance_tests/`, который переживёт задачу только пока не будет
  вычищен, TEST_REPORT/T023 — та же оговорка про недолговечность
  acceptance_tests уже отмечена в `tests/test_stack.py`).

## Предложения системе

- `docs/codebase-map.md`/`scripts/codebase_map.py` не сканирует
  подкаталоги (`orchestrator/doctor/*.py` не попадают в карту как
  отдельные модули, виден только пакет-фасад через прямые импорты) — не
  чинил, вне зоны этой задачи, но SPEC-зоны, ссылающиеся на «файл»
  `orchestrator/doctor.py`, на самом деле адресуют пакет из 19 файлов;
  формулировка зон при пакетизации модуля могла бы называть каталог
  явно.
