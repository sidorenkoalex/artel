---
task: 01M3HP7WAXKFK3GYZ3T6HX08M0
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Шум журнала и алертов: предупреждения один раз на пребывание в состоянии, черновик запроса на слияние после первого коммита

## Фаза A: гейт плана

1. **Покрытие требований.** Таблица PLAN полна: требования 1–12 разложены
   по шагам 1–6, дырок нет. Требование 11 (ручная уборка 121 инцидента)
   честно вынесено в шаг 6 сценарием для Оператора, а отсутствие команды
   массового закрытия — строкой «Предложения системе», как и требует SPEC.
2. **Размер шагов.** Шаги 1–4 — проверяемые единицы (узел + два бюджетных
   места; предполёт; адаптер; тесты), шаг 5 — регенерация карты, шаг 6 —
   действие Оператора. Ни микроопераций, ни «сделать всё».
3. **Конвенции и архитектура.** Размещение узла в `budget.py` обосновано
   и разрешено ANSWER-1 п. 2 (новый модуль не заводится, размещение за
   разработчиком); из четырёх файлов зоны только `budget.py` уже
   импортируется вторым потребителем на уровне модуля
   (`orchestrator/runner.py:16`), встречный импорт не заводится. Граница
   пребывания взята существующей идиомой `store.refusal_history`
   (`orchestrator/store.py:385-413`), новой колонки нет,
   `orchestrator/store.py` не правится — журнал остаётся только
   дописываемым. Зоны не расширялись: `orchestrator/fsm_advance.py` и
   `orchestrator/fsm.py` в диффе отсутствуют, требование 9 закрыто из
   `github_adapter.py`, как и предполагал раздел «Не входит» SPEC.
4. **«Влияние на систему» = дифф.** Заявлено ровно то, что изменено:
   три файла `orchestrator/` + два новых файла `tests/` + карта. Правок
   защищённых путей (`skills/`, `templates/`, `gates.yaml`, `.github/`),
   инвариантов и существующих тестов нет — `git diff --stat` подтверждает.
   Абзац «Возврат из `verifying`» описывает реальный коммит e64a5850
   (адреса фикстуры → loopback, инвариант 35 не трогался). Откат описан
   и верен: правки аддитивны, схема БД и формат записей не менялись.

Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Все три места идут через узел: `orchestrator/budget.py:158`, `:164`, `:294`, `orchestrator/runner.py:366`. |
| 2 | OK | Счётчика нет ни в записи, ни сводной строкой; узел только пишет или молчит. |
| 3 | OK | `key=detail` для двух текстовых мест, `key=None` (ключ = само действие) для «бюджет: предупреждение» — порог у записи один. |
| 4 | OK | `orchestrator/budget.py:68-75`: граница — последняя запись с префиксом `state -> ` журнала ЭТОЙ задачи, вырожденный случай «записи нет» = граница 0, как у `store.refusal_history`. |
| 5 | OK | Ветка исчерпания (`orchestrator/budget.py:263-282`) возвращает управление до порогового блока; «бюджет из SPEC отклонён»/«бюджет из SPEC»/`pre-flight FAILED` не тронуты. |
| 6 | OK | `print` во всех трёх местах стоит НИЖЕ вызова узла и от его ответа не зависит (`budget.py:160`, `:166`, `:296`, `runner.py:369`); ответ узла (`True`/`False`) вызывающие места не читают вовсе. |
| 7 | OK | Константы несут прежние литералы байт-в-байт: `"pre-flight WARNING"`, `"бюджет из SPEC не применён"`, `"бюджет: предупреждение"`. |
| 8 | OK | `orchestrator/github_adapter.py:113-124`: локальная сверка `_commits_over_base` стоит ДО `git push` и до `gh pr create`; пропуск — `store.journal` обычного уровня, без `_incident`/алерта, `draft_mr_created` не выставляется. `None` («git не ответил») в пропуск не превращается. |
| 9 | OK | Хук `_ensure_draft_mr_after_publish` на ветке УСПЕШНОГО push `ensure_head_in_origin` (`github_adapter.py:209`), а её зовёт рубеж `advance_gates/tests_writing.py::_origin_push_gate`. Проверил отдельно, что кодовую ветку до этого рубежа не публикует никто другой: `git push` кодовой ветки в `orchestrator/` есть только в `github_adapter.py:127/197` и `fsm_merge_gate.py:476/816` (остальные push — артефактная ветка, notes, snapshot), поэтому на первом проходе рубежа `local != remote` и черновик заводится. |
| 10 | OK | Отказ push/`gh` при наличии коммита не изменён — `Draft MR FAILED` + `_incident`; новый пропуск срабатывает только на положительном ответе git «ровно 0». |
| 11 | OK | PLAN шаг 6 даёт перечень номеров и `alert-ack` на каждый; `alerts.open_alerts(conn, "incident")` и колонки `source`/`message` в сценарии существуют (`orchestrator/alerts.py:110`, `orchestrator/store.py:925`). Отсутствие команды массового закрытия вынесено в «Предложения системе». |
| 12 | реализовано не так (частично) | Тесты заведены и зелены, все четыре названных SPEC модуля зелёные, ни один существующий тест не изменён и не удалён (диффа `tests/` сверх двух НОВЫХ файлов нет). Но один из семи случаев `tests/test_draft_mr_commits.py` заявленную мутацию не ловит — R1-F1. |

## Замечания

- **major — tests/test_draft_mr_commits.py:229-247 (заявка — строки 233-236) —
  `test_a_branch_identical_to_the_base_wakes_nobody` не ловит мутацию,
  которую заявляет, и заявка описывает неверное последствие.** Докстринг
  обещает: «Ловит мутацию: узел черновика зовётся на каждой успешной
  публикации без разбора — рубеж `merge_gate` … обращался бы к форджу на
  заведомо пустой ветке». Проверил исполнением: подменил
  `github_adapter._ensure_draft_mr_after_publish` на версию БЕЗ сверки
  `head == gitcmd.branch_head_sha(base)` (то есть ровно на заявленную
  мутацию) и прогнал класс — `Ran 3 tests … OK`, все три случая зелёные.
  Причина в том, что под мутацией до форджа дело не доходит: авторитетную
  сверку делает сама `ensure_draft_mr` (`orchestrator/github_adapter.py:120`),
  `_commits_over_base` отдаёт 0, и `gh` не зовётся — ассерты
  `assertEqual(self.gh_calls, [])` и `assertEqual(self.flag(), 0)` остаются
  верны. Это тот же довод, которым PLAN сам обосновывает устройство хука
  («АВТОРИТЕТНУЮ сверку несёт сама `ensure_draft_mr`»), — то есть
  докстринг противоречит плану. Последствие: единственный страж дешёвой
  сверки `head == base` снимается без единого красного теста, а её снятие —
  не безобидно: на ветке, равной базе, каждая успешная публикация начнёт
  дописывать в журнал `Draft MR пропущен: в ветке нет коммитов`, то есть
  ровно тот класс шума, который задача и лечит. Наблюдаемая разница под
  мутацией одна, я её снял пробой: журнал становится
  `['push (голова не в origin)', 'Draft MR пропущен: в ветке нет коммитов']`
  вместо `['push (голова не в origin)']`. Предложение: добавить в тест
  ассерт на эту разницу — `self.assertNotIn(github_adapter.DRAFT_MR_SKIPPED_ACTION,
  self.actions())` (проверено: он краснеет под мутацией и зелен на текущем
  коде) — и переписать вторую половину заявки так, чтобы она называла
  настоящее последствие (лишняя запись журнала на каждый approve, а не
  обращение к форджу). Либо, если дешёвая сверка признаётся избыточной
  рядом с проверкой в `ensure_draft_mr`, — убрать её вместе с тестом.
  Остальные шесть случаев этого файла и все девять случаев
  `tests/test_journal_warning_once.py` я сверил с их заявками поштучно,
  второго экземпляра класса не нашёл: две самые дешёвые к проверке заявки
  (`None` приравнен к нулю; ключ = текст вместо порога) подтверждаются
  прямо ассертами `len(self.push_calls) == 1` и
  `len(self.details(BUDGET_WARNING_ACTION)) == 1`.

- **minor — orchestrator/budget.py:74 — `key` сверяется со СТОРОННИМ
  полем записи (`row["detail"]`), а не с сохранённым ключом: любой
  будущий вызов, где `key != detail`, молча перестанет подавлять.**
  Сегодня оба текстовых места зовут узел с `key=detail`, а пороговое — с
  `key=None`, так что дефекта в поведении нет. Сценарий поломки: у
  `config.BUDGET_ALERT_RATIO` появляется второй порог (класс живёт в
  `docs/backlog.md:156`), вызывающий естественно передаёт
  `key=f"{ratio}"` — узел сравнивает этот ключ с текстом записи («…больше
  70% бюджета»), совпадения не будет никогда, и журнал снова получит
  запись на каждый шаг, причём молча и без красного теста. Предложение:
  либо сузить контракт явно (в докстринге и ассертом/проверкой:
  допустимо только `key is None` или `key == detail`), либо сверять по
  вычисляемому из записи ключу, а не по сырому `detail`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_draft_mr_commits.py:229-247 | Заявка «Ловит мутацию» ложна: подмена `_ensure_draft_mr_after_publish` на версию без сверки `head == base` оставляет класс зелёным (проверено прогоном), и заявленное последствие («обращался бы к форджу») неверно — `ensure_draft_mr` всё равно останавливает вызов | Сверка `head == base` снимается без красного теста; её снятие возвращает шум журнала (`Draft MR пропущен` на каждый approve при ветке, равной базе) | Добавить `self.assertNotIn(github_adapter.DRAFT_MR_SKIPPED_ACTION, self.actions())` и переписать вторую половину заявки на настоящее последствие; либо убрать сверку вместе с тестом |
| R1-F2 | open | orchestrator/budget.py:74 | `key` сверяется с `row["detail"]`, а не с сохранённым ключом — контракт «ключ ≠ текст» узлом не поддержан и отказывает молча | Второй порог бюджета (класс `docs/backlog.md:156`) с `key=f"{ratio}"` вернёт запись на каждый шаг, без красного теста | Сузить контракт явно (`key is None` либо `key == detail`, в докстринге и проверкой) или сверять по вычисляемому ключу записи |

## Вердикт

`changes_requested` — два пункта:

1. R1-F1 (major): дотянуть `test_a_branch_identical_to_the_base_wakes_nobody`
   до её собственной заявки (ассерт на отсутствие записи
   `DRAFT_MR_SKIPPED_ACTION`) и исправить текст заявки; либо убрать
   избыточную сверку `head == base` вместе с тестом.
2. R1-F2 (minor): явно сузить контракт `key` в `journal_warning_once`.

Код по существу требований 1–11 реализован верно, планка и все затронутые
модули зелёные; правок защищённых путей, ослабления тестов, гейтов и
инвариантов нет.

## Проверено исполнением

- `python3 -m unittest tests.test_draft_mr_commits tests.test_journal_warning_once -v` —
  18 тестов, OK.
- `python3 -m pytest -q -p no:cacheprovider tasks/01M3HP7WAXKFK3GYZ3T6HX08M0/acceptance_tests` —
  планка задачи: 10 passed, 4 subtests passed (совпадает с заявкой PLAN).
  Пометок `# AC-n: manual|skip` в планке нет — автогейт acceptance задачи
  не выключен; AC-1..AC-10 разложены по четырём файлам планки без дыр.
- `python3 -m unittest tests.test_github_adapter tests.test_fsm_draft_mr_reentry
  tests.test_spec_budget tests.test_runner_model_preflight
  tests.test_budget_live_lease_and_escalation tests.test_store_journal` —
  110 тестов, OK (четыре модуля требования 12 в их числе).
- `python3 -m unittest tests.test_step_cost tests.test_invariants
  tests.test_advance_guard tests.test_fsm_spec_gate_reject
  tests.test_budget_calibration_table tests.test_program_spend_reseed` —
  161 тест, OK (в том числе инвариант 35 и оба существующих читателя
  записи «бюджет: предупреждение», `tests/test_step_cost.py:841,850`).
- `python3 -m unittest tests.test_merge_gate_ci_wait tests.test_multitarget
  tests.test_multitarget_invariants tests.test_auto_cycle
  tests.test_acceptance_tests_flow tests.test_step_autocommit
  tests.test_git_fixation tests.test_runner_role_model
  tests.test_runner_wave_breaker tests.test_catalog_zone_overlap` —
  440 тестов, OK.
- `python3 -m unittest tests.test_amend tests.test_catalog_zone_overlap
  tests.test_detached_cycle tests.test_timeout_checkpoint tests.test_doctor` —
  255 тестов, OK (все оставшиеся модули, упоминающие `ensure_draft_mr`/
  `ensure_head_in_origin`, по `grep -rln` покрыты).
- Мутационная проба R1-F1: подмена `github_adapter._ensure_draft_mr_after_publish`
  на версию без сверки `head == base` → `DraftMrAtTheVerifyingRubiconTest`
  `Ran 3 tests … OK`; зонд журнала под той же мутацией показал
  `['push (голова не в origin)', 'Draft MR пропущен: в ветке нет коммитов']`,
  `gh: []`, `flag: 0`.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` —
  расхождение только в строке `built_at_sha` (1 строка), содержимое карты
  свежее; дерево восстановлено `git checkout -- docs/codebase-map.md`.
- `git diff --stat 6b8cee21…HEAD` — изменены только `orchestrator/budget.py`,
  `orchestrator/github_adapter.py`, `orchestrator/runner.py` и два НОВЫХ
  файла `tests/`; ни одного изменённого/удалённого ассерта существующих
  тестов, ни одной правки `skills/`, `templates/`, `gates.yaml`,
  `roles.yaml`, `.github/`, `docs/invariants.md`.

Читал сверх пакета (причины названы в замечаниях и таблице выше):
`orchestrator/github_adapter.py` целиком — проверить, что `base` и
`repo_context` посчитаны ДО вставленной сверки (требование 8);
`orchestrator/gitcmd.py` (`commits_behind`, `branch_head_sha`) — убедиться,
что переставленные аргументы дают именно «коммиты ветки сверх базы» и что
деградация к `None` реальна; `orchestrator/store.py`
(`task_steps`, `refusal_history`, `open_alerts`) — сверить порядок выборки
(без LIMIT, `ORDER BY id`) и идиому границы пребывания; вызывающие места
`_maybe_ensure_draft_mr`/`ensure_head_in_origin` в `orchestrator/fsm.py`,
`fsm_advance.py`, `fsm_merge_gate.py`, `advance_gates/tests_writing.py` —
проверить требование 9 на прямом пути; `orchestrator/alerts.py` — сверить
сигнатуру `open_alerts` из сценария PLAN шага 6.

## Предложения системе

- Заявка «Ловит мутацию» проверяется ревьювером глазами, и ложная заявка
  (R1-F1) выявляется только ручной подменой узла. `skills/test-authoring.md`
  стоило бы прямо потребовать от автора теста ПРОГНАТЬ заявленную мутацию
  и назвать в PLAN, что тест на ней покраснел, — ровно тем же приёмом,
  каким `skills/conventions-core.md` уже требует `git apply --check` для
  диффа по защищённому пути.
