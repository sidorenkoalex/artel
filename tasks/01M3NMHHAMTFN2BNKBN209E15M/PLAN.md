---
task: 01M3NMHHAMTFN2BNKBN209E15M
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Трассируемость AC видит долгоживущие файлы test_author в tests/ кодовой ветки

## Подход

### Причина отказа канарейки 20260929T004220Z (задача 01M3N9SNEZSNC2G4X2Y2DGEY4R) — AC-6

Диагностика канарейки (`.artel/canary/…`) лежит вне рабочего каталога шага,
прочитать её не удалось (Read отклонён). Поэтому причина установлена по коду
и по фактам журнала, которые Оператор привёл в SPEC. Кроме того, каждый
дефект воспроизведён временной мутацией: сквозной тест AC-4 краснеет на своём
варианте (см. ниже).

**Общий корень.** Канарейка исполняет FSM и чекпоинты кодом процесса пульта,
то есть кодом ПИНА 171ab4c6, а не целевым sha клона a4cf36bb.
`canary._ephemeral_clone` (`orchestrator/canary.py:804-953`) делает checkout
`target_sha` в клоне. Модули `orchestrator.*` при этом не перезагружает: он
только переадресует пути `config` (`_CLONE_CONFIG_ATTRS`,
`orchestrator/canary.py:376`), а `auto.cmd_auto`/`runner.cmd_run` зовёт в том
же процессе (`orchestrator/canary.py:1339`, `:1406`). Скилы роли бриф при этом
читает с `main` КЛОНА: `gitcmd.show(config.MAIN_BRANCH, "skills/…")`
(`orchestrator/brief.py:436`), `config.ROOT` — корень клона. Итог:
test_author получил правило ADR-0020 из a4cf36bb («долгоживущий файл — в
`tests/`»), а чекпоинт и `advance` исполнялись кодом 171ab4c6. Этот код
предшествует мержу 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ (ef9149b7): `git merge-base
--is-ancestor ef9149b7 171ab4c6` → нет.

**Дефект А — чекпоинт test_author-1 не закоммитил файл и молчал.** Место
кода: `orchestrator/checkpoint.py:488-489` на 171ab4c6 — `if role !=
"developer": return ""` в `commit_success_checkpoint`. Для test_author это
немедленный выход без коммита и без записи в журнал. Отсюда «sha
зафиксирован: код=a4cf36bb» после шага 1: голова кодовой ветки равна main. В
a4cf36bb то же место уже несёт мандат test_author (`orchestrator/checkpoint.py:597` после этой
правки,
`_test_author_checkpoint`). Подтверждение: мутация «`if role != "developer":
return ""`» в текущем `commit_success_checkpoint` краснит вариант (а)
сквозного теста («файла нет на голове»), вариант (б) остаётся зелёным.

**Дефект Б — трассируемость test_author-2 не увидела файл на d0eb9b05.**
Место кода: `orchestrator/fsm_advance.py:329` на 171ab4c6 —
`fsm._tests_writing_ac_state(conn, task_id, branch, tdir)` без
`long_lived_sources`. Сама функция там же (`orchestrator/fsm.py:422`)
параметра не имеет: `tests/` кодовой ветки на пине не читается вовсе, как бы
ни был закоммичен файл. Отказ «AC-1: нет теста … добавь … в
acceptance_tests/» — ровно текст `guard.traceability_errors_from_content`.
В a4cf36bb чтение есть: `_tests_writing_code_diff`
(`orchestrator/advance_gates/tests_writing.py:231`) →
`long_lived_sources` (`orchestrator/fsm_advance.py:357-359`). Подтверждение:
мутация `long_lived_sources=[]` в текущем `fsm_advance.tests_writing` краснит
оба варианта сквозного теста, включая (б), отказом «переход отклонён:
трассируемость AC».

**Следствие для требования 1.** На коде a4cf36bb оба звена работают. Это
доказывает сквозной тест: он зелёный на a4cf36bb без правки
`fsm_advance.py`/`fsm.py`/`advance_gates/tests_writing.py`; планка
test_author тоже «зелёная с рождения». Исправление обоих дефектов для боевого
пульта — сдвиг пина на main с этой задачей (`pin-update`, действие
Оператора, вне роли). Правка кода связки, «лечащая» уже рабочий путь, была бы
изменением без эффекта, поэтому её нет.

### Что меняется в коде

1. **Тихие выходы чекпоинта test_author становятся видимыми (остаток дефекта
   А в текущем коде).** SPEC перечисляет места тихого выхода
   `_test_author_checkpoint`: `_test_author_own_paths` → `None` (git не
   ответил на `status`/`diff_base`/`ls_tree_files`) и `_commit_worktree_change`
   → «не закоммичено». В a4cf36bb оба выхода по-прежнему молчат. Теперь оба
   пишут в журнал действие `TEST_AUTHOR_NOT_COMMITTED_ACTION` («долгоживущие
   тесты не закоммичены пультом»): в первом случае с причиной, во втором —
   с путями файлов. Поведение (коммит/откат) не меняется. Место:
   `orchestrator/checkpoint.py::_test_author_checkpoint`.
2. **Сквозной тест** `tests/test_long_lived_step_end_to_end.py` на
   песочнице `tests/sandbox.py` (`FakeProc`, `is_claude_call`) поверх
   `_WorktreeCheckpointTest`. Подменён только `runner.spawn_agent`; дальше
   штатные `runner.cmd_run` (чекпоинт успешного шага, автокоммит
   артефактов) и `fsm.cmd_advance`, гейты не подменяются.
   - `test_prefixed_file_counts_after_checkpoint_and_advance` — варианты
     (а)/(б). Проверяет: файл на голове (в (а) голова ≠ база), `in_dev`, нет
     отказа трассируемости, «перечень долгоживущих тестов записан», строка
     `<sha256>␣␣<путь>` в перечне. Заявка AC-4 дословно.
   - `test_unprefixed_file_keeps_tests_writing` — файл без префикса в обоих
     вариантах: `tests_writing`, отказ трассируемости либо «только
     добавление» (AC-5).
   - два теста записи журнала из п. 1: git молчит на `diff_base`; хук
     `pre-commit` отказывает коммиту.

## Шаги

1. `orchestrator/checkpoint.py`: `TEST_AUTHOR_NOT_COMMITTED_ACTION` и запись
   журнала на двух выходах `_test_author_checkpoint` без коммита.
2. `tests/test_long_lived_step_end_to_end.py`: сквозные сценарии AC-4/AC-5
   и сторожа записи журнала; регенерация `docs/codebase-map.md`.
3. Проверка исполнением. Все прогоны — в переднем плане:
   - `python3 -m pytest tests/test_long_lived_step_end_to_end.py` — 4 passed,
     4 subtests;
   - планка задачи (`tasks/…/acceptance_tests/test_ac1_ac3_*.py`,
     `test_ac3_ac5_*.py`) — 8 passed, 8 subtests; включает прогон моего
     теста под мутациями `guard` (трассируемость, правило имени) — красный
     провалом, как требует планка;
   - `tests/test_long_lived_manifest.py`, `tests/test_long_lived_transitions.py`,
     `tests/test_timeout_checkpoint.py`, `tests/test_step_autocommit.py`,
     `tests/test_checkpoint_zone_filter.py` — 79 passed, 20 subtests.
   - Временные мутации кода (каждая возвращена `git checkout`):
     - оба выхода снова тихие → оба теста журнала красные;
     - `role != "developer"` (пин, дефект А) → красный вариант (а);
     - `long_lived_sources=[]` (пин, дефект Б) → красные варианты (а) и (б).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | Подход (причина обоих дефектов, путь исправлен в a4cf36bb и доказан шагом 2); шаг 1 — тихие выходы видимы |
| 2 | 2 (перечень и отказ «только добавление»/групп — тем же `advance`; планка AC-3 зелёная) |
| 3 | 2 |
| 4 | Подход (AC-6) |

## Влияние на систему

- Поведение чекпоинта не меняется: добавлены только записи журнала на путях,
  где коммита и так не было. Новое действие журнала ничем не читается как
  отказ перехода. Гейт посторонних файлов планки
  (`_tests_writing_stray_plank_files_gate`) сравнивает только
  `STRAY_ACCEPTANCE_FILES_ACTION`, стоп-кран и история отказов брифа
  смотрят на префикс «переход отклонён», так что новое действие их не
  задевает.
- Гейты `tests_writing`, трассируемость, перечень, `tests/test_long_lived_*.py`
  не тронуты и не ослаблены: планка AC-3 сверяет методы базы и прогон.
- Откат — revert коммита ветки задачи.

## Риски

- Боевой пульт до сдвига пина продолжит вести себя как в канарейке. Это
  знание процесса, не кода: канарейка ADR-смены правил ролей до сдвига пина
  проверяет новые скилы старым кодом пульта (см. «Предложения системе»).

## Предложения системе

- `orchestrator/canary.py::_ephemeral_clone` + `orchestrator/brief.py::skills_text`:
  канарейка на `target_sha` исполняет FSM кодом пина, а скилы ролей берёт
  с `main` клона (целевой sha). Правка правил ролей вместе с кодом пульта
  (ADR-0020) проверяется несогласованной парой. В итоге красная канарейка на
  исправном main стоила $38.98 и эту задачу. Предложение: канарейка
  исполняет шаги кодом клона (подпроцесс `artel.py` из клона) либо
  отказывает/предупреждает, если `target_sha` несёт изменения
  `orchestrator/`, которых нет в пине.
- Диагностика канарейки (`.artel/canary/<прогон>/`) лежит вне рабочего
  каталога шага, а SPEC адресует её разработчику для AC-6: чтение отклонено
  песочницей роли. Нужна материализация диагностики в `tasks/<id>/` либо
  явная оговорка в SPEC.
