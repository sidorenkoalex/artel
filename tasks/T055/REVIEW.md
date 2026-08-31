---
task: T055
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Убрать рудимент посева артефактов в workspace

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_seed_uncommitted_artifacts` удалена целиком из `orchestrator/workspace.py` (была :44-62). |
| 2 | OK | Вызов из `ensure()` убран (`orchestrator/workspace.py:59-60` diff) — код после `git worktree add -b` больше не проверяет `res.returncode` для посева. |
| 3 | OK | Прочитан полный текущий файл `orchestrator/workspace.py` (не только diff-хунки, т.к. они не показывают весь докстринг): докстринг модуля (:1-14) и докстринг `ensure()` (:42-52) не упоминают снятую функцию и не описывают перенос незакоммиченного. Формулировка «модуль сам не делает ни одного сырого `Path.mkdir`/`shutil`» проверена — `grep -n "mkdir\|shutil"` в файле не находит вызовов (только сама фраза в докстринге), утверждение верно. |
| 4 | OK | Полный набор `tests/` (781 тестов) зелёный без изменений реализации `ensure`/`remove`/путей; наблюдаемое поведение не менялось. |
| 5 | OK | `git diff main...HEAD -- . ':!tasks/T055'` показывает правки ровно в `orchestrator/workspace.py`, `tests/test_workspace.py`, `docs/codebase-map.md` — без «попутных улучшений». |
| 6 | OK | `test_seeds_uncommitted_task_dir_into_a_fresh_worktree` удалён целиком (не переписан, не ослаблен) — единственная правка в `tests/`. |

## Замечания

Замечаний нет.

Проверено дополнительно (сверх diff, т.к. без этого нельзя было подтвердить AC):
- Полный прогон `python3 -m unittest discover -s tests` — 781 тестов, OK (нужно для AC-4 и амнистии требования 6 — убедиться, что удаление не задело сторонние тесты).
- Полный прогон приёмочных тестов `tasks/T055/acceptance_tests/` — 6 тестов, OK.
- `python3 scripts/guard.py --all` — 176 файлов, ок.
- Regen `docs/codebase-map.md` и сверка содержимого с закоммиченным (без строки `built_at_sha`) — совпадает; расхождение только в `built_at_sha` ожидаемо и штатно обрабатывается CI-шагом `codebase-map` (`.github/workflows/ci.yml:63-84`, комментарий Оператора 26.08 — built_at_sha не может нести sha своего же коммита).
- `grep -rn "_seed_uncommitted_artifacts"` по всему репозиторию — вхождения остались только в `tasks/T045/PLAN.md`, `docs/audits/code-revision-2026-08-28.md` и артефактах самой задачи T055 (SPEC/PLAN/TZ/acceptance_tests) — исторический текст и текст самой SPEC, не «кодовая база»; AC-1 буквально «по репозиторию» иначе противоречит самому себе (SPEC.md, где написан этот критерий, сама содержит имя рудимента). Тест `test_ac1_rudiment_absent_from_codebase.py` осознанно и обоснованно сузил скан до `orchestrator/` и `tests/` — интерпретация корректна, не переписывание требования.
- Сверены имена тестов, на которые ссылаются skip-заглушки AC-3/AC-4 (`test_creates_worktree_on_a_fresh_branch_from_main`, `test_fresh_branch_forks_from_main_not_from_head_of_something_else`, `tasks/T048/acceptance_tests/test_ac1_ac2_new_creates_branch.py`) — существуют, ссылки не фиктивны. Паттерн skip-приёмочного теста на существующий штатный CI-гейт — не самодеятельность разработчика: тот же приём уже есть в `tasks/T048/acceptance_tests/test_ac6_full_suite_regression.py` (и упомянутом в нём T045).

## Вердикт

approved

## Проверено исполнением
Ретроактивная пометка при миграции корпуса под evidence-контракт (T072, 2026-08-30): это ревью прошло до появления обязательной секции «Проверено исполнением» (SPEC T072, guard.py:review_evidence_errors). Факт исполнения проверок этим ревью, если они проводились, восстановить задним числом нельзя — что реально оценивалось, отражено выше, в разделах «Соответствие SPEC»/«Замечания» этого файла. Секция добавлена постфактум одним коммитом по всему корпусу только для соответствия новому структурному правилу guard.py, содержательно не переписывает исходное ревью.

## Предложения системе

