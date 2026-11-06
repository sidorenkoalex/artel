---
task: 01M6RJDRR027G50D81W8T3T8AK
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Шаблон заголовка MR задачи внешнего проекта: policy.mr_title_template

# Шаблон заголовка MR задачи внешнего проекта: policy.mr_title_template

## Факты

1. Заголовок MR задачи внешнего проекта собирается без шаблона: `f"{task_id}: {t['title'] or task_id}"` — `orchestrator/github_adapter.py:441` (черновой MR через `forge.open_mr`, в том числе для GitLab) и `:186` (`gh pr create`). Адаптер GitLab добавляет префикс черновика `Draft: ` (`orchestrator/gitlab_adapter.py:541-548`), снятие черновика убирает его (`:554-562`); правка заголовка через `PUT` проходит `_title_refusal` (`:178-190`): разрешено только добавление или снятие префикса черновика.
2. Соглашения проектов на хостинге часто требуют заголовок MR с ключом задачи трекера, например `<ключ>: <описание>`. Ключ задачи уже есть у пульта: ссылка системы `policy.ref_required` (`orchestrator/targets.py:373-378`), из неё `new` подставляет `{ref}` в имя ветки (`catalog._branch_ref_key`, `orchestrator/catalog.py:642-662`); ссылки задачи хранятся в `external_refs` (`orchestrator/store.py:751`).
3. Поля доставки через MR раздела `policy` с подстановками и их проверка — `orchestrator/targets.py`: `DEFAULT_BRANCH_TEMPLATE`, `BRANCH_PLACEHOLDERS`, `DEFAULT_COMMIT_TEMPLATE`, `COMMIT_PLACEHOLDERS` (`:416-419`), `DELIVERY_POLICY_FIELDS` (`:424-427`), `LOCAL_FIELDS` (`:395-410`), `_check_delivery` (`:664-720`; образец — `branch_template`: подстановки только из перечня, `{ref}` — только при `policy.ref_required`).

## Требуется

1. Новое необязательное поле `policy.mr_title_template` локального слоя: непустая строка с подстановками только из перечня `{id}`, `{ref}`, `{title}`; `{ref}` — только при заданном `policy.ref_required`. Иное — отказ загрузки записи с именем поля (как у `branch_template`). Умолчание — `{id}: {title}`: без поля заголовок прежний побайтно.
2. Подстановки: `{id}` — id задачи как сейчас (прежний регистр), `{title}` — название задачи (`t['title']`, а при пустом — id задачи, как сейчас), `{ref}` — ключ ссылки системы `policy.ref_required` этой задачи (тот же, что в имени ветки).
3. Заголовок по шаблону используется в обоих местах факта 1 (`forge.open_mr` и `gh pr create`); префикс черновика и его снятие, `_title_refusal` — без изменений.
4. Шаблон с `{ref}`, а ссылки системы `ref_required` у задачи нет (задача заведена до записи поля) — MR открывается с заголовком по умолчанию `{id}: {title}` и записью журнала с причиной; задача не останавливается.
5. Поле пишется командой `target-set <проект> policy.mr_title_template <значение>` (скалярное поле раздела `policy`, путь уже поддержан формой значения); справка `target-set` не меняется.

## Критерии приёмки

- Given вымышленная запись GitLab с `ref_required: tracker`, `mr_title_template: "{ref}: {title}"` и задача со ссылкой `tracker:ABC-12`, When открывается черновой MR (подменённый `forge.open_mr` / транспорт адаптера), Then заголовок `Draft: ABC-12: <название задачи>`; после снятия черновика — `ABC-12: <название задачи>`;
- Given запись без `mr_title_template`, Then заголовок прежний `<id>: <название>` побайтно (и при пустом названии — `<id>: <id>`);
- Given шаблон с неизвестной подстановкой `{foo}`, пустой строкой или `{ref}` без `ref_required`, When загрузка записи, Then отказ с именем поля `policy.mr_title_template`;
- Given шаблон с `{ref}` и задача без ссылки системы `ref_required`, Then MR открыт с заголовком по умолчанию, в журнале запись с причиной;
- Given `target-set <проект> policy.mr_title_template "{ref}: {title}"`, Then поле записано в локальный слой с копией прежнего файла; недопустимое значение — отказ, слой побайтно прежний;
- путь `gh pr create` (`github_adapter.py:186`) берёт тот же шаблон; существующие тесты — зелёные без правки.

Безопасность тестов: вымышленные проекты и ключи, локальный слой — во временной песочнице (`tests.sandbox`), хостинг — подмена `forge.open_mr`/`gitlab_adapter.request`/`ci.gh`, без сети; никогда — настоящий `.artel/targets.yaml`.

Существующие тесты: правка не должна сделать красным ни один существующий тест; если краснеет — эскалация с именем теста, без правки.

Зоны: `orchestrator/targets.py` (поле, перечень подстановок, проверка в `_check_delivery`), `orchestrator/github_adapter.py` (сборка заголовка в двух местах), `docs/codebase-map.md` (только генерацией), `tests/` (долгоживущие файлы задачи).

Только чтение: `orchestrator/gitlab_adapter.py`, `orchestrator/forge.py`, `orchestrator/catalog.py`, `orchestrator/store.py`, `orchestrator/projects.py`, `tests/sandbox.py`.

Не входит:
- шаблон описания MR;
- переименование заголовка уже открытых MR;
- шаблон сообщений коммитов без squash;
- правка настоящего локального слоя `.artel/targets.yaml` в тестах и при разработке.

Приоритет 2.

Рамка: $30. Набор моделей — по умолчанию.
