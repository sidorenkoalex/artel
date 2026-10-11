---
task: 01M4M68557TT4KYN814H8AZ01A
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Этап 4 ADR-0021, часть B — исторические снимки для каталогов tasks/ без refs/artifacts

## Подход
Имя команды и флага уже зафиксировала планка
(`tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`):
`artel.py artifact-history-snapshots [--dry-run]`. Реализация — в
`orchestrator/snapshot.py`, рядом с коммитом закрытия: оба пишут неизменную
ссылку документов, и `doctor` сверяет обе одной проверкой.

Команда (`snapshot.cmd_artifact_history_snapshots(dry_run)`), репозиторий —
клон артели `artifact_branch.repo_for_target(config.DEFAULT_TARGET)`:
1. `git fetch origin main` (свежий `origin/main`) и одним `git fetch`
   все `refs/artifacts/*` из origin в приватное пространство
   `refs/artel/history-snapshots/<pid>/*`. Это даёт и перечень ссылок в origin,
   и объекты снимков, которых нет локально: они нужны для отчёта «main новее».
   Пространство убирается в `finally`. Не ответил origin — отказ кодом 1,
   ничего не создаётся: без перечня origin нельзя гарантировать, что
   существующая ссылка не будет переписана (требование 3).
2. Перечень каталогов — `git ls-tree -d origin/main tasks/`.
3. Задача со ссылкой локально или в origin — существующая, её ссылка не
   трогается. Для отчёта сверяются файлы `tasks/<id>/` main и головы
   снимка (локальной, иначе из origin). Файл «в main новее», если его блоб в
   main отличается от блоба в снимке (или файла в снимке нет), а последний
   коммит main, менявший путь, позже (`%ct`) последнего коммита снимка,
   менявшего путь. Строка отчёта:
   `tasks/<id>/<файл>  main <блоб>  снимок <блоб|нет>`.
4. Задача без ссылки — кандидат. Пробный режим печатает перечень и выходит:
   ни ссылок, ни журнала. Обычный режим собирает дерево
   `tasks/<id>/` = дерево каталога из `origin/main` как есть (`git mktree`
   двумя уровнями, без чтения файлов). Коммит без родителя, автор — пульт
   (`fixation.FIXATION_AUTHOR_*`), сообщение:
   `<id>: исторический снимок tasks/<id>/ из origin/main <sha>`.
5. Порядок записи для кандидата: сначала `git push origin
   <коммит>:refs/artifacts/<id>` без force. Отказ — ссылка не создаётся
   ни там, ни тут, и строка отказа идёт в вывод. Затем локальный
   `update-ref` со сверкой «ссылки не было», затем запись журнала
   `steps`: действие `HISTORY_ACTION = "исторический снимок"`, деталь
   `refs/artifacts/<id> <- <коммит> (origin/main <sha>)`, той же формы, что
   у коммита закрытия. Target передаётся явно (`config.DEFAULT_TARGET`), строка
   `tasks` не заводится. Push первым — потому что журнал обещает `doctor`'у
   ссылку в origin. Ссылка без записи в журнале была бы неотличима от чужой.
6. Повторный запуск: ссылка уже есть — задача существующая (п.3),
   идемпотентность без отдельной логики.

`doctor` (`orchestrator/doctor/artifact_branches.py::check_artifact_ref_sync`):
`snapshot.history_snapshots(conn)` даёт `{id: коммит}` из последних записей
`HISTORY_ACTION` (`store.steps_of_action`), target — артель. Это одна выборка по действию, строки
`tasks` не нужны. Задачи из неё, у которых нет записи о коммите закрытия и
которые не живые, сверяются по правилу закрытой ссылки: голова локально и в
origin = коммиту снимка. Подмена даёт `warn` с id задачи. «Только в origin и
равна коммиту» не считается расхождением и попадает в ту же строку `ok`.
Другие проверки `doctor` журнал по этому действию не читают. Сироты
сканируют каталоги, счётчики журнал не читают, recovery читает `tasks.fixed_sha`
(разобрано в «Влиянии на систему»). Поэтому записи без строки `tasks`
ложных тревог не дают; это проверяет AC-5 планки.

## Шаги
1. `orchestrator/snapshot.py`: `HISTORY_ACTION`, `history_snapshots`,
   `cmd_artifact_history_snapshots` и помощники. `orchestrator/artel.py`:
   строка таблицы диспетчера, справка, абзац модуля. Команда остаётся вне
   белого списка ролей, потому что пишет ссылки и ходит в сеть.
   `orchestrator/doctor/artifact_branches.py`: сверка исторических ссылок.
   Юнит-тесты `tests/test_snapshot_history.py` на то, что не покрывает
   долгоживущий файл: отказ при недоступном origin, отказ push (ни ссылки, ни
   журнала), файл есть только в main (строка отчёта с «нет»). Каждый
   тест проверен временной мутацией из своей заявки «Ловит мутацию» и на ней
   красный. Отказ процессу роли отдельно не тестируется: команда не внесена в
   белый список `_ROLE_ALLOWED_COMMANDS`, а белый список закрыт по
   умолчанию и уже покрыт `tests/test_artel_role_restricted_commands.py`.
   Регенерация `docs/codebase-map.md`.

## Проверка
- `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py` (долгоживущий,
  AC-1…AC-8): 8 passed, 4 subtests passed. Файл не правился.
- `tests/test_snapshot_history.py`: 3 passed.
- Тесты затронутых модулей (`test_artel_role_restricted_commands`,
  `test_docs_fetch_edges`, `test_doctor_artifact_branch_sync`,
  `test_snapshot_closing_outcome`, `test_01m446wv7s94ftzgjcgmpj667f_clone_refs`,
  `test_artifact_ref_sync`, `test_doctor_closed_ref_fix`, `test_invariants`,
  `test_multitarget_invariants`, `test_01m409ynswacnfknje2x263zsd_project_docs_ref`
  и долгоживущий файл): 161 passed, 219 subtests passed.
- Полный набор — `artel.py suite-run 01M4M68557TT4KYN814H8AZ01A`. Прогон №1
  был красным: одно новое падение относительно базы 415f1de4.
  `tests/test_multitarget.py::SqlOnlyInStoreTest::test_no_sql_outside_store`
  поймал сырой SELECT по `steps` в `snapshot.py`. Исправлено переходом на
  `store.steps_of_action`. Повтор упавших (№2) зелёный: 1 passed.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (команда: дерево из origin/main, метка, push) |
| 2 | 1 (`--dry-run`) |
| 3 | 1 (перечень ссылок локально + origin; отказ без origin) |
| 4 | 1 (отчёт «main новее») |
| 5 | 1 (существующая ссылка пропускается) |
| 6 | 1 (журнал `HISTORY_ACTION`, сверка `doctor`) |
| 7 | 1 (doctor: приоритет закрытия/живой, только-в-origin = ok) |
| 8 | 1 (ссылка с деревом `tasks/<id>/` — `docs_fetch` без правки) |

## Влияние на систему
- Новое действие журнала читают только `snapshot.history_snapshots` и `doctor`.
  `watch` будит дозор только на своих классах событий, это действие в них не
  входит. `report` фильтрует журнал по строкам `tasks`.
- `check_artifact_ref_sync` получает новые сверяемые ссылки. Существующие
  ветви (живые, закрытые) не меняются: исторические идут отдельным набором
  и только для задач без записи о закрытии, вне живого состояния.
  Существующие тесты doctor не меняют ожиданий.
- Существующие ссылки команда не пишет ни в одной ветке кода. Push без force:
  origin сам отклонит непродвигающее обновление. Локальный `update-ref` идёт
  со сверкой нулевого прежнего значения.
- Защищённые пути, гейты, лимиты не трогаются. Read-only пути из SPEC
  (`artifact_branch.py`, `store.py`, `docs_fetch.py`, …) не правятся. Записи
  журнала читаются существующим `store.steps_of_action`, SQL вне `store.py`
  нет (инвариант `test_multitarget.py::SqlOnlyInStoreTest`). Target
  исторического снимка всегда артель: так команду писать ему target не
  нужно.
- Откат: revert merge-коммита. Созданные Оператором ссылки — обычные
  ссылки документов, читатели их уже понимают.

## Риски
- Критерий «новее» по датам коммитов: если дату коммита переписали руками,
  отчёт может ошибиться. Отчёт информационный, ссылки он не меняет.
- Сотни существующих ссылок: на каждую сверку идёт `ls-tree`, `git log` —
  только для различающихся блобов. Для разовой команды Оператора это приемлемо.

## Предложения системе
- `skills/coding-standards.md` («Тесты»): `python3 -m pytest … -n 6` в шаге
  роли роняет все воркеры (`node down: Not properly terminated`, «no tests
  ran»), и раннер ничего не объясняет. Скил стоит прямо сказать, что
  тесты затронутых модулей идут без `-n`.
- Оболочка шага роли: `ls`/`cat` без полного пути — «command not found»
  (`/bin/ls` работает). Похоже, `PATH` курируемого HOME роли урезан: стоит
  сверить `runner.role_env` с ожиданиями скилов.
