---
task: 01M1NEEYSP0QWPMXHG0BK591M7
type: review
author_role: reviewer
status: changes_requested
iteration: 4
schema_version: 3
---

# REVIEW: Предупреждение при чужом живом lease (pause, release)

## Фаза A: проверка плана
- Покрытие требований (таблица PLAN.md «Покрытие требований») — полное, без изменений с итерации 1: все 5 требований отображены на шаги, требование 5 закрыто как «не входит» со ссылкой на ANSWER-1.
- Шаги 1-4 — проверяемые единицы разумного размера.
- Разделы «Подход»/«Шаги» PLAN.md текстуально не менялись с коммита `fc6b2ebf` (сверено `git show fc6b2ebf:tasks/.../PLAN.md` против текущего файла) — доработки итерации 4 (ANSWER-3) добавили только код+тесты и текстовые разделы «Замечания REVIEW.md итерации 3 закрыты (ANSWER-3)» / «Проверено исполнением» в конец PLAN.md, не тронув «Подход»/«Шаги»/«Покрытие требований».
- Раздел «Влияние на систему» PLAN.md неполон относительно текущего HEAD: описывает merge main для ANSWER-2 (`git merge main`, конфликт только в `docs/codebase-map.md`), но НЕ упоминает более поздний коммит `7c955628` («01M1NEEYSP0QWPMXHG0BK591M7: подтяжка main», merge `90eaa1dc` + `abddc895`) — который лёг ПОСЛЕ раздела «Проверено исполнением (итерация после ANSWER-3)» и не отражён нигде в PLAN.md. Этот коммит и есть источник блокера ниже (Замечания, R4-F1).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (предупреждение до выполнения, pause/release, держатель+возраст heartbeat, роль/шаг если известны) | OK | Прочитан текущий `orchestrator/lease.py:128-186` — `foreign_live_lease` сверяет `hostname` перед `_pid_alive` (R1-F1 закрыт), `warn_foreign_live` подмешивает `role=…, step=…`, когда `runner.step_role` резолвится (R1-F2 закрыт). AC-1/AC-3 зелёные. |
| 2 (свой/мёртвый-протухший lease — без предупреждения) | OK | `test_own_live_lease_returns_none`, `test_foreign_dead_pid_returns_none`, `test_foreign_stale_heartbeat_returns_none` зелёные; AC-4/AC-5 зелёные. |
| 3 (дубль в журнал тем же API, identity держателя) | OK | `store.journal(conn, task_id, "operator", …, session_id=row["session_id"])`, AC-6 зелёный. |
| 4 (read-only команды не предупреждают) | OK | `grep -rn warn_foreign_live orchestrator/` — только `lease.py`/`pause.py`/`release.py`; AC-7 (4 теста, включая дословную сверку `doctor.check_leases`) зелёный. |
| 5 (approve/reject/budget/kill/answer не меняются) | OK | `git diff main...HEAD -- orchestrator/fsm.py orchestrator/budget.py orchestrator/cleanup.py orchestrator/answer.py` — пусто (изменения `fsm.py` от подтяжки main принадлежат чужой задаче 01M1KS8K9RXWHX2PW3ZKB0P903, не этому SPEC). |

Все пять требований содержательно закрыты. Блокер ниже — не про SPEC/код фичи, а про состояние артефактов ветки на текущем HEAD.

## Замечания

- **blocker** — `tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md` (весь файл, секции нет) — `python3 scripts/guard.py --all` (тот же вызов, что CI-джоб `.github/workflows/ci.yml:17-20`, «guard.py по всем артефактам задач») **падает** прямо сейчас на этом файле:
  ```
  GUARD: нарушения структуры артефактов:
    - tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md: сработали сигналы подозрения
      на большой объём (число затрагиваемых модулей/файлов, прогноз диффа не
      дан), а секция '## Оценка объёма и деление' пуста или отсутствует —
      заполни секцию нарезкой на 2-4 подзадачи ... либо обоснованием
      монолита
  ```
  Причина: коммит `7c955628` («подтяжка main», Merge `90eaa1dc` + `abddc895`) — САМЫЙ ПОСЛЕДНИЙ коммит ветки, лёгший ПОСЛЕ закрытия R1-F1..R1-F4 — принёс новую проверку `scripts/guard.py::split_assessment_errors` (задача 01M1KS8K9RXWHX2PW3ZKB0P903, требования 1/3): SPEC с `schema_version >= 3` обязан нести заполненную секцию «## Оценка объёма и деление», если сработал хоть один сигнал «подозрения на большой объём». У SPEC этой задачи сигнал «число затрагиваемых модулей/файлов» срабатывает честно — в тексте (в основном в «Не входит») упомянуто 7 разных путей `orchestrator/*.py` (`pause.py`, `release.py`, `fsm.py`, `budget.py`, `cleanup.py`, `answer.py`, `session.py`) при пороге `config.SPLIT_SIGNAL_ZONE_FILES = 5`. Задача не подпадает под исключение `_closed_before_split_assessment` — `docs/retro/01M1NEEYSP0QWPMXHG0BK591M7.md` не существует, задача ещё не закрыта.
  Последствие: PLAN.md заявляет «GUARD: ок (3 файлов)» в разделе «Проверено исполнением (итерация после ANSWER-3)» — это верно было на коммите `90eaa1dc`, но НЕ верно на текущем HEAD (`7c955628`), и PLAN.md нигде не упоминает сам факт этого более позднего merge-коммита. Если ветку в этом состоянии запушить — сработает и провалится CI-джоб `guard.py по всем артефактам задач` (проверено напрямую: `python3 scripts/guard.py --all` даёт тот же результат).
  Предложение: заполнить в `SPEC.md` секцию «## Оценка объёма и деление» — для задачи такого размера (3 файла реального диффа: `lease.py`/`pause.py`/`release.py`) естественный путь — обоснование монолита («не подлежит нарезке на 2-4 подзадачи: единый общий хелпер + два тривиальных подключения»), а не деление на подзадачи. Поскольку `SPEC.md` по конвенции — артефакт analyst, а не developer, и вопрос затрагивает работу другой роли постфактум (гейт появился уже после того, как SPEC был `ready`), возможно потребуется решение Оператора о том, кто и как вносит правку (похожий прецедент этой же задачи — ANSWER-2 по гейту лока `acceptance_tests/`). Пока секция не заполнена — «GUARD: ок» из PLAN.md недостоверно на HEAD, и вердикт `approved` не может опираться на эту устаревшую евиденцию.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/lease.py:150 | `foreign_live_lease` вызывала `_pid_alive` без сверки `hostname` | ложное «жив»/«мёртв» при чужом host | Проверено на текущем HEAD: `row["hostname"] == socket.gethostname()` сверяется ПЕРЕД `_pid_alive` — паттерн идентичен `acquire` (lease.py:73) и `catalog._lease_holder_suffix` (catalog.py:194-197). Новый тест `test_foreign_host_live_heartbeat_unaddressable_pid_returns_the_row` зелёный, фиксирует регресс на будущее. Закрываю. |
| R1-F2 | accepted | orchestrator/lease.py:155-186 | предупреждение не включало роль/шаг | требование 1 не полностью выполнено | Проверено: `warn_foreign_live` резолвит `runner.step_role(t)`, подмешивает `role=…, step=…` при непустой роли. Тест `test_warn_foreign_live_includes_role_and_step_when_known` зелёный (T001 в `in_dev` → `role=developer, step=in_dev`). Закрываю. |
| R1-F3 | accepted | orchestrator/lease.py:181-183 | грамматическая ошибка в тексте предупреждения | косметика в тексте для Оператора | Проверено: текст сейчас «она может активно работать над задачей; предупреждение не блокирует выполнение» — грамматически корректно. Закрываю. |
| R1-F4 | accepted | tests/test_lease.py, tests/test_pause.py, tests/test_release.py | 13 тестов без докстринга «Ловит мутацию: …»; не было теста с чужим hostname | заявленное свойство теста не проверяемо заранее | Прочитаны все 13 методов на текущем HEAD — у каждого докстринг с конкретной заявкой «Ловит мутацию: …», описывающей сценарий и наблюдаемое свойство (не пересказ имени метода). Добавлен `test_foreign_host_live_heartbeat_unaddressable_pid_returns_the_row` (чужой host + `_dead_pid()` + свежий heartbeat). Два предсуществующих теста T062-эпохи (`test_journals_former_holder_with_numeric_heartbeat_age`, `test_row_replaced_between_read_and_delete_is_not_removed`) корректно адаптированы под побочный эффект R1-F1 (теперь honestly печатают предупреждение на `HOLDER_HOST`) — фильтруют журнал по `action == "lease снят Оператором"`, что не искажает изначально проверяемое свойство (гонка снятия). Закрываю. |
| R4-F1 | open | tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md | `scripts/guard.py --all` (= CI-джоб) падает: у SPEC нет обязательной секции «## Оценка объёма и деление», хотя сигнал «число затрагиваемых модулей/файлов» сработал (7 путей `orchestrator/*.py` в тексте ≥ порога 5) | пуш/мерж ветки в этом состоянии ломает CI; заявление PLAN.md «GUARD: ок (3 файлов)» устарело относительно HEAD (не покрывает коммит `7c955628`) | — |

## Вердикт
changes_requested — R1-F1..R1-F4 содержательно закрыты (проверено чтением кода и прогоном тестов, перевожу в `accepted`), но на текущем HEAD ветки (коммит `7c955628`, подтяжка main ПОСЛЕ ANSWER-3) `python3 scripts/guard.py --all` падает на `tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md` — новое обязательное правило («## Оценка объёма и деление») из смерженной задачи 01M1KS8K9RXWHX2PW3ZKB0P903 сработало на SPEC этой задачи и не заполнено. Это реальный блокер (тот же вызов гоняет CI-джоб «guard.py по всем артефактам задач» на каждый пуш) и одновременно расхождение: PLAN.md заявляет «GUARD: ок», что верно было на коммите `90eaa1dc`, но не на HEAD. Нужно закрыть R4-F1 (заполнить секцию в SPEC.md — вероятно потребуется решение Оператора, кто вносит правку, раз SPEC — артефакт analyst) и обновить «Проверено исполнением» PLAN.md, отразив коммит `7c955628`.

## Проверено исполнением
- `git checkout -- tasks/01M1NEEYSP0QWPMXHG0BK591M7/` — рабочее дерево снова показало каталог задачи как `deleted` без staged-изменений при старте (известный симптом, memory `feedback_task_dir_deletion_recovery`); восстановлено из HEAD.
- `git log --oneline -5 HEAD` — HEAD = `7c955628` (merge `90eaa1dc` + `abddc895`), позже коммита ANSWER-3-фикса `90eaa1dc`.
- Прямое чтение `orchestrator/lease.py:100-186` на текущем HEAD — подтверждает R1-F1 (сверка hostname перед `_pid_alive`, lease.py:150), R1-F2 (role/step в detail, lease.py:174-177), R1-F3 (текст lease.py:181-183) исправлены.
- `sed -n '185,198p' orchestrator/catalog.py` и `sed -n '60,82p' orchestrator/lease.py` — паттерн «сверить hostname перед `_pid_alive`» в `foreign_live_lease` идентичен уже существующим `acquire`/`_lease_holder_suffix`.
- Чтение `tests/test_lease.py:317-481` (класс `ForeignLiveLeaseTest`, 9 методов), `tests/test_pause.py:109-127`, `tests/test_release.py:60-82,130-149,169-206` целиком — у всех 13 методов докстринг «Ловит мутацию: …» с конкретным сценарием; новый межхостовый тест присутствует.
- `python3 -m pytest tests/test_lease.py tests/test_pause.py tests/test_release.py -q` — 58 passed.
- `python3 -m pytest tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/ -q` — 18 passed, состав не менялся (лок не тронут).
- `grep -rn warn_foreign_live orchestrator/` — только `lease.py`, `pause.py`, `release.py` (требование 4/AC-7).
- `git diff main...HEAD -- orchestrator/fsm.py orchestrator/budget.py orchestrator/cleanup.py orchestrator/answer.py` — пусто (требование 5).
- `python3 -m pytest tests/ -q` — 1430 passed, 417 subtests passed, 170.53s, 0 ошибок, 0 регрессов.
- `python3 scripts/codebase_map.py` (сухой прогон, сравнение с `docs/codebase-map.md` без строки `built_at_sha`) — расхождений нет, карта свежая.
- `python3 scripts/guard.py tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md` — падает (см. «Замечания», R4-F1). `python3 scripts/guard.py --all` — падает тем же единственным сообщением про этот SPEC.md (проверено, что это не false positive из-за постороннего файла в беклоге — единственная строка ошибки называет именно `tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md`).
- `git diff --stat 90eaa1dc 7c955628 -- . ':(exclude)tasks/01M1NEEYSP0QWPMXHG0BK591M7'` — подтверждает источник: merge принёс `scripts/guard.py` (+181 строка), `templates/SPEC.md`, `skills/spec-authoring.md`, `tasks/01M1KS8K9RXWHX2PW3ZKB0P903/*` — новую проверку объёма; `orchestrator/lease.py`/`pause.py`/`release.py` и их тесты этим merge-коммитом не затронуты (код фичи цел).

## Предложения системе
Третья итерация подряд, где задача проходит `review -> in_dev -> review` не из-за содержания замечаний реестра, а из-за инфраструктурных гейтов, пришедших подтяжкой main ПОСЛЕ того, как разработчик уже закрыл содержательные замечания (итерация 2/3: лок `acceptance_tests/` с `__pycache__`; итерация 4: новая секция «Оценка объёма и деление» в guard.py). Оба раза источник — гейт, появившийся в main уже ПОСЛЕ того, как SPEC.md этой задачи стал `ready` (гейт не существовал на момент авторства SPEC), и оба раза единственный практический выход у разработчика — подтянуть main, что само по себе и приносит новый гейт-конфликт следующей итерации. Стоит рассмотреть: должен ли SPEC.md, ставший `ready` ДО появления новой guard-проверки, ретроактивно подпадать под неё в живых (не закрытых) задачах — сейчас `_closed_before_split_assessment` освобождает только уже смерженные (`docs/retro/`) задачи, а не те, что просто были `ready` раньше правила.
