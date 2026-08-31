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
  answer <id> <файл-с-ответом> | kill <id> | release <id> | pause <id> |
  resume <id> | log <id> | budget <id> <usd> | target-init <target> |
  doctor [--restore] | alert-ack <id> "<решение>" | version |
  canary <каталог-ТЗ> [--rewrite-baseline]

`pause <id>` (SPEC T070) — штатная приостановка: помечает задачу в БД,
не заводя нового состояния FSM; `run`/`auto` перед стартом агентного
шага видят пометку и останавливаются штатно, уже идущий шаг не
прерывается. `resume <id>` снимает пометку, сама шаги не запускает.
`kill`/`approve`/`reject`/`advance` пометку не читают и работают на
приостановленной задаче как обычно.

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
  pause     штатная приостановка задачи: pause/resume, без нового состояния FSM (T070)
  catalog   каталог задач: init, new, status, show, log
  alerts    таблица alerts: incident|threshold|trigger, ack с решением (A3)
  doctor    pre-flight, recovery-сверка, сироты, смоук CLI/изоляции (A3)
  version   пин CLI, фактическая версия, версия схемы артефактов (T030)
  canary    синтетический прогон конвейера, метрики, бейзлайн (T065)
"""
import sys
from pathlib import Path

# Файл живёт двумя жизнями: модуль пакета (`from orchestrator import artel` в
# тестах) и скрипт (`python3 orchestrator/artel.py <cmd>` — так его зовут
# Оператор и документация). У скрипта нет пакета-родителя, поэтому импорт
# только абсолютный, а корень репозитория кладётся в sys.path руками:
# у запущенного файла в нём лежит orchestrator/, а не корень.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (answer, auto, budget, canary, catalog,  # noqa: E402
                          cleanup, config, doctor, fsm, pause, projects,
                          release, runner, version, workspace)


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


def main() -> None:
    _refuse_if_worktree()
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    table = {
        "init": lambda: catalog.cmd_init(),
        "new": lambda: catalog.cmd_new(rest[0], tz_path=_tz_arg(rest)),
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
        "pause": lambda: pause.cmd_pause(rest[0]),
        "resume": lambda: pause.cmd_resume(rest[0]),
        "log": lambda: catalog.cmd_log(rest[0]),
        "budget": lambda: budget.cmd_budget(rest[0],
                                            rest[1] if len(rest) > 1 else ""),
        "target-init": lambda: projects.cmd_target_init(rest[0]),
        "doctor": lambda: doctor.cmd_doctor("--restore" in rest),
        "alert-ack": lambda: doctor.cmd_alert_ack(
            rest[0], rest[1] if len(rest) > 1 else ""),
        "version": lambda: version.cmd_version(),
        "canary": lambda: canary.cmd_canary(
            rest[0], rewrite_baseline="--rewrite-baseline" in rest),
    }
    fn = table.get(cmd)
    if fn is None:
        sys.exit(f"Неизвестная команда {cmd}. Без аргументов — справка.")
    fn()


if __name__ == "__main__":
    main()
