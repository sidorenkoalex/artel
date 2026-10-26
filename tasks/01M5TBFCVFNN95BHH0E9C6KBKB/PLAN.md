---
task: 01M5TBFCVFNN95BHH0E9C6KBKB
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Эпики Э3 — черновики и решения эпика, копия эпика в `refs/artifacts/epic-<id>`

## Подход
- **Схема.** Две таблицы с составным ключом `(epic_id, number)` — номер в
  эпике и для черновика, и для решения: у решения появляется естественный
  ключ, по которому `epic restore` сверяет и не дублирует строки (AC-13), а
  `rowid` в строки не выходит. DDL — одним литералом в `SCHEMA` и в
  `migrate` (`CREATE TABLE IF NOT EXISTS`, без записи журнала), как
  `PAIR_SUSPENSION_DDL`.
- **Команды** `epic draft add|edit|drop|promote`, `epic decision`,
  `epic export`, `epic restore` — в `orchestrator/epics.py` тем же каркасом,
  что команды Э1: проверки, транзакция `BEGIN IMMEDIATE` с записью журнала
  эпика последней. SQL — в `store.py`.
- **promote** идёт путём `new`: `catalog.cmd_new` получает keyword
  `tz_text` (текст ТЗ вместо файла; `tz_path` — подпись источника в
  отказах), `epic_id`, `after` (merge_after черновика — объединение со
  строкой «Порядок:» делает сам `new`), `start_after`. Адреса черновиков
  перечней разрешаются в id задач-результатов до вызова; незаведённый —
  отказ с перечнем. Рамка — `budget.apply_operator_frame` (общее ядро с
  `apply_division_frame`, источник `operator`).
- **Копия эпика.** Файлы `epics/<id>/EPIC.md`, `drafts/<n>.md`,
  `DECISIONS.md`: человекочитаемый Markdown плюс первая строка — HTML-
  комментарий с JSON строк БД (все колонки, `NULL` как `null`). Восстановление
  читает только JSON — без разбора Markdown, побайтно (ТЗ с `---`, `# `,
  без хвостового перевода строки). Запись — `artifact_branch.commit_files`
  под ключом `epic-<id>` с `target` = проект эпика (плотницкий
  `write_commit` поверх головы). Журнал отправки ключа `epic-<id>` идёт под id
  эпика с `target` проекта (`artifact_branch._journal_identity`).
- **Одна отправка на команду.** `cmd_epic` открывает
  `artifact_branch.deferred_sends()` вокруг любой подкоманды; `epic add|remove`
  пишут ссылку внутри своего `lease.run_locked` (вложенная область) — в обоих
  случаях ссылка уходит один раз при выходе.
- **Неудача записи** (клона нет, git не ответил): предупреждение в выводе и
  запись журнала эпика «запись ссылки эпика FAILED», БД не откатывается;
  следующая команда пишет полное состояние поверх головы.
- **export** читает файлы из ссылки (нет ссылки — тот же рендер по БД с
  предупреждением). **restore** сверяет поля и отказывает перечнем
  «таблица, строка, поле».
- **Перебор `refs/artifacts/*`** (требование 15): префикс имени
  `config.EPIC_REF_NAME_PREFIX = "epic-"`; `fetch_all_from_origin`
  сдвигает и ссылки эпиков, но в исходы задач их не отдаёт; явные фильтры в
  `retro_corpus`, `plan_appendix_ci.remote_docs_refs`, `artifact_cleanup`,
  `snapshot._history_pass`, `doctor._origin_artifact_refs`.
  `scripts/plan_appendix_ci.py` пульт не импортирует (тест
  `test_ac9_ci_script_does_not_import_orchestrator`): префикс там — свой
  литерал `"epic-"`, как `DOCS_REF_PREFIX`; равенство с
  `config.EPIC_REF_NAME_PREFIX` держит
  `tests/test_epic_drafts_units.py::test_ci_script_epic_prefix_matches_config`
  (возврат из verifying, прогон CI 40266189759).
- **Сторожа фильтров `epic-` (возврат из merge_gate 26.10).** Код фильтров
  не менялся. Долгоживущий `…_ref_scans.py` сверяет вывод «со ссылкой
  эпика = без неё», а на реальных данных фильтры doctor, snapshot и
  cleanup на вывод не влияют: ссылки там ищутся по id задачи
  (`remote.get(branch_name(id))`, `remote.get(<каталог main>)`, ключ ветки
  `artifact/<id>`), а имя `epic-…` таким id не бывает. Фильтр становится
  видимым, только если на стороне задачи есть имя `epic-…`. Новый файл
  `tests/test_epic_ref_scan_filters.py` (существующие тесты не тронуты)
  проверяет ровно это:
  - doctor: `_origin_artifact_refs` (через фасад doctor) при обеих ссылках
    в origin не несёт `epic-…`, но несёт ссылку задачи с её головой;
  - snapshot: каталог main `tasks/epic-<id>/` не получает ссылку эпика
    в качестве своего снимка («со ссылкой 1, без ссылки 1»);
  - artifact_cleanup: ветку `artifact/epic-<id>`, за которой стоит только
    ссылка эпика, `--execute` не удаляет (отказ, ветка в origin цела).
    Без фильтра опись сочла бы `refs/artifacts/epic-<id>` ссылкой
    документов и удалила бы ветку. Значит, фильтр не косметический: на
    этом входе он и есть защита от удаления, и его надо оставить.
- **Готовность к закрытию** (требование 17): `board` считает черновики
  `draft`; `epic close` отказывает перечнем «адрес «название»».

## Шаги
1. Схема и `store`: `EPIC_DRAFTS_DDL`, догон в `migrate`; функции черновиков,
   решений, вставки строк восстановления.
2. `artifact_branch`: ключ ссылки эпика, журнал отправки под id эпика,
   `fetch_all_from_origin` без ссылок эпиков в исходах; фильтры мест перебора.
3. `epics.py`: черновики, решения, рендер/запись ссылки, обновление ссылки
   всеми меняющими командами, `export`, `restore`, готовность к закрытию;
   `catalog.cmd_new(tz_text=…)`, `budget.apply_operator_frame`, `board`.
4. Справка `artel.py`, карта кодовой базы, прогон долгоживущих файлов задачи и
   тестов затронутых модулей.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 3 |
| 3 | 3 |
| 4 | 3 |
| 5 | 3 |
| 6 | 3 |
| 7 | 3 |
| 8 | 3 |
| 9 | 1, 3 |
| 10 | 3 |
| 11 | 3 |
| 12 | 2, 3 |
| 13 | 3 |
| 14 | 2 |
| 15 | 2 |
| 16 | 3 |
| 17 | 3 |

## Влияние на систему
- `catalog.cmd_new`: новый keyword `tz_text` по умолчанию `None` — прежние
  вызовы не меняются.
- `budget.apply_division_frame`: тело вынесено в `apply_operator_frame`;
  текст журнала и вывода рамки деления прежний.
- `artifact_branch`: для ключей задач журнал отправки прежний (id задачи,
  `target=None`); `fetch_all_from_origin` возвращает те же исходы по задачам.
- Гейты, лимиты, инварианты, существующие тесты не трогаются. Откат — revert
  merge-коммита; таблицы `epic_drafts`/`epic_decisions` после отката остаются
  в БД неиспользуемыми (`CREATE TABLE IF NOT EXISTS`, без удаления).

## Риски
- Две одновременные `promote` одного черновика: повторная проверка состояния
  в транзакции после `new` не отменяет уже заведённую задачу — вторая
  задача возможна (окно — время `new`). Lease по эпику SPEC Э1 не берёт.

## Проверка
- Долгоживущие файлы задачи: 39 тестов зелёные (`pytest` четырёх файлов +
  `tests/test_epic_drafts_units.py`); `plank-run … tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_epic_ref.py` — 13 passed.
- Тесты затронутых модулей (40 файлов: эпики Э1/Э2а, `artifact_branch*`,
  `catalog_*`, `retro_corpus`, `plan_appendix_ci*`, `snapshot_history`,
  `doctor_artifact_branch_sync`, миграции, `test_invariants.py`) — зелёные.
- Свой тест `tests/test_epic_drafts_units.py` (строка данных ссылки, отказ
  ссылки черновика на себя) покраснел на обеих заявленных мутациях;
  тест равенства префикса — красный на мутации литерала `"epic_"`.
- После возврата из verifying: `test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`,
  все `tests/*plan_appendix*`, `…_ref_scans.py`, `…_drafts.py`,
  `test_epic_drafts_units.py` — 84 passed.
- После возврата из merge_gate: `pytest tests/test_epic_ref_scan_filters.py
  tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py` — 10 passed. Временная
  мутация «убрать фильтр `epic-`» в `doctor/artifact_branches.py:34`,
  `snapshot.py:354` и `artifact_cleanup.py:71-74`: все три новых теста
  красные (каждый идёт через свой модуль), 7 долгоживущих зелёные; код
  возвращён `git checkout`, карта перегенерирована. Полный набор в шаге разработчика
  не запускается (сторож роли) — его гоняют CI и гейт приёмки.

## Предложения системе
- Тест-сторож вида «вывод с X равен выводу без X» не может покраснеть на
  фильтре X, если на реальных данных X на вывод не влияет: ни
  test_author, ни ревью этого не заметили, поймал только гейт мержа.
  Предлагаю добавить в `skills/test-authoring.md` правило: заявку «Ловит
  мутацию» проверять самой мутацией ещё на шаге test_author.
- Песочница роли отказывает Bash-heredoc с `{…"…"}` («brace with quote
  character») и `$var` в цикле — большой Python-код приходится вставлять
  Edit'ом; стоит упомянуть в `skills/coding-standards.md` рядом с правилом
  «по одной команде».
- `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`, запущенный
  первым/один, падает на сборке циклом импорта `checkpoint → fixation →
  workspace → lease → artifact_branch → fixation.FIXATION_AUTHOR_NAME`
  (воспроизводится и на origin/main); в полном наборе маскируется порядком.
