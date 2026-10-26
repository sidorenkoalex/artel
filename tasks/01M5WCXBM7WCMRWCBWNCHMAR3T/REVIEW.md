---
task: 01M5WCXBM7WCMRWCBWNCHMAR3T
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: GitLab А1.1 — интерфейс адаптера, реализация GitLab, подключение ci

## Фаза A — план
Таблица покрытия PLAN полна: требования 1–9 разнесены на шаги 1–2. Оба шага размером с MR. Подход не противоречит архитектуре. Раздел «Возврат из merge_gate (6 пунктов)» совпадает с фактическим diff коммита `f34c796f5`: изменены только `orchestrator/gitlab_adapter.py`, `tests/test_forge_gitlab_request.py` и карта. «Влияние на систему» сходится с diff: `config.py`, `targets.py`, сторожа А0 и инвариантов не тронуты. Откат — revert. Замечаний к плану нет.

## Что изменилось с итерации 1
- `c31508925` — правка долгоживущего `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py`, фикстура `lab`. Раньше она подменяла `time.sleep` на весь процесс, это ловил сторож `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`. Теперь подменяется ссылка адаптера `gitlab_adapter.time`, через `TimeWithSleep(fake.sleep)`. Утверждения тестов не менялись: в diff только строки подмены, импорта и докстринга. Проверяемые свойства AC-11 (паузы повтора не ждут, число вызовов ограничено) сохранены. Основание правки названо в коммите: красный CI ветки.
- `f34c796f5` — возврат merge_gate:
  - `transport` больше не следует перенаправлениям: свой `HTTPRedirectHandler` возвращает `None`, и 3xx приходит кодом через `HTTPError`;
  - `_status_reason` даёт на 3xx причину «перенаправление запрещено», повтора нет;
  - `_address` отказывает при схеме, отличной от `https`;
  - число в шаблоне `:n`, в `_MR_PATH_RE` и при сверке `X-Total` — `[0-9]+` вместо `\d+` и `isdigit()`.

  Шесть новых тестов в `tests/test_forge_gitlab_request.py` несут заявки «Ловит мутацию» с наблюдаемым расхождением. Долгоживущие файлы задачи эти свойства не держат, повтора нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Реестр `IMPLEMENTATIONS` — единственное место литералов хостинга. В `ci.py` литералов хостинга и чтения поля `forge` нет. Сторож AC-17/AC-21 зелёный и после правки `transport`: класс `NoRedirect` стоит внутри `transport`. |
| 2 | OK | `_GitHub.pipeline_status` разбирает check runs в порядке требования 2. Остальные функции отказывают «не реализовано для github» без `gh`. |
| 3 | OK | Токен передаётся в `PRIVATE-TOKEN`. Пара `(None, None)` даёт «токен не получен». Адрес не по https теперь отказ до запроса: токен не уходит открытым текстом. Перенаправление не уносит токен на чужой хост. |
| 4 | OK | Состав `ALLOWED_PAIRS` закреплён тестом. `:id` — только проект записи. `:n` — только ASCII-цифры. Ключи строки запроса ограничены `QUERY_KEYS`. Смена заголовка разрешена только префиксом `Draft: `. |
| 5 | OK | Без изменений с итерации 1. Сверка `X-Total` строже: не-ASCII цифра даёт `unknown`. |
| 6 | OK | Без изменений. |
| 7 | OK | Повтор только на 429/5xx, на 3xx повтора нет. Тексты причин различаются. |
| 8 | OK | Без изменений с итерации 1. |
| 9 | OK | Константы в `gitlab_adapter.py`. `config.py` и `SUPPORTED_FORGES` не тронуты. |

## Замечания
Blocker и major нет. Два наблюдения итерации 1 к Б1/Б2 остаются в силе, дефектами по SPEC этой задачи они не являются:
- `undraft_mr` узнаёт черновик только по префиксу `Draft: `;
- обязательное задание, которого в конвейере нет вовсе, не мешает `green`.

Третье наблюдение (`_address` принимал `http://`) закрыто возвратом merge_gate.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

В итерациях 1 и 2 замечаний нет, реестр пуст.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5wcxbm7wcmrwcbwnchmar3t_forge_guards.py tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py tests/test_forge_gitlab_request.py tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` — 245 passed, 45 subtests.
- `python3 -m pytest -q -p no:cacheprovider tests/test_ci_*.py tests/test_github_adapter*.py tests/test_main_ci_line*.py tests/test_invariants.py` — 261 passed, 1128 subtests.
- Временные мутации `orchestrator/gitlab_adapter.py`, каждая прогнана против `tests/test_forge_gitlab_request.py`. Каждая краснит свой тест, код возвращён:
  - M1: `opener.open` заменён на `urllib.request.urlopen`. Красный `test_transport_does_not_follow_redirect`.
  - M2: схема `http` разрешена. Красный `test_plain_http_address_refused_before_transport`.
  - M3: сверка `X-Total` через `isdigit()`. Красный `test_pipelines_without_x_total_unknown[١]`.
  - M4: шаблон `:n` — `\d+`. Красные оба случая `test_extra_query_key_and_non_ascii_number_refused` с «٣» и «١».
  - M5: ветка 3xx в `_status_reason` выключена. Красный `test_redirect_reply_is_named_refusal`.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет, файл восстановлен. `git status` после всех проверок чистый.
- Статус CI коммита `f34c796f` по пакету — зелёный, 16 проверок.

## Предложения системе
- Пакет ревью итерации 2 не определил базу инкрементального diff и дал полный diff от main. Причина: прошлый вердикт был `approved`, а переход отклонён как «уже учтённый». Инкремент пришлось восстанавливать вручную через `git log main..HEAD` (orchestrator/ — сборка пакета ревьювера).
