---
task: 01M6RB74H9BDTJAA5D2S4QPK1E
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Автор коммитов пульта для проекта на GitLab: автопоиск, сторож, отказ new

## Подход
Одна опора — владелец токена (`forge.TokenUser` с `name`/`commit_email`),
вокруг неё три потребителя: сторож `doctor`, автопоиск `doctor --fix`,
отказ `catalog.cmd_new`.

- `forge.TokenUser` получает поля `name`, `commit_email` (по умолчанию
  `None`); `gitlab_adapter.token_user` берёт `commit_email`, иначе
  `email` ответа `GET /user` (пустая/пробельная строка — адреса нет).
  `_GitHub` `token_user` не реализует — поля пусты.
- `projects.set_commit_author(name, author) -> (причина, текст)` — запись
  путём `target-set` без `sys.exit`: рубежи `_target_set_load` вынесены в
  `_local_layer_for` (возвращает причину; `_target_set_load` сохраняет
  прежние тексты, дописывая `target-set: ` и `sys.exit`), сверка до записи —
  `_target_set_block_mismatches` по отображению `machine.commit_author`
  целиком, копия — `_backup_copy`, запись — `_write_atomic`, строка журнала
  `target-set` (actor `doctor`, target проекта). Отказ сверки — причина с
  префиксом «сверка до записи не прошла».
- `doctor/project_checks.py`: `commit_author_applies` (не артель,
  `token_slot`, `forge.ci_by_pipeline(name)` — без литерала хостинга),
  `check_commit_author` (skip в роли / warn без ответа или адреса / fail
  «автор коммитов не задан: doctor --fix» / fail несовпадения с текстом
  «doctor --fix не перезаписывает — …» / ok), `commit_author_checks`
  (строка или пусто), `fix_commit_authors` (в роли — выход до
  `token_user`; заданное поле не трогается; причины — строкой с именем
  проекта).
- `doctor/cli.py`: строка сторожа — сразу за `project_entry_checks`;
  автопоиск — в блоке `--fix` до `all_checks`, так что строка того же
  прогона видит записанное, а отказ записи не мешает прочим проверкам.
- `catalog._commit_author_gate(target)` — в `cmd_new` сразу после
  `targets.unsupported_reason`: `fail` — `sys.exit` текстом проверки до
  клона, id и ссылки документов; `warn` — предупреждение. Путь
  `epic draft promote` идёт через `cmd_new` и получает тот же отказ.
  Пакет `doctor` импортируется лениво (он сам тянет `catalog`).

## Шаги
1. `forge.TokenUser` + `gitlab_adapter.token_user` (требование 1).
2. `projects.set_commit_author` + вынос `_local_layer_for` (требование 3).
3. Сторож и автопоиск в `doctor/project_checks.py`, вызовы в
   `doctor/cli.py` (требования 2, 4).
4. Отказ в `catalog.cmd_new` (требование 5).
5. Юнит-тесты `tests/test_commit_author_units.py` (свойства вне
   долгоживущих файлов: строки нет у хостинга без конвейеров и `--fix` не
   зовёт `token_user`; отказ записи при комментарии в слое, записи артели и
   отсутствующей записи — причиной, без `sys.exit`). Карта —
   `scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 3 |
| 3 | 2, 3 |
| 4 | 3 |
| 5 | 4 |
| 6 | — (существующие тесты не правились; `pair_support` и `unsupported_project` зелёные без правки, мандатом ANSWER-2 не пользовался) |
| 7 | — (`orchestrator/gitcmd.py` не тронут) |

Проверено: `tests/test_01m6rb74h9bdtjaa5d2s4qpk1e_token_user.py`,
`tests/test_01m6rb74h9bdtjaa5d2s4qpk1e_commit_author.py` — 29 passed;
19 файлов тестов forge/gitlab/doctor/target-set/pair_support/
unsupported_project — 541 passed; doctor/catalog/epic/projects — 196
passed; `tests/test_commit_author_units.py` — 4 passed, оба сторожа
покраснели на своих мутациях (снят `ci_by_pipeline` из условия; снята
проверка комментария в `_local_layer_for`) и вернулись в зелёный.

## Влияние на систему
- `doctor`: на каждый проект GitLab с `token_slot` добавляется один запрос
  `GET /user` в проверках и ещё один в `--fix` (только при отсутствии
  поля). В процессе роли ни запросов, ни записи нет. Без сети строка —
  `warn`, `doctor` от неё не краснеет.
- `new`/`epic draft promote` проекта GitLab делают один запрос `GET /user`;
  недоступный API даёт `warn` и не блокирует заведение (SPEC, AC-6).
  Артель и GitHub не затронуты (строки нет).
- `target-set`: тексты отказов `_target_set_load` прежние (вынос без
  смены формулировок, проверено тестами target-set). Сверка до записи и
  копия в `config.LOGS` не ослаблены — функция записи идёт через те же
  `_target_set_block_mismatches`/`_merge_mismatches`/`_backup_copy`.
- Гейты, лимиты, существующие тесты не меняются. Откат — revert коммита
  задачи.

## Риски
- В песочницах прочих тестов с вымышленной записью GitLab `new`/`doctor`
  теперь зовут `token_user`; без подмены транспорта — отказ соединения
  `localhost` → `warn`. Затронутые файлы прогнаны — зелёные; полный набор
  — за CI.

## Предложения системе
- `orchestrator/projects.py`: хелперы `target-set` завершают процесс
  `sys.exit` на каждом рубеже — переиспользовать их из других команд
  (здесь — `doctor --fix`) пришлось выносом рубежей в функцию с причиной;
  тот же вынос для `_rendered`/`_target_set_write` сделал бы запись слоя
  пригодной для любых автопочинок.
