---
task: 01M5W67E0AYGKF03SEM6E2AQX2
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: GitLab Б1: ветка по ключу трекера, автор и шаблон коммита, сжатие и перебазирование, единая точка отправки

# GitLab, шаг Б1: ветка задачи по ключу трекера, автор и шаблон коммита, сжатие и перебазирование, единая точка отправки с белым списком

## Факты

ADR-0029 (принят 26.10.2026), п. 1 (подготовка ветки на входе в `verifying`), п. 4–6, п. 11, п. 13; шаг Б1 после А0 (`targets.unsupported_reason`).

1. Имя ветки задачи — `orchestrator/catalog.py:912` `f"task/{task_id.lower()}-{slugify(title)}"`; поиск веток пульта — `orchestrator/coldstart.py:59` `gitcmd.list_branches("task/", …)`. Внешние ссылки задачи — `new --ref <система>:<ключ>`, поля `policy.ref_systems`, `policy.ref_required` (`targets.py:289-305`, `catalog.py:558-604`); при делении ссылки копируются частям (`catalog.py:1030-1033`).
2. Отправки на сервер разбросаны по модулям: `github_adapter.py:166,241`, `fsm_merge_gate.py:744,1316`, `cleanup.py:265` (`push --delete`), `cleanup.py:268` (`--force-with-lease`), `artifact_branch.py:427`, `artifact_cleanup.py:103` (`--delete`), `snapshot.py:297`, `notes.py`, `pool_seal.py`, `doctor/*`. Все идут через `gitcmd.in_repo`/`repo_context.git` → `gitcmd`; `gitcmd.py:37` `HOSTING_SUBCOMMANDS`, `gitcmd.py:~95-118` определяет проект по пути/адресу вызова и токен хостинга (`hosting_token`).
3. Автор коммитов роли — окружение роли `GIT_AUTHOR_*` (`orchestrator/doctor/preflight.py:69-88`); коммиты фиксации пульта — `fixation.FIXATION_AUTHOR_*` (`checkpoint.py:1882`, `amend.py:799`); документы задачи — `artifact_branch.py:291`.
4. Подтяжка перед шагом разработчика — `runner._pull_before_developer_step` (`runner.py:620`); переход `in_dev → verifying` и его рубежи — ADR-0015 п. 2, инвариант 39 (`orchestrator/fsm_advance.py`).
5. Токен Developer подключаемого проекта может отправлять в любые незащищённые ветки (в том числе `feature/*` коллег), вливать в них MR и удалять их — защита только кодом пульта (сверка защит 26.10.2026).

## Требуется

1. **Поля записи** (`targets.py`, проверка при загрузке, значения по умолчанию — нынешнее поведение):
   - `policy.branch_template` (по умолчанию `task/{id}-{slug}`), подстановки `{id}`, `{slug}`, `{ref}`; `{ref}` — ключ ссылки системы `policy.ref_required`; шаблон с `{ref}` без `ref_required` — отказ загрузки;
   - `policy.ref_pattern` — регулярное выражение допустимого ключа (полное совпадение);
   - `policy.freshness`: `merge` (по умолчанию) | `rebase`;
   - `policy.squash_before_mr` (по умолчанию `false`);
   - `policy.commit_template` (по умолчанию `{id}: {text}`), подстановки `{id}`, `{ref}`, `{text}`; шаблон, отличный от умолчания, без `squash_before_mr: true` — отказ загрузки (шаблон применяется к сжатому коммиту);
   - `machine.commit_author` (имя и email) и `policy.co_author` (строка `Co-authored-by: …`) — необязательны;
   - `policy.push_options` (список, по умолчанию пусто); отказ загрузки на `ci.skip` и на переменные из `policy.push_options_forbidden` (список имён переменных, которые запись запрещает передавать);
   - `policy.ci_required_jobs` (список имён заданий, по умолчанию пусто — читает адаптер А1);
   - `policy.mr_assignee`, `policy.draft_mr` (по умолчанию `true`), `policy.max_in_flight` — только объявление и проверка (исполняет Б2).
2. **Ветка задачи.** `new` строит имя по `branch_template`; ключ не по `ref_pattern` — отказ до заведения задачи. `new` и деление отказывают, если ветка с этим именем уже есть на сервере (`ls-remote`) или у любой задачи проекта в любом состоянии (БД). Поиск веток пульта (`coldstart` и др.) — по шаблону записи, а не по префиксу `task/`.
3. **Автор и соавтор.** Для записи с `commit_author` окружение роли и коммиты пульта в ветке задачи и в `refs/artifacts/<id>` получают этого автора (и коммиттера); `co_author` дописывается строкой в сообщение каждого коммита задачи пультом (не настройкой, которую может сменить роль). До первой отправки — сверка `commit_author` с владельцем токена через адаптер (`forge.token_user`, А1; до мержа А1 — шаг пропускается с записью журнала «сверка автора — после адаптера»).
4. **Подготовка ветки на входе в `verifying`** (каждый переход `in_dev → verifying`, ADR-0015 п. 2): при `squash_before_mr: true` — коммиты задачи от точки ответвления сжимаются в один с сообщением по `commit_template` (`{text}` — название задачи); затем подтяжка методом `freshness` (`merge` — как сейчас, `rebase` — перебазирование ветки задачи на `origin/<base>` только в рабочей копии задачи, `base` не меняется). Конфликт — возврат в `in_dev` тем же путём, что конфликт подтяжки сейчас. Без новых полей поведение перехода не меняется.
5. **Перезапись своей ветки** (после сжатия/перебазирования) — только `push --force-with-lease=refs/heads/<ветка>:<sha последней своей отправки из журнала>`; первая отправка — без перезаписи. Голова на сервере не совпала с последней своей отправкой — чужой коммит: эскалация, без перезаписи.
6. **Единая точка отправки с белым списком** (`gitcmd`): для проекта, у которого `branch_template` отличен от умолчания или `merge_gate` не `operator`, любая отправка на сервер проверяется до вызова git: разрешены только ветка задачи по шаблону (сверка имени с задачей в БД) и `refs/artifacts/*`; отправка в `base`, удаление веток (`--delete`, `:<ref>`), теги, `refs/heads/*` вне шаблона — отказ с причиной и записью журнала. Каталог хуков — в самом вызове (`-c core.hooksPath=<каталог пульта вне зон записи ролей>`) с хуком `pre-push` тех же правил (сверка контрольной суммы хука в `doctor` — шаг Б2). Для артели и проектов с полями по умолчанию поведение отправок прежнее.
7. Строки `doctor` (хук, шаблон ветки против правила `workflow`, показ `push_options`) — в шаге Б2: зону `orchestrator/doctor/` держит параллельная А1.

Критерии приёмки:
- `new --ref tracker:PROJ-7` при `branch_template: feature/{ref}`, `ref_pattern: PROJ-\d+` — ветка `feature/PROJ-7`; `--ref tracker:PROJ-7x` — отказ, задачи нет; ветка `feature/PROJ-7` уже на сервере (подменённый `ls-remote`) или у задачи проекта в `done` — отказ; часть деления с той же ссылкой — отказ деления с причиной;
- белый список: отправка в `feature/PROJ-8` (чужая задача), в `main`, удаление своей ветки, тег — отказ до вызова git (шпион `subprocess.run` не вызван), запись журнала; отправка своей ветки и `refs/artifacts/<id>` — проходит;
- перезапись: `--force-with-lease` несёт sha последней своей отправки; голова сервера другая — эскалация, отправки нет;
- сжатие и `rebase` на фикстурном репозитории: после перехода в `verifying` в ветке один коммит с сообщением по шаблону и автором `commit_author`, строка `Co-authored-by`, ветка поверх `origin/<base>`; конфликт перебазирования — возврат в `in_dev`;
- проверка записи: шаблон с `{ref}` без `ref_required`, `commit_template` без сжатия, `push_options` с `ci.skip` или запрещённой переменной — отказ загрузки с именем поля;
- артель и проект с полями по умолчанию: существующие тесты `new`, подтяжки, отправок, `coldstart`, `cleanup` зелёные без правки, кроме перечисленных в «Существующие тесты».

Порядок: после 01M5W27CY7K7NR9347NKD8F0NX

Зоны: `orchestrator/targets.py`, `orchestrator/catalog.py`, `orchestrator/coldstart.py`, `orchestrator/gitcmd.py`, `orchestrator/fsm_advance.py`, `orchestrator/runner.py` (подтяжка и окружение роли — автор), `orchestrator/checkpoint.py` (автор и соавтор коммитов пульта), `orchestrator/artifact_branch.py` (автор документов), `orchestrator/pull_main.py`, `tests/` (долгоживущие файлы задачи). Аналитик сверяет по коду все места отправки и построения имени ветки и вносит их файлы в зоны SPEC поимённо.

Только чтение: `orchestrator/config.py` и `orchestrator/doctor/` (держит параллельная А1; константы — в модулях задачи), `orchestrator/forge.py`, `orchestrator/gitlab_adapter.py` (появятся в А1), `orchestrator/fsm_merge_gate.py`, `orchestrator/cleanup.py`, `docs/adr/0029-external-delivery-via-mr.md`, `docs/adr/0015-ci-before-review.md`.

Существующие тесты: правка — по мандату Оператора 26.10 на тесты, которые меняет ADR-0029 (без ослабления, с матрицей и независимой проверкой) через гейт SPEC; ожидается `tests/test_coldstart.py` (поиск веток по шаблону). Иное — эскалация.

Не входит: открытие и снятие черновика MR, `awaiting_human`, `mr-sync`, поведение `kill` и `cleanup` для `target-human` (Б2); `full_suite` и `verify` (В1, В2); адаптер (А1).

Рамка: $70. Набор моделей — по умолчанию.
