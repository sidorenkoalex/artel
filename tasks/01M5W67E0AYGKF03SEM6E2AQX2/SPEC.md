---
task: 01M5W67E0AYGKF03SEM6E2AQX2
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/targets.py, orchestrator/catalog.py, orchestrator/coldstart.py, orchestrator/gitcmd.py, orchestrator/fsm_advance.py, orchestrator/runner.py, orchestrator/checkpoint.py, orchestrator/artifact_branch.py, orchestrator/pull_main.py, orchestrator/pull.py, orchestrator/fsm.py, orchestrator/github_adapter.py, orchestrator/amend.py, orchestrator/snapshot.py, tests/
merge_after: 01M5W27CY7K7NR9347NKD8F0NX
budget_usd: 70
---

# SPEC: GitLab Б1 — ветка по ключу трекера, автор и шаблон коммита, сжатие и перебазирование, единая точка отправки

## Контекст
ADR-0029 (принят 26.10.2026), п. 1, 4–6, 11, 13; шаг Б1 после А0
(`targets.unsupported_reason`). Подключаемый проект на GitLab требует ветку
по ключу трекера, своего автора и шаблон коммита, сжатие и перебазирование
перед MR. Токен Developer такого проекта может отправлять в любые
незащищённые ветки (в том числе `feature/*` коллег), вливать и удалять их —
защита только кодом пульта, а отправки сейчас разбросаны по модулям
(`github_adapter.py:166,241`, `fsm_merge_gate.py:744,1316`,
`cleanup.py:265,268`, `artifact_branch.py:427`, `artifact_cleanup.py:103`,
`snapshot.py:297` и др.), все через `gitcmd`. Имя ветки строится только в
`catalog.py:912`, поиск веток пульта по префиксу `task/` — только в
`coldstart.py:59`.

Решения Оператора по батчу вопросов — `ANSWER-1.md` (26.10.2026): белый
список только при `merge_gate` не `operator`; проверка занятости имени —
только при нестандартном шаблоне; зоны расширены поимённо; деление на две
части; `freshness` — только на `in_dev → verifying`; `Co-authored-by` — в
коммитах пульта.

## Требования

1. **Поля записи** (`targets.py`, проверка при загрузке; значения по
   умолчанию — нынешнее поведение):
   - `policy.branch_template` (по умолчанию `task/{id}-{slug}`), подстановки
     `{id}`, `{slug}`, `{ref}`; `{ref}` — ключ ссылки системы
     `policy.ref_required`; шаблон с `{ref}` без `ref_required` — отказ
     загрузки;
   - `policy.ref_pattern` — регулярное выражение допустимого ключа (полное
     совпадение);
   - `policy.freshness`: `merge` (по умолчанию) | `rebase`;
   - `policy.squash_before_mr` (по умолчанию `false`);
   - `policy.commit_template` (по умолчанию `{id}: {text}`), подстановки
     `{id}`, `{ref}`, `{text}`; шаблон, отличный от умолчания, без
     `squash_before_mr: true` — отказ загрузки;
   - `machine.commit_author` (имя и email) и `policy.co_author` (строка
     `Co-authored-by: …`) — необязательны;
   - `policy.push_options` (список, по умолчанию пуст); отказ загрузки на
     `ci.skip` и на переменные из `policy.push_options_forbidden` (список
     имён переменных, которые запись запрещает передавать);
   - `policy.ci_required_jobs` (список имён заданий, по умолчанию пуст);
   - `policy.mr_assignee`, `policy.draft_mr` (по умолчанию `true`),
     `policy.max_in_flight` — только объявление и проверка формы.
   Отказ загрузки называет имя поля.
2. **Ветка задачи.** `new` строит имя ветки по `branch_template`; ключ ссылки
   не по `ref_pattern` — отказ до заведения задачи. Когда `branch_template`
   отличен от умолчания (или не несёт `{id}`), `new` и деление отказывают,
   если ветка с этим именем уже есть на сервере (`ls-remote`) или у любой
   задачи проекта в любом состоянии (БД); сбой `ls-remote` — отказ `new`/
   деления с причиной «имя ветки не проверено». При шаблоне по умолчанию
   сетевого вызова нет. Поиск веток пульта (`coldstart` и др.) — по шаблону
   записи, а не по префиксу `task/`.
3. **Автор и соавтор.** Для записи с `commit_author` окружение роли и
   коммиты пульта в ветке задачи и в `refs/artifacts/<id>` получают этого
   автора и коммиттера. `co_author` дописывается строкой в сообщение каждого
   коммита, который пишет пульт (чекпоинты, фиксация, документы, сжатый
   коммит), — не настройкой, которую может сменить роль; коммиты роли без
   сжатия не переписываются. До первой отправки — сверка `commit_author` с
   владельцем токена через адаптер (`forge.token_user`, А1); пока адаптера
   нет — шаг пропускается с записью журнала «сверка автора — после
   адаптера».
4. **Подготовка ветки на входе в `verifying`** (каждый переход
   `in_dev → verifying`): при `squash_before_mr: true` коммиты задачи от
   точки ответвления сжимаются в один с сообщением по `commit_template`
   (`{text}` — название задачи); затем подтяжка методом `freshness`
   (`merge` — как сейчас; `rebase` — перебазирование ветки задачи на
   `origin/<base>` только в рабочей копии задачи, `base` не меняется).
   Конфликт — возврат в `in_dev` тем же путём, что конфликт подтяжки сейчас.
   Подтяжка перед шагом разработчика и `pull-main` — прежний `merge` при
   любом `freshness`. Без новых полей поведение перехода не меняется.
5. **Перезапись своей ветки** (после сжатия/перебазирования) — только
   `push --force-with-lease=refs/heads/<ветка>:<sha последней своей
   отправки из журнала>`; первая отправка — без перезаписи. Голова на
   сервере не совпала с последней своей отправкой — эскалация, без
   перезаписи. Поведение черновика MR (`github_adapter.py`) не меняется —
   меняется только место отправки ветки.
6. **Единая точка отправки с белым списком** (`gitcmd`): для проекта, у
   которого `merge_gate` не `operator`, любая отправка на сервер
   проверяется до вызова git: разрешены только ветка задачи по шаблону
   (сверка имени с задачей в БД) и `refs/artifacts/*`; отправка в `base`,
   удаление веток (`--delete`, `:<ref>`), теги, `refs/heads/*` вне шаблона —
   отказ с причиной и записью журнала. Каталог хуков — в самом вызове
   (`-c core.hooksPath=<каталог пульта вне зон записи ролей>`) с хуком
   `pre-push` тех же правил. Для проектов с `merge_gate: operator` (в том
   числе с нестандартным `branch_template`), для артели и проектов с
   полями по умолчанию поведение отправок прежнее.

## Критерии приёмки

AC-1. Запись с шаблоном ветки, несущим `{ref}`, без `policy.ref_required` — отказ загрузки с именем поля `branch_template`.
AC-2. Запись с `commit_template`, отличным от `{id}: {text}`, без `squash_before_mr: true` — отказ загрузки с именем поля `commit_template`.
AC-3. Запись с `push_options`, несущим `ci.skip`, или переменную из `push_options_forbidden` — отказ загрузки с именем поля `push_options`.
AC-4. Запись без новых полей загружается, значения по умолчанию: `branch_template` `task/{id}-{slug}`, `freshness` `merge`, `squash_before_mr` `false`, `commit_template` `{id}: {text}`, `push_options` и `ci_required_jobs` пусты, `draft_mr` `true`.
AC-5. `new --ref tracker:PROJ-7` при `branch_template: feature/{ref}`, `ref_pattern: PROJ-\d+` — ветка задачи `feature/PROJ-7`.
AC-6. `new --ref tracker:PROJ-7x` при том же `ref_pattern` — отказ, задача не заведена.
AC-7. Ветка `feature/PROJ-7` уже на сервере (подменённый `ls-remote`) или у задачи проекта в `done` — `new` отказывает, задача не заведена; сбой `ls-remote` — отказ с причиной «имя ветки не проверено».
AC-8. Часть деления с той же ссылкой, что у существующей задачи проекта (ветка занята), — отказ деления с причиной.
AC-9. При шаблоне по умолчанию `new` не вызывает `ls-remote`.
AC-10. Поиск веток пульта (`coldstart`) при `branch_template: feature/{ref}` находит ветки по шаблону записи, а не по префиксу `task/`.
AC-11. Белый список (запись с `merge_gate: target-human`): отправка в `feature/PROJ-8` (ветка чужой задачи), в `main`, удаление своей ветки, тег — отказ до вызова git (шпион `subprocess.run` не вызван) и запись журнала с причиной.
AC-12. Белый список (та же запись): отправка своей ветки задачи и `refs/artifacts/<id>` проходит; вызов отправки несёт `-c core.hooksPath=<каталог пульта>` с хуком `pre-push`.
AC-13. Проект с `merge_gate: operator` и `branch_template: feature/{ref}`: отправка в `base` и удаление ветки своей задачи не отказываются белым списком.
AC-14. Перезапись своей ветки после сжатия/перебазирования несёт `--force-with-lease=refs/heads/<ветка>:<sha последней своей отправки из журнала>`; первая отправка — без перезаписи.
AC-15. Голова ветки на сервере отличается от последней своей отправки — эскалация, отправки нет.
AC-16. Сжатие и `rebase` на фикстурном репозитории: после перехода в `verifying` в ветке задачи один коммит от `origin/<base>` с сообщением по `commit_template`, автором и коммиттером `commit_author` и строкой `Co-authored-by` из `co_author`; ветка лежит поверх `origin/<base>`, `base` не изменён.
AC-17. Конфликт перебазирования на входе в `verifying` — возврат в `in_dev` тем же путём, что конфликт подтяжки сейчас.
AC-18. Для записи с `commit_author` окружение роли несёт `GIT_AUTHOR_*`/`GIT_COMMITTER_*` этого автора, коммиты пульта (чекпоинт, документ в `refs/artifacts/<id>`) — того же автора и строку `Co-authored-by`.
AC-19. Без адаптера `forge.token_user` сверка автора пропускается с записью журнала «сверка автора — после адаптера».
AC-20. При `freshness: rebase` подтяжка перед шагом разработчика и `pull-main` выполняются прежним `merge`.
AC-21. Артель и проект с полями по умолчанию: существующие тесты `new`, подтяжки, отправок, `coldstart`, `cleanup` зелёные без правки, кроме перечисленных в разделе «Меняемое поведение» SPEC части.

## Оценка объёма и деление
Сработавшие сигналы: файлов зоны ≥ 5 (15), критериев приёмки ≥ 10 (21),
`budget_usd` ≥ $30 (70). По калибровке (8+ файлов, >15 критериев) — ~$85
либо деление.

Решение — **нарезка на две части** (ANSWER-1, ответ 4) по границе зон:
- Часть 1 (механика): требования 1, 2, 6 — поля записи и их проверка, имя
  ветки по шаблону, проверка занятости и поиск веток, белый список и хук
  (`targets.py`, `catalog.py`, `coldstart.py`, `gitcmd.py`). Мержима одна:
  поля по умолчанию и `merge_gate: operator` держат прежнее поведение, новые
  поля без исполнителей части 2 только объявлены и проверены.
- Часть 2 (после части 1): требования 3–5 — автор/соавтор, сжатие,
  `rebase`, перезапись с `--force-with-lease` (`runner.py`, `checkpoint.py`,
  `artifact_branch.py`, `fsm_advance.py`, `pull.py`, `fsm.py`,
  `github_adapter.py`, `pull_main.py`, `amend.py`, `snapshot.py`). Опирается
  на поля записи и единую точку отправки части 1.

Части разделимы по зонам, атомарной смены механики между ними нет.
Параллельная А1 (01M5W670PHF08VPZWDRM5BY56W) держит `github_adapter.py`:
часть 2 ждёт её зону очередью зон (ANSWER-1, ответ 3), не зависимостью
мержа.

## Деление

### GitLab Б1.1: поля записи, ветка по шаблону, единая точка отправки с белым списком

Зоны: orchestrator/targets.py, orchestrator/catalog.py, orchestrator/coldstart.py, orchestrator/gitcmd.py, tests/
Порядок: после 01M5W27CY7K7NR9347NKD8F0NX
Рамка: $40

Часть 1 деления задачи 01M5W67E0AYGKF03SEM6E2AQX2 (ADR-0029 п. 4–6, 11, 13; решения Оператора — ANSWER-1.md родителя, 26.10.2026).

Факты: имя ветки задачи строится только в `orchestrator/catalog.py:912` (`f"task/{task_id.lower()}-{slugify(title)}"`); поиск веток пульта по префиксу — только `orchestrator/coldstart.py:59` (`gitcmd.list_branches("task/", …)`). Внешние ссылки задачи — `new --ref <система>:<ключ>`, поля `policy.ref_systems`, `policy.ref_required` (`targets.py`, `catalog.py:558-604`); при делении ссылки копируются частям (`catalog.py:1030-1033`). Все отправки на сервер идут через `gitcmd.in_repo`/`repo_context.git` → `gitcmd` (`gitcmd.py:37` `HOSTING_SUBCOMMANDS`, `gitcmd.py:~95-118` определяет проект и токен хостинга). Токен Developer подключаемого проекта может отправлять в любые незащищённые ветки — защита только кодом пульта.

Требуется:
1. Поля записи (`targets.py`, проверка при загрузке, значения по умолчанию — нынешнее поведение; отказ загрузки называет имя поля): `policy.branch_template` (по умолчанию `task/{id}-{slug}`, подстановки `{id}`, `{slug}`, `{ref}`; `{ref}` — ключ ссылки системы `policy.ref_required`; шаблон с `{ref}` без `ref_required` — отказ); `policy.ref_pattern` (регулярное выражение ключа, полное совпадение); `policy.freshness` `merge` (по умолчанию) | `rebase`; `policy.squash_before_mr` (по умолчанию `false`); `policy.commit_template` (по умолчанию `{id}: {text}`, подстановки `{id}`, `{ref}`, `{text}`; отличный от умолчания без `squash_before_mr: true` — отказ); `machine.commit_author` (имя и email) и `policy.co_author` (строка `Co-authored-by: …`) — необязательны; `policy.push_options` (список, по умолчанию пуст; отказ на `ci.skip` и на переменные из `policy.push_options_forbidden`); `policy.ci_required_jobs` (список, по умолчанию пуст); `policy.mr_assignee`, `policy.draft_mr` (по умолчанию `true`), `policy.max_in_flight` — только объявление и проверка. Поля `freshness`, `squash_before_mr`, `commit_template`, `commit_author`, `co_author` исполняет часть 2.
2. Ветка задачи: `new` строит имя по `branch_template`; ключ не по `ref_pattern` — отказ до заведения задачи. Только когда `branch_template` отличен от умолчания (или без `{id}`): `new` и деление отказывают, если ветка с этим именем уже есть на сервере (`ls-remote`) или у любой задачи проекта в любом состоянии (БД); сбой `ls-remote` — отказ с причиной «имя ветки не проверено». У артели и проектов с полями по умолчанию сетевого вызова нет. Поиск веток пульта (`coldstart` и др.) — по шаблону записи, а не по префиксу `task/`.
3. Единая точка отправки с белым списком (`gitcmd`): только для проекта с `merge_gate`, отличным от `operator` (ADR-0029 п. 13), любая отправка на сервер проверяется до вызова git: разрешены только ветка задачи по шаблону (сверка имени с задачей в БД) и `refs/artifacts/*`; отправка в `base`, удаление веток (`--delete`, `:<ref>`), теги, `refs/heads/*` вне шаблона — отказ с причиной и записью журнала. Каталог хуков — в самом вызове (`-c core.hooksPath=<каталог пульта вне зон записи ролей>`) с хуком `pre-push` тех же правил. У проекта `operator` (в том числе с нестандартным `branch_template`), у артели и проектов с полями по умолчанию отправки прежние — мерж и уборка пульта не меняются.

Критерии приёмки:
- проверка записи: шаблон с `{ref}` без `ref_required`, `commit_template` без сжатия, `push_options` с `ci.skip` или запрещённой переменной — отказ загрузки с именем поля; запись без новых полей — значения по умолчанию;
- `new --ref tracker:PROJ-7` при `branch_template: feature/{ref}`, `ref_pattern: PROJ-\d+` — ветка `feature/PROJ-7`; `--ref tracker:PROJ-7x` — отказ, задачи нет; ветка `feature/PROJ-7` уже на сервере (подменённый `ls-remote`) или у задачи проекта в `done` — отказ; сбой `ls-remote` — отказ «имя ветки не проверено»; часть деления с той же ссылкой — отказ деления с причиной; при шаблоне по умолчанию `ls-remote` не вызывается;
- `coldstart` при нестандартном шаблоне находит ветки по шаблону;
- белый список (запись с `merge_gate: target-human` в тесте; живого такого проекта до Б2 нет): отправка в `feature/PROJ-8` (чужая задача), в `main`, удаление своей ветки, тег — отказ до вызова git (шпион `subprocess.run` не вызван), запись журнала; отправка своей ветки и `refs/artifacts/<id>` — проходит, с `core.hooksPath` в вызове;
- проект `operator` с `branch_template: feature/{ref}`: отправка в `base` и удаление своей ветки не отказываются;
- артель и проект с полями по умолчанию: существующие тесты `new`, отправок, `coldstart`, `cleanup` зелёные без правки, кроме перечисленных в «Меняемое поведение» (ожидается `tests/test_coldstart.py` — поиск веток по шаблону; правка — по мандату Оператора 26.10 на тесты, которые меняет ADR-0029, без ослабления, через гейт SPEC; иное — эскалация).

Только чтение: `orchestrator/config.py` и `orchestrator/doctor/` (держит А1; константы — в модулях задачи), `orchestrator/forge.py`, `orchestrator/gitlab_adapter.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/cleanup.py`, `docs/adr/0029-external-delivery-via-mr.md`.

Не входит: исполнение `freshness`, сжатия, шаблона коммита, автора и перезаписи (часть 2); строки `doctor` — хук, шаблон ветки против правила `workflow`, показ `push_options`, сверка контрольной суммы хука (Б2); исполнение `mr_assignee`, `draft_mr`, `max_in_flight` (Б2); чтение `ci_required_jobs` (адаптер А1); черновик MR, `awaiting_human`, `mr-sync`, `kill`/`cleanup` для `target-human` (Б2).

### GitLab Б1.2: автор и соавтор, сжатие и перебазирование на входе в verifying, перезапись своей ветки

Зоны: orchestrator/runner.py, orchestrator/checkpoint.py, orchestrator/artifact_branch.py, orchestrator/fsm_advance.py, orchestrator/pull.py, orchestrator/fsm.py, orchestrator/github_adapter.py, orchestrator/pull_main.py, orchestrator/amend.py, orchestrator/snapshot.py, tests/
Порядок: после части 1
Рамка: $45

Часть 2 деления задачи 01M5W67E0AYGKF03SEM6E2AQX2 (ADR-0029 п. 1, 4–6; решения Оператора — ANSWER-1.md родителя, 26.10.2026). Опирается на поля записи и единую точку отправки части 1.

Факты: автор коммитов роли — окружение роли `GIT_AUTHOR_*` (`orchestrator/runner.role_env`; проверка — `orchestrator/doctor/preflight.py:69-88`); коммиты пульта с `fixation.FIXATION_AUTHOR_*` — `checkpoint.py:1882`, `amend.py:799` (кодовая ветка, долгоживущие тесты), `snapshot.py:272` (коммит закрытия в `refs/artifacts`); документы задачи — `artifact_branch.py:291`. Подтяжка перед шагом разработчика — `runner._pull_before_developer_step` (`runner.py:620`). Переход `in_dev → verifying` — `fsm_advance.in_dev` → `fsm._pull_main_or_escalate` (`fsm.py:236`) → `pull.evaluate` (`pull.py:762`); `git merge --no-ff` — `pull._run_merge` (`pull.py:535`), откат конфликта — `pull._handle_merge_failure` (`pull.py:543`). Отправка ветки задачи на входе в `verifying` у `forge: github` — `github_adapter.py:166`, `:241` (`push -u origin <ветка>`).

Требуется:
1. Автор и соавтор: для записи с `commit_author` окружение роли и коммиты пульта в ветке задачи и в `refs/artifacts/<id>` получают этого автора (и коммиттера). `co_author` дописывается строкой в сообщение каждого коммита, который пишет пульт (чекпоинты, фиксация, документы, сжатый коммит), — не настройкой, которую может сменить роль; коммиты роли без сжатия не переписываются. До первой отправки — сверка `commit_author` с владельцем токена через адаптер (`forge.token_user`, А1); пока адаптера нет — шаг пропускается с записью журнала «сверка автора — после адаптера».
2. Подготовка ветки на входе в `verifying` (каждый переход `in_dev → verifying`, ADR-0015 п. 2): при `squash_before_mr: true` коммиты задачи от точки ответвления сжимаются в один с сообщением по `commit_template` (`{text}` — название задачи); затем подтяжка методом `freshness` (`merge` — как сейчас, `rebase` — перебазирование ветки задачи на `origin/<base>` только в рабочей копии задачи, `base` не меняется). Конфликт — возврат в `in_dev` тем же путём, что конфликт подтяжки сейчас. `freshness` действует только на этом переходе: подтяжка перед шагом разработчика и `pull-main` — прежний `merge`. Без новых полей поведение перехода не меняется.
3. Перезапись своей ветки (после сжатия/перебазирования) — только `push --force-with-lease=refs/heads/<ветка>:<sha последней своей отправки из журнала>`; первая отправка — без перезаписи. Голова на сервере не совпала с последней своей отправкой — чужой коммит: эскалация, без перезаписи. В `github_adapter.py` меняется только место отправки ветки; поведение черновика MR не меняется.

Критерии приёмки:
- перезапись: `--force-with-lease` несёт sha последней своей отправки; первая отправка — без перезаписи; голова сервера другая — эскалация, отправки нет;
- сжатие и `rebase` на фикстурном репозитории: после перехода в `verifying` в ветке один коммит с сообщением по шаблону и автором `commit_author`, строка `Co-authored-by`, ветка поверх `origin/<base>`, `base` не изменён; конфликт перебазирования — возврат в `in_dev`;
- запись с `commit_author`: окружение роли и коммиты пульта (чекпоинт, документ в `refs/artifacts/<id>`) несут этого автора и строку `Co-authored-by`; без адаптера — запись журнала «сверка автора — после адаптера»;
- `freshness: rebase`: подтяжка перед шагом разработчика и `pull-main` — прежний `merge`;
- артель и проект с полями по умолчанию: существующие тесты подтяжки, отправок, `cleanup` зелёные без правки, кроме перечисленных в «Меняемое поведение» (правка — по мандату Оператора 26.10 на тесты, которые меняет ADR-0029, без ослабления, через гейт SPEC; иное — эскалация).

Зона `orchestrator/github_adapter.py` занята параллельной А1 (01M5W670PHF08VPZWDRM5BY56W, «только вынос в интерфейс») — часть ждёт её очередью зон.

Только чтение: `orchestrator/config.py` и `orchestrator/doctor/` (держит А1; константы — в модулях задачи), `orchestrator/forge.py`, `orchestrator/gitlab_adapter.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/cleanup.py`, `docs/adr/0029-external-delivery-via-mr.md`, `docs/adr/0015-ci-before-review.md`.

Не входит: поля записи, имя ветки и белый список отправок (часть 1); открытие и снятие черновика MR, `awaiting_human`, `mr-sync`, `kill`/`cleanup` для `target-human` (Б2); `full_suite` и `verify` (В1, В2); адаптер (А1); переписывание коммитов роли без сжатия; `freshness` вне перехода `in_dev → verifying`.

## Не входит

- Строки `doctor` (хук, шаблон ветки против правила `workflow`, показ `push_options`) и сверка контрольной суммы хука — шаг Б2 (зону `orchestrator/doctor/` держит А1).
- Открытие и снятие черновика MR, `awaiting_human`, `mr-sync`, поведение `kill` и `cleanup` для `target-human`, исполнение `mr_assignee`, `draft_mr`, `max_in_flight` — Б2.
- `full_suite` и `verify` — В1, В2; адаптер `forge`/`gitlab_adapter` и чтение `ci_required_jobs` — А1.
- Правка `orchestrator/config.py`, `orchestrator/doctor/`, `orchestrator/fsm_merge_gate.py`, `orchestrator/cleanup.py` — только чтение по ТЗ.
- Белый список для проектов с `merge_gate: operator` (ANSWER-1, ответ 1); `freshness` вне перехода `in_dev → verifying` (ответ 5); переписывание коммитов роли без сжатия (ответ 6).
- Полный зелёный `tests/`, зелёный CI ветки, неизменность защищённых путей — их держит пульт.

## Материалы

- `docs/adr/0029-external-delivery-via-mr.md` п. 1, 4–6, 11, 13; `docs/adr/0015-ci-before-review.md` п. 2.
- `tasks/01M5W67E0AYGKF03SEM6E2AQX2/ANSWER-1.md` — решения Оператора по батчу.
- Зоны сверх перечня ТЗ: `pull.py`, `fsm.py`, `github_adapter.py` — по ANSWER-1 (ответ 3); `amend.py` (`amend.py:799`) и `snapshot.py` (`snapshot.py:272`) — коммиты пульта с автором фиксации в ветке задачи и в `refs/artifacts/<id>`, прямое следствие требования 3 (ТЗ, факт 3 называет `amend.py:799`).
