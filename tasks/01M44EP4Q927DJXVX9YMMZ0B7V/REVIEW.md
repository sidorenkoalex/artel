---
task: 01M44EP4Q927DJXVX9YMMZ0B7V
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Помощник планки от пульта

## Фаза A — план
- Таблица покрытия полна: требования 1–9 → шаги 1–7, шаг 8 закрывает возврат
  из verifying (строгие заглушки `gitcmd.in_repo` в
  `test_fsm_map_conflict_autoresolve.py`). Шаги размера MR, не микрооперации.
- Подход не противоречит архитектуре: одна точка выкладки (`_write_plank` через
  `_with_plank_helper`), потребители не правятся, кроме двух `is_dir()` по
  ANSWER-1 (вопрос 1, вариант A). Раздел «Расширение зон» есть и совпадает с
  диффом: `orchestrator/pull.py:540`, `orchestrator/advance_gates/acceptance.py:228`,
  по одной строке в каждом.
- «Влияние на систему» сходится с диффом: `plank_present` для пустой планки,
  резерв имени через `guard.is_extraneous_acceptance_test_file`, дополнительные
  чтения git только в клоне проекта и репозитории ссылки. Путь отката описан.
- Приложение к `skills/test-authoring.md` есть. Проверка `git apply --check`
  в PLAN подтверждена, планка AC-10 зелёная.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/plank_helper.py` импортирует только stdlib (`os`, `subprocess`, `tempfile`, `pathlib`). Есть константы и четыре функции. `ArtifactReadError` — подкласс `GitError`, отличим от `None`. `apply_check` подаёт дифф файлом и проверяет во временном индексе (`read-tree HEAD` + `--cached`). Правило `changed_paths` записано в докстрингах модуля и функции. |
| 2 | OK | `_plank_helper_text` берёт `gitcmd.diff_base`/`diff_base_source(t.branch, repo=workspace.task_repo)`, ту же пару, что у `_zones_gate` (`zones.py:198-199`). Сам помощник базу не считает. |
| 3 | OK | Обе выкладки идут через `_with_plank_helper` → `_write_plank`. Помощник — ключ `wanted`, поэтому прунинг его не удаляет. `drop_from_code_copy` убирает каталог целиком. Потребители получают помощник без правки. |
| 4 | OK | Ссылка документов: автокоммит отбрасывает `_pult.py` как посторонний (`guard.py` — `RESERVED_PLANK_HELPER_NAME`). Кодовая ветка: код коммитится с `exclude=f"tasks/{task_id}"` (`checkpoint.py:127,321,755`). Каталог документов задачи: выкладка туда не пишет. |
| 5 | OK | `_reserved_plank_helper_refusal` отказывает, если файл есть в голове ссылки. Для черновика срабатывает подсказка по записи журнала «посторонние файлы». Действие одно — `STRAY_PLANK_FILES_ACTION`, подсказка «имя занято помощником пульта». Файл пульта побеждает (`{**wanted, HELPER: …}`). |
| 6 | OK | `ARTIFACT_DISK_READ_RECIPE_TMPL` и подсказка гейта называют `artifact_text(`. Правило `scan_artifact_disk_reads` не тронуто. |
| 7 | OK | Приложение в PLAN: раздел о помощнике и ссылки из двух разделов. Применимость подтверждает планка AC-10. |
| 8 | OK | Карта регенерирована, AC-11 зелёный. |
| 9 | OK | `tests/test_plank_helper.py`: 12 тестов с заявками «Ловит мутацию», покрывают требования 1, 2, 3, 5, 6 и механизм требования 4 (имя в посторонних). |

## Замечания
Блокеров и major нет. Наблюдения без требования правки — в «Предложениях
системе» (там же расхождение текста SPEC с фактическим гейтом зон: код следует
явной букве SPEC).

Сверка изменённых утверждений `tests/` с base:
- `tests/test_guard_artifact_disk_read.py` (3 метода) и
  `tests/test_fsm_advance_tests_writing_artifact_source.py` (2 метода): меняется
  только ожидаемый текст рецепта/подсказки, этого требует SPEC (требование 6),
  и есть мандат ANSWER-1 (вопрос 2, 2.1–2.5). Чувствительность сохранена:
  проверка подстановки найденного имени (`SPEC.md`, `ANSWER-1.md`,
  `ANSWER-3.md`, семь имён в `subTest`) и `assertNotIn("-PLAN.md")` остались.
- `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`: снимок `observed_run`
  исключает только `acceptance.PLANK_HELPER_NAME`, утверждения методов не
  менялись (ANSWER-1, 2.6). Это сужение данных под неизменным утверждением, но
  оно в точности совпадает с мандатом.
- `tests/test_branch_freshness_gate.py` в диффе отсутствует, файл равен base.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний уровня blocker/major/minor в этой итерации не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M44EP4Q927DJXVX9YMMZ0B7V`:
  35 passed in 26.70s, код выхода pytest 0.
- `python3 -m pytest -q tests/test_plank_helper.py tests/test_guard_artifact_disk_read.py tests/test_fsm_advance_tests_writing_artifact_source.py tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py tests/test_pull.py tests/test_branch_freshness_gate.py tests/test_fsm_map_conflict_autoresolve.py tests/test_acceptance.py tests/test_acceptance_collect.py tests/test_zones_gate.py`:
  135 passed, 48 subtests passed.
- Временная мутация в `orchestrator/acceptance.py`: в `_with_plank_helper`
  порядок изменён на `{HELPER: …, **wanted}`, а в `plank_present` перестал
  исключаться `PLANK_HELPER_NAME`. Под мутацией `tests/test_plank_helper.py`
  дал 2 failed: `test_pult_file_wins_over_plank_file_and_drop_removes_it` и
  `test_helper_alone_is_not_a_plank`. Заявки обоих тестов подтверждены. Файл
  возвращён через `git checkout -- orchestrator/acceptance.py`,
  `git status --porcelain` пуст.
- CI коммита 836e299e зелёный (16 проверок, из пакета) — полный набор `tests/`.

## Предложения системе
- SPEC 01M44EP4Q927DJXVX9YMMZ0B7V, «Контекст», и приложение к
  `skills/test-authoring.md` утверждают, что гейт зон не включает
  незакоммиченные правки отслеживаемых файлов. Это не так:
  `orchestrator/advance_gates/zones.py:145-166`
  (`_untracked_worktree_paths`) читает `git status --porcelain=v1
  --untracked-files=all`, то есть staged и unstaged правки тоже. Помощник
  следует явной букве SPEC, поэтому на грязном дереве `changed_paths()` уже
  списка гейта. Обычно не всплывает: перед гейтом пульт коммитит код. Но
  формулировку «правилом гейта зон» в скиле Оператору стоит уточнить, когда он
  будет применять приложение (или явно задокументировать это различие).
- Все файлы планки помечены `Группа: разовый`, хотя AC-2…AC-8 — свойства кода.
  Здесь это компенсировано `tests/test_plank_helper.py` (требование 9), но
  класс «свойство кода в разовой группе» test_author повторяет. Стоит, чтобы
  гейт `tests_writing` предупреждал, когда критерий SPEC называет модуль кода,
  а файл планки помечен разовым.
