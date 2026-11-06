---
task: 01M6RJDRR027G50D81W8T3T8AK
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/targets.py, orchestrator/github_adapter.py, docs/codebase-map.md, tests/
budget_usd: 28
---

# SPEC: Шаблон заголовка MR задачи внешнего проекта: policy.mr_title_template

## Контекст
Заголовок MR задачи внешнего проекта сейчас собирается жёстко:
`f"{task_id}: {t['title'] or task_id}"` — `orchestrator/github_adapter.py:186`
(`gh pr create`) и `:441` (черновой MR через `forge.open_mr`, в том числе для
GitLab). Соглашения проектов на хостинге часто требуют заголовок с ключом
задачи трекера (`<ключ>: <описание>`). Ключ у пульта уже есть — ссылка системы
`policy.ref_required` (`orchestrator/targets.py:377`), из неё `new` подставляет
`{ref}` в имя ветки (`catalog._branch_ref_key`). Задача — поле шаблона
заголовка в разделе `policy` локального слоя по образцу `branch_template`.

## Требования

1. Новое необязательное поле `policy.mr_title_template` локального слоя
   (`orchestrator/targets.py`, `LOCAL_FIELDS["policy"]`, поля доставки):
   непустая строка с подстановками только из перечня `{id}`, `{ref}`,
   `{title}`; `{ref}` допустима только при заданном `policy.ref_required`.
   Иное значение (неизвестная подстановка, пустая строка, `{ref}` без
   `ref_required`) — отказ загрузки записи с именем поля
   `policy.mr_title_template`, как у `branch_template` (`_check_delivery`).
2. Умолчание шаблона — `{id}: {title}`: запись без поля даёт заголовок,
   побайтно совпадающий с прежним.
3. Подстановки: `{id}` — id задачи в том же виде (регистре), что сейчас
   стоит в заголовке; `{title}` — название задачи (`t['title']`), а при пустом
   названии — id задачи, как сейчас; `{ref}` — ключ ссылки системы
   `policy.ref_required` этой задачи — тот же, что подставляется в имя ветки.
4. Заголовок по шаблону используется в обоих местах сборки заголовка:
   черновой MR через `forge.open_mr` (`github_adapter.py:441`) и
   `gh pr create` (`github_adapter.py:186`). Префикс черновика `Draft: `
   адаптера GitLab, его снятие и проверка правки заголовка `_title_refusal`
   (`orchestrator/gitlab_adapter.py`) не меняются.
5. Шаблон содержит `{ref}`, а ссылки системы `ref_required` у задачи нет
   (задача заведена до записи поля) — MR открывается с заголовком по
   умолчанию `{id}: {title}`, в журнал задачи пишется запись с причиной;
   задача не останавливается.
6. Поле пишется существующей командой
   `target-set <проект> policy.mr_title_template <значение>` как скалярное
   поле раздела `policy`; недопустимое значение отклоняется той же проверкой
   записи (требование 1), локальный слой остаётся побайтно прежним. Справка
   `target-set` не меняется.

## Критерии приёмки

AC-1. Given вымышленная запись GitLab с `policy.ref_required: tracker`,
`policy.mr_title_template: "{ref}: {title}"` и задача со ссылкой
`tracker:ABC-12`, When открывается черновой MR (подменённый `forge.open_mr` /
транспорт адаптера `gitlab_adapter.request`), Then заголовок MR —
`Draft: ABC-12: <название задачи>`; после снятия черновика —
`ABC-12: <название задачи>`.

AC-2. Given запись без `policy.mr_title_template`, When открывается MR задачи,
Then заголовок побайтно прежний `<id>: <название>`, а при пустом названии
задачи — `<id>: <id>`.

AC-3. Given значение `policy.mr_title_template` с неизвестной подстановкой
`{foo}`, When загрузка записи, Then отказ, текст которого называет поле
`policy.mr_title_template`.

AC-4. Given значение `policy.mr_title_template` — пустая строка, When загрузка
записи, Then отказ, текст которого называет поле `policy.mr_title_template`.

AC-5. Given значение `policy.mr_title_template` с `{ref}` в записи без
`policy.ref_required`, When загрузка записи, Then отказ, текст которого
называет поле `policy.mr_title_template`.

AC-6. Given запись с `policy.ref_required` и шаблоном с `{ref}` и задача без
ссылки системы `ref_required`, When открывается MR, Then MR открыт с
заголовком по умолчанию `<id>: <название>`, задача не остановлена, в журнале
задачи запись с причиной.

AC-7. Given `target-set <проект> policy.mr_title_template "{ref}: {title}"`
для вымышленного проекта с `ref_required` в песочнице, Then поле записано в
локальный слой и рядом сохранена копия прежнего файла.

AC-8. Given `target-set <проект> policy.mr_title_template` с недопустимым
значением (например `{foo}`), Then отказ команды, файл локального слоя
побайтно прежний.

AC-9. Given запись с `policy.mr_title_template: "{ref}: {title}"` и задача со
ссылкой `tracker:ABC-12`, When MR открывается путём `gh pr create`
(подменённый `ci.gh`), Then переданный заголовок — `ABC-12: <название задачи>`.

Безопасность тестов (из ТЗ): вымышленные проекты и ключи; локальный слой —
во временной песочнице (`tests.sandbox`); хостинг — подмена
`forge.open_mr`/`gitlab_adapter.request`/`ci.gh`, без сети; никогда —
настоящий `.artel/targets.yaml`.

## Оценка объёма и деление

Сработавшие сигналы (guard): число затрагиваемых модулей/файлов зоны
(зона `tests/` — каталог), прогноз диффа не дан.

Прогноз диффа: 12 КиБ

Обоснование монолита: правка кода — две точки (`orchestrator/targets.py` —
поле и проверка; `orchestrator/github_adapter.py` — сборка заголовка в двух
местах), остальное — тесты задачи и регенерация карты. Часть «поле без
использования» мержима, но бесполезна: поле принимается загрузкой и
`target-set`, а заголовок от него не меняется — молчаливо неработающая
настройка у Оператора; часть «сборка по шаблону» без поля не имеет входа.
Объём одной задачи укладывается в класс «до 10 критериев, до 4 файлов»;
решение о монолите — за Оператором на гейте SPEC.

## Не входит

- Шаблон описания MR.
- Переименование заголовка уже открытых MR.
- Шаблон сообщений коммитов без squash.
- Правка настоящего локального слоя `.artel/targets.yaml` в тестах и при
  разработке.
- Правка `orchestrator/gitlab_adapter.py`, `orchestrator/forge.py`,
  `orchestrator/catalog.py`, `orchestrator/store.py`,
  `orchestrator/projects.py`, `tests/sandbox.py` — по ТЗ только чтение.
- Изменение справки `target-set`.
- Зелёный полный набор `tests/` без правки существующих тестов — её держит
  пульт; покраснел существующий тест — эскалация с именем теста, без правки.
- `docs/codebase-map.md` — только регенерацией `scripts/codebase_map.py`.

## Материалы

- ТЗ: `tasks/01M6RJDRR027G50D81W8T3T8AK/TZ.md`.
- Образец проверки: `orchestrator/targets.py` — `BRANCH_PLACEHOLDERS`,
  `COMMIT_PLACEHOLDERS` (`:417-419`), `DELIVERY_POLICY_FIELDS` (`:424`),
  `LOCAL_FIELDS` (`:391`), `_check_delivery`.
- Ключ ссылки в имени ветки: `catalog._branch_ref_key`
  (`orchestrator/catalog.py`); ссылки задачи — `store.external_refs`.
- Допустимые имена полей `target-set`: `orchestrator/projects.py:780`
  (`targets.LOCAL_FIELDS[section]`).
