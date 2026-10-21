---
task: 01M5FGJW4RBN9C9P48Q8MDHJX1
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Ветка задачи task/… удаляется из origin после мержа

## Фаза A: план
- Таблица покрытия полна (требования 1–8 → шаги 1–4); шаги размера MR; подход
  (расширение `_delete_origin_branch` необязательным `head`, новая функция
  рядом с уборкой kill, вызов последним в `_cleanup_merged_task`) не
  конфликтует с архитектурой.
- Строка «8 → свои тесты не нужны — свойства покрыты» неверна в части
  проводки гейта: см. R1-F1.
- «Влияние на систему» совпадает с diff: 3 файла (`cleanup.py`,
  `fsm_merge_gate.py`, `docs/retention.md`) + карта; `gitcmd.py` не тронут;
  откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `cleanup_merged_remote(conn, task_id, branch, merged_sha)` (`orchestrator/cleanup.py:356`), вызвана последней в `_cleanup_merged_task` (`fsm_merge_gate.py:1365`), `final_sha` передан из `_cmd_approve_merge_gate` (`:1533`) — после `_finalize_done_state`, т.е. только на пути `"ok"`→`done`. Клон — `workspace.task_repo`. |
| 2 | OK | `_origin_branch_head` — `ls-remote` через `_bounded` с `-c`-парами, три исхода как у `remote_ref_state` (stderr[:200] / «ls-remote не удался» / пусто). `is_ancestor` в клоне; удаление `push --force-with-lease=refs/heads/<b>:<sha> origin --delete refs/heads/<b>`; kill без `head` — прежние аргументы побайтно (`_bounded` даёт тот же argv); `None` разобран. Пустая ветка — ранний `return`. |
| 3 | OK | Исключение тела → «оставлено — <тип>: <текст>», без подсказок; запись журнала тоже под `try`; исход печатается с отступом `  `, подсказки — после него с отступом `    `, в журнал не идут. Набор подсказок по исходам — как в SPEC (на сбое чтения — `ls-remote` + удаление с плейсхолдером `<голова>`). |
| 4 | OK по коду | Вызов стоит после `done`; kill меняет только исход на `None`. Сторожа проводки в `tests/` нет — R1-F1. |
| 5 | OK | Затрагивается только `refs/heads/<branch>`; `gh` не зовётся (планка AC-8 и долгоживущий AC-8 зелёные). |
| 6 | OK | Абзац в «Ветки `task/*` пульта» `docs/retention.md`, фраза о PR на месте. |
| 7 | OK | В `fsm_merge_gate.py` — только подпись закрытой `_cleanup_merged_task` и её вызов. |
| 8 | Частично | Долгоживущий файл задачи покрывает функцию уборки; проводка гейта (AC-1/AC-4/AC-6г/AC-7 на уровне гейта) — только в разовой планке, см. R1-F1. |

## Замечания

- major — `orchestrator/fsm_merge_gate.py:1365` (проводка) / `tests/` — то,
  что гейт мержа после `done` вызывает уборку ветки в `origin`, а на отказе
  до push и на `"moved"` не вызывает, держит только планка
  `acceptance_tests/test_merge_gate_remote_cleanup.py` с пометкой «Группа:
  разовый». Долгоживущий файл `tests/test_01m5fgjw…_merged_remote_cleanup.py`
  зовёт `cleanup.cleanup_merged_remote` напрямую. Проверено временной
  мутацией: строка `cleanup.cleanup_merged_remote(conn, task_id, branch,
  merged_sha)` удалена — все 12 файлов `tests/` о гейте мержа
  (`test_*merge_gate*.py`, `test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`,
  `test_plan_appendix.py`; 84 теста) зелёные. Сценарий: следующий рефакторинг
  `_cleanup_merged_task` теряет вызов — ветки `task/*` в `origin` снова копятся
  (ровно дефект этой задачи), CI молчит, потому что планку после мержа не
  гоняет никто (ADR-0018 п. 3). PLAN («свои тесты не нужны — свойства
  покрыты») это пропустил. Предложение: тест разработчика в `tests/` (не
  повтор долгоживущего — тот проводку не проверяет) через тело гейта, тем же
  приёмом, что `tests/test_fsm_merge_gate_done_snapshot.py`: после `("done",)`
  ветки `refs/heads/<branch>` в bare-`origin` нет и есть запись «уборка»;
  при `_push_merged_main` → `"moved"` ветка на месте и записи нет. С заявкой
  «Ловит мутацию: вызов уборки удалён из `_cleanup_merged_task` / перенесён
  до проверки исхода push».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/fsm_merge_gate.py:1365; tests/ | Проводка «гейт после done удаляет ветку в origin, до push/на moved — нет» держится только разовой планкой; временная мутация (вызов удалён) — 84 теста гейта в tests/ зелёные | Регресс проводки после мержа не ловит CI, ветки task/* снова копятся в origin | Добавить тест в tests/ через тело гейта мержа (done → ветки нет и есть запись «уборка»; moved → ветка на месте, записи нет) с заявкой «Ловит мутацию» |

## Вердикт
changes_requested: закрыть R1-F1 — добавить в `tests/` долгоживущий сторож
проводки уборки в гейте мержа. Код уборки замечаний не имеет.

## Проверено исполнением
- `python3 …/artel.py plank-run 01M5FGJW4RBN9C9P48Q8MDHJX1` — 13 passed, код
  выхода 0.
- `python3 -m pytest -q tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py
  tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py` — 24 passed,
  26 subtests passed (уборка kill с расширенным `_delete_origin_branch` не
  сломана).
- Временная мутация: удалил вызов `cleanup.cleanup_merged_remote` из
  `_cleanup_merged_task`, прогнал 12 файлов `tests/` о гейте мержа
  (`-p no:xdist`) — 84 passed, 10 subtests passed (никто не покраснел → R1-F1);
  код возвращён `git checkout`, `git status` чист.
- `python3 scripts/codebase_map.py` — diff карты только в `built_at_sha`
  (карта свежа); возвращено `git checkout`.
- `grep` вызовов: `_cleanup_merged_task` зовётся только из
  `_cmd_approve_merge_gate:1533` и подменяется `lambda *a, **k` в
  `tests/test_merge_gate_ci_wait.py:415` — новый параметр не ломает.

## Предложения системе
- Правило ADR-0020 «проводку через закрытое тело гейта — в разовую группу»
  у test_author сталкивается с ADR-0018 п. 3 (долгоживущее свойство обязано
  иметь сторожа в `tests/`): свойство проводки гейта систематически остаётся
  без сторожа, если разработчик не добавит свой тест. Стоит явно возложить
  этот тест на developer в skills/test-authoring.md или PLAN-шаблоне.
