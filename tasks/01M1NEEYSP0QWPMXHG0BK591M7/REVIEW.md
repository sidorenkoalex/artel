---
task: 01M1NEEYSP0QWPMXHG0BK591M7
type: review
author_role: reviewer
status: changes_requested
iteration: 3
schema_version: 3
---

# REVIEW: Предупреждение при чужом живом lease (pause, release)

## Фаза A: проверка плана
- Покрытие требований (таблица PLAN.md «Покрытие требований») — полное: все
  5 требований отображены на шаги, требование 5 корректно закрыто как «не
  входит», со ссылкой на ANSWER-1.
- Шаги 1-4 — проверяемые единицы разумного размера, не микрооперации.
- `git log --reverse HEAD -- orchestrator/lease.py orchestrator/pause.py
  orchestrator/release.py tests/test_lease.py tests/test_pause.py
  tests/test_release.py` — последний коммит, трогающий эти файлы, это
  `fc6b2ebf` («предупреждение о чужом живом lease в pause/release +
  PLAN.md»); разделы «Подход»/«Шаги» PLAN.md по тексту совпадают с версией
  на этом же коммите (`git show fc6b2ebf:tasks/.../PLAN.md`) — с итерации 1
  не изменились ни разу.
- С прошлого вердикта (`changes_requested`, итерация 2) в код и тесты не
  внесено ни единого коммита — все замечания реестра ниже перенесены без
  изменения содержания.
- Раздел «Эскалация: снята (ANSWER-2)» PLAN.md — про инфраструктурный гейт
  лока `acceptance_tests/` (`__pycache__` в автокоммите test_author),
  устранённый на уровне пульта задачей 01M1KVG3KSCY47HWXWF5HM0E76; к
  предмету ревью (SPEC/код) не относится, отдельно не разбирается.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (предупреждение до выполнения, pause/release, держатель+возраст heartbeat, роль/шаг если известны) | Частично | Для lease на ЭТОМ host — работает, AC-1/AC-3 зелёные. Для lease на ДРУГОМ host (легитимный и, судя по «Контексту» SPEC, основной практический случай) поведение неверно в обе стороны — R1-F1. Роль/шаг не печатаются никогда — R1-F2. |
| 2 (свой/мёртвый-протухший lease — без предупреждения) | OK | `foreign_live_lease` корректна для однохостового случая, AC-4/AC-5 зелёные. |
| 3 (дубль в журнал тем же API, identity держателя) | OK | `store.journal(..., session_id=row["session_id"])`, AC-6 зелёный. |
| 4 (read-only команды не предупреждают) | OK | `grep -rl warn_foreign_live orchestrator/` — только `lease.py`/`pause.py`/`release.py`; AC-7 зелёный. |
| 5 (approve/reject/budget/kill/answer не меняются) | OK | `git diff main...HEAD -- orchestrator/fsm.py orchestrator/budget.py orchestrator/cleanup.py orchestrator/answer.py` — пусто. |

## Замечания

Код (`orchestrator/lease.py`, `orchestrator/pause.py`, `orchestrator/release.py`,
`tests/test_lease.py`, `tests/test_pause.py`, `tests/test_release.py`) не
менялся с коммита `fc6b2ebf` (итерация 1). Все четыре замечания реестра
переносятся как `open` — содержание проверено заново на текущем коде, не
переписано механически:

- major — `orchestrator/lease.py:128-150` (`foreign_live_lease`) —
  функция вызывает `liveness._pid_alive(row["pid"])` БЕЗ предварительной
  сверки `row["hostname"]` с локальным hostname, хотя ровно этот приём уже
  применяют три других места той же кодовой базы: `orchestrator/lease.py:73`
  (`acquire`, `if row["hostname"] == hostname and not
  liveness._pid_alive(...)`), `orchestrator/catalog.py:189-197`
  (`_lease_holder_suffix`, при чужом host `alive = True` без вызова
  `_pid_alive`) и `orchestrator/pause.py:190-193` (`cmd_pause_now`, тот же
  приём различения через `runner.step_role`+`t["hostname"]`). Следствие в
  обе стороны: (а) lease чужого host, чей номер pid случайно совпал с
  PID-ом РЕАЛЬНО работающего локального процесса, → `foreign_live_lease`
  возвращает строку («ложно жив», предупреждение печатает существующего,
  но фактически непричастного локального процесса как «держателя»); (б)
  lease чужого host с типичным непроверяемым локально pid (обычный
  межхостовый случай — тот самый инцидент 02.09.2026 из «Контекст» SPEC) →
  `_pid_alive` возвращает `False`, функция молчит там, где обязана
  предупредить. И то и другое — прямое нарушение назначения фичи.
  Предложение прежнее (не исправлено с итерации 1): сравнивать
  `row["hostname"]` перед `_pid_alive`; если для чужого host решено не
  предупреждать — явно задокументировать этот компромисс как сознательное
  ограничение объёма (SPEC/PLAN «Риски»), а не молчаливо ловить его как
  побочный эффект отсутствия проверки.
- minor — `orchestrator/lease.py:153-173` (`warn_foreign_live`) —
  предупреждение по-прежнему не включает роль/шаг, хотя требование 1 прямо
  просит «роль/шаг — если известны», а `runner.step_role(t)` уже
  используется в том же модуле-вызывающем (`orchestrator/pause.py:193`,
  внутри `cmd_pause_now`) — тривиально доступно и в `cmd_pause`/
  `cmd_release`. Не исправлено с итерации 1.
- minor — `orchestrator/lease.py:168-170` — формулировка предупреждения
  по-прежнему грамматически сбоит: «вмешательство продолжится, но она
  может быть активно работать над задачей». Это текст, который читает
  Оператор в реальном инциденте — стоит поправить. Не исправлено с
  итерации 1.
- major — 13 юнит-тестов по-прежнему без докстринга с заявкой «Ловит
  мутацию: …» (skills/test-authoring.md, review-checklist требование 3);
  прочитаны целиком — докстрингов нет ни у одного метода:
  - `tests/test_lease.py:342` `test_no_lease_returns_none`
  - `tests/test_lease.py:346` `test_own_live_lease_returns_none`
  - `tests/test_lease.py:353` `test_foreign_live_lease_returns_the_row`
  - `tests/test_lease.py:362` `test_foreign_stale_heartbeat_returns_none`
  - `tests/test_lease.py:370` `test_foreign_dead_pid_returns_none`
  - `tests/test_lease.py:377` `test_warn_foreign_live_prints_holder_and_heartbeat_age`
  - `tests/test_lease.py:387` `test_warn_foreign_live_journals_with_holder_session_id`
  - `tests/test_lease.py:399` `test_warn_own_live_lease_prints_nothing_and_does_not_journal`
  - `tests/test_lease.py:409` `test_warn_no_lease_prints_nothing_and_does_not_journal`
  - `tests/test_pause.py:109` `test_pause_warns_on_foreign_live_lease`
  - `tests/test_pause.py:118` `test_pause_journals_the_warning_as_an_extra_entry`
  - `tests/test_release.py:130` `test_release_warns_on_foreign_live_lease`
  - `tests/test_release.py:139` `test_release_journals_the_warning_as_an_extra_entry`
  Показательно: заявка «Ловит мутацию: hostname не сверяется перед
  _pid_alive» на `test_foreign_live_lease_returns_the_row`, если бы её
  написали, обязала бы автора теста задать lease с ЧУЖИМ hostname (сейчас
  везде `socket.gethostname()` — свой) — и тест сам поймал бы R1-F1 при
  написании. Отсутствие докстринга и отсутствие межхостового теста —
  один и тот же пробел. Не исправлено с итерации 1. Предложение прежнее:
  докстринг с явной заявкой к каждому из 13 методов; отдельно — тестовый
  кейс с чужим `hostname` для `foreign_live_lease`/`warn_foreign_live`
  зафиксировал бы R1-F1 как регресс на будущее (сейчас такого случая нет
  ни в юнит-, ни в приёмочных тестах — все инсталляции lease в
  `insert_lease` используют `socket.gethostname()`).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/lease.py:128-150 | `foreign_live_lease` вызывает `_pid_alive` без сверки `hostname` — не исправлено, код идентичен итерации 1 | ложное «жив» при коллизии pid с чужим host; ложное молчание для реального межхостового живого lease (сценарий инцидента из SPEC) | сравнить `row["hostname"]` с локальным перед `_pid_alive`, как в `lease.acquire`/`catalog._lease_holder_suffix`/`pause.cmd_pause_now`; либо явно задокументировать ограничение объёма в SPEC/PLAN |
| R1-F2 | open | orchestrator/lease.py:153-173 | предупреждение не включает роль/шаг — не исправлено | требование 1 («если известны») выполнено не полностью | добавить роль/шаг в `detail`, когда `runner.step_role(t)` не `None` |
| R1-F3 | open | orchestrator/lease.py:168-170 | грамматическая ошибка «может быть активно работать» — не исправлено | косметика в тексте для Оператора в реальном инциденте | поправить формулировку |
| R1-F4 | open | tests/test_lease.py:342-414, tests/test_pause.py:109-127, tests/test_release.py:130-149 | 13 юнит-тестов без докстринга «Ловит мутацию: …»; заодно нет ни одного теста с чужим hostname — не исправлено | заявленное свойство теста не проверяемо заранее; R1-F1 не покрыт тестом даже как известный баг | докстринг с конкретной заявкой к каждому методу; тест-кейс с чужим hostname для `foreign_live_lease` |

## Вердикт
changes_requested — с прошлого вердикта (итерация 2, тоже
`changes_requested`) в `orchestrator/lease.py`, `orchestrator/pause.py`,
`orchestrator/release.py`, `tests/test_lease.py`, `tests/test_pause.py`,
`tests/test_release.py` не внесено ни одного коммита: все четыре
замечания реестра (R1-F1..R1-F4) остаются в исходном виде третью итерацию
подряд, две из них (R1-F1, R1-F4) — major. Между итерацией 2 и текущей
PLAN.md получил только текст про инфраструктурный гейт лока
`acceptance_tests/` (снятая эскалация ANSWER-2) и наблюдение про
расхождение ANSWER-2 с `guard.py` — обе темы не связаны с содержанием
ревью. Нужно исправить R1-F1 (major) и добавить докстринги R1-F4 (major)
как минимум; R1-F2/R1-F3 minor, но дёшевы и стоит закрыть в этой же
итерации.

## Проверено исполнением
- `git checkout -- tasks/01M1NEEYSP0QWPMXHG0BK591M7/` — рабочее дерево
  этого запуска снова показало каталог задачи как `deleted` без
  staged-изменений при старте; восстановлено из HEAD (известный симптом,
  memory `feedback_task_dir_deletion_recovery`).
- `git log --reverse HEAD -- orchestrator/lease.py orchestrator/pause.py
  orchestrator/release.py tests/test_lease.py tests/test_pause.py
  tests/test_release.py` — последний коммит `fc6b2ebf` (итерация 1);
  никаких последующих коммитов по этим файлам нет.
- Прямое чтение `orchestrator/lease.py:100-174` — подтверждает R1-F1
  (нет сверки hostname), R1-F2 (нет роли/шага), R1-F3 (формулировка) на
  текущем HEAD, не по памяти прошлой итерации.
- `sed -n '185,200p' orchestrator/catalog.py` и `sed -n '60,82p'
  orchestrator/lease.py` — подтверждают, что паттерн «сверить hostname
  перед `_pid_alive`» уже применяется в двух других местах модуля.
- Чтение `tests/test_lease.py:342-414`, `tests/test_pause.py:109-127`,
  `tests/test_release.py:130-149` целиком — докстрингов «Ловит мутацию»
  нет ни у одного метода; ни один `insert_lease`/аналог не использует
  hostname, отличный от `socket.gethostname()`.
- `grep -rl warn_foreign_live orchestrator/` — только `lease.py`,
  `pause.py`, `release.py` (требование 4/AC-7).
- `git diff main...HEAD -- orchestrator/fsm.py orchestrator/budget.py
  orchestrator/cleanup.py orchestrator/answer.py` — пусто (требование 5).
- `python3 -m pytest tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/
  -q` — 18 passed.
- `python3 -m pytest tests/ -q` — 1400 passed, 417 subtests passed,
  163.16s, 0 ошибок, 0 регрессов.
- `python3 scripts/guard.py tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md
  tasks/01M1NEEYSP0QWPMXHG0BK591M7/PLAN.md` — «GUARD: ок (2 файлов)».

## Предложения системе
Третья итерация подряд: задача возвращается на review без единого
коммита, адресующего замечания реестра (R1-F1..R1-F4 неизменны с
итерации 1) — оба предыдущих цикла `review -> in_dev -> review`
проходили только за счёт разрешения ИНФРАСТРУКТУРНЫХ блокеров (лок
`acceptance_tests/`, расхождение ANSWER-2/guard.py), не за счёт работы
над содержанием ревью. Итерация 2 уже отметила этот паттерн как разовое
наблюдение («Предложения системе»); он подтвердился повторно и
однозначно тем же способом (`git log --reverse HEAD -- <файлы фичи>`
называет один и тот же коммит все три раза). Стоит проверить, не
позволяет ли `orchestrator/fsm_advance.py`/цикл `in_dev -> review`
двигать задачу вперёд по одним только механическим гейтам (лок тестов,
guard), не сверяя, что код с прошлого `changes_requested`-вердикта
вообще менялся — иначе цикл ревью рискует буксовать бесконечно, не
регистрируя это как детектируемое зависание.
