---
task: 01M5WDB7F14SQ30QVWJY2XYBG2
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/targets.py, orchestrator/catalog.py, orchestrator/gitcmd.py, orchestrator/fsm.py, tests/
merge_after: 01M5W27CY7K7NR9347NKD8F0NX
budget_usd: 40
---

# SPEC: GitLab Б1.1 — поля записи, ветка по шаблону, единая точка отправки с журналом и белым списком

## Контекст
Часть 1 деления задачи 01M5W67E0AYGKF03SEM6E2AQX2 (ADR-0029 п. 4–6, 11, 13;
решения Оператора — ANSWER-1.md родителя и два возврата с гейта SPEC
родителя, 26.10.2026). Сейчас имя ветки задачи строится жёстко
(`orchestrator/catalog.py:918`, `f"task/{task_id.lower()}-{slugify(title)}"`,
в `_new_task_row`; при делении — тоже там, до копирования ссылок частям),
части деления заводятся по одной в цикле `fsm._spawn_division_subtasks`
(`orchestrator/fsm.py:1037`), родитель уходит в `killed` после всех частей.
Все отправки на сервер идут через `gitcmd` (`HOSTING_SUBCOMMANDS`,
`orchestrator/gitcmd.py:37`; определение проекта и токена — `gitcmd.py:86-118`,
`_declared_targets` при нечитаемом `targets.yaml` возвращает `{}`), процессы
git запускают пять точек: `git` (`:164`), `carpentry` (`:341`), `read`
(`:413`), `read_env` (`:441`, `Popen`), `read_stream` (`:469`, `Popen`).
Токен Developer подключаемого проекта может отправлять в любые незащищённые
ветки — защита только кодом пульта. Задача вводит поля записи проекта для
доставки через MR, ветку по шаблону и единую точку отправки с журналом
отправленного sha и белым списком для проектов с `merge_gate`, отличным от
`operator`. А0 (`targets.unsupported_reason`) отказывает `new`/`run`/`auto`/
`approve` проекту с `merge_gate: target-human` и `forge: gitlab`, поэтому
сценарии `new` и деления проверяются на записях `forge: github`,
`merge_gate: operator`, а белый список — на уровне `gitcmd`.

## Требования

1. Поля записи проекта (`orchestrator/targets.py`): проверка при загрузке,
   значения по умолчанию — нынешнее поведение, отказ загрузки называет имя
   поля.
   - `policy.branch_template` — по умолчанию `task/{id}-{slug}`, подстановки
     `{id}`, `{slug}`, `{ref}`; `{id}` подставляется в нижнем регистре, как
     сейчас (`catalog.py:918`); `{ref}` — ключ ссылки системы
     `policy.ref_required`; шаблон с `{ref}` без `ref_required` — отказ.
   - `policy.ref_pattern` — регулярное выражение ключа, полное совпадение;
     обязано компилироваться; `ref_pattern` при шаблоне без `{ref}` — отказ
     загрузки.
   - `policy.freshness` — `merge` (по умолчанию) | `rebase`; иное значение —
     отказ; `rebase` без `squash_before_mr: true` — отказ.
   - `policy.squash_before_mr` — по умолчанию `false`.
   - `policy.commit_template` — по умолчанию `{id}: {text}`, подстановки
     `{id}`, `{ref}`, `{text}`; значение, отличное от умолчания, без
     `squash_before_mr: true` — отказ.
   - `machine.commit_author` — необязательно; отображение `{name, email}`,
     оба — непустые строки; иной вид, отсутствующий или пустой `name`/`email`
     — отказ.
   - `policy.co_author` — необязательно; строка, начинающаяся с
     `Co-authored-by: `, иначе отказ.
   - `policy.push_options` — список, по умолчанию пуст; элемент —
     `ci.variable=ИМЯ=значение` или `ИМЯ=значение`, элемент иной формы —
     отказ; отказ на `ci.skip`, на любой элемент `merge_request.*` (создание
     и слияние MR при отправке запрещены всегда, независимо от
     `push_options_forbidden`) и на элемент, чьё `ИМЯ` есть в
     `policy.push_options_forbidden`.
   - `policy.push_options_forbidden` — раздел `policy`, список строк (имена
     переменных), по умолчанию пуст; иной вид — отказ.
   - `policy.ci_required_jobs` — список строк, по умолчанию пуст.
   - `policy.mr_assignee` (непустая строка), `policy.draft_mr` (булево, по
     умолчанию `true`), `policy.max_in_flight` (целое > 0) — только
     объявление и проверка формы.
   Поля `freshness`, `squash_before_mr`, `commit_template`, `commit_author`,
   `co_author` в этой части только объявляются и проверяются — исполняет их
   часть 2.

2. Ветка задачи:
   - `new` строит имя ветки по `branch_template`; `{ref}` — ключ ссылки
     системы `ref_required`. При шаблоне с `{ref}` такая ссылка у `new`
     ровно одна — больше одной — отказ `new`; ключ не по `ref_pattern` —
     отказ до заведения задачи.
   - Только когда `branch_template` отличен от умолчания (или без `{id}`):
     `new` и деление отказывают, если ветка с этим именем уже есть на
     сервере (`ls-remote`) или у любой задачи проекта в любом состоянии,
     включая `killed` и `done` (БД); сбой `ls-remote` — отказ с причиной
     «имя ветки не проверено». У артели и проектов с полями по умолчанию
     сетевого вызова нет.
   - Отказ деления (любой из двух ниже) — в `_division_check`
     (`orchestrator/fsm.py:1403`), до любых записей гейта (журнал заявленных
     изменений, `zones`, `merge_after`, потолок) и до создания эпика
     `approve --as-epic`: частей нет, эпика нет, родитель остаётся на гейте
     SPEC.
   - Деление при шаблоне с `{ref}` — отказ с причиной «ветка по ключу
     трекера: делите задачу в трекере».
   - При шаблоне не по умолчанию без `{ref}` имена всех частей проверяются
     до заведения первой; конфликт хоть одной (сервер, БД) — отказ деления.
     При шаблоне без `{id}` совпадение имён частей между собой — тот же
     отказ.
   - При шаблоне по умолчанию деление прежнее.

3. Единая точка отправки (`orchestrator/gitcmd.py`):
   - (а) после каждой успешной (код 0) отправки ветки задачи (любой проект)
     пишет в журнал задачи запись «ветка отправлена: <sha>» с отправленным
     локальным sha; неудачная отправка и отправка с `--dry-run` записи не
     оставляют.
   - (б) ко всем отправкам ветки задачи проекта добавляет `-o <опция>` на
     каждую строку `policy.push_options`; к `refs/artifacts/*` — нет.
   - (в) белый список — только для проекта с `merge_gate`, отличным от
     `operator` (ADR-0029 п. 13): любая отправка на сервер проверяется до
     вызова git. «Своя ветка» — имя ветки задачи этого проекта из БД в
     любом состоянии, кроме `killed` и `done`, совпавшее с назначением
     refspec. Разрешены только своя ветка, `refs/artifacts/*` и удаление
     `refs/artifacts/<id>` задач этого проекта. Назначение отправки — только
     `origin` клона проекта или URL, равный `url` записи проекта; иное
     назначение — отказ. Флаги `push` — только белым списком: `-u`/
     `--set-upstream`, `-q`, `-o <опция>` (опция `merge_request.*` — отказ),
     `--force-with-lease=<ref>:<sha>`; любой иной флаг — отказ. Отказ также:
     отправка в `base`; в ветку, не являющуюся своей; иные удаления
     (`--delete`, `:<ref>` — в том числе своей ветки); теги; отправка без
     явного refspec; refspec с `+`. Флаги `--tags`, `--follow-tags`,
     `--mirror`, `--all`, `--force`/`-f`, `--dry-run` — вне белого списка,
     то есть отказ. Единственная форма перезаписи —
     `--force-with-lease=<ref>:<sha>`, которую строит сама точка отправки;
     голый `--force-with-lease` и форма без `<sha>` — отказ; `<sha>`
     сверяется с последней записью журнала задачи «ветка отправлена: <sha>»
     — другой sha или нет записи — отказ. Отправка такого проекта идёт с
     `-c push.followTags=false`.
   - Каждый отказ (в) и (г) — с причиной и записью: в журнал задачи, к
     ветке или ссылке которой относится отправка; отправка без своей задачи
     — в журнал задачи, в контексте которой выполняется команда; без задачи
     — запись в `alerts` с источником `branch_push_whitelist`.
   - (г) проверка — в одной внутренней функции, через которую проходят все
     пять точек запуска git в `gitcmd` (`git`, `carpentry`, `read`,
     `read_env`, `read_stream`), либо в каждой из них. Нечитаемая запись
     проекта (`merge_gate` неизвестен) — отказ отправки из клона любого
     внешнего проекта, в том числе проекта, чья запись при читаемом
     `targets.yaml` — `operator`.
   - У проекта `operator` с читаемой записью (в том числе с нестандартным
     `branch_template`), у артели и у проектов с полями по умолчанию
     отправки, кроме (а) и (б), прежние — мерж и уборка пульта не меняются.

## Критерии приёмки

AC-1. Проверка записи: шаблон ветки с `{ref}` без `ref_required`;
`commit_template`, отличный от умолчания, без `squash_before_mr: true`;
`freshness: rebase` без `squash_before_mr: true`; `push_options` с
`ci.skip` — каждый отказ загрузки записи с именем своего поля. При
`push_options_forbidden: [SECRET]` элементы `ci.variable=SECRET=1` и
`SECRET=1` — отказ с именем поля `push_options`, `ci.variable=OTHER=1` —
запись загружается. Элемент `push_options` вне обеих форм (`novalue`, без
`=`) и элемент `merge_request.target=main` при пустом
`push_options_forbidden` — отказ с именем поля `push_options`.
`ref_pattern: PROJ-\d+` при `branch_template` без `{ref}` — отказ загрузки с
именем поля `ref_pattern`.

AC-2. Один параметризованный критерий формы полей: `freshness: squash`,
`ref_pattern: "PROJ-("` (при шаблоне с `{ref}`), `commit_author` без email,
`commit_author` с `name: ""`, `commit_author` строкой `"X <x@y>"`,
`co_author: "Reviewed-by: X"`, `mr_assignee: ""`, `draft_mr: "yes"`,
`max_in_flight: 0`, `ci_required_jobs: build`, `push_options_forbidden: SECRET`
— каждый отказ загрузки с именем своего поля; допустимое значение каждого
поля (для `commit_author` — `{name: X, email: x@y}`) загружается. Запись без
новых полей загружается со значениями по умолчанию (`branch_template`
`task/{id}-{slug}`, `freshness` `merge`, `squash_before_mr` `false`,
`commit_template` `{id}: {text}`, `push_options`, `push_options_forbidden` и
`ci_required_jobs` пусты, `draft_mr` `true`).

AC-3. `new --ref tracker:PROJ-7` при `branch_template: feature/{ref}`,
`ref_required: tracker`, `ref_pattern: PROJ-\d+` — задача заведена с веткой
`feature/PROJ-7`; `--ref tracker:PROJ-7x` — отказ, задачи нет;
`--ref tracker:PROJ-7 --ref tracker:PROJ-9` — отказ, задачи нет.

AC-4. При том же шаблоне: ветка `feature/PROJ-7` уже на сервере
(подменённый `ls-remote`), у задачи проекта в `done` или у задачи проекта в
`killed` — каждое отказ `new`, задачи нет; сбой `ls-remote` — отказ с
причиной «имя ветки не проверено»; при шаблоне по умолчанию `ls-remote` не
вызывается ни в `new`, ни в делении.

AC-5. Каждый из трёх случаев деления — отказ `approve` гейта SPEC, после
которого ни одна часть не заведена (ни строки БД, ни ссылки документов),
эпика нет (в том числе при `approve --as-epic`), у родителя не изменились
`zones`, `merge_after` и потолок, родитель в `spec_gate`: (1) шаблон
`feature/{ref}` — причина «ветка по ключу трекера: делите задачу в трекере»;
(2) шаблон `feature/{slug}`, имя второй части занято (сервер или БД);
(3) шаблон `feature/{slug}`, две части с одинаковым slug.

AC-6. Белый список (запись с `merge_gate: target-human` в тесте): отправка в
`feature/PROJ-8`, которой нет среди веток задач проекта; в ветку задачи в
`done`/`killed`; в `main`; удаление своей ветки (`--delete` и `:<ref>`);
удаление `refs/artifacts/<id>` задачи, которой нет в БД проекта; тег;
отправка без явного refspec; своя ветка с `--tags`, `--follow-tags`,
`--mirror`, `--all`, `--force`, `-f`, `--dry-run`, флагом вне белого списка
(`--prune`, `--receive-pack=x`) или `+<ветка>`; своя ветка с
`-o merge_request.create`; своя ветка по URL, отличному от `url` записи;
голый `--force-with-lease` и `--force-with-lease=refs/heads/<ветка>` без
sha; перезапись `--force-with-lease=refs/heads/<ветка>:<sha>` с sha,
отличным от последней записи «ветка отправлена», или без такой записи —
каждое отказ до вызова git (шпион `subprocess.run` не вызван) с причиной;
отказ, относящийся к задаче проекта, оставляет запись с причиной в её
журнале, отказ без своей задачи при команде вне контекста задачи — запись
`alerts` с источником `branch_push_whitelist`. Отправка ветки живой задачи
проекта (в `origin` клона и по URL, равному `url` записи, с `-u`, `-q`,
`-o X`), её перезапись `--force-with-lease=refs/heads/<ветка>:<sha>` с sha
последней записи «ветка отправлена», отправка `refs/artifacts/<id>` и
удаление `refs/artifacts/<id>` задачи проекта — проходят, вызов несёт
`-c push.followTags=false`.

AC-7. Для записи `target-human` отправка в `main` через каждую из точек
`git`, `carpentry`, `read`, `read_env`, `read_stream` — отказ до запуска
процесса (шпионы `subprocess.run` и `subprocess.Popen` не вызваны).
Нечитаемая запись (испорченный `targets.yaml`) — отправка из клона
внешнего проекта отказана до запуска процесса, в том числе из клона
проекта, чья запись в исправном `targets.yaml` — `merge_gate: operator`.

AC-8. Проект `merge_gate: operator` с `branch_template: feature/{ref}`:
отправка в `base` и удаление своей ветки не отказываются.

AC-9. Успешная отправка ветки задачи (запись по умолчанию и `target-human`)
оставляет в журнале задачи «ветка отправлена: <sha>» с отправленным
локальным sha; отправка с ненулевым кодом и отправка с `--dry-run` (запись
по умолчанию, код 0) — не оставляют. При
`push_options: [X, Y]` отправка ветки задачи несёт `-o X -o Y`; отправка
`refs/artifacts/<id>` и отправка при пустом списке — без `-o`.

## Оценка объёма и деление
Сигналов нет: зона — 4 файла (`tests/` — общая зона), 9 критериев,
`budget_usd` 40 ниже порога. Задача сама — часть 1 деления родителя
01M5W67E0AYGKF03SEM6E2AQX2.

## Не входит

- Исполнение `freshness`, сжатия, шаблона коммита, автора коммита, трейлера
  пульта и перезаписи — часть 2.
- Хук `pre-push` и строки `doctor` (хук, шаблон ветки против правила
  `workflow`, показ `push_options`, сверка контрольной суммы хука) — Б2.
- Поиск веток пульта по шаблону (`coldstart` сканирует ветки только артели
  ради номера Tnnn, у артели шаблон по умолчанию) и правка
  `scripts/plan_appendix_ci.py`.
- Исполнение `mr_assignee`, `draft_mr`, `max_in_flight` — Б2; чтение
  `ci_required_jobs` — адаптер А1.
- Черновик MR, `awaiting_human`, `mr-sync`, `kill`/`cleanup` для
  `target-human` — Б2.
- Деление задачи с шаблоном `{ref}` средствами пульта (делится в трекере).
- Правка файлов только для чтения: `orchestrator/config.py` и
  `orchestrator/doctor/` (держит А1; константы задачи — в модулях задачи),
  `orchestrator/coldstart.py`, `orchestrator/artifact_cleanup.py`,
  `scripts/plan_appendix_ci.py`, `orchestrator/forge.py`,
  `orchestrator/gitlab_adapter.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/cleanup.py`, `docs/adr/0029-external-delivery-via-mr.md`.
- Зелёность существующих тестов `new`, деления, отправок, `cleanup` для
  артели и проектов с полями по умолчанию — её держит пульт (полный набор
  `tests/`). Правка существующих тестов этим SPEC не заказана (раздела
  «Меняемое поведение» нет); понадобится — только эскалацией к Оператору
  (мандат Оператора 26.10: разделом «Меняемое поведение» и матрицей
  неослабления этой части).

## Материалы
- `tasks/01M5WDB7F14SQ30QVWJY2XYBG2/TZ.md`; родитель
  01M5W67E0AYGKF03SEM6E2AQX2 (ANSWER-1.md, возвраты с гейта SPEC 26.10.2026).
- `docs/adr/0029-external-delivery-via-mr.md` п. 4–6, 11, 13.
- Решения гейта SPEC этой части (возврат 26.10.2026, 12 пунктов, права
  волны G): внесены в требования 1–3 и AC-1, AC-2, AC-4–AC-7, AC-9;
  `SPEC-AUDIT.md` (verdict: concerns) — их основание.
- Зависимость мержа 01M5W27CY7K7NR9347NKD8F0NX (А0, `targets.unsupported_reason`)
  — из строки ТЗ «Порядок: после …».
