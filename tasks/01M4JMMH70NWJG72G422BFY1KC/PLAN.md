---
task: 01M4JMMH70NWJG72G422BFY1KC
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Регенерация карты кодовой базы под интерпретатором пульта, не голым `python3`

## Подход
- Три регенерации карты (`orchestrator/pull.py::_resolve_map_stage`,
  `orchestrator/fsm_postmerge.py::_regenerate_and_commit_map`,
  `orchestrator/brief.py::_regenerate_map`) зовут
  `[sys.executable, "scripts/codebase_map.py"]` вместо `["python3", …]`.
  Общего помощника не заводим: `sys.executable` — интерпретатор процесса
  пульта, который `artel.py::_ensure_supported_interpreter` уже держит
  ≥ `stack.REQUIRED_PYTHON`; тот же приём уже применён в
  `fsm_merge_gate.py:466`, `canary.py:2262`, `suite_run.py:660`.
- Журнал сбоя авторазрешения (требование 2) — в `pull.py`: константа
  действия `AUTO_RESOLVE_STEP_FAILED_ACTION`, помощник
  `_journal_step_failure` (шаг, код возврата или «нет», хвост stderr —
  последние `STEP_STDERR_TAIL = 500` символов) и обёртка
  `_git_step_ok` для git-шагов. Ею покрыты все шаги
  `_auto_resolve_conflict`, у которых есть процесс и код возврата:
  `add` слитого документа, `checkout --theirs` карты, регенерация,
  `add` карты, завершающий `commit`; `OSError` записи слитого документа и
  запуска регенерации журналируется с кодом «нет» и текстом исключения.
  `_resolve_map_stage` получил `conn, task_id` (единственный вызывающий —
  `_auto_resolve_conflict`). Решения «не-документ в наборе» и «аддитивность
  не доказана» — не отказ шага, а штатный отказ политики; журнал для них не
  добавляется (вне требования 2, иначе меняется журнал каждого обычного
  конфликта). Эскалация (`_handle_merge_failure`) не тронута: запись
  журнала делается внутри `_auto_resolve_conflict`, то есть до
  `merge --abort` и `set_state`.
- Перечень исключений требования 3: **пуст**. После правки в
  `orchestrator/` и `scripts/` нет `subprocess`-вызовов со списком,
  начинающимся с `"python3"` (`git grep -n '"python3"' -- orchestrator
  scripts`: остались `acceptance.py:61`, `runner.py:897`, `stack.py:277/648/653`
  — не дочерние вызовы). Сторож — долгоживущий
  `tests/test_01m4jmmh70nwjg72g422bfy1kc_bare_python3_guard.py`
  (`ALLOWED` пуст — совпадает).

## Шаги
1. `pull.py`: `sys.executable` в регенерации, журнал отказа шагов
   авторазрешения; `fsm_postmerge.py`, `brief.py`: `sys.executable`.
   Регенерация `docs/codebase-map.md`. Свой тест
   `tests/test_pull_autoresolve_step_journal.py` — отказ завершающего
   `commit` авторазрешения (шаг, не покрытый долгоживущими тестами задачи).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (AC-1, AC-2, AC-3) | 1 |
| 2 (AC-4, AC-5) | 1 |
| 3 (AC-6) | 1 |
| 4 | 1 — существующие ожидания не меняются |

Проверка: долгоживущие `tests/test_01m4jmmh70nwjg72g422bfy1kc_*.py`
зелёные; мутации «голый `python3`» поочерёдно в `pull`/`fsm_postmerge`/
`brief` краснят соответствующий тест AC-1/AC-2/AC-3 и сторож AC-6
(проверено временной правкой, возвращено); мутация «отказ commit молча
`False`» краснит `tests/test_pull_autoresolve_step_journal.py`.
Затронутые модули: `test_pull*.py`, `test_fsm_map_regen.py`,
`test_fsm_map_conflict_autoresolve.py`, `test_brief.py`,
`test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py`,
`test_runner_pre_step_pull.py`, `test_fsm_merge_conflict_note.py`,
`test_codebase_map.py` — 142 passed. Полный набор `suite-run` №1:
новых падений на ветке 0, одно падение есть и на базе 1f3a0413 (сводка
пульта показала «прошло: 1, упало: 0» при одном падающем и на базе — лог
`.artel/logs/…-suiterun-1.log` роли на чтение недоступен, перечень не
сверен).

## Влияние на систему
- Поведение эскалации неразрешённого конфликта (состояние, `merge
  --abort`, текст `detail`, метка «нужен шаг роли») не меняется; новая
  запись журнала с действием `авторазрешение конфликта подтяжки: шаг
  отказал` от `orchestrator` появляется только при отказе шага и до
  `state -> escalated`. Читатели журнала по префиксу «конфликт подтяжки»
  (`auto._pull_conflict_marker_streak` считает только
  `PULL_CONFLICT_ROLE_STEP_MARKER`) её не задевают — действие нарочно
  начинается не с «конфликт подтяжки».
- Гейты, лимиты, тесты не ослабляются; существующие тесты не правились.
- Откат — revert коммита задачи.

## Риски
- `sys.executable` пустой (встраиваемый интерпретатор) — для CLI пульта
  не встречается; `subprocess.run` тогда упадёт `OSError`/ненулевым кодом
  и уйдёт в прежнюю эскалацию/инцидент, теперь с записью журнала.

## Предложения системе
- Шаблон окружения шага: в shell роли нет `ls`/`cat` (`command not
  found`) — мелочь, но ломает привычные команды осмотра каталога.
