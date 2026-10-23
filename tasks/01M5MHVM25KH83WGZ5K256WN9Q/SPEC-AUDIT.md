---
task: 01M5MHVM25KH83WGZ5K256WN9Q
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: в) пути-признаки (тесты): tests/, tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py, tests/test_cycle_hint.py, tests/test_observation_acceptance_return.py, tests/test_observation_edges.py
spec_sha: 4cca7d2edf7fdb58180cca13f9ef14476445cdf2
schema_version: 5
---

# SPEC-AUDIT: Свежесть связи наблюдения — одна функция вместо трёх копий

Аудит круга 3: SPEC после двух возвратов с гейта SPEC (решения Оператора №1 и №2).

## ТЗ и SPEC
- Требования 1–5 ТЗ перенесены в SPEC без потерь: две функции `watch.observation_age`/`observation_link_fresh` и подмена `watch.datetime` (SPEC, требование 1); замена трёх копий, единичный вызов «сейчас», пустая строка как `None` и устранение `ValueError` (требование 2); линтер (требования 3, 4в); тест (а)(б)(в) с красным на текущем коде (требование 4); неизменность формата хранения и существующих тестов (требование 5). «Не входит» и «Только чтение» совпадают с ТЗ.
- Решение №1: п. 1 (поведенческая проверка свежести через подменённый `watch.datetime`, настоящее время не дальше 1 с от `last_seen_at`) — в AC-4 и AC-5; п. 2 (счётчик вызовов `now`, ровно один за вызов `_launch_observation`) — в AC-4; п. 3 (тест `watch_progress`) — правки не требует, держится AC-7/требованием 5.
- Решение №2: п. 1 — AC-6 с подменой времени, «ровно порог» → `"fresh"`, «порог + 1 с» → `"stale"`, `None`/`""` → `"unstarted"`; уточнение требования 2 про ветку `pid is None` (вызов `observation_link_fresh(row)`, без своего сравнения) — в SPEC, требование 2, третий пункт. П. 2 — AC-4: «устарела на 91 с» при пороге 90 с.
- Требований сверх ТЗ и решений Оператора в SPEC нет. Расхождений не найдено.

## Факты против кода
- `orchestrator/artel.py:949–958` — блок свежести `_launch_observation` (функция с `artel.py:906`): `last_seen_at is None` → отказ «связи с watch ещё нет» (`:950–952`), `age` на `datetime.now(timezone.utc) - datetime.fromisoformat(...)` (`:953–954`), `age > config.OBSERVATION_STALE_SECONDS` → отказ «связь устарела на {age:.0f} с (порог … с)» (`:955–958`). Подтверждено.
- `orchestrator/artel.py:1066–1071` — `_observation_fresh`: `state != "active" or last_seen_at is None` → `False`, иначе `age <= порог`. Подтверждено; пустая строка сейчас роняет `fromisoformat("")` — намеренно устраняемое падение, как в SPEC.
- `orchestrator/watch.py:320–326` — `observation_process_state`, ветка `pid is None`: `not row["last_seen_at"]` → `"unstarted"`, иначе `"fresh"`/`"stale"` по `age <= порог`. Подтверждено.
- `orchestrator/watch.py:27` и `orchestrator/artel.py:703` — каждый модуль импортирует `datetime` своим именем на уровне модуля: подмена `mock.patch.object(watch, "datetime", …)` не затрагивает `artel.datetime`, на чём строятся поведенческие проверки AC-4/AC-5. Подтверждено.
- Других вызовов `fromisoformat` с `"last_seen_at"` в `orchestrator/` нет (grep): ровно три места, как в SPEC. Потребители: `artel.py:1130` (`_observation_fresh`), `artel.py:1133` и `orchestrator/doctor/observations.py:16` (`observation_process_state`) — поведение для них сохраняется требованием 2.
- `_launch_observation` до блока свежести (`artel.py:913–948`) не вызывает ничего из `watch` — счётчик `now` в AC-4 видит только вызов из блока свежести.
- `config.OBSERVATION_STALE_SECONDS` = 90 (`config.py:82–83`, сверено в прошлом круге; файл в задаче только для чтения).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `observation_age` не возвращает `None` на `""` (проверка `is None` вместо пустоты); знак разности перепутан (−30 вне 30 ± 2); возраст в минутах/мс |
| AC-2 | да | `<` вместо `<=` (ровно порог → `False`); сравнение с порогом выброшено (порог + 1 → `True`); падение/`True` на пустом `last_seen_at` |
| AC-3 | да | своя копия `datetime.fromisoformat(row["last_seen_at"])` возвращена в `artel.py` или `watch.py`; копия старого кода не удалена |
| AC-4 | да | `""` роняет `ValueError` (старая проверка `is None`); копия разбора на `artel.datetime` (реальное время ≈ `last_seen_at` → отказа нет при «порог + 1»); второй расчёт `age` для текста отказа на `artel.datetime` («устарела на 0 с» вместо 91); второй вызов `now` (счётчик 2); `>=` вместо `>` (отказ при ровно пороге) |
| AC-5 | да | снята проверка `state`; `""` роняет `ValueError`; копия на `artel.datetime` (обратный результат на «порог + 1» и «порог») |
| AC-6 | да | `<` вместо `<=` в ветке `pid is None` («ровно порог» → `"stale"`); `""` → не `"unstarted"`; сравнение выброшено |
| AC-7 | да | правка `store.py`/формата записи; правка любого из четырёх названных файлов тестов (сравнение с main) |

Остаточное, не отклонение: копия разбора через промежуточную переменную, работающая на `watch.datetime` (в `watch.py` или явным `watch.datetime.now` в `artel.py`), поведенчески неотличима от вызова функции и проходит линтер AC-3. Форму линтера Оператор оставил решением №1 п. 1, закрыв поведенческими проверками вариант на `artel.datetime`; эквивалентная по поведению копия — вопрос ревью, не приёмки.

## Зоны
- Зоны SPEC `orchestrator/watch.py, orchestrator/artel.py, docs/codebase-map.md, tests/` покрывают всё, что меняют требования: две новые публичные функции `watch.py` (меняют карту — `docs/codebase-map.md` в зонах), правка двух мест `artel.py`, новый тест в `tests/`.
- Защищённых путей (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) задача не трогает. `store.py`, `config.py` — только чтение. Песочница ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Блок свежести `_launch_observation` (`artel.py:949–958`) | Отказы «связи ещё нет»/«связь устарела», граница «ровно порог — свежая»: `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py` (ac2, ac4, ac5, ac6, ac8) | да; пустая строка теперь отказ вместо `ValueError` (намеренно, требование 2) | существующий файл без правок (AC-7) + новый тест AC-4 | остаётся |
| `_observation_fresh` (`artel.py:1066–1071`) | Поле `fresh` в списке наблюдений: `tests/test_observation_edges.py`, `tests/test_cycle_hint.py` | да | существующие файлы без правок (AC-7) + AC-5 | остаётся |
| Ветка `pid is None` в `observation_process_state` (`watch.py:320–326`) | `doctor` о мёртвом pid и устаревшей связи: `tests/test_observation_acceptance_return.py::test_doctor_warns_for_dead_pid_and_stale_link` | да | существующий тест без правок (AC-7) + AC-6 | остаётся |
| Свежесть в `artel.py` начинает следовать подмене `watch.datetime` | `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py:147–160` подменяет `watch.datetime` | да (тест не меняется, должен остаться зелёным; решение Оператора №1 п. 3) | полный прогон пульта; файл не правится | остаётся |
| Формат `last_seen_at`/`started_at`/`created_at` | `store.touch_observation`, `store.touch_claimed_observation`, `store.claim_observation` (равенство `started_at`) | да, не меняется | AC-7 | остаётся |

Раздела «Меняемое поведение» в SPEC нет и не требуется: ни одно утверждение существующих тестов не меняется.

## Пути обхода гейтов
- Линтер AC-3 обходится промежуточной переменной; вариант на `artel.datetime` ловят AC-4/AC-5 (поведенчески), лишний вызов `now` — счётчик AC-4, отдельный расчёт возраста для текста — «устарела на 91 с». Остаётся только поведенчески эквивалентная копия на `watch.datetime` — см. «Проверяемость критериев», форма принята решением Оператора №1.
- Подгонка новых тестов под код через правку существующих тестов закрыта AC-7 (сравнение четырёх файлов с main) и гейтом неослабления пульта.
- Других путей не найдено.

## Вердикт
pass — отклонений нет. Факты SPEC сходятся с кодом (`orchestrator/artel.py:949–958`, `orchestrator/artel.py:1066–1071`, `orchestrator/watch.py:320–326`, `orchestrator/watch.py:27`, `orchestrator/artel.py:703`). Решения Оператора на гейте SPEC №1 и №2 перенесены полностью и друг другу не противоречат (AC-4, AC-5, AC-6, требование 2). Каждый AC ловит хотя бы одну правдоподобную мутацию. Остаточная поведенчески эквивалентная копия разбора на `watch.datetime` — замечание для ревью, не отклонение (форму линтера Оператор оставил решением №1).
