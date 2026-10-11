---
task: T083
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Тестовая подметалка: уборка git-песочниц и изоляция от реального git

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (устойчивая уборка git-песочниц, одно общее место) | OK | `resilient_tmp_cleanup` в `tests/sandbox.py:52-75`, `TmpRootTest.setUp` переключён на него (`tests/sandbox.py:217`). Все 10 мест из PLAN/шага 2 переведены на тот же хелпер; `self.git("init"` в `tests/` даёт 11-е вхождение (`test_coldstart.py::GitObservedWorldTest`), но оно уже наследует `TmpRootTest` и общий фикс покрывает его без отдельной правки — список PLAN исчерпывающий. |
| 2 (перевод классов-родственников T047 на fake_git) | OK | `LegacyDbMigrationTest.setUp` (`tests/test_spec_budget.py:409-437`) получил ту же связку `ROOT/PROJECTS/TARGETS/ROLE_HOME/ROLE_CONFIG_DIR/BACKUP_MARKER/WORKTREES` + `gitcmd.git = fake_git`, что и `SpecBudgetOnTheGateTest.setUp` (строки 124-151) — дословное совпадение множества патчей. |
| 3 (полный набор `tests/` зелёный, независим от реального git) | OK | Подтверждено запуском (см. «Проверено исполнением»): полный набор в рабочей копии и приёмочный AC-3 (изолированная копия + посторонние ветки + worktree) — оба зелёные. |
| 4 (боевой код не меняется) | OK | `git diff main...HEAD --stat` и приёмочный `test_ac4_prod_code_unchanged` подтверждают: диффа в `orchestrator/`/`scripts/` нет, только `tests/`, `tasks/T083/*`, `docs/codebase-map.md`. |

## Замечания

Нет.

## Вердикт
approved

## Проверено исполнением

- `python3 -m unittest discover -s tests -p "test_*.py"` — 1032 теста, все зелёные (в рабочей копии на ветке задачи, ~111с).
- `python3 -m unittest tasks.T083.acceptance_tests.test_ac1_sandbox_cleanup_resilience tasks.T083.acceptance_tests.test_ac2_no_real_pult_git tasks.T083.acceptance_tests.test_ac4_prod_code_unchanged` — 5 тестов, все зелёные.
- `python3 -m unittest tasks.T083.acceptance_tests.test_ac3_full_suite_green_with_arbitrary_branches` — 1 тест, зелёный (~109с; изолированная копия репозитория, посторонние ветки включая коллизию `task/t001-byudzhet`, отдельный worktree).
- Мутационная проверка (не тавтология): временно откатил `tests/sandbox.py`/`tests/test_spec_budget.py` до версии `main` (через `git show main:<path>` поверх рабочей копии, с бэкапом изменённых файлов в scratchpad и восстановлением после проверки — `git diff HEAD -- tests/sandbox.py tests/test_spec_budget.py` пуст, рабочее дерево вернулось в точности к закоммиченному состоянию) —
  - `test_ac2_no_real_pult_git` красный: 208 вызовов `subprocess.run` с `cwd=<реальный ROOT пульта>` — то же число, что в докстринге приёмочного теста;
  - `test_ac1_sandbox_cleanup_resilience::NamedFlakyClassesCleanupSurvivesTest` красный при точечном откате только `TmpRootTest.setUp` к голому `tmp.cleanup()` (при сохранении экспортируемого имени `resilient_tmp_cleanup`, чтобы не ломать импорты остальных файлов) — падает с тем же `OSError: [Errno 39] Directory not empty: '.git'`, что в фактуре инцидента.
  - оба возвращены в зелёное состояние после восстановления файлов из бэкапа.
- Полнота списка мест AC-1: `grep -rn 'self.git("init"' tests/*.py` (в обход `tests/sandbox.py`) — 11 вхождений; все либо в списке PLAN/шага 2 (10 мест, все переведены на `resilient_tmp_cleanup`), либо `test_coldstart.py::GitObservedWorldTest`, чей `setUp` идёт через `TmpRootTest.setUp` и получает фикс от общего места без отдельной правки.
- Полнота класса дефекта AC-2: делегировал general-purpose агенту сплошной обход `tests/*.py` на классы, которые патчат `config.ROOT` (напрямую или через `TmpRootTest`), но не патчат `gitcmd.git` и не заводят свой git — агент прошёл ~32 файла и не нашёл ни одного непокрытого родственника `LegacyDbMigrationTest`: везде либо `gitcmd.git` подменён в нужной области видимости, либо `ROOT`/`WORKTREES` патчатся так, что непойманный вызов git бьёт по пустому tmp-каталогу, а не по реальному пульту, либо класс намеренно поднимает свой git внутри уже изолированной песочницы.
- `python3 scripts/codebase_map.py` (перегенерация) — диффа против закоммиченного `docs/codebase-map.md` нет, кроме строки `built_at_sha` (5f4c367 — коммит T083 с правками — против a42d941 — коммит слияния main); это ожидаемо в свете `.github/workflows/ci.yml:74-83` (гейт свежести карты сверяет содержимое, игнорируя `built_at_sha`, и работает только на `main`) — не дефект.
- `python3 -m py_compile` по всем изменённым файлам `tests/*.py` — без ошибок.

## Предложения системе

Нет.
