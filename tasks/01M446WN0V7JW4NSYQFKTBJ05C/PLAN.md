---
task: 01M446WN0V7JW4NSYQFKTBJ05C
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Мандат Оператора на расширение зон доходит до коммита пульта

## Подход
Общий узел чтения мандатов — существующий
`orchestrator/advance_gates/zones.py::_answer_zones_mandate` (все
`ANSWER-*.md` ссылки документов, правило исключения ANSWER, последний коммит
которого — автокоммит шага роли, разбор строки `mandate.elements`). Его НЕ
копируем и не переносим: `orchestrator/checkpoint.py` зовёт его же
отложенным импортом (`from .advance_gates import zones` внутри функции —
идиома модуля, `zones` сам импортирует `checkpoint` на уровне модуля).
Ветка — `artifact_branch.branch_name(task_id)`, ровно то, что гейт получает
от `artifact_source.resolve`. Покрытие пути мандатом — формулой гейта
`zones._touches_zone` (а не `zone_lock._paths_overlap`), поэтому множества
«покрыто мандатом» у гейта и у коммита пульта совпадают по построению
(AC-7). Защищённый путь (`config.is_protected_path`) мандатом в коммите
пульта не покрывается — гейт зон его всё равно безусловно отклоняет
(«мандат на расширение зон — не мандат на правку защищённого пути»), и
коммит пульта не должен протаскивать такой файл в ветку.

Мандат читается ТОЛЬКО когда по зонам задачи нашёлся путь вне зон
(ленивое чтение): шаг без посторонних путей не платит git-вызовами
ссылки документов, а существующие тесты с подменённым git не видят новых
вызовов. Пустые `zones`/`zones_extension` — фильтр не применяется вовсе,
как сейчас.

`_zone_paths` не меняется (его ассертят `tests/test_checkpoint_zone_filter.py`);
мандат применяется поверх: новый помощник `_mandate_covered(task_id, paths)`
делит пути вне зон на покрытые мандатом и прочие. Гейт зон не меняется:
мандат не вливается в список зон для гейта, раздел «## Расширение зон»
PLAN.md по-прежнему обязателен (AC-8).

## Шаги
1. `orchestrator/checkpoint.py`:
   - `_mandate_paths(task_id)` — элементы мандата из общего узла
     `zones._answer_zones_mandate` на ссылке документов задачи;
   - `_mandate_covered(task_id, paths)` — подсписок `paths`, покрытый
     мандатом (формула гейта `_touches_zone`, без защищённых путей);
     пустой вход — без единого вызова git;
   - `_commit_worktree_change`: посторонние по зонам минус покрытые
     мандатом; возврат дополнен пятым элементом — пути, принятые по
     мандату (все вызывающие обновлены: `_wip_checkpoint`,
     `_test_author_checkpoint`, `commit_success_checkpoint`,
     `commit_pull_checkpoint`). Так мандат получают автокоммит,
     WIP-чекпоинты таймаута/аварии/`pause --now` и чекпоинт перед
     подтяжкой (отказ `pull.py` «посторонние файлы в worktree» читает
     запись `STRAY_WORKTREE_FILES_ACTION`, где путей мандата больше нет —
     `pull.py` не меняется);
   - `commit_success_checkpoint`: деталь записи «код закоммичен пультом за
     роль» дописывается «; по мандату Оператора вне зон: <пути>», если
     такие есть (требование 5/AC-9);
   - `restore_out_of_bounds_deletions`: удаление developer по мандату не
     восстанавливается;
   - `pult_commit_failed_paths`: незакоммиченный путь по мандату — путь
     результата шага.
2. Тесты: долгоживущий файл `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`
   (AC-1–AC-9) — зафиксирован, не правится. Свой юнит-тест
   `tests/test_checkpoint_zone_mandate.py` — на свойства, не покрытые
   долгоживущим: защищённый путь мандатом не покрывается; без посторонних
   по зонам мандат не читается (ни одного вызова общего узла); формула
   покрытия — та же, что у гейта (`docs/x` без `/` покрывает
   `docs/x/y.md`).
3. Регенерация `docs/codebase-map.md` (`python3 scripts/codebase_map.py`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1, 2 |
| 4 | 1 (гейт зон не трогается), 2 (AC-8) |
| 5 | 1 |
| 6 | 2 |

## Влияние на систему
- Затрагивается фильтр зон коммита пульта (все пять мест требования 1) —
  он становится строго шире только на пути, покрытые мандатом Оператора из
  ANSWER, закоммиченного не автокоммитом роли; путь без мандата и
  защищённый путь ведут себя как прежде. Гейт зон, гейт защищённых путей,
  гейт неослабления тестов не меняются; требование раздела PLAN остаётся.
- Отказ чтения ссылки документов (git не ответил) — пустой мандат, т.е.
  прежнее поведение (снятие со стейджа / отказ подтяжки): fail-closed.
- Сигнатура закрытого `_commit_worktree_change` (возврат 4 → 5 элементов)
  — тесты её не распаковывают (grep `tests/`), все вызывающие в модуле.
- Откат — revert коммита задачи.

## Проверка
- `python3 -m pytest tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`
  — 11 passed, 26 subtests passed. Мутация `_mandate_covered` → всегда `[]`
  (мандат не доходит до коммита) — 13 failed: подключение проверено.
- `tests/test_checkpoint_zone_mandate.py` — 4 passed; каждая из четырёх
  заявленных мутаций (без проверки защищённого пути, без раннего возврата
  на пустом списке, формула `_paths_overlap` вместо `_touches_zone`, чтение
  мандата с кодовой ветки) краснит ровно свой тест.
- Затронутые модули: `test_checkpoint_zone_filter`, `test_timeout_checkpoint`,
  `test_step_autocommit`, `test_zones_gate`, `test_answer_mandate`,
  `test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted`,
  `test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit`, `test_role_commit_by_pult`,
  `test_pause_now` — 133 passed; `test_pull`, `test_pull_additive_conflict`,
  `test_runner_pre_step_pull`, `test_plank_run_edges`,
  `test_checkpoint_external_step_artifacts`, `test_long_lived_step_end_to_end`,
  `test_auto_cycle` — 128 passed; `test_review_package`,
  `test_test_author_long_lived_artifact`, `test_long_lived_transitions`,
  `test_codebase_map`, `test_test_integrity_gate`, `test_pause` — 260 passed.
- `docs/codebase-map.md` регенерирована.

## Риски
- Существующие тесты с подменённым `gitcmd.in_repo`/`subprocess` и путями
  вне зон теперь вызовут чтение ссылки документов; риск снижен ленивым
  чтением и fail-closed деградацией, проверяется прогоном
  `tests/test_checkpoint_zone_filter.py`, `tests/test_timeout_checkpoint.py`,
  `tests/test_pull.py`, `tests/test_zones_gate.py` и соседних.

## Предложения системе
- `orchestrator/plank_run.py`: `plank-run <id> [файл]` отказывает «планки
  нет: … нет файлов test_*.py», когда планка задачи — только долгоживущая
  группа в `tests/` (в `acceptance_tests/` лишь `long_lived.sha256.txt`);
  миссия шага требует гонять планку только этой командой — для такой
  задачи штатного пути нет, долгоживущий файл пришлось гонять `pytest`
  напрямую.
