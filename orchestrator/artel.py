#!/usr/bin/env python3
"""Артель, Фаза 0 — FSM-оркестратор (CLI).

Детерминированный конечный автомат; агенты думают внутри шага, между
шагами не думает никто. Все гейты Фазы 0 — ручные (approve/reject из CLI).

Состояния:
  spec_writing -> spec_gate -> tests_writing -> in_dev -> verifying -> review -> acceptance -> merge_gate -> done
                                                   ^______________________|  (changes_requested, <=3)
                                                   ^__________________________________|  (acceptance reject, <=1)
  из любого: escalated (вопрос Оператору), killed.

`verifying` (ADR-0015): CI подтянутой головы кодовой ветки проверяется ДО
ревьювера, не после — рубежи перехода `in_dev -> review` (подтяжка main,
прогон приёмочной планки, гейт зон/ёмкости, лок планки, гейт «замечания
не отработаны», сверка головы на origin) стоят теперь на `in_dev ->
verifying`; из `verifying` в `review` ведёт только зелёный CI. Возврат
`changes_requested` — снова в `in_dev`, повторный вход в `review` — опять
через `verifying`.

`tests_writing` (A4, tasks/T023) — приёмочные тесты до кода, роль
test_author: `spec_gate` заводит её при approve, если SPEC не помечен
`skip_tests` и несёт AC-разметку критериев (`schema_version >= 2`); иначе
approve идёт прямо в `in_dev`, как до T023. Выход из `tests_writing` —
каждый AC-n получил тест либо пометку manual/skip/escalate
(`tasks/<id>/acceptance_tests/`); `escalate` уводит задачу в `escalated`
немедленно. После выхода каталог `acceptance_tests/` залочен фиксацией
(T021): правка после лока — отказ перехода `in_dev -> verifying`.

`approve` из escalated возвращает задачу в in_dev, а если эскалировал упавший
агент — в тот шаг, на котором он упал (см. escalated_from): чинить надо шаг,
а не откатывать готовую работу в разработку.

Бюджет задачи — жёсткий потолок: стоимость каждого запуска агента снимается
с финального события потока CLI и копится в spent_usd. На 70% бюджета —
предупреждение, на 100% — escalated и отказ запускать агента, пока Оператор
не поднимет потолок (`budget <id> <usd>`) или не закроет задачу (`kill`).

Потолок по умолчанию один на все задачи, но класс задачи виден аналитику
при постановке: `budget_usd` в frontmatter SPEC применяется к задаче один
раз, на переходе spec_writing -> spec_gate, потолком в обе стороны — и
выше, и ниже дефолта — в пределах потолка ролей (`ROLE_BUDGET_CAP`,
ADR-0014). Значение, не разбираемое как число (мусор в поле), —
предупреждение, переход продолжается с прежним потолком. Значение выше
потолка ролей — другой случай: guard отказывает сам переход целиком
(`spec_writing -> spec_gate`), задача остаётся в `spec_writing`, пока
аналитик не поправит число либо не разделит задачу; поднять потолок
выше `ROLE_BUDGET_CAP` вправе только Оператор командой `budget`
(инвариант 10). Ручное поднятие сильнее значения из SPEC; кто задал
потолок, помнит колонка budget_source.

`kill` не только переводит задачу в `killed`, но и убирает её хвосты в
рабочем дереве: каталог `tasks/<id>/`, не попавший в main, и локальную
ветку задачи, не смерженную в main. Всё убранное и всё оставленное —
записью `уборка` в журнале. Логи прогонов не трогаются.

`merge_gate -> done` (approve) той же логикой убирает worktree и, следом
за ним, локальную ветку задачи — та уже влита `--no-ff` в main (история
мержа полная, без squash), поэтому удаляется безопасным `git branch -d`
(tasks/T073/SPEC.md, требование 2). Обе уборки — журналом.

`prune [--execute]` (tasks/T073/SPEC.md) исполняет retention-политику
`docs/retention.md` для `.artel/logs/` (90 дней И N=20 последних задач,
`config.LOG_RETENTION_DAYS`/`LOG_RETENTION_KEEP_TASKS`) и `alerts`
(архивация старше 90 дней в `alerts_archive`, не удаление). Без флага —
dry-run: план, ничего не трогает. С `--execute` — исполняет и печатает,
что́ фактически убрано. Не привязана к переходу FSM ни одной задачи и
не отменяет инвариант 16 (`.artel/logs/` уборка `kill`/`done` не
трогает) — `prune` не часть этой уборки.

Вердикт ревьювера учитывается конечным автоматом ровно один раз: после
возврата задачи в in_dev переход review -> acceptance требует нового
REVIEW.md (iteration больше уже учтённого, см. fresh_verdict_iteration).

Вход ревьювера собирает оркестратор, а не сам агент: ревью-пакет
(SPEC, PLAN, прошлый REVIEW, стат-список и diff ветки) целиком уходит
в промпт шага, а его размер — в журнал. Так стоимость прогона задаётся
размером изменения, а не тем, как широко агент разбрёлся по репозиторию.

Фаза 0: гейт плана (фаза A review-checklist) выполняется ревьювером в одном
прогоне с ревью MR. Отдельное состояние plan_review появится в MVP.

`auto <id>` избавляет Оператора от механического чередования `run` и
`advance`: цикл зовёт те же две команды, пока задача в агентском состоянии
(in_dev, review), и останавливается на первом месте, где нужен человек —
ручной гейт, эскалация, done/killed, отказ `run` по бюджету или лимит
AUTO_MAX_STEPS шагов за вызов. Решений auto не принимает: approve и reject
остаются ручными (§4), пути мимо гейта у цикла нет.

`run <id>`/`auto <id>` без `--attach` (по умолчанию, SPEC
01M1NWCHVTYQ0M8PCJ1YJ2N78P) отвязывают цикл от процесса сессии Оператора:
команда сама порождает себя отдельным процессом ОС и сразу возвращает
управление, напечатав pid, путь лога (`.artel/logs/<id>-<cmd>-<n>.log`)
и подсказку `artel.py log <id>`; цикл переживает обрыв породившей его
сессии. `--attach` — прежнее (до этой задачи) поведение: передний план
вызывающего процесса, без отвязки. `stop <id>` шлёт отвязанному циклу
SIGTERM; гарантия «доигрывает уже начатый шаг и завершается сам между
шагами» — про `auto` (у него есть граница между шагами, на которой
сигнал проверяется). У отвязанного `run` границы нет — один шаг и
естественный выход, обработчика `SIGTERM` он не ставит, `stop` для него
обрывает процесс немедленно, как и до этой задачи. `kill <id>` прерывает
немедленно в обоих случаях, включая принудительное завершение самого
цикла.

Целевые проекты объявляются в targets.yaml (ADR-0003 п.2), каталог
проекта заводит `target-init <target>` (.artel/projects/<target>/ —
workspace, tasks, knowledge, logs). БД одна на все проекты: строка
задачи и запись журнала помнят свой target, номера задач считает
персистентный счётчик проекта. Артефакты задач самой артели до A7
остаются в tasks/ пульта — особый случай догфуда.

`new "<название>" --tz <файл>` заводит задачу с ТЗ Оператора
(`tasks/<id>/TZ.md`, SPEC T025): `spec_writing` в этом случае исполняет
роль analyst (`run`/`auto`), а не Оператор руками — без флага поведение
не меняется. Батч вопросов analyst (`QUESTIONS.md`) эскалирует задачу
немедленно на первом же `advance`, тем же путём `escalated_from`, что
и падение любого другого агентского шага.

Команды:
  init | new "<название>" [--tz <файл>] | status | show <id> | advance <id> |
  run <id> [--attach] | auto <id> [--attach] | stop <id> |
  approve <id> [sha] | reject <id> "<причина>" |
  answer <id> <файл-с-ответом> | zones-extend <id> <путь>[, <путь>...] |
  kill <id> | release <id> |
  pause [--now] <id> | resume <id> | log <id> | budget <id> <usd> |
  target-init <target> | doctor [--restore] [--fix] | alert-ack <id> "<решение>" |
  version | canary --k <N> [--sha <sha>] | canary pool-seal | prune [--execute] |
  amend-tests <id> --reason "<основание>" [--from-branch] | pin-update <sha main артели> |
  pin --to [<sha>] | zone-release <id> | zone-reorder <id1> <id2> ... |
  venv-sync | note (копилка|бэклог|очередь) --text "<строка>" |
  note --append <ключ> --text "<текст>" | note --flush |
  doc-commit <путь-в-репозитории> --from <файл> --message "<основание>" |
  doc-commit --flush |
  watch [--tasks <id>[,<id>...]] [--mine] [--all] [--events <класс>[,...]]
        [--interval SEC] [--until <state>]

`pin-update <sha>` (A7, Stage1) — обновляет пин запущенной версии:
продвигает рабочее дерево и HEAD `config.ROOT` до `<sha>` main артели
(`git fetch` + `git merge --ff-only`), журналирует операторскую
идентичность и оба sha. `merge_gate -> done` (Stage0) НЕ двигает
`config.ROOT` сам — это единственный способ его продвинуть; `doctor`
только сообщает о расхождении (`check_root_pin`), не обновляет пин сам.
С tasks/01M1NGFK3N6MRMYGCC09H975V3 отказывает без зелёного прогона
канарейки не старше `config.CANARY_MAX_MERGES_SINCE_GREEN` мержей main
на целевом sha (ADR-0013) — `doctor` поднимает триггер по тому же
порогу заранее.

`pin --to [<sha>]` (tasks/01M1NGFK3N6MRMYGCC09H975V3, ADR-0013 ч.3) —
откат пина: с явным `<sha>` (обязан быть предком текущего HEAD) —
`git reset --hard` на него; без аргумента — на sha последнего зелёного
прогона канарейки по журналу. Main пульта на origin не трогается ни в
одном случае (ни fetch, ни push) — откат касается только `config.ROOT`
этой машины. Каждый вызов журналируется отдельной записью, успешной или
отказом.

`pause <id>` (SPEC T070) — штатная приостановка: помечает задачу в БД,
не заводя нового состояния FSM; `run`/`auto` перед стартом агентного
шага видят пометку и останавливаются штатно, уже идущий шаг не
прерывается. `resume <id>` снимает пометку, сама шаги не запускает.
`kill`/`approve`/`reject`/`advance` пометку не читают и работают на
приостановленной задаче как обычно.

`pause --now <id>` (SPEC T074) — жёсткая приостановка: та же пометка,
что у обычной `pause`, ПЛЮС, если сейчас бежит агентный шаг задачи (в
этом же процессе или в другом процессе этой машины — параллельная
CLI-сессия, фоновый `auto`), прерывает его: процесс агента завершается,
незакоммиченный WIP worktree задачи чекпоинтится служебным коммитом с
пометкой причины «pause --now», lease держателя снимается, частичная
стоимость шага учитывается по механике T040. Адресация — по данным
lease задачи (pid, host); lease нет, его процесс мёртв или агентного
шага сейчас нет вовсе — честная деградация до обычной `pause`, не
ошибка; lease на другом host — честный отказ прервать (вне объёма).

`release <id>` — операторское снятие lease задачи (SPEC T062): удаляет
строку `leases` независимо от свежести heartbeat и журналирует данные
бывшего держателя. Не мутирующая команда в смысле lease — своего lease
не берёт и лимитер `MAX_PARALLEL_TASKS` не проходит (инвариант 32,
тот же класс, что `kill`/`status`/`approve`/`reject`/`budget`/`log`/
`doctor`); задача без lease — не ошибка, код возврата 0.

`canary --k <N>` (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, v2 — переработка
v1, tasks/T065/SPEC.md) — синтетический прогон конвейера: отбирает `N`
случайных шаблонов ТЗ из пула ВНЕ корня пульта (`~/.artel-canary`,
Оператор заводит и наполняет его вручную). Целевой sha прогона (SPEC
01M2B6K02YVJBWE1JDWP85EJH0) — по умолчанию голова `origin/<config.
MAIN_BRANCH>`, не HEAD главной копии (пина); явный `--sha <sha>` берёт
целевым именно его, без обращения к `origin`. Эфемерный клон делает
checkout этого sha, `canary_runs.main_sha` несёт его же. Ведёт КАЖДУЮ
выбранную
задачу ПОЛНЫМ циклом в ОТДЕЛЬНОМ эфемерном клоне пульта (`git clone`
во временный каталог + origin-заглушка — своя рабочая копия, своя БД,
свой origin, ноль следов в главном пульте: ни веток, ни RETRO, ни
алертов, ни снапшотов, ни для успешных, ни для убитых задач), сама
проходит `spec_gate`/`acceptance` внутри клона (отдельный от
`cmd_approve`/`auto` кодовый путь — инвариант 18 не затронут) и убивает
на `merge_gate`/`verifying` (никогда не approve, main клона не
трогает). Эскалация (`escalated`) закрывается синтетическим ANSWER
Оператора-заглушки, прогон продолжается сам. Метрики (шаги, стоимость,
итерации ревью, эскалации, исход) — БД пульта СНАРУЖИ клона, таблицы
`canary_runs`/`canary_baseline`; бейзлайн — per-task (ключ — стабильное
имя шаблона), не суммой по набору: первый прогон шаблона пишет его,
следующие сравнивают и поднимают алерт (`kind=threshold`) при
отклонении сверх `config.CANARY_DEVIATION_RATIO` — без автоматического
действия. Маркер шаблона «ожидается эскалация» сверяется с фактом,
расхождение — в отчёте.

`canary pool-seal` (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW) — хранит пул
`~/.artel-canary` в репозитории пульта ОДНИМ зашифрованным файлом
(`canary/pool.sealed`, `openssl enc -aes-256-cbc -pbkdf2` + тег
HMAC-SHA256), ключ — в keychain пульта; манифест GUID шаблонов
(`canary/guids.txt`) — открыт, для CI-сторожа утечки выше. `init`/
`doctor --restore` расшифровывают пул обратно в `~/.artel-canary`, если
каталог отсутствует; `doctor` предупреждает о незапечатанных правках.
Расшифровка недоступна ролям — запрет в курируемом слое роли и отказ
самого пульта, если вызван из окружения роли (`role_env`).

Занятость зоны на старте кода (SPEC 01M1P9QAG65GVF69YJEV0V18D9): перед
первым шагом `in_dev` зоны задачи (`zones:` SPEC, часть 1 —
01M1NKVPD2A79PQ6K0JVV1B2Q1) сверяются с зонами всех задач в фазах
`in_dev`…`merge_gate` — пересечение вне общего списка (`config.
COMMON_ZONES`) отказывает шагу именованно («зона <путь> занята задачей
<id> (<состояние>)»), `run`/`auto` не стартуют агента; `auto` останавливает
цикл причиной «ждёт зоны» без алерта буксования, `status`/`doctor`
показывают ожидание и держателя. Снимается само после `merge_gate ->
done`/`kill` занявшей задачи либо явно: `zone-release <id>` (журналируется
как осознанный риск). `zone-reorder <id1> <id2> ...` переставляет порядок
очереди задач, заблокированных одной и той же зоной (естественный порядок
— по времени approve их SPEC); `status`/`doctor` показывают позицию
задачи в этой очереди («очередь N/M») рядом с держателем, когда
конкурентов по зоне больше одного — очередь сама по себе ничего не
решает (кто стартует первым, решает только занятость), только показывает
Оператору порядок.

`watch [--tasks <id>[,...]] [--mine] [--all] [--events <класс>[,...]]
[--interval SEC] [--until <state>]` (SPEC 01M1VBEKRN0GA029J98S0K2DAQ) —
дозор событий журнала для сессии Оператора: печатает на stdout, без
буферизации, поток НОВЫХ (с момента запуска) записей `steps`/`alerts`
выбранных задач строками формата `log` плюс идентификатор задачи;
классы `--events` — именованные фильтры над `action` (дефолт
`transitions,refusals,gates,steps`). Селекторы `--tasks`/`--mine`/
`--all` взаимоисключающие (ровно один обязателен); `--mine`/`--all`
пересчитывают выборку заново каждые `--interval` секунд (по умолчанию
30) — новая задача подхватывается без перезапуска. Смена `tasks.state`
отслеживаемой задачи печатается отдельно (`STATE=<state>`) независимо
от `--events`. Завершается кодом 0 по `--until <state>` (выборка обязана
быть из одной задачи) либо по истощению нетерминальных задач выборки.
Не мутирующая команда: своё соединение `store.db()`, без lease, без
записи в `steps`/`alerts`, без смены `tasks.state` — тем же классом, что
`status`/`log`/`doctor`. Заменяет внерепозиторные сценарии сессии
(`watch_tasks.py`/`watch_spec_gate.py`, `docs/operator-session.md`).

`venv-sync` (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8) — создаёт/обновляет
`.artel/venv` средствами стандартной библиотеки (`python3 -m venv` тем же
интерпретатором, что и сам пульт, затем `pip install -r requirements.lock`
внутрь него), идемпотентно. `check_stack()` (`orchestrator/stack.py`)
сверяет установленные там версии с `requirements.lock` и предупреждает
на расхождении/отсутствии venv; `runner.role_env` берёт интерпретатором
роли `.artel/venv`, если он согласован с `requirements.lock`, и отказывает
шагу (`agent run SKIPPED`) без тихого отката на системный python иначе.

`canary <каталог>` (tasks/T065/SPEC.md) — синтетический прогон конвейера:
заводит по задаче на каждый `*.md` каталога (`catalog.cmd_new`, пометка
canary ТОЛЬКО колонкой БД, не в title), ведёт их `auto`-циклом, сама
проходит `spec_gate`/`acceptance` (отдельный от `cmd_approve`/`auto`
кодовый путь — инвариант 18 не затронут) и убивает на `merge_gate`
(никогда не approve, main не трогает). Отчёт — stdout и
`.artel/canary/<таймстамп>.json`; первый прогон без `.artel/canary/
baseline.json` пишет его, следующие сравнивают и предупреждают при
отклонении >50%, не перезаписывая файл без `--rewrite-baseline`.

`approve` на гейтах, где фиксация уже есть (A2b, ADR-0003 п.15),
подтверждает КОНКРЕТНЫЙ sha: без него печатает текущий зафиксированный
и просит повторить команду с ним, с несовпадающим — отказывает.

`answer <id> <файл-с-ответом>` (SPEC T075) — канал ответа Оператора на
эскалацию: читает текст из файла, создаёт `tasks/<id>/ANSWER-n.md` в
worktree задачи и коммитит его в её ветку. Эскалация со структурированным
вопросом роли (батч QUESTIONS.md из `spec_writing`, маркер `AC-n:
escalate` из `tests_writing`, вердикт REVIEW.md `status: escalate` из
`review`) требует нового ANSWER-n.md на ветке — `approve` из `escalated`
без него отказывает и печатает, какого файла не хватает; эскалации
класса «лимит» (бюджет, попытки агента, итерации ревью, отказы приёмки,
инцидент целостности, конфликт подтяжки главной ветки) ответа не
требуют, как и до этой задачи. Следующий запуск роли получает ответ
(и исходный вопрос, если он был) в своём брифе (`orchestrator/brief.py`).

`answer <id> <файл>` для задачи в `in_dev`/`review` (SPEC
01M287TPG0HAVXS8CHBCY679WN) — принимается ТОЛЬКО если текст файла
несёт строку «Расширение зон разрешено: <пути>»: коммитит
`ANSWER-n.md` тем же путём, что и для `escalated`, состояние задачи не
меняется. Файл без этой строки в `in_dev`/`review` отказывает так же,
как любое состояние вне `escalated`.

`zones-extend <id> <путь1>[, <путь2>]` (SPEC 01M287TPG0HAVXS8CHBCY679WN)
— коммитит `ANSWER-n.md` с той же строкой маркера и текстом «мандат
Оператора: <пути>»; если PLAN.md головы артефактной ветки уже несёт
раздел «## Расширение зон» с РОВНО теми же путями — сразу обновляет
`tasks.zones_extension` (гейт зон пропускает дифф без отдельного
`answer`), иначе БД не трогает и журналирует, что раздела PLAN нет.

Структуру артефакта на переходах проверяет код: `advance` прогоняет guard
по тому артефакту, статус которого и есть условие перехода (SPEC — на гейт
SPEC, PLAN — в ревью, REVIEW — из ревью). Нарушение структуры отказывает
в переходе с названным файлом и причиной. Merge из `merge_gate` требует
зелёного CI головного коммита ветки задачи (`gh`); неизвестный статус —
тоже отказ, задача остаётся на гейте.

`amend-tests <id> --reason "<основание>"` (ADR-0012, SPEC
01M1HNNHDMP2C1AJTH5QF1BTN2) — штатная правка уже зафиксированной планки
приёмки: Оператор правит `tasks/<id>/acceptance_tests/` прямо в
worktree задачи, команда коммитит правку, сдвигает `tests_locked_sha`
на sha этого коммита и журналирует событие «правка планки» с прежним и
новым sha и основанием. Отказывает именованно (без изменений), если:
изменений в каталоге нет; есть изменения за его пределами; лок ещё не
стоял; `--reason` пуст; обязательный прогон `acceptance_tests/` не
«OK» (кроме падений, промаркированных «Красен до реализации»/«Зелёный
с рождения» — тем же разбором, что выход из `tests_writing`). Не
оценивает существо правки (это чек-лист ревьювера) и не запускает
агентов. Больше одной правки в скользящем окне последних 5 задач
пульта, дошедших до фиксации лока (program-wide), поднимает алерт
«планка девальвируется» (kind=threshold) сразу после записи события.

`amend-tests <id> --reason "<основание>" --from-branch` (SPEC
01M287TPG0HAVXS8CHBCY679WN) — источник правки не worktree, а
расхождение содержимого `acceptance_tests/` между `tests_locked_sha` и
головой артефактной ветки (правка, унесённую автокоммитом шага роли в
обход `amend-tests`, легализует эта форма): при расхождении журналирует
отличающиеся файлы и сдвигает лок на голову ветки без нового коммита
(содержимое уже там); без расхождения отказывает («нет расхождения»).
Без флага `--from-branch` поведение команды прежнее (сверка с worktree).

Модули пакета (T015; здесь — только разбор argv и таблица команд):
  config    пути и константы; все обращения к ним идут через модуль
  store     БД, миграции схемы, журнал шагов, смена состояния
  yamlmini  разбор подмножества YAML: frontmatter и roles.yaml
  artifacts frontmatter артефактов и свежесть вердикта ревьювера
  roles     карта исполнителей из roles.yaml: состав скилов роли
  targets   декларация целевых проектов из targets.yaml
  projects  каталог проекта в .artel/: структура target'а
  gitcmd    вызовы git и вопросы к ветке задачи
  fixation  hash-фиксация артефактов на переходах FSM (A2b, ADR-0003 п.15)
  acceptance прогон и сводка приёмочных тестов задачи (A4, tasks/T023)
  ci        статус CI головного коммита ветки задачи (`gh`)
  agent_log логи прогонов, перекачка вывода агента (OutputPump)
  spend     разбор события со стоимостью шага и учёт в spent_usd
  review    сборка ревью-пакета (артефакты + diff под потолками)
  budget    потолок задачи: из SPEC, блокировка run, реакция после шага
  fsm       advance по артефактам, approve/reject Оператора
  runner    запуск агента шага: промпт, попытки, исход
  auto      цикл run+advance до места, где нужен человек
  cleanup   kill switch и уборка хвостов задачи
  release   операторское снятие lease задачи, независимо от свежести (T062)
  answer    канал ответа Оператора на эскалацию: ANSWER-n.md (T075)
  pause     штатная и жёсткая (--now) приостановка задачи: pause/resume (T070, T074)
  catalog   каталог задач: init, new, status, show, log
  alerts    таблица alerts: incident|threshold|trigger, ack с решением (A3)
  doctor    pre-flight, recovery-сверка, сироты, смоук CLI/изоляции (A3)
  version   пин CLI, фактическая версия, версия схемы артефактов (T030)
  canary    синтетический прогон конвейера в эфемерном клоне, метрики,
            per-task бейзлайн, изоляция пула от ролей (v2,
            01M1NEEWH5K1XPFRDGRMPYSBXJ; v1 — T065)
  prune     retention-политика: .artel/logs/, архивация alerts (T073)
  dry_run   сухой прогон приёмки: read-only предпросмотр без исполнения
            (SPEC 01M1GJ3ZP1YGG5QRB6FQ44NN8D)
  amend     штатная правка зафиксированной планки приёмки: коммит,
            лок, журнал, порог «планка девальвируется» (ADR-0012,
            SPEC 01M1HNNHDMP2C1AJTH5QF1BTN2)
  zone_lock занятость зоны на старте кода: предусловие первого шага
            developer, снятие ожидания и очередь Оператором
            (SPEC 01M1P9QAG65GVF69YJEV0V18D9)
  venv      `.artel/venv` пульта: создание/синхронизация с
            `requirements.lock`, идемпотентно (SPEC
            01M1REVEZ1HESMJ7AFD5A9MEJ8)
  notes     команда `note`: строка в копилку/бэклог/очередь изолированным
            коммитом от origin/main, повтор non-fast-forward, удержание
            коммита при сетевом отказе (tasks/01M1VBEHTDYPK3E4RRFHWYYYW3);
            команда `doc-commit`: документ `docs/**` или конфигурация
            Оператора целиком тем же механизмом, со сверкой базы с пином
            (tasks/01M2XMCG167615YS9EZD9TYJWV)
  watch     дозор событий журнала (steps/alerts) для сессии Оператора,
            read-only, без lease (SPEC 01M1VBEKRN0GA029J98S0K2DAQ)
"""
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

# Файл живёт двумя жизнями: модуль пакета (`from orchestrator import artel` в
# тестах) и скрипт (`python3 orchestrator/artel.py <cmd>` — так его зовут
# Оператор и документация). У скрипта нет пакета-родителя, поэтому импорт
# только абсолютный, а корень репозитория кладётся в sys.path руками:
# у запущенного файла в нём лежит orchestrator/, а не корень.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, stack  # noqa: E402

# Самовыбор интерпретатора (SPEC 01M1SHK3MD4ZF9NYXSCT67J8AP): `python3` из
# PATH зависит от профиля оболочки (pyenv инициализируется только в
# интерактивном шелле) — в неинтерактивной login-оболочке (ассистент, cron,
# хуки) он резолвится в системный интерпретатор ниже `stack.REQUIRED_PYTHON`,
# и безусловный импорт модулей пульта ниже (синтаксис 3.10+, например
# `X | None` в `orchestrator/doctor.py`) падает `TypeError` из глубины
# импорта вместо именованного отказа. Проверка стоит ЗДЕСЬ — до этого
# импорта и до исполнения любого `def` этого файла с таким синтаксисом
# (`_tz_arg` ниже несёт `-> str | None`) — код проверки сам не использует
# `X | None`/`match` (требование 1).
#
# `stack.REQUIRED_PYTHON` читается прямым импортом, не дублируется: сам
# `stack.py` (и `config.py`, от которого он зависит) держится 3.9-совместимым
# специально ради этого (требование 2, комментарий у `stack.REQUIRED_PYTHON`).
_REEXEC_MARKER_ENV = "ARTEL_PYTHON_REEXEC"


def _venv_python_path():
    return Path(config.VENV_DIR) / "bin" / "python"


def _venv_python_version(python_path):
    """Версия интерпретатора `python_path` парой (major, minor) — `None`,
    если вызов не удался или вывод не разобрался (venv битый/чужой)."""
    try:
        result = subprocess.run(
            [str(python_path), "-c",
             "import sys; print(sys.version_info[0], sys.version_info[1])"],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    parts = result.stdout.split()
    if len(parts) != 2:
        return None
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def _refuse_unsupported_interpreter():
    """Требование 4: именованный отказ одной строкой, код выхода 2 — не
    молчаливый `TypeError` из глубины импорта."""
    version_text = ".".join(str(p) for p in sys.version_info[:3])
    required_text = ".".join(str(p) for p in stack.REQUIRED_PYTHON)
    print(
        "нужен Python {0}+, найден {1} ({2}): создай venv: artel.py "
        "venv-sync".format(required_text, version_text, sys.executable),
        file=sys.stderr)
    sys.exit(2)


def _ensure_supported_interpreter():
    """Требования 3-5: текущий интерпретатор ниже `stack.REQUIRED_PYTHON` —
    перезапуск под `.artel/venv/bin/python`, если он пригоден и рекурсии ещё
    не было; иначе именованный отказ вместо `TypeError`."""
    if tuple(sys.version_info[:2]) >= stack.REQUIRED_PYTHON:
        return
    if os.environ.get(_REEXEC_MARKER_ENV):
        _refuse_unsupported_interpreter()
        return
    venv_python = _venv_python_path()
    venv_version = (_venv_python_version(venv_python)
                    if venv_python.is_file() else None)
    if venv_version is None or venv_version < stack.REQUIRED_PYTHON:
        _refuse_unsupported_interpreter()
        return
    os.environ[_REEXEC_MARKER_ENV] = "1"
    os.execv(str(venv_python), [str(venv_python), sys.argv[0]] + sys.argv[1:])


_ensure_supported_interpreter()

from orchestrator import (amend, answer, auto, budget, canary, catalog,  # noqa: E402
                          cleanup, doctor, dry_run, fsm, lease, liveness,
                          notes, pause, pin, pool_seal, projects, prune,
                          release, report, runner, store, venv, version,
                          watch, workspace, zone_lock)


# Отвязка `run`/`auto` от процесса сессии Оператора (SPEC
# 01M1NWCHVTYQ0M8PCJ1YJ2N78P) — детали см. SPEC.md этой задачи. `--attach`
# сохраняет прежнее поведение (передний план, без отвязки); без флага
# команда порождает себя же отдельным процессом ОС (`start_new_session`)
# и сразу возвращает управление, напечатав pid/лог/подсказку.

_CYCLE_FLAGS_RUN = ("--attach",)
_CYCLE_FLAGS_AUTO = ("--attach", "--wait-zone")


def _task_id_and_attach(rest: list, usage: str,
                        known: tuple = _CYCLE_FLAGS_RUN) -> tuple:
    """Hotfix №22 (11.09): неизвестный флаг — отказ с текстом, а не
    молчаливое проглатывание (`auto <id> --wait-zone` дважды «успешно»
    стартовал без ожидания зоны, пока флага в разборе не было)."""
    unknown = [a for a in rest if a.startswith("--") and a not in known]
    if unknown:
        sys.exit(f"неизвестный флаг {unknown[0]!r}; использование: {usage}")
    attach = "--attach" in rest
    positional = [a for a in rest if not a.startswith("--")]
    if not positional:
        sys.exit(usage)
    return positional[0], attach


def _launch_detached(cmd: str, task_id: str, extra: tuple = ()) -> None:
    """R1-F3 (REVIEW.md итерации 1): до отвязки — дешёвая проверка
    `lease.is_live`, не авторитетное взятие lease (тем ниже и остаётся,
    внутри спавненного процесса, через `lease.run_locked`). Без неё
    повторный `run`/`auto` при уже идущем цикле раньше отказывал СИНХРОННО
    прямо на экране, а после детача молча печатал бы «отвязан: pid …» и
    сразу же падал бы внутри свежего процесса — отказ был бы виден только
    в его логе. Гонка (lease освобождается/занимается между этой проверкой
    и спавном) не авторитетна и не обязана быть — тело `run_locked` внутри
    спавненного процесса решает по факту, эта проверка только возвращает
    немедленную обратную связь на очевидный случай."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    if lease.is_live(conn, task_id):
        row = store.lease_row(conn, task_id)
        sys.exit(f"[{task_id}] задачу уже ведёт живой lease "
                 f"(session_id={row['session_id']}, pid={row['pid']}, "
                 f"host={row['hostname']}) — не запускаю второй отвязанный "
                 f"процесс; подожди её или `artel.py stop {task_id}`")
    config.LOGS.mkdir(parents=True, exist_ok=True)
    prefix = f"{task_id}-{cmd}-"
    used = [int(p.stem[len(prefix):]) for p in config.LOGS.glob(f"{prefix}*.log")
           if p.stem[len(prefix):].isdigit()]
    n = max(used, default=0) + 1
    log_path = config.LOGS / f"{prefix}{n}.log"
    log_fh = open(log_path, "ab", buffering=0)
    try:
        proc = subprocess.Popen(
            # `-u`: stdout к файлу (не к терминалу) иначе блочно
            # буферизуется питоном — маркер старта цикла осел бы в
            # буфере до конца процесса, лог выглядел бы пустым живьём
            # (AC-3, «наблюдать: artel.py log <id>» обязан видеть
            # прогресс, не только финал).
            # Hotfix №22 (11.09): флаги команды (`--wait-zone`) едут в
            # дочерний процесс — иначе отделённый цикл терял их молча.
            [sys.executable, "-u", str(Path(__file__).resolve()), cmd,
             task_id, *extra, "--attach"],
            stdout=log_fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True)
    finally:
        log_fh.close()
    print(f"[{task_id}] {cmd} отвязан от сессии: pid {proc.pid}")
    print(f"  лог: {log_path}")
    print(f"  наблюдать: artel.py log {task_id}")


def _cmd_run_or_detach(rest: list) -> None:
    task_id, attach = _task_id_and_attach(rest, "run <id> [--attach]")
    if attach:
        runner.cmd_run(task_id)
        return
    _launch_detached("run", task_id)


def _cmd_auto_or_detach(rest: list) -> None:
    task_id, attach = _task_id_and_attach(
        rest, "auto <id> [--attach] [--wait-zone]", known=_CYCLE_FLAGS_AUTO)
    wait_zone = "--wait-zone" in rest
    if attach:
        auto.cmd_auto(task_id, wait_zone=wait_zone)
        return
    _launch_detached("auto", task_id,
                     extra=("--wait-zone",) if wait_zone else ())


def _cmd_stop(task_id: str) -> None:
    """Штатная остановка отвязанного цикла (SPEC требование 5, AC-9):
    SIGTERM держателю lease — тот же адрес, что уже несёт AC-6 (lease.pid
    отвязанного процесса, не короткоживущей команды).

    Чужой host не трогаем — тем же приёмом различения, что уже применяют
    `cleanup._cmd_kill`/`doctor.check_leases`: pid на другом хосте не наш
    для отправки сигнала, даже случайное числовое совпадение адресовало
    бы посторонний процесс.

    Адресация — по lease, не по имени команды: `_cmd_stop` не знает и не
    спрашивает, `run` держит lease или `auto` — доигровка текущего шага
    гарантирована только для `auto` (`orchestrator/auto.py::_on_sigterm`
    ставит обработчик на границе между шагами), голый отвязанный `run`
    такого обработчика не ставит и обрывается немедленно тем же
    сигналом (см. модульный докстринг выше и `docs/operator-session.md`)."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    row = store.lease_row(conn, task_id)
    if row is None:
        sys.exit(f"[{task_id}] lease не найден — нечего останавливать")
    if row["hostname"] != socket.gethostname():
        sys.exit(f"[{task_id}] lease держит host {row['hostname']}, не "
                 f"этот ({socket.gethostname()}) — останови оттуда")
    if not liveness._pid_alive(row["pid"]):
        sys.exit(f"[{task_id}] процесс цикла (pid={row['pid']}) уже не "
                 f"существует")
    try:
        os.kill(row["pid"], signal.SIGTERM)
    except ProcessLookupError:
        sys.exit(f"[{task_id}] процесс цикла (pid={row['pid']}) уже не "
                 f"существует")
    print(f"[{task_id}] stop: SIGTERM отправлен pid={row['pid']} — "
          f"`auto` доиграет текущий шаг и завершится сам; голый `run` "
          f"обработчика не ставит и завершится немедленно")


def _refuse_if_worktree() -> None:
    """Инвариант T056: пульт исполняется только из главной копии, не из
    git-worktree роли (`.artel/worktrees/<id>`, T045). До T056 запуск
    `artel.py` с cwd внутри worktree резолвил `config.ROOT` туда же и
    на ходу заводил там паразитную пустую `.artel/state.db` — инцидент
    28.08 (T052, T055): читающая команда над такой БД лжёт, мутирующая
    исполнилась бы мимо настоящего пульта. Признак worktree — `ROOT/.git`
    файл-ссылка (`gitdir: <main>/.git/worktrees/<id>`), а не каталог;
    у тестовых песочниц (`config.ROOT` во временном каталоге без `.git`)
    признак не срабатывает — их поведение не меняется.
    """
    git_path = config.ROOT / ".git"
    if not git_path.is_file():
        return
    marker = "gitdir: "
    line = git_path.read_text(encoding="utf-8").strip()
    gitdir = line[len(marker):] if line.startswith(marker) else ""
    suffix = "/.git/worktrees/"
    idx = gitdir.find(suffix)
    main_copy = gitdir[:idx] if idx != -1 else "?"
    sys.exit(
        f"[инвариант] {config.ROOT} — git-worktree, не главная копия "
        f"репозитория: пульт исполняется только из главной копии. "
        f"Перезапусти команду из {main_copy}."
    )


def _tz_arg(rest: list) -> str | None:
    """Значение флага `--tz new "<название>" --tz <файл>` либо None, если
    флага нет. Флаг без значения (последним аргументом) — понятный отказ,
    не IndexError из голого `rest[rest.index("--tz") + 1]`."""
    if "--tz" not in rest:
        return None
    idx = rest.index("--tz")
    if idx + 1 >= len(rest):
        sys.exit("--tz требует путь к файлу ТЗ следующим аргументом.")
    return rest[idx + 1]


_NEW_USAGE = 'new "<название>" [--tz <файл>]'


def _parse_new_args(rest: list) -> tuple | None:
    """Разбор argv `new` до вызова `catalog.cmd_new` (tasks/T102/SPEC.md):
    нераспознанное (лишний позиционный, неизвестный флаг, название с `-`)
    отказывает ДО расходования номера задачи и создания ветки — сегодня
    `rest[0]` берёт первый токен названием безусловно, а всё остальное
    молча теряется (T097 — «--help» стало названием, T098/T099 — путь
    ТЗ, переданный позиционно, проигнорирован).

    Возвращает `(title, tz_path)` либо `None` — сигнал «задачу не заводим»
    (пустой `rest` или `-h`/`--help`: справка, не ошибка)."""
    if not rest or rest[0] in ("-h", "--help"):
        print(_NEW_USAGE)
        return None
    title = rest[0]
    if title.startswith("-"):
        sys.exit(f"Нераспознанный аргумент: {title}\n{_NEW_USAGE}")
    tz_path = _tz_arg(rest)
    remainder = rest[1:]
    if "--tz" in remainder:
        idx = remainder.index("--tz")
        remainder = remainder[:idx] + remainder[idx + 2:]
    if remainder:
        sys.exit(f"Нераспознанный аргумент: {remainder[0]}\n{_NEW_USAGE}")
    return title, tz_path


def _k_arg(rest: list) -> int:
    """Значение флага `canary --k <N>` — тот же приём отказа, что и
    `_tz_arg` (флаг без значения/нечисловое значение — именованный
    отказ, не голый исключение)."""
    if "--k" not in rest:
        sys.exit("canary: нужен параметр --k <число> (SPEC "
                 "01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 1)")
    idx = rest.index("--k")
    if idx + 1 >= len(rest):
        sys.exit("--k требует целое число следующим аргументом.")
    try:
        return int(rest[idx + 1])
    except ValueError:
        sys.exit(f"--k требует целое число, получено {rest[idx + 1]!r}.")


def _sha_arg(rest: list) -> str | None:
    """Значение флага `canary --k <N> --sha <sha>` (SPEC
    01M2B6K02YVJBWE1JDWP85EJH0, требование 1, AC-2) — `None`, если флаг
    не передан вовсе: целевой sha берётся по умолчанию из головы
    `origin/<config.MAIN_BRANCH>` (`canary.cmd_canary`)."""
    if "--sha" not in rest:
        return None
    idx = rest.index("--sha")
    if idx + 1 >= len(rest):
        sys.exit("--sha требует значение следующим аргументом.")
    return rest[idx + 1]


def _cmd_canary(rest: list) -> None:
    """`canary pool-seal` (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW, требование 2)
    — отдельная подкоманда семейства `canary`, разбирается ДО `--k`:
    `pool-seal` не берёт `--k` и не заводит прогон."""
    if rest and rest[0] == "pool-seal":
        pool_seal.cmd_pool_seal()
        return
    canary.cmd_canary(k=_k_arg(rest), sha=_sha_arg(rest))


def _cmd_new(rest: list) -> None:
    parsed = _parse_new_args(rest)
    if parsed is None:
        return
    title, tz_path = parsed
    catalog.cmd_new(title, tz_path=tz_path)


def _reason_arg(rest: list) -> str | None:
    """Значение флага `--reason` команды `amend-tests <id> --reason
    "<основание>"`; `None` — флаг не передан вовсе. `amend.cmd_amend_tests`
    не различает «флага нет» и «флаг передан пустой строкой» — оба
    отказывают одинаково (SPEC AC-5), поэтому здесь достаточно вернуть
    `None`/пустую строку как есть, без специальной обработки."""
    if "--reason" not in rest:
        return None
    idx = rest.index("--reason")
    if idx + 1 >= len(rest):
        sys.exit("--reason требует основание правки следующим аргументом.")
    return rest[idx + 1]


def _cmd_pin(rest: list) -> None:
    """`pin --to <sha>` / `pin --to` (tasks/01M1NGFK3N6MRMYGCC09H975V3,
    ANSWER-1 п.5) — откат пина; отдельная команда от `pin-update`, не
    его подформа (`--to` — единственный поддерживаемый режим сегодня)."""
    if not rest or rest[0] != "--to":
        sys.exit('pin: используется как `pin --to <sha>` либо `pin --to` '
                 '(откат на последний зелёный прогон канарейки).')
    pin.cmd_pin_to(rest[1] if len(rest) > 1 else None)


def _cmd_pause(rest: list) -> None:
    """`pause <id>` (T070) либо `pause --now <id>` (T074) — флаг перед id,
    тем же местом разбора, что уже держит команду `pause` в таблице
    диспетчера ниже, а не второй записью в ней (SPEC T074 называет её
    формой той же команды `pause`, не отдельной)."""
    if rest and rest[0] == "--now":
        if len(rest) < 2:
            sys.exit("pause --now требует id задачи следующим аргументом.")
        pause.cmd_pause_now(rest[1])
        return
    pause.cmd_pause(rest[0])


def _role_restricted_command(cmd: str, rest: list) -> str | None:
    """Название команды, недоступной процессу роли, либо `None` (SPEC
    01M2B6K3EM7F2J72RC2F520Y2K, требование 3) — частичная замена
    `permissions.deny` курируемого слоя LLM-независимым признаком
    (`ARTEL_ROLE` в окружении, `orchestrator/runner.py::role_env`):
    `init`, `doctor --restore`, `canary pool-seal` отказывают роли до
    исполнения, остальные команды (включая голый `doctor`/`canary`) не
    затронуты."""
    if cmd == "init":
        return "init"
    if cmd == "doctor" and "--restore" in rest:
        return "doctor --restore"
    if cmd == "canary" and rest[:1] == ["pool-seal"]:
        return "canary pool-seal"
    return None


def _refuse_if_role_restricted(cmd: str, rest: list) -> None:
    role = os.environ.get(config.ARTEL_ROLE_ENV)
    if not role:
        return
    restricted = _role_restricted_command(cmd, rest)
    if restricted:
        sys.exit(f"artel.py {restricted}: команда недоступна процессу "
                 f"роли {role}")


def main() -> None:
    _refuse_if_worktree()
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    _refuse_if_role_restricted(cmd, rest)
    table = {
        "init": lambda: catalog.cmd_init(),
        "new": lambda: _cmd_new(rest),
        "status": lambda: catalog.cmd_status(),
        "show": lambda: catalog.cmd_show(rest[0]),
        "advance": lambda: fsm.cmd_advance(rest[0]),
        "workspace": lambda: workspace.cmd_workspace(rest[0]),
        "run": lambda: _cmd_run_or_detach(rest),
        "auto": lambda: _cmd_auto_or_detach(rest),
        "stop": lambda: _cmd_stop(rest[0]),
        "approve": lambda: fsm.cmd_approve(rest[0],
                                           rest[1] if len(rest) > 1 else None),
        "reject": lambda: fsm.cmd_reject(rest[0],
                                         rest[1] if len(rest) > 1 else ""),
        "answer": lambda: answer.cmd_answer(rest[0], rest[1]),
        "zones-extend": lambda: answer.cmd_zones_extend(rest[0], rest[1]),
        "kill": lambda: cleanup.cmd_kill(rest[0], confirmed="--yes" in rest[1:]),
        "release": lambda: release.cmd_release(rest[0]),
        "pause": lambda: _cmd_pause(rest),
        "resume": lambda: pause.cmd_resume(rest[0]),
        "log": lambda: catalog.cmd_log(rest[0]),
        "budget": lambda: budget.cmd_budget(rest[0],
                                            rest[1] if len(rest) > 1 else ""),
        "target-init": lambda: projects.cmd_target_init(rest[0]),
        "doctor": lambda: doctor.cmd_doctor("--restore" in rest, "--fix" in rest),
        "alert-ack": lambda: doctor.cmd_alert_ack(
            rest[0], rest[1] if len(rest) > 1 else ""),
        "version": lambda: version.cmd_version(),
        "canary": lambda: _cmd_canary(rest),
        "prune": lambda: prune.cmd_prune("--execute" in rest),
        "report": lambda: report.cmd_report(),
        "acceptance-dry-run": lambda: dry_run.cmd_acceptance_dry_run(rest[0]),
        "amend-tests": lambda: amend.cmd_amend_tests(
            rest[0], _reason_arg(rest), from_branch="--from-branch" in rest),
        "pin-update": lambda: pin.cmd_pin_update(rest[0]),
        "pin": lambda: _cmd_pin(rest),
        "zone-release": lambda: zone_lock.cmd_zone_release(rest[0]),
        "zone-reorder": lambda: zone_lock.cmd_zone_reorder(rest),
        "venv-sync": lambda: venv.cmd_venv_sync(),
        "note": lambda: notes.cmd_note(rest),
        "doc-commit": lambda: notes.cmd_doc_commit(rest),
        "watch": lambda: watch.cmd_watch(rest),
    }
    fn = table.get(cmd)
    if fn is None:
        sys.exit(f"Неизвестная команда {cmd}. Без аргументов — справка.")
    fn()


if __name__ == "__main__":
    main()
