#!/usr/bin/env python3
"""Артель, Фаза 0 — FSM-оркестратор (CLI).

Детерминированный конечный автомат; агенты думают внутри шага, между
шагами не думает никто. Все гейты Фазы 0 — ручные (approve/reject из CLI).

Состояния:
  spec_writing -> spec_gate -> tests_writing -> in_dev -> review -> acceptance -> merge_gate -> done
                     |                             ^________|  (changes_requested, <=3)
                     |                             ^___________ (acceptance reject, <=1)
  из любого: escalated (вопрос Оператору), killed.

`tests_writing` (A4, tasks/T023) — приёмочные тесты до кода, роль
test_author: `spec_gate` заводит её при approve, если SPEC не помечен
`skip_tests` и несёт AC-разметку критериев (`schema_version >= 2`); иначе
approve идёт прямо в `in_dev`, как до T023. Выход из `tests_writing` —
каждый AC-n получил тест либо пометку manual/skip/escalate
(`tasks/<id>/acceptance_tests/`); `escalate` уводит задачу в `escalated`
немедленно. После выхода каталог `acceptance_tests/` залочен фиксацией
(T021): правка после лока — отказ перехода `in_dev -> review`.

`approve` из escalated возвращает задачу в in_dev, а если эскалировал упавший
агент — в тот шаг, на котором он упал (см. escalated_from): чинить надо шаг,
а не откатывать готовую работу в разработку.

Бюджет задачи — жёсткий потолок: стоимость каждого запуска агента снимается
с финального события потока CLI и копится в spent_usd. На 70% бюджета —
предупреждение, на 100% — escalated и отказ запускать агента, пока Оператор
не поднимет потолок (`budget <id> <usd>`) или не закроет задачу (`kill`).

Потолок по умолчанию один на все задачи, но класс задачи виден аналитику
при постановке: `budget_usd` в frontmatter SPEC применяется к задаче один
раз, на переходе spec_writing -> spec_gate. Понижать потолок так можно,
поднимать — нет: значение выше DEFAULT_BUDGET_USD отвергается с
предупреждением, потому что поднять потолок вправе только Оператор
командой `budget` (инвариант 10). Ручное поднятие сильнее значения из
SPEC; кто задал потолок, помнит колонка budget_source.

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
  run <id> | auto <id> | approve <id> [sha] | reject <id> "<причина>" |
  answer <id> <файл-с-ответом> | kill <id> | release <id> |
  pause [--now] <id> | resume <id> | log <id> | budget <id> <usd> |
  target-init <target> | doctor [--restore] [--fix] | alert-ack <id> "<решение>" |
  version | canary <каталог-ТЗ> [--rewrite-baseline] | prune [--execute] |
  amend-tests <id> --reason "<основание>" | pin-update <sha main артели>

`pin-update <sha>` (A7, Stage1) — обновляет пин запущенной версии:
продвигает рабочее дерево и HEAD `config.ROOT` до `<sha>` main артели
(`git fetch` + `git merge --ff-only`), журналирует операторскую
идентичность и оба sha. `merge_gate -> done` (Stage0) НЕ двигает
`config.ROOT` сам — это единственный способ его продвинуть; `doctor`
только сообщает о расхождении (`check_root_pin`), не обновляет пин сам.

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
  canary    синтетический прогон конвейера, метрики, бейзлайн (T065)
  prune     retention-политика: .artel/logs/, архивация alerts (T073)
  dry_run   сухой прогон приёмки: read-only предпросмотр без исполнения
            (SPEC 01M1GJ3ZP1YGG5QRB6FQ44NN8D)
  amend     штатная правка зафиксированной планки приёмки: коммит,
            лок, журнал, порог «планка девальвируется» (ADR-0012,
            SPEC 01M1HNNHDMP2C1AJTH5QF1BTN2)
"""
import sys
from pathlib import Path

# Файл живёт двумя жизнями: модуль пакета (`from orchestrator import artel` в
# тестах) и скрипт (`python3 orchestrator/artel.py <cmd>` — так его зовут
# Оператор и документация). У скрипта нет пакета-родителя, поэтому импорт
# только абсолютный, а корень репозитория кладётся в sys.path руками:
# у запущенного файла в нём лежит orchestrator/, а не корень.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (amend, answer, auto, budget, canary, catalog,  # noqa: E402
                          cleanup, config, doctor, dry_run, fsm, pause, pin,
                          projects, prune, release, report, runner, version,
                          workspace)


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


def main() -> None:
    _refuse_if_worktree()
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    table = {
        "init": lambda: catalog.cmd_init(),
        "new": lambda: _cmd_new(rest),
        "status": lambda: catalog.cmd_status(),
        "show": lambda: catalog.cmd_show(rest[0]),
        "advance": lambda: fsm.cmd_advance(rest[0]),
        "workspace": lambda: workspace.cmd_workspace(rest[0]),
        "run": lambda: runner.cmd_run(rest[0]),
        "auto": lambda: auto.cmd_auto(rest[0]),
        "approve": lambda: fsm.cmd_approve(rest[0],
                                           rest[1] if len(rest) > 1 else None),
        "reject": lambda: fsm.cmd_reject(rest[0],
                                         rest[1] if len(rest) > 1 else ""),
        "answer": lambda: answer.cmd_answer(rest[0], rest[1]),
        "kill": lambda: cleanup.cmd_kill(rest[0]),
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
        "canary": lambda: canary.cmd_canary(
            rest[0], rewrite_baseline="--rewrite-baseline" in rest),
        "prune": lambda: prune.cmd_prune("--execute" in rest),
        "report": lambda: report.cmd_report(),
        "acceptance-dry-run": lambda: dry_run.cmd_acceptance_dry_run(rest[0]),
        "amend-tests": lambda: amend.cmd_amend_tests(rest[0], _reason_arg(rest)),
        "pin-update": lambda: pin.cmd_pin_update(rest[0]),
    }
    fn = table.get(cmd)
    if fn is None:
        sys.exit(f"Неизвестная команда {cmd}. Без аргументов — справка.")
    fn()


if __name__ == "__main__":
    main()
