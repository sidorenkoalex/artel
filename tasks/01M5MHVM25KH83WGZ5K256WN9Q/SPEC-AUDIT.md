---
task: 01M5MHVM25KH83WGZ5K256WN9Q
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py, tests/test_cycle_hint.py, tests/test_observation_acceptance_return.py, tests/test_observation_edges.py."
spec_sha: cd64155ca6a7cc5d4fb6b9dde4b4284741d8c308
schema_version: 5
---

# SPEC-AUDIT: Свежесть связи наблюдения — одна функция вместо трёх копий

## ТЗ и SPEC
ANSWER-n.md и решений Оператора на гейте SPEC нет. Требования 1–5 ТЗ перенесены
в SPEC почти дословно (SPEC «Требования» 1–5), «Зоны», «Только чтение», «Не
входит» (миграция формата, `rows.sort`), бюджет $25 — совпадают. Ограничение зон
по смыслу ТЗ («только блок свежести `_launch_observation` и `_observation_fresh`;
в watch.py — новые функции и ветка `pid is None`») перенесено в «Не входит».
Требований сверх ТЗ нет. Пункт «Не входит» «Зелёный полный набор `tests/` … держит
пульт» не противоречит ТЗ 5: неизменность четырёх названных файлов закреплена AC-7.
Расхождений нет.

## Факты против кода
Сверено с рабочим каталогом (HEAD 55d469fd):
- `orchestrator/artel.py:950–958` — блок свежести `_launch_observation` после
  `chosen = observer["id"]` (`artel.py:949`): `is None` → «связи с watch ещё нет»,
  `age > порог` → «связь устарела на {age:.0f} с (порог … с)». Подтверждено.
- `orchestrator/artel.py:1066–1071` — `_observation_fresh`: `state != "active"`
  или `last_seen_at is None` → `False`, иначе `age <= порог`. Подтверждено;
  `""` здесь сейчас падает в `fromisoformat("")` — заявленное устранение верно.
- `orchestrator/watch.py:320–326` — `observation_process_state`, ветка
  `pid is None`, пустота через `not`. Подтверждено.
- `orchestrator/watch.py:27` — `from datetime import datetime, timezone`: имя
  `datetime` модуля `watch` есть, подмена `mock.patch.object(watch, "datetime", …)`
  применима (так уже делает `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py:157`).
- `orchestrator/config.py:82–83` — период 30, порог `3 * 30` = 90 с. Подтверждено.
- `fromisoformat` с `"last_seen_at"` в `orchestrator/` — ровно три места
  (`artel.py:954`, `artel.py:1070`, `watch.py:325`); остальные `fromisoformat`
  (`fixation.py:347`, `canary.py:2825`, `ci.py:415`, `advance_gates/review.py:105,126,170`,
  `doctor/model_tariffs.py:29`) константы `"last_seen_at"` не несут — линтер (в)
  на них не сработает. Подтверждено.
- Потребители: `artel.py:1130` (`_observation_fresh`), `artel.py:1133` и
  `doctor/observations.py:16` (`observation_process_state`) — сигнатуры не меняются.
- Существующие тесты не проверяют `ValueError` на `""` (grep по четырём файлам
  ТЗ пуст) — намеренная смена поведения ничьё ожидание не ломает.

Побочный эффект, не отмеченный SPEC: после правки свежесть в `artel.py` берёт
время через `watch.datetime`, поэтому замороженные часы дозора в
`tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py:147–160` начнут влиять и
на свежесть в `artel.py`. В этом тесте `artel.main()` вызывается только для
`observe stop` (`:274–276`), который свежесть не проверяет, — поломки не жду;
отмечаю для разработчика, не как отклонение.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `observation_age` бросает на `""` (проверка `is None` вместо пустоты); возвращает минуты/отрицательный возраст (`fromisoformat(...) - now`) |
| AC-2 | да | `<` вместо `<=` у порога (ровно 90 → `False`); `True` при пустом `last_seen_at`; порог захардкожен не из `config` (при +1 с) |
| AC-3 | да | возвращена копия `datetime.fromisoformat(row["last_seen_at"])` в `artel.py`/`watch.py`; разбор вынесен в функцию с другим именем |
| AC-4 | да (через подмену `watch.datetime`) | `""` снова роняет `ValueError`; отказ по `>=` вместо `>`; блок оставлен на собственном `datetime.now` `artel.py` — при подмене `watch.datetime` на «порог+1» отказа не будет. Формулировка «время берётся один раз» способ проверки не называет — см. Вердикт п.2 |
| AC-5 | да | `_observation_fresh` перестаёт проверять `state`; `""` → `ValueError` |
| AC-6 | да | `"stale"` при ровно пороге; `"fresh"`/`"stale"` вместо `"unstarted"` при пустом |
| AC-7 | да (`git diff main -- <файлы>`) | правка формата записи в `store.py` или одного из четырёх тестов |

## Зоны
Зоны SPEC `orchestrator/watch.py, orchestrator/artel.py, docs/codebase-map.md, tests/`
покрывают всё, что требования заставляют менять: две новые публичные функции
`watch` меняют карту (`docs/codebase-map.md`, раздел `orchestrator/watch.py`),
новый тест — `tests/`. Защищённые пути (`skills/`, `templates/`, `gates.yaml`,
`roles.yaml`, `.github/`) не затрагиваются; приложения PLAN не нужны. Песочница
ролей не расширяется. `store.py`, `config.py` — только чтение, правка им не нужна.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Блок свежести `_launch_observation` (`artel.py:950–958`) | гейт свежести при запуске; `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py` (ac2, ac4–ac6, ac8) | да; `""` теперь отказ вместо `ValueError` (намеренно, ТЗ 2) | те же тесты без правки (AC-7) + новый тест AC-4 | сохраняется |
| `_observation_fresh` (`artel.py:1066–1071`) | поле `fresh` в `observe list` (`artel.py:1130`); `tests/test_observation_edges.py` | да | тот же файл без правки + AC-5 | сохраняется |
| `observation_process_state`, `pid is None` (`watch.py:320–326`) | `doctor` (`doctor/observations.py:16`); `tests/test_observation_acceptance_return.py::test_doctor_warns_for_dead_pid_and_stale_link` | да | тот же тест без правки + AC-6 | сохраняется |
| Существующие тесты | — | не правятся (ТЗ 5) | AC-7 | сохраняется |

Тесты, гейты, лимиты не ослабляются; раздела «Меняемое поведение» SPEC не
несёт и не должен — ни одно существующее утверждение не меняет литерал.

## Пути обхода гейтов
1. Линтер AC-3 ищет константу `"last_seen_at"` в поддереве аргумента
   `fromisoformat`. Копия через косвенность — `stamp = row["last_seen_at"]`,
   затем `datetime.fromisoformat(stamp)` в `artel.py` — линтер проходит, а
   требование 3 по смыслу (одна точка разбора) нарушено. Отчасти страхует AC-4,
   если тест фиксирует время именно подменой `watch.datetime`, но для
   `_observation_fresh` AC-5 такой копии не поймает (она даёт тот же результат).
   Форма линтера задана ТЗ 4(в) дословно, поэтому это вопрос Оператору, не
   ошибка аналитика.
2. AC-4 «текущее время берётся один раз» не называет способ проверки:
   исполнитель тестов может проверить только тексты отказов, и вторая выборка
   `datetime.now` в `artel.py` пройдёт незамеченной.

## Вердикт
concerns — SPEC точно переносит ТЗ, факты о коде подтверждены, зоны полны,
ослаблений нет. Отклонения, решаемые на гейте:
1. `SPEC.md`, AC-3 / требование 4(в) (= ТЗ 4(в)): линтер не ловит копию разбора
   через промежуточную переменную (`artel.py:954`, `artel.py:1070` можно
   переписать так, что AST-проверка зелёная). Варианты: принять как есть (ТЗ
   задал форму) либо дополнить AC-4/AC-5 требованием, чтобы тест фиксировал время
   подменой `watch.datetime` и проверял, что свежесть в `artel.py` ей следует.
2. `SPEC.md`, AC-4, последняя фраза: «время берётся один раз» без способа
   проверки (например, подсчёт вызовов `now` подменённого `watch.datetime`) —
   правдоподобная мутация (второй `datetime.now` в блоке `artel.py:950–958`)
   может пройти.
Замечание без отклонения: подмена `watch.datetime` в
`tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py:157` после правки
затронет и свежесть `artel.py`; на текущих вызовах (`:274–276`, `observe stop`)
это не влияет.
