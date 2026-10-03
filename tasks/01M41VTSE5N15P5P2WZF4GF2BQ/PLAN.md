---
task: 01M41VTSE5N15P5P2WZF4GF2BQ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Команда docs, подсказка show и уборка веток artifact/**

## Подход
Узел git-логики подтягивания — в `orchestrator/artifact_branch.py` (SPEC,
требование 1: «узлом artifact_branch»), CLI-обвязка — в двух новых малых
модулях по образцу `plank_run.py`:

- `artifact_branch.fetch_from_origin(task_id)` /
  `fetch_all_from_origin(repo)`: `git fetch origin +<ref>:refs/artel/docs-fetch/<pid>/…`
  в приватное пространство (не прямо в `refs/artifacts/*`), затем сдвиг
  локальной ссылки только вперёд — `merge-base --is-ancestor` + `update-ref
  <ref> <new> <old>` со сверкой прежнего значения. Локальная впереди или
  разошлась — исход `FETCH_DIVERGED`, ссылка не тронута, текст называет
  `origin` (AC-7). Приватные ссылки убираются одним `update-ref --stdin`.
  `--fetch-all` — один `git fetch` с glob-рефспеком на репозиторий (AC-8).
  Отсутствие ссылки в `origin` отличается от недоступного `origin`
  (`gitcmd.remote_ref_state`) только когда fetch отказал — в штатном пути
  один сетевой вызов.
- `orchestrator/docs_fetch.py::cmd_docs` — `docs <id> [файл]` и
  `docs --fetch-all`; репозиторий — `artifact_branch.task_repo` (target
  задачи, AC-5); строка задачи в БД не обязательна (вторая машина);
  чтение — `artifact_branch.ls_tree`/`show` по sha головы, исторический
  снимок читается так же (AC-4). Ссылки нет нигде — `sys.exit` с id и
  именем ссылки (AC-6). `origin` недоступен, но локальная ссылка есть —
  предупреждение и чтение локальной.
- `orchestrator/artifact_cleanup.py::cmd_artifact_branches_cleanup` —
  `ls-remote origin refs/heads/artifact/*`, локальные `artifact/*`
  (`gitcmd.list_branches`), `ls-remote origin refs/artifacts/*` одним
  вызовом; id задачи — первый сегмент после `artifact/`, сверка без учёта
  регистра (ветки в нижнем регистре, ссылки — в исходном). `--execute`:
  нехватка — отказ до любого удаления (AC-13); иначе `push origin --delete`
  одним вызовом, затем `branch -D` (AC-14).
- `artel.py`: две записи таблицы диспетчера, `_ROLE_ALLOWED_COMMANDS` не
  меняется — закрытый по умолчанию белый список сам отказывает роли (AC-9).
- `catalog.cmd_show`: при пустом `artifact_branch.ref_head` — строка с
  `artel.py docs <id>` (AC-10).
- `retro_corpus.py`: только докстринг — первая строка (её берёт карта)
  называет `docs --fetch-all`; карта регенерирована (AC-11).

Бюджет не переоценивается: объём совпал с оценкой SPEC.

## Шаги
1. Узел подтягивания в `artifact_branch.py`, модуль `docs_fetch.py`,
   подсказка `show`, регистрация в `artel.py` (+ справка докстринга).
2. Модуль `artifact_cleanup.py` и регистрация в `artel.py`.
3. Докстринг `retro_corpus.py`, регенерация `docs/codebase-map.md`.
4. Тесты: долгоживущие файлы задачи (`tests/test_01m41vtse5n15p5p2wzf4gf2bq_*.py`,
   не правились) + свои углы `tests/test_docs_fetch_edges.py`
   (недоступный origin при локальной ссылке, уборка приватных ссылок,
   отсутствующий файл). Сторожа проверены временной мутацией — все три
   красные, код возвращён.

Прогоны (передний план, `-p timeout -o timeout=120`):
- `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`,
  `..._branches_cleanup.py`, `tests/test_docs_fetch_edges.py`,
  `tests/test_codebase_map.py`, `tests/test_guard_mutation_claim.py` —
  66 passed;
- `test_artel_role_restricted_commands`, `test_retro_corpus`,
  `test_artifact_branch_read_node`, `test_catalog_status_log`,
  `test_task_id_prefix_regression`, `test_01m3xtf5506gf43hd51ece230t_role_refusal`,
  `test_artifact_ref_sync`, `test_doctor_artifact_branch_sync`,
  `test_multitarget`, `test_invariants`, `test_artel_bootstrap` — 227 passed;
- планка `artel.py plank-run 01M41VTSE5N15P5P2WZF4GF2BQ` — 3 passed.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (`docs <id> [файл]`, история, отказ, не перезаписывать) | 1, 4 |
| 2 (`docs --fetch-all`) | 1, 4 |
| 3 (недоступно процессу роли) | 1, 2, 4 |
| 4 (подсказка `show`) | 1, 4 |
| 5 (`retro_corpus` без сети, докстринг, карта) | 3, 4 |
| 6 (`artifact-branches-cleanup`) | 2, 4 |
| 7 (девять постоянных тестов) | 4 |

## Влияние на систему
- Новое поведение только в двух новых командах Оператора и одной строке
  `show`; существующие пути `artifact_branch` (запись, отправка, чтение) не
  менялись — добавлены функции рядом. `push` ссылок документов по-прежнему
  без force; `docs` локальную ссылку только сдвигает вперёд со сверкой
  прежнего значения, так что зафиксированный коммит живой задачи не
  теряется (гейты фиксации/`ref_drift` не обходятся).
- Белый список команд роли (`_ROLE_ALLOWED_COMMANDS`) не расширен — обе
  команды отказывают процессу роли тем же гейтом диспетчера.
- `retro_corpus` — только докстринг, поведение и сеть не меняются.
- Приватное пространство `refs/artel/docs-fetch/<pid>/` убирается в
  `finally`; никакие читатели `refs/artifacts/*` его не видят.
- Откат — revert коммита задачи; данных/схемы БД изменение не трогает.

## Риски
- `artifact-branches-cleanup --execute` необратимо удаляет ветки — поэтому
  предпросмотр по умолчанию и сверка ссылок в `origin` до любого удаления;
  исполняет Оператор после мержа (SPEC, «Не входит»).
- Сбой `branch -D` после успешного удаления в `origin` (например, главная
  копия выписана на ветку `artifact/*`) — отказ называет, что в `origin`
  уже удалено; повтор команды доубирает локальные.

## Предложения системе
- `docs_fetch.py`/`doctor/artifact_branches.py` пользуются закрытыми
  `artifact_branch._NO_REPO`/`_origin_configured`/`_head` — у узла нет
  публичного «репозиторий с origin для target»; кандидат в отдельную
  задачу-рефакторинг узла.
- Bash роли в этом шаге отказывал на `ls` (`command not found`) и на
  составных командах с `$VAR` — читать каталог документов приходилось
  через `git ls-files`/Read; класс «инструмент окружения роли недоступен».
