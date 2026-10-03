---
task: 01M41VTSE5N15P5P2WZF4GF2BQ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Команда docs, подсказка show и уборка веток artifact/**

## Фаза A: план
- Таблица покрытия PLAN.md охватывает все 7 требований SPEC; шаги 1–4 — единицы размера MR (узел + команда `docs` + `show`; уборка; докстринг + карта; тесты).
- Подход согласован с архитектурой: git-логика в узле `artifact_branch` (требование 1 прямо называет узел), CLI-обвязка — малые модули по образцу `plank_run.py`; белый список ролей не трогается (закрыт по умолчанию).
- «Влияние на систему» сверено с diff: изменены ровно `artel.py` (справка, импорт, две записи диспетчера), `artifact_branch.py` (только добавленные функции после `origin_sync_refusal`, существующие не тронуты), `catalog.py` (5 строк в `cmd_show`), `retro_corpus.py` (только докстринг), два новых модуля, один новый тест; `docs/codebase-map.md` регенерирована. Путь отката (revert) назван.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `docs_fetch._docs` → `artifact_branch.fetch_from_origin` (репозиторий — `task_repo`, target задачи), чтение по sha головы через `ls_tree`/`show`; исторический снимок читается так же (нет обращения к родителю); отсутствие ссылки везде — `sys.exit` с id и именем ссылки; локальная впереди/разошлась — `FETCH_DIVERGED`, `update-ref` не вызывается, stderr называет `origin`. Сдвиг вперёд — `update-ref <ref> <new> <old>` со сверкой прежнего значения. Fetch идёт в приватное `refs/artel/docs-fetch/<pid>/…`, поэтому даже `fetch.prune=true` не может задеть `refs/artifacts/*`. |
| 2 | OK | `fetch_all_from_origin`: один `git fetch` с glob-рефспеком на репозиторий; `_fetch_all` обходит артель и target'ы из `targets.yaml` с дедупликацией репозитория; печатает «принесено N, обновлено M» и расхождения построчно. |
| 3 | OK | `_ROLE_ALLOWED_COMMANDS` не тронут; отказ диспетчера под `ARTEL_ROLE` подтверждён тестами AC-9 обоих долгоживущих файлов. |
| 4 | OK | `catalog.cmd_show`: при пустом `ref_head` — строка `… artel.py docs <id>`. |
| 5 | OK | `retro_corpus.py` — только докстринг, первая строка называет `docs --fetch-all`; секция карты (`docs/codebase-map.md:1360-1362`) совпадает; поведение без сети (AC-11 зелёный). |
| 6 | OK | `artifact_cleanup`: предпросмотр без удаления; `--execute` — сверка `ls-remote origin refs/artifacts/*` до любого удаления, без учёта регистра; затем `push origin --delete` одним вызовом и `branch -D`. Ссылки документов не трогаются. |
| 7 | OK | Девять сценариев закрыты долгоживущими `tests/test_01m41vtse5n15p5p2wzf4gf2bq_{docs_command,branches_cleanup}.py`, у каждого метода «Ловит мутацию:»; планка AC-15 зелёная. |

## Замечания
Нет замечаний уровня blocker/major/minor. Наблюдения без требования правки:
- `task_repo` при отсутствии строки задачи в БД (вторая машина без БД) выбирает артель — `docs <id>` задачи внешнего проекта там пойдёт в `origin` артели и получит отказ «нет ни в origin, ни локально». Это свойство узла (`orchestrator/artifact_branch.py:83-89`), а не новой команды; SPEC сценарий «внешняя задача без строки БД» не задаёт, а `docs --fetch-all` обходит проекты по `targets.yaml` и эту дыру закрывает.
- `tests/test_docs_fetch_edges.py` не повторяет долгоживущие тесты: недоступный `origin`, уборка приватных ссылок и отсутствующий файл в них не проверяются.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py tests/test_docs_fetch_edges.py tests/test_retro_corpus.py tests/test_artel_role_restricted_commands.py tests/test_artifact_branch_read_node.py tests/test_catalog_status_log.py` — 47 passed, 4 subtests passed.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M41VTSE5N15P5P2WZF4GF2BQ` — 3 passed, код выхода 0.
- `python3 scripts/codebase_map.py` + `git diff docs/codebase-map.md` — расхождение только в строке `built_at_sha`; карта свежая. Регенерированный файл откачен `git checkout`.
- Временные мутации на `tests/test_docs_fetch_edges.py` (каждая откачена `git checkout`, дерево чистое):
  1. `_drop_fetch_refs(repo, [tmp])` в `fetch_from_origin` заменён на `pass` → `test_fetch_leaves_no_private_refs` красный;
  2. `FETCH_FAILED` в `docs_fetch._docs` превращён в `sys.exit` → `test_unreachable_origin_reads_local_ref` красный;
  3. `text is None` из `artifact_branch.show` печатается как пустой файл → `test_missing_file_named_refusal` красный.
- CI коммита 17de7de1 зелёный (16 проверок, из пакета).

## Предложения системе
- Планка `acceptance_tests/test_task_facts.py` помечена `Группа: разовый`, но `test_ac11_docstring_and_map_name_fetch_all` проверяет свойство кода (докстринг `retro_corpus` называет `docs --fetch-all`), которое в `tests/` никто не сторожит. Адрес: skills/test-authoring.md — граница групп для «документационных» свойств кода.
