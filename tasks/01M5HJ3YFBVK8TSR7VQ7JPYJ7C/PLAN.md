---
task: 01M5HJ3YFBVK8TSR7VQ7JPYJ7C
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Тесты amend-tests для файлов с меткой без перечня лока (перенос приёмки G3б-1)

## Подход
Выход задачи — один файл долгоживущих тестов
`tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`. Его написал
test_author (ADR-0020), и пульт закоммитил его в ветку задачи (36aacffd).
Файл зафиксирован перечнем сумм, поэтому я его не правлю. Код пульта
задача не меняет. За разработчиком остаются три вещи: регенерировать
карту кода, прогнать мутации М1–М8 требования 6 и записать их итог
таблицей ниже.

## Шаги
1. Регенерирована `docs/codebase-map.md` командой `python3 scripts/codebase_map.py`. Изменились `built_at_sha` и блоки «Импортируется» с новым файлом тестов.
2. Прогон долгоживущего файла:
   `python3 -m pytest tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py -p no:cacheprovider -p timeout -o timeout=120 --durations=3`.
   Итог: 15 passed и 4 subtests passed за 31.95 с. Самый долгий тест — `test_ac1_worktree_valid_labelled_edit_moves_lock_without_manifest`, 5.21 с, это меньше потолка 15 с.
3. Мутации М1–М8. Каждая мутация — временная правка одной строки `orchestrator/amend.py` или `orchestrator/fsm.py`. После правки прогонялся файл из шага 2, затем `git checkout -- orchestrator/amend.py orchestrator/fsm.py`. До каждой правки файл зелёный (шаг 2). После всех откатов `git status --porcelain orchestrator/ scripts/` пуст.

## Проверка мутацией

| Мутация | Правка | Красные тесты | Прогнана |
|---|---|---|---|
| М1 | `amend.py:853` `profile = _task_profile(...) if _by_rule(rule) else None` → `profile = None` | `test_ac2_worktree_ban_in_labelled_file_refused`, `test_ac2_worktree_labelled_file_without_group_line_refused`, `test_ac2_worktree_only_md_with_banned_labelled_file_refused` (3 failed / 12 passed) | прогнана ✓, откачена |
| М2 | `amend.py:856` `guard.acceptance_test_files(tdir, rule)` → `guard.acceptance_test_files(tdir)` | `test_ac2_worktree_ban_in_labelled_file_refused`, `test_ac2_worktree_labelled_file_without_group_line_refused`, `test_ac2_worktree_only_md_with_banned_labelled_file_refused` (3 failed) | прогнана ✓, откачена |
| М3 | `amend.py:1201` → `by_rule = _by_rule(rule) and profile is not None and bool(manifest)` | `test_ac3_from_branch_ban_in_labelled_file_refused`, `test_ac3_from_branch_labelled_file_without_group_line_refused`, `test_ac3_from_branch_only_md_with_banned_labelled_file_refused` (3 failed) | прогнана ✓, откачена |
| М4 | `amend.py:286` `for label, text in [*plank_files, *items]:` → `for label, text in items:` | `test_ac4_worktree_removal_with_name_moved_to_plank_passes`, `test_ac4_from_branch_removal_with_name_moved_to_plank_passes` (2 failed) | прогнана ✓, откачена |
| М5 | `fsm.py:1127` `if decision.refusal:` → `if decision.refusal and repo_context.is_artel(decision.target):` | `test_ac5_multi_component_decision_refusal_on_approve` (1 failed) | прогнана ✓, откачена |
| М6 | `amend.py:852` (`_amend_plank_only`) `_refuse_traceability(conn, task_id, trace_errors)` → `pass` | `test_ac2_worktree_broken_traceability_refused`, `test_ac2_worktree_removed_only_labelled_file_refused` (2 failed) | прогнана ✓, откачена |
| М7 | `amend.py:1199` (путь `--from-branch`) `_refuse_traceability(conn, task_id, trace_errors)` → `pass` | `test_ac3_from_branch_broken_traceability_refused`, `test_ac3_from_branch_removed_only_labelled_file_refused` (2 failed) | прогнана ✓, откачена |
| М8 | `amend.py:847` `acceptance_traceability_errors(tdir, rule=rule)` → `acceptance_traceability_errors(tdir)` | `test_ac1_worktree_valid_labelled_edit_moves_lock_without_manifest` (оба подслучая), а также `test_ac2_worktree_ban_in_labelled_file_refused`, `test_ac2_worktree_labelled_file_without_group_line_refused`, `test_ac2_worktree_only_md_with_banned_labelled_file_refused` (5 failed) | прогнана ✓, откачена |

У М6, М7 и М8 номера строк в SPEC расходятся с кодом на HEAD 8c758cfa:
849-850 против 851-852, 1194-1195 против 1198-1199, 846 против 847. Я
нашёл строки по их тексту, сама мутация та же, что в SPEC. Под М8 сверх
требуемого п. 1 (а) краснеют и п. 1 (б)–(г): без `rule` трассируемость
не видит файл с меткой, и отказ приходит раньше с другим префиксом
группы.

После последнего отката `git status --porcelain orchestrator/ scripts/` пуст.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (AC-1, AC-2) | долгоживущий файл test_author; шаг 2 (зелёный), шаг 3 (М1, М2, М6, М8) |
| 2 (AC-3) | шаг 2, шаг 3 (М3, М7) |
| 3 (AC-4) | шаг 2, шаг 3 (М4) |
| 4 (AC-5) | шаг 2, шаг 3 (М5) |
| 5 (AC-6) | долгоживущий файл; шаг 1 (карта); шаг 2 (≤ 15 с на тест) |
| 6 (AC-7) | шаг 3, таблица «Проверка мутацией» |

## Влияние на систему
Ветка добавляет один новый файл в `tests/` и регенерирует
`docs/codebase-map.md`. Код пульта и существующие тесты не меняются, гейты
и инварианты тоже. Мутации были временными, все откачены, проверено
пустым `git status --porcelain orchestrator/ scripts/`. Полный набор
дорожает примерно на 30 с (решение Оператора: принято). Откат — revert
merge-коммита.

## Риски
- Под нагрузкой машины тесты файла шли медленнее: при мутационных
  прогонах файл занимал 60–97 с против 32 с в спокойном прогоне. Потолок
  15 с на тест рассчитан на отдельный прогон файла.
- Повторная сдача 22.10: прошлый advance отклонён таймаутом 110 с в
  `test_ac6_longest_test_within_limit_and_seed_printed` (подпроцесс
  pytest убит, `returncode -9`). Load average машины был около 19.
  Код и файлы не менялись. `plank-run` при load около 13–17 зелёный:
  5 passed за 33.73 с, AC-6 отдельно — 3 passed за 30.69 с. Если
  нагрузка повторится, таймаут может сработать снова.

## Предложения системе
- SPEC с адресами `файл:строка` для мутаций устаревает на 1–4 строки уже
  к шагу разработчика (здесь М6–М8). Надёжнее задавать мутацию текстом
  заменяемой строки, а номер давать только подсказкой.
- Скил coding-standards требует проверять тесты мутацией, но у пульта
  нет команды для прогона набора мутаций. Пришлось писать временный
  сценарий в каталоге документов и потом удалять его. Пригодилась бы
  команда вроде `artel.py mutate <id> <файл> <строка> <было> <стало>
  <тест>` с гарантированным откатом.
- Гейт приёмки красит шаг таймаутом подпроцесса планки, который зависит
  от нагрузки машины (AC-6, `timeout=110`). Сам гейт при этом не говорит,
  что дело в нагрузке. Стоит печатать в отказе load average или
  классифицировать `TimeoutExpired` как отказ окружения.
