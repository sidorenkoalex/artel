---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Этап 4 ADR-0021, часть A — мерж не кладёт в main снимок задачи и RETRO

## Соответствие SPEC

Фаза A (план): таблица покрытия PLAN закрывает требования 1–10; шаги 1–5
размером с MR, шаги 6–9 — исполнение мандатов ANSWER-1…4, каждый со своей
проверкой. Подход (проверка документов на ссылке вместо наложения, sha мержа
и приложения пробрасываются в коммит закрытия) с архитектурой ADR-0021 не
конфликтует. «Влияние на систему» сходится с диффом: тронуты только зоны SPEC
(`snapshot.py` — по мандату ANSWER-1), защищённый `tests/test_invariants.py`
— только приложением PLAN.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_overlay_artifact_snapshot` удалён (`fsm_merge_gate.py`), коммита снимка нет ни у одного проекта; AC-1, AC-12. |
| 2 | OK | `_generate_and_commit_retro`/долги удалены из `fsm_postmerge.py`; остались merge, приложения, карта; AC-1, AC-6. |
| 3 | OK | `snapshot._retro_with_frontmatter` строит `build_done` + `_with_appendices_line`; без приложений `_with_appendices_line` возвращает текст как есть. `merge_sha = gitcmd.head_sha(scratch)` берётся после `_apply_plan_appendices` и до `_map_step` (`_cmd_approve_merge_gate`); AC-2–AC-4. |
| 4 | OK | Все четыре ветки отказа `commit_closing` идут через `_closing_failed` → incident `snapshot.closing` с target проекта; исключение построения RETRO перехвачено. Работает на обоих путях: `_commit_closing` общий. AC-7, AC-8. |
| 5 | OK | Подбора долгов больше нет; на пути `kill` RETRO пишет коммит закрытия, провал даёт инцидент. |
| 6 | OK | `_guard_task_docs_or_refuse` первым шагом `_publish_merge_artifacts`, до карты/push/закрытия, у любого проекта. Ревизия — `fixed_sha`, без фиксации — голова ссылки. Правила взяты из `scripts/guard.py` пульта; сверил с `guard.main()` в режиме `--all`: посторонние файлы корня и подкаталогов, посторонние файлы `acceptance_tests/` (без `__pycache__`), отступ AC у `test_*.py`, `check_content` для `.md` без паспорта. Тот же набор, только без освобождения по `docs/retro`. AC-9, AC-10, AC-12. |
| 7 | OK | Ссылки нет / `ls_tree` → None / `show` → None — нарушение, отказ; AC-11 (оба случая). |
| 8 | OK | Порядок: приложения → проверка документов → карта → `_guard_all_or_refuse` (внутри по-прежнему ранний выход для не-артели) → `final_sha`. AC-5. |
| 9 | OK | `retro.build_done` по умолчанию даёт `artifact_branch.branch_name(id)`; `artifacts_in_main` = каталог в main ИЛИ `ref_head`. `drop_task_dir` остался на `_dir_in_main` по ANSWER-2 п.5. AC-13. |
| 10 | OK | Для внешнего проекта новое только 1, 3, 4, 6(а), 7: `guard_rules` требует `is_artel` и `scripts/guard.py` в дереве, `_guard_all_or_refuse` сам выходит для не-артели. |

Тесты и целостность:
- Удаление `tests/test_fsm_retro.py`, метода
  `GuardAllLaunchTest::test_task_retro_does_not_hide_snapshot_violation`
  и `assertLess` в `test_plan_appendix.py` — по мандату ANSWER-1.
  Тесты-замены AC-4, AC-5, AC-7–AC-11 есть в долгоживущем файле.
- Сменённые ожидания сверил с base по пакету «Изменённые утверждения»:
  - `test_plan_appendix.py` → требование 1;
  - `test_retro_artifact_branch_reads.py` → требование 9 и ANSWER-2 п.3:
    явный адрес «X-адрес» отличим от адреса по умолчанию, мутация «address
    игнорируется» по-прежнему ловится;
  - `test_retro.py` → ANSWER-2 п.1, добавлен `assertIn` итога с sha;
  - `test_01m3sf7…::test_ac1_clean_snapshot_merges_as_before` → ANSWER-2
    п.2, добавлена проверка файла планки в `refs/artifacts/<id>` origin;
  - `test_01m42pencs…::test_ac5_…` → ANSWER-3 п.1–3: `assertNotIn` и RETRO
    закрытия с «Итог: done» из ссылки origin.

  У всех сохранены прежние `done`/сдвиг main/карта, у изменённых методов
  есть «Ловит мутацию».
- Не видное гейту изменение: у помощника `TaskFlowSandbox.approve_until_settled`
  появился ключ `live_fixation=False`. По умолчанию подмена `fixation.read`
  прежняя, так что данные прочих методов не сужены. Включает ключ только
  метод ANSWER-3, и в PLAN (шаг 8) это обосновано.
- Приложение PLAN к `tests/test_invariants.py` (три метода, ANSWER-2 п.4,
  ANSWER-4) не трогает утверждения и `SpyRun`. Подмена стоит только вокруг
  `cmd_approve` в подтесте `merge_gate`.

## Замечания

Блокирующих и major нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved.

## Проверено исполнением

- `python3 -m pytest -q -x tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py tests/test_plan_appendix.py tests/test_retro_artifact_branch_reads.py tests/test_snapshot_closing_outcome.py tests/test_guard_task_root_subdirectory.py tests/test_kill_cleanup.py tests/test_retro.py tests/test_main_ci_line.py tests/test_fsm_map_regen.py`:
  129 passed, 29 subtests. Остановился на первом падении,
  `FixesMainArgTest::test_flag_without_reason_is_refused` («artel.py approve:
  команда недоступна процессу роли reviewer»). Это ограничение окружения
  роли, не кода; в PLAN тот же класс отмечен как «зелёный в suite-run».
- `tests/test_main_ci_line.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`,
  `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_fsm_merge_gate_done_snapshot.py`,
  `tests/test_merge_gate_ci_wait.py`, `tests/test_artifact_ref_sync.py`: 83
  passed, 19 failed. Все 19 — `FixesMainArgTest` и классы `test_01m3sf7…`,
  которые зовут `artel.py approve`/`pin`. Один из них
  (`MergeGuardAfterSnapshotTest::test_ac1_clean_snapshot_merges_as_before`)
  я разобрал: причина — «команда недоступна процессу роли reviewer».
  Прогнать их без переменной роли разрешения не дали. Поэтому их статус
  здесь не проверен; в пакете CI коммита a2810fb9 (HEAD ветки) зелёный,
  16 проверок, — это и есть их свидетельство.
- Временные мутации (код возвращён, `git status` чистый):
  - `_guard_task_docs_or_refuse` зовёт `_task_docs_violations(..., False)`
    (правила `guard --all` не применяются) → `test_ac10_stray_acceptance_file_refuses`
    красный;
  - `_closing_failed` без `alerts.raise_alert` → `test_ac7`/`test_ac8`
    красные по всем причинам (8 subfailed).
- `artel.py plank-run 01M4M67SGNEYMN9F1C7XVX24XE`: «планки нет: … нет файлов
  test_*.py; pytest не запускался». Планка задачи — только перечень
  долгоживущих файлов, сам файл прогнан выше.
- `git apply --check` для diff-блока приложения из PLAN.md на дереве ветки
  — rc 0.
- `python3 scripts/codebase_map.py` и сравнение карты без `built_at_sha` —
  карта свежая; файл возвращён `git checkout`.

## Предложения системе

- `orchestrator/github_adapter.py:16` упоминает в комментарии удалённый
  `_generate_and_commit_retro`. Файл вне зон задачи, поведения не меняет.
  Класс «докстринги, ссылающиеся на удалённые функции, вне зоны задачи»
  стоит ловить grep-ом имён удалённых функций при ревью удаления.
- Падения «команда недоступна процессу роли <роль>» у тестов, которые зовут
  `artel.py approve` через `artel.main()`, не дают ни разработчику, ни
  ревьюверу прогнать затронутые модули локально (здесь —
  `test_01m3sf7…`). Стоит, чтобы песочница тестов сама снимала
  `ARTEL_ROLE`, как это делает долгоживущий файл этой задачи
  (`DocsSandbox.setUp`).
