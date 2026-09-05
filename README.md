# Артель

Мультиагентная система доведения запроса Оператора до смердженного MR.
Конвейер ролей-агентов, управляемый детерминированным конечным
автоматом; роли общаются материальными артефактами в git, автономия
дозируется политикой гейтов.

Документы: [design.md](docs/design.md) — механика (роли, скилы,
runtime, политика гейтов); [roadmap.md](docs/roadmap.md) — фазы,
задачи, экономика; [docs/adr/](docs/adr/) — решения (ADR-0003 —
целевые проекты, ADR-0004 — пульт и ассистент);
[docs/triggers.md](docs/triggers.md) — триггеры отложенных
механизмов; [docs/deferred/](docs/deferred/) — отложенное;
[docs/operator-gates.md](docs/operator-gates.md) — протокол ручных
гейтов Оператора; [docs/operator-session.md](docs/operator-session.md)
— контракт ассистентской сессии при Операторе;
[docs/retention.md](docs/retention.md) — что хранится вечно и что
чистит `prune`; [docs/retro/](docs/retro/) — дайджесты закрытых задач;
[docs/research/](docs/research/) — исследования (готовность к внешнему
проекту, 04.09).

## Где мы: артель ведёт себя как внешний целевой проект (A7)

Фаза 0 и Фаза A закрыты (13 и далее задач полного цикла «запрос →
смерженный MR» на самом пульте, критерий выхода — roadmap §2). Задача
A7 (сентябрь) перевела пульт на единый контур целевого проекта для
любого target, включая саму артель: пульт исполняется из главной
копии с **пином** запущенной версии (`pin-update`, ADR-0013),
артефакты каждой задачи живут в артефактной ветке `artifact/<id>` и
снапшотах `refs/artifacts/<id>`, код — в ветке `task/<id>-<slug>` и
worktree `.artel/worktrees/<id>`. Волна 04.09 закрыла регрессии нового
контура (реестр — roadmap §4): свежесть против origin/main, автогейт
приёмки из артефактной ветки, ANSWER в брифе ревьювера, WIP-чекпоинт
по зоне роли, изоляция тестов от настоящего репозитория, оценка
объёма задачи и деление на гейте SPEC, курс токенов для частичной
стоимости шага. Следующая линия — B: подключение внешнего проекта
(исследование `docs/research/2026-09-04-external-target-readiness.md`).

Ролей конвейера четыре: analyst (SPEC из свободного ТЗ), test_author
(приёмочные тесты до кода, планка залочена фиксацией), developer,
reviewer. Гейты spec_gate и merge_gate — ручные (`approve`/`reject`
по sha); acceptance умеет автопроход по политике gates.yaml (ADR-0007,
ADR-0010), manual/skip-критерии возвращают приём человеку. Один токен
на все роли (слоты в roles.yaml раздельные; разделение PAT — по
триггеру №3 из docs/triggers.md).

## Структура

```
orchestrator/  модульный пакет FSM-оркестратора + artel.py (CLI)
tests/         инварианты и юнит-тесты оркестратора
templates/     шаблоны артефактов (SPEC, PLAN, REVIEW, TEST_REPORT)
skills/        скилы ролей (процедурные знания, подключаются к промптам)
tasks/<id>/    артефакты смерженных задач (живые задачи — в ветках artifact/<id>)
docs/          design, roadmap, invariants, adr/, audits/, deferred/, triggers,
               operator-gates, operator-session, retention, reference/, research/, retro/
scripts/       guard.py — валидатор структуры артефактов; codebase_map.py — карта кода
sandbox/       Dockerfile песочницы агента (в строй — задача B3)
gates.yaml     политика гейтов (ADR-0007): acceptance умеет auto, читает orchestrator/gates.py
roles.yaml     карта исполнителей и слоты токенов
targets.yaml   целевые проекты: forge, база, токен, no_paths, гейт мержа
.artel/        состояние вне git: БД, логи, worktrees задач, каталоги проектов, слой ролей, ТЗ Оператора (tz/)
```

## Быстрый старт

```bash
python3 orchestrator/artel.py init                 # БД, слой ролей, посев
python3 orchestrator/artel.py target-init artel    # каталог проекта в .artel/
python3 orchestrator/artel.py new "Название" --tz tz.md   # ТЗ Оператора → analyst пишет SPEC
python3 orchestrator/artel.py auto <id>            # цикл до ближайшего гейта (фоном)
python3 orchestrator/artel.py approve <id> <sha>   # гейт: SPEC / приёмка / merge — по sha
python3 orchestrator/artel.py answer <id> ANSWER.md   # ответ на эскалацию
python3 orchestrator/artel.py status               # доска задач
python3 orchestrator/artel.py doctor [--fix]       # диагностика; --fix — уборка по явной команде
python3 orchestrator/artel.py pin-update <sha>     # продвинуть пин запущенной версии
```

Остальные команды (`pause [--now]`, `resume`, `release`, `budget`,
`amend-tests`, `kill`, `log`, `canary`, `prune`) — в справке
`artel.py` без аргументов. Команды пульта запускаются только из
главной копии (не из worktree); циклы `run`/`auto` — фоновым процессом.

Гейты verifying и merge требуют зелёного CI ветки: GitHub Actions
запускает джобы только в пределах бесплатной квоты минут и лимита
расходов аккаунта (Settings → Billing & plans); при нулевом лимите
после исчерпания квоты джобы падают без единого шага, и мержи встают.

## Инварианты (не нарушаются ни в одной фазе)

1. Всё детерминированное — код и пайплайны, не LLM. Оркестратор не думает.
2. Каждая передача между ролями — файл в `tasks/<id>/`, не контекст чата.
3. У каждого цикла — числовой лимит; после лимита — Оператор, не ретрай.
4. Молчание ≠ согласие: ручной гейт не «автопроходит» по таймауту.
5. Потолок задачи = её денежный бюджет; журнал шагов пишется всегда.

Полный реестр с кодирующими тестами — `docs/invariants.md`
(ослабление — только Оператор через ADR, см. ADR-0002).

## Статус

После A7 (артель как внешний target), волна регрессий нового контура —
04.09.2026; 114 задач done. Подробности и очередь — roadmap §4.
