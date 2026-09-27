---
task: 01M3HP7WAXKFK3GYZ3T6HX08M0
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Шум журнала и алертов: предупреждения один раз на пребывание в состоянии, черновик запроса на слияние после первого коммита

## Фаза A: гейт плана

1. **Покрытие требований.** Таблица PLAN по-прежнему полна (требования
   1–12 по шагам 1–6), итерация 2 её не тронула и не должна была: правки
   этой итерации — внутри шагов 1 и 4.
2. **Размер шагов.** Без изменений с итерации 1: шаги 1–4 — проверяемые
   единицы, шаг 5 — карта, шаг 6 — действие Оператора.
3. **Конвенции и архитектура.** Зоны не расширены: правились
   `orchestrator/budget.py` и два НОВЫХ файла `tests/`. Защищённые пути
   (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`,
   `docs/invariants.md`) не тронуты — `git diff --stat 6b8cee21...HEAD`
   даёт ровно `orchestrator/budget.py`, `orchestrator/github_adapter.py`,
   `orchestrator/runner.py`, `docs/codebase-map.md` и два новых файла
   тестов.
4. **«Влияние на систему» = дифф.** Новый абзац PLAN «Итерация 2»
   соответствует факту построчно, включая две проверяемые заявки:
   «содержимое карты не изменилось, расхождение только в `built_at_sha`»
   — подтвердил регенерацией (см. «Проверено исполнением»), и «ослаблений
   нет» — в диффе `tests/` этой итерации ни одной удалённой или
   изменённой строки `assert`, только добавленные (docstring
   `test_a_branch_identical_to_the_base_wakes_nobody` переписан, ассерты
   прежние плюс один новый).

Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Три места через узел: `orchestrator/budget.py:177`, `:183`, `:313`, `orchestrator/runner.py:366`. |
| 2 | OK | Счётчика нет ни в записи, ни сводной строкой — узел только пишет либо молчит (`budget.py:90-96`). |
| 3 | OK | `key=detail` у двух текстовых мест, `key=None` («ключ = само действие») у «бюджет: предупреждение»; контракт `key` теперь сужен явно и отказывает громко (`budget.py:80-84`) — закрытие R1-F2. |
| 4 | OK | `budget.py:85-89`: граница — последняя запись с префиксом `state -> ` журнала ЭТОЙ задачи; `store.task_steps` (`store.py:624-627`) отдаёт весь журнал задачи `ORDER BY id`, без LIMIT, а `set_state` (`store.py:473`) пишет ровно `f"state -> {state}"` — префикс сверки и запись совпадают. |
| 5 | OK | Ветка исчерпания возвращает управление до порогового блока (`budget.py:284-303`); «бюджет из SPEC отклонён», «бюджет из SPEC», `pre-flight FAILED` идут прежним `store.journal`. |
| 6 | OK | `print` во всех трёх местах ниже вызова узла и от его ответа не зависит (`budget.py:179`, `:185`, `:315`, `runner.py:369`). |
| 7 | OK | Литералы прежние: `"pre-flight WARNING"`, `"бюджет из SPEC не применён"`, `"бюджет: предупреждение"`. Итерация 2 текстов не касалась. |
| 8 | OK | `github_adapter.py:113-125`: `_commits_over_base` стоит ДО `git push` и до `gh pr create`; пропуск — `store.journal` обычного уровня без `_incident`, `draft_mr_created` не выставляется; `None` в пропуск не превращается (`:44` — `gitcmd.commits_behind(base, branch)` = `rev-list --count base..branch`, то есть коммиты ветки сверх базы). |
| 9 | OK | Хук `_ensure_draft_mr_after_publish` (`github_adapter.py:222`) на ветке УСПЕШНОГО push `ensure_head_in_origin`; ветка «sha уже совпал» осталась no-op. Дешёвая сверка `head == база` (`:253-254`) сохранена и теперь охраняется тестом — см. R1-F1. |
| 10 | OK | Отказ push/`gh` при наличии коммита не изменён: `Draft MR FAILED` + `_incident` (`github_adapter.py:129-133`, `:142-147`). |
| 11 | OK | PLAN шаг 6 даёт перечень номеров и `alert-ack` на каждый; отсутствие команды массового закрытия — строкой «Предложения системе». |
| 12 | OK | Оба новых файла зелены (19 тестов), четыре названных SPEC модуля зелены, ни один существующий тест не изменён и не удалён. Обе заявки «Ловит мутацию» этой итерации проверил исполнением — под названной мутацией тест краснеет (было `реализовано не так` на итерации 1, R1-F1 закрыт). |

## Замечания

Новых замечаний нет; обе записи прошлой итерации закрыты (см. реестр).

Оценка закрытий:

- **R1-F1 (`accepted`).** Разработчик взял первый из двух предложенных
  путей: сверка `head == база` оставлена, а тест дотянут до собственной
  заявки — `tests/test_draft_mr_commits.py:247-248`. Проверил не текстом,
  а той самой мутацией: подменил
  `github_adapter._ensure_draft_mr_after_publish` на копию БЕЗ двух строк
  сверки и прогнал `DraftMrAtTheVerifyingRubiconTest` — теперь
  `FAILED (failures=1)` ровно на новом ассерте (`'Draft MR пропущен: в
  ветке нет коммитов' unexpectedly found in ['push (голова не в origin)',
  'Draft MR пропущен: в ветке нет коммитов']`), на итерации 1 та же
  подмена давала `Ran 3 tests … OK`. Переписанная заявка
  (`:234-239`) называет последствие верно: до форджа мутация не доходит
  (останавливает `ensure_draft_mr`), а цена — запись журнала на каждый
  approve `merge_gate`; это ровно то, что показал мой зонд журнала.
- **R1-F2 (`accepted`).** Контракт сужен явно: `budget.py:80-84` —
  `ValueError` на любом `key`, который не `None` и не равен `detail`,
  докстринг (`:60-78`) называет два допустимых значения и причину (носителя
  ключа в журнале нет). Отказ от второго пути («сверять по вычисляемому
  ключу») обоснован верно: из записи восстановим только `detail`, колонка
  под ключ потребовала бы `orchestrator/store.py`, который в зоны не
  входит (ANSWER-1 п. 1). Проверил, что новый тест держит контракт
  мутацией: подменил `budget.journal_warning_once` на копию без охранного
  условия — `test_a_key_other_than_the_text_is_refused_loudly` краснеет
  (`AssertionError: ValueError not raised`), на коде ветки зелен. Оба
  сегодняшних вызывающих места под контракт попадают без исключений
  (`budget.py:177`, `:183` — `key=detail`; `:313` — `key=None`;
  `runner.py:366` — `key=detail`), так что новый отказ живого пути не
  задевает: 190 тестов затронутых модулей зелены.
- **Класс R1-F1 («заявка мутации не проверена прогоном»), а не
  экземпляр.** Второго экземпляра в диффе не нашёл: обе новые заявки этой
  итерации я прогнал сам (выше), а остальные 17 случаев двух файлов
  сверил с заявками поштучно на итерации 1 и заново — на итерации 2 они не
  менялись (в диффе `tests/` только добавленные строки).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_draft_mr_commits.py:229-248 | Заявка «Ловит мутацию» была ложна: подмена `_ensure_draft_mr_after_publish` на версию без сверки `head == base` оставляла класс зелёным | Сверка `head == base` снималась без красного теста, а её снятие возвращает шум журнала (`Draft MR пропущен` на каждый approve при ветке, равной базе) | Закрыто первым путём: сверка оставлена, добавлен `assertNotIn(DRAFT_MR_SKIPPED_ACTION, self.actions())` (`:247-248`), заявка переписана на настоящее последствие. **Итерация 2 (reviewer):** `accepted` — мутационный зонд повторён, класс теперь краснеет ровно этим ассертом (на итерации 1 был `OK`) |
| R1-F2 | accepted | orchestrator/budget.py:80-84 | `key` сверялся с `row["detail"]`, а не с сохранённым ключом — контракт «ключ ≠ текст» узлом не поддерживался и отказал бы молча | Второй порог бюджета с `key=f"{ratio}"` вернул бы запись на каждый шаг, без красного теста | Закрыто сужением контракта: `ValueError` на третьем значении, докстринг `:60-78` называет допустимые `key=None`/`key=detail` и причину; тест `test_a_key_other_than_the_text_is_refused_loudly`. **Итерация 2 (reviewer):** `accepted` — без охранного условия тест краснеет (`ValueError not raised`), все четыре сегодняшних вызова контракту соответствуют, затронутые модули зелены |

## Вердикт

`approved`.

Обе записи реестра прошлых итераций закрыты в `accepted` — гейт `review ->
verifying` по реестру пройдёт. Требования 1–12 реализованы, планка задачи
(10 тестов, 4 subtests) и все затронутые модули зелёные; правок защищённых
путей, ослабления тестов, гейтов, лимитов и инвариантов нет, ни одного
удалённого или изменённого ассерта существующих тестов в диффе ветки.
Пометок `# AC-n: manual|skip` в планке нет — автогейт acceptance задачи не
выключен.

## Проверено исполнением

- `python3 -m unittest tests.test_journal_warning_once
  tests.test_draft_mr_commits` — 19 тестов, OK (12 + 7, совпадает с
  заявкой PLAN итерации 2).
- `python3 -m pytest -q -p no:cacheprovider
  tasks/01M3HP7WAXKFK3GYZ3T6HX08M0/acceptance_tests` — 10 passed,
  4 subtests passed. Четыре файла планки покрывают AC-1..AC-10, пометок
  `manual|skip` нет (`grep -rn "AC-" acceptance_tests/` — только
  докстринги).
- **Мутационный зонд R1-F1.** Подмена
  `github_adapter._ensure_draft_mr_after_publish` копией без сверки
  `head == gitcmd.branch_head_sha(base)` →
  `DraftMrAtTheVerifyingRubiconTest`: `Ran 3 tests … FAILED (failures=1)`,
  падает `test_a_branch_identical_to_the_base_wakes_nobody` на
  `assertNotIn` с текстом `'Draft MR пропущен: в ветке нет коммитов'
  unexpectedly found in ['push (голова не в origin)', 'Draft MR пропущен:
  в ветке нет коммитов']`. На итерации 1 та же подмена давала `OK` — тест
  действительно дотянут до заявки.
- **Мутационный зонд R1-F2.** Подмена `budget.journal_warning_once`
  копией без охранного `if key is not None and key != detail: raise` →
  `JournalWarningOnceTest`: `Ran 6 tests … FAILED (failures=1)`,
  `test_a_key_other_than_the_text_is_refused_loudly` —
  `AssertionError: ValueError not raised`.
- `python3 -m unittest tests.test_github_adapter
  tests.test_fsm_draft_mr_reentry tests.test_spec_budget
  tests.test_runner_model_preflight tests.test_step_cost
  tests.test_store_journal tests.test_budget_live_lease_and_escalation
  tests.test_budget_calibration_table tests.test_program_spend_reseed` —
  190 тестов, OK (четыре модуля требования 12 и оба читателя записи
  «бюджет: предупреждение» в их числе).
- `python3 -m unittest tests.test_invariants tests.test_guard_mutation_claim
  tests.test_advance_guard tests.test_auto_cycle
  tests.test_fsm_spec_gate_reject` — 151 тест, OK (инвариант 35 на новых
  файлах и гейт заявки мутации в их числе).
- `python3 scripts/codebase_map.py` + `git diff --numstat --
  docs/codebase-map.md` — 1 изменённая строка, и это только
  `built_at_sha` (`0490b7e0` → `2b99fc87`); содержимое карты свежее,
  заявка PLAN верна. Дерево восстановил `git checkout --
  docs/codebase-map.md`, `git status --short` чист.
- `git diff --stat 6b8cee21...HEAD -- . ':!tasks/'` — только
  `orchestrator/budget.py`, `orchestrator/github_adapter.py`,
  `orchestrator/runner.py`, `docs/codebase-map.md` и два НОВЫХ файла
  `tests/`; `git diff 6b8cee21...HEAD -- tests/ | grep -E "^-[^-]"` —
  пусто (ни одной удалённой строки в `tests/`, включая ассерты).

Читал сверх пакета (причины — в замечаниях и таблице выше):
`orchestrator/budget.py:1-130` и вызывающие места `:170-195`, `:305-316` —
проверить, что новый `ValueError` не задевает ни один живой вызов (R1-F2);
`orchestrator/runner.py:355-375` — то же для предполёта;
`orchestrator/github_adapter.py:27-275` — сверить порядок локальной
проверки относительно push/`gh` и содержимое хука (требования 8–10 и
мутация R1-F1); `orchestrator/store.py` (`task_steps`, `set_state`) —
убедиться, что выборка границы пребывания не ограничена LIMIT и префикс
записи входа в состояние совпадает с префиксом сверки (требование 4);
`tests/test_draft_mr_commits.py`, `tests/test_journal_warning_once.py`
целиком — сверка заявок мутации с ассертами.

## Предложения системе

- Реестр замечаний и правило вердикта расходятся на `minor`: «0
  blocker/major → approved», но гейт `review -> verifying` требует ВСЕ
  записи в `accepted`. Заведённое `minor`-замечание тем самым стоит
  полной итерации ревью, как `major` — на этой задаче так закрывался
  R1-F2. Стоит назвать это в `skills/review-checklist.md` прямо (либо
  «minor тоже блокирует, заводи осознанно», либо отдельный терминальный
  статус для принятого-к-сведению minor), иначе ревьювер выбирает между
  «промолчать» и «оплатить итерацию» вслепую.
</content>
