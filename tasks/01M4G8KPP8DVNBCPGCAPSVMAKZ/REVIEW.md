---
task: 01M4G8KPP8DVNBCPGCAPSVMAKZ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Роль не пишет в главную копию пульта — корень генератора карты и сторож после шага роли

## Фаза A: план
- Таблица покрытия полна: требования 1–5 → шаги 1–3; AC-1..AC-8 закрыты
  долгоживущими файлами задачи, свой `tests/test_main_copy_watch.py` — на
  свойства вне них (сбой git на сверке, окно выборки соседей).
- Шаги размера MR, не микрооперации. Подход не конфликтует с архитектурой:
  сторож — в `checkpoint.py` рядом с чекпоинтами, вызов из всех четырёх
  `_finish_*`; `store.py` (путь «только чтение») не тронут, используются
  существующие `steps_of_action`/`last_task_step_of`.
- «Влияние на систему» совпадает с diff: 4 файла (`checkpoint.py`,
  `runner.py`, `scripts/codebase_map.py`, новый тест) + карта; существующие
  тесты не правились. Откат — revert.
- ANSWER-1 учтён: `_main_copy_status` зовёт git своей точкой
  (`subprocess.run(["git", "-C", config.ROOT, ...], env=gitcmd.pult_env())`),
  оба упавших в CI теста теперь зелёные (прогнал, см. ниже); долгоживущие
  тесты не правились.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `scripts/codebase_map.py::main` — `repo_root(Path(__file__).resolve().parent)`. Все вызовы пульта (`brief.py:283`, `pull.py:322`, `fsm_postmerge.py:92`, `fsm_merge_gate.py` через `MAP_GENERATOR_REL`) запускают относительный `scripts/codebase_map.py` с `cwd=<дерево>` — сценарий того же дерева, поведение прежнее (проверено grep). `RepoRootTest` не тронут. |
| 2 | OK | Снимок — `runner.run_agent_once` сразу после `_prepare_step` (после записи «agent run started», `runner.py:1496`), до `_spawn_and_wait`; сверка — во всех `_finish_timeout`/`_finish_failed`/`_finish_missing_artifact`/`_finish_ok` сразу после чекпоинта (в `_finish_ok` — вне `if`, после обоих вариантов чекпоинта). Пути SKIPPED агента не запускают — сверка им не нужна. |
| 3 | OK | `raise_alert(None, "warning", "main-copy-watch", …)`: роль, id задачи, пути, перечень пересекающихся шагов (по `id` журнала, окно 2×`AGENT_TIMEOUT_SEC`), явное «Кто их внёс, не установлено». |
| 4 | OK | `after - watch.status` по строкам porcelain; пустая разница — без алерта. |
| 5 | OK | Только `git status` и `raise_alert`; ни FSM, ни git-записи. AC-7 зелёный. |

Наблюдение без замечания: каталог, неотслеживаемый уже до шага, porcelain
сворачивает в `?? dir/` — новый файл внутри него сторож не увидит. Тот же
класс, что риск PLAN «файл грязный до шага» (строка статуса не меняется),
требование 4 его не противоречит; инцидентный случай (правка
отслеживаемого `docs/codebase-map.md`) ловится.

## Замечания
Нет blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний в итерации 1 не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_main_copy_watch.py tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py tests/test_01m4g8kpp8dvnbcpgcapsvmakz_codebase_map_root.py tests/test_codebase_map.py tests/test_review_package.py tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py tests/test_timeout_checkpoint.py`
  — 230 passed, 24 subtests passed (165 с); в том числе оба теста из ANSWER-1.
- `artel.py plank-run 01M4G8KPP8DVNBCPGCAPSVMAKZ` — отказ «планки нет: в
  refs/artifacts/… нет test_*.py; pytest не запускался» (у задачи только
  долгоживущие файлы в `tests/`, они прогнаны выше).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` —
  расходится только строка `built_at_sha`, содержимое карты свежее;
  регенерация откачена `git checkout -- docs/codebase-map.md`, дерево чистое.
- `grep -rn "codebase_map\.(main|py)|chdir"` по `orchestrator/ scripts/ tests/` —
  все вызывающие запускают сценарий своего дерева, импортного вызова
  `codebase_map.main()` с подменой cwd нет.
- Статус CI коммита 0dfc571f по пакету — зелёный (16 проверок).
- Заявки «Ловит мутацию» `tests/test_main_copy_watch.py` сверены с кодом:
  снятие записи журнала → `len(records) == 1` краснеет; снятие окна
  `cutoff` → `assertNotIn("01TASKORPHAN")` краснеет; временную мутацию
  руками не вносил (разработчик её зафиксировал в PLAN, сомнений нет).

## Предложения системе
- `orchestrator/review.py` (пакет ревью): при задаче только с долгоживущими
  тестами `plank-run` отказывает «планки нет» — стоит указать это в пакете
  заранее, чтобы ревьювер не тратил прогон.
