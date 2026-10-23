---
task: 01M5MHVM25KH83WGZ5K256WN9Q
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Свежесть связи наблюдения — одна функция вместо трёх копий

## Фаза A — план
- Таблица покрытия PLAN полна (требования 1–5 → шаг 1). Один шаг — нормальный
  размер для правки в 3 места + 2 функции, не «сделать всё».
- Подход совпадает с SPEC: функции в `watch`, `datetime` берётся через имя
  модуля `watch`, `artel.py` зовёт `watch.observation_age`/`observation_link_fresh`.
- «Влияние на систему» соответствует diff: тронуты только `orchestrator/artel.py`
  (блок свежести `_launch_observation`, `_observation_fresh`),
  `orchestrator/watch.py` (две новые функции, ветка `pid is None`) и карта.
  Откат — revert, правка обратима.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `watch.py:320–336`: `observation_age` (`not row["last_seen_at"]` → None для None и ""; один `datetime.now(timezone.utc)` через имя модуля `watch`), `observation_link_fresh` (`age is not None and age <= порог`). |
| 2 | OK | `artel.py:950–957`: `age = watch.observation_age(observer)`, None → прежний текст «связи с watch ещё нет», `age > порог` → прежний текст с `age:.0f`; второго `now` нет. `artel.py:1065–1068`: `state != "active"` → False, иначе `observation_link_fresh`. `watch.py:339–342`: `unstarted` при пустом, иначе `fresh`/`stale` по `observation_link_fresh`, своего сравнения с порогом нет. Пустая строка в `artel.py` → «связи нет» / False. Тексты и порядок проверок не менялись. |
| 3 | OK | `grep fromisoformat orchestrator/` — с `last_seen_at` только `watch.py:330`; AST-тест ac3 зелёный. |
| 4 | OK | Долгоживущий файл test_author покрывает (а)/(б)/(в); докстринг ac3 несёт заявку из SPEC дословно. |
| 5 | OK | `store.py`, `config.py`, существующие тесты не в diff (`git diff --stat 55d469fd...HEAD`: только карта, artel.py, watch.py, файл задачи); планка AC-7 зелёная. |

Тесты: у всех методов долгоживущего файла есть «Ловит мутацию: …» с
наблюдаемым расхождением (False/«stale» на пороге, счётчик `now` 0/2,
`ValueError` на ""). Группа «долгоживущий» — свойства кода, верно. Своих
тестов разработчик не добавлял — повтора долгоживущего нет. Неизменённые
утверждения существующих тестов: в `tests/` изменён только новый файл задачи.

## Замечания

Нет. (Наблюдение без severity: в `observation_process_state` проверка
`not row["last_seen_at"]` перед `observation_link_fresh` дублирует ту же
проверку внутри `observation_age` — оставлена для различения `unstarted`
и `stale`, это законно по SPEC.)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py tests/test_observation_edges.py tests/test_observation_acceptance_return.py tests/test_cycle_hint.py -p no:cacheprovider -q` — 33 passed, 62 subtests passed.
- `artel.py plank-run 01M5MHVM25KH83WGZ5K256WN9Q` — `test_ac7_untouched_files.py` 1 passed, код выхода 0.
- Временная мутация 1: в `watch.observation_link_fresh` `<=` → `<` — долгоживущий файл: 7 failed (ac2, ac4, ac5, ac6 на пороге). Код возвращён.
- Временная мутация 2: в `artel._launch_observation` перед проверкой порога второй вызов `watch.observation_age` (второй `now`) — 2 failed (ac4, счётчик `now`). Код возвращён, `git status` чистый.
- `python3 scripts/codebase_map.py` + `git diff -U0 -- docs/codebase-map.md` — различие только в `built_at_sha`, карта свежа; файл возвращён.
- `grep -rn fromisoformat orchestrator/` — разбор `last_seen_at` только в `watch.py:330`.

## Предложения системе
