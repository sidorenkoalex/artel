---
task: T023
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: A4 — роль test_author: приёмочные тесты до кода

## Фаза A: гейт плана

Тот же PLAN.md (шаги 1–9) плюс шаг 10 «Итерация 2: замечания ревью 1» —
две точечные правки в той же зоне, размером с проверяемый MR-шаг, не
«переделать план». Покрытие требований и подход не изменились относительно
итерации 1. **Гейт плана: аппрув** (подтверждаю решение итерации 1).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (состояние tests_writing, роль test_author, скилы) | OK | Без изменений с итерации 1. |
| 2 (AC-разметка SPEC, skip_tests, старые SPEC валидны) | OK | Без изменений; `guard.py --all` перепроверил — 60 файлов, зелёный. |
| 3 (выход роли: acceptance_tests/, без второго документа) | OK | Без изменений. |
| 4 (трассируемость на выходе, эскалация неисполнимости) | OK | Без изменений. |
| 5 (лок фиксацией T021) | OK | Замечание 1 итерации 1 закрыто — см. ниже. |
| 6 (прогон приёмки review→acceptance, сводка) | Реализовано не так | Замечание 2 итерации 1 (таймаут) закрыто в коде, но регрессия закрытия не защищена тестом — см. замечание 1 (major, новое). |
| 7 (триггер пересмотра лока) | OK | Без изменений. |
| 8 (маршрут эскалации test_author) | OK | Без изменений. |
| 9 (manual-критерий: живой прогон test_author) | N/A | Как в итерации 1 — вне зоны кодового ревью. |

**Замечания итерации 1 — проверка закрытия:**

- Blocker (fail-open лока при неответившем git) — закрыт. `orchestrator/fsm.py`
  (ветка `in_dev`, ~157–169) теперь различает `diff is None` (отказ
  перехода, fail-closed) / `is True` (отказ, «изменены после лока») /
  `is False` (переход проходит) — три исхода вместо `if locked and diff`.
  Новый тест `LockTest.test_unreachable_locked_sha_fails_closed`
  (tests/test_acceptance_tests_flow.py) подставляет заведомо недостижимый
  `tests_locked_sha` и проверяет отказ с «не проверен» в выводе. Запустил
  файл целиком реальным git (класс `LockTest` этого требует) — 34/34
  зелёные, в том числе этот тест.
- Major (`acceptance.run()` без таймаута) — закрыт в коде. `config.
  ACCEPTANCE_TIMEOUT_SEC = 300` (orchestrator/config.py:52), `subprocess.run(
  ..., timeout=config.ACCEPTANCE_TIMEOUT_SEC)` в `orchestrator/acceptance.py:32
  –33`, `subprocess.TimeoutExpired` ловится и возвращает `(False, "прогон
  превысил Nс...")`. Но эта защита не codified тестом — см. замечание 1 ниже,
  новый пробел вместо старого.
- Minor (диаграмма состояний) — закрыт. `orchestrator/artel.py:8–10`:
  колонки `^`/`|` теперь выровнены под `in_dev`/`review` для новой ширины
  (`tests_writing` вставлена).
- Minor (опечатка «тестов_writing») — закрыт. `orchestrator/artel.py:16`:
  «Выход из `tests_writing`».

Регрессия: `python3 -m unittest discover -s tests` — 479 тестов, 3 упавших
(`test_multitarget.RoleEnvTest.*`) — та же среда-зависимая причина, что
в итерации 1 (не относится к диффу T023). `tests/test_acceptance_tests_flow.py`
— 34/34 зелёные (было 33, +1 — `test_unreachable_locked_sha_fails_closed`).
`guard.py --all` — зелёный (60 файлов).

## Замечания

- major — orchestrator/acceptance.py:29–33 — фикс замечания 2 (таймаут)
  не защищён ни одним автотестом: ни в `tests/test_acceptance_tests_flow.py`
  (класс `AcceptanceRunTest`), ни где-либо ещё нет теста, мокающего
  `subprocess.run`/`subprocess.Popen` так, чтобы он бросил
  `subprocess.TimeoutExpired`, и проверяющего, что `run()` возвращает
  `(False, "прогон превысил...")`. Проверил мутацией напрямую: убрал
  `timeout=config.ACCEPTANCE_TIMEOUT_SEC)` из вызова `subprocess.run` в
  `orchestrator/acceptance.py` (оставив `capture_output=True, text=True)`)
  и прогнал `python3 -m unittest tests.test_acceptance_tests_flow` —
  34/34 зелёные, ни один тест не покраснел; откатил правку. То есть
  ровно тот регресс, который замечание 2 итерации 1 просило исключить
  («прогон без предела вешает advance/auto»), сейчас снова может тихо
  вернуться при любой будущей правке `acceptance.py`, и об этом никто
  не узнает до продакшн-инцидента. PLAN.md (шаг 10, п. «major») объясняет
  отсутствие автотеста тем, что реальный `time.sleep` в наборе «бьёт по
  скорости прогона» — но это не так: в этой же кодовой базе таймаут
  агента (`config.AGENT_TIMEOUT_SEC`) тестируется без единого реального
  `sleep` — `subprocess.Popen`/`.wait` мокается на прямой `side_effect=
  subprocess.TimeoutExpired(...)` (`tests/test_agent_failure.py:322`,
  `tests/test_agent_log.py:438`). Тот же приём применим к
  `orchestrator/acceptance.py:run()` — мок `subprocess.run` с
  `side_effect=subprocess.TimeoutExpired(cmd=..., timeout=...)`, без
  реального ожидания. Предложение: добавить в `AcceptanceRunTest`
  тест по этому образцу (не обязательно с реальным `time.sleep` — в
  крайнем случае короткий, но мок без сна дешевле и надёжнее).

- minor — templates/PLAN.md, templates/REVIEW.md, templates/TEST_REPORT.md
  — `schema_version: 1 → 2` в этих трёх файлах не упомянут ни в шагах
  PLAN.md, ни в разделе «Влияние на систему» (там перечислены только
  `roles.yaml`, `templates/SPEC.md`, `skills/`). SPEC T023 требование 1
  прямо просит ревьювера «проверить состав [protected-paths] отдельно» —
  проверил: `git diff --stat main...HEAD -- templates/` показывает 4
  файла, не 1. Функционально безвредно — `guard.schema_errors`
  (scripts/guard.py:58–66) отклоняет только `version > SUPPORTED_SCHEMA_VERSION`,
  версия 1 в PLAN/REVIEW/TEST_REPORT остаётся валидной и без этого бампа,
  так что дефекта в поведении нет и артефакты по этим шаблонам не ломались.
  Но раз PLAN явно перечисляет протектед-пути как «одна роль, один скил,
  разметка шаблона» — фактический диф шире перечисленного молча.
  Предложение: либо дополнить «Влияние на систему» этими тремя файлами
  и указать причину бампа (синхронизация версии формата артефактов), либо
  откатить бамп в файлах, где он не нужен по существу.

## Вердикт

changes_requested. Оба замечания итерации 1 (blocker по локу, major по
таймауту) закрыты корректно в коде — проверил чтением diff, прогоном
`LockTest` на реальном git и мутацией `diff_paths`/логики fail-closed в
уме (снятие ветки `diff is None` вернуло бы старое поведение — код это
исключает). Новый major — сама защита от таймаута (то, ради чего было
предыдущее замечание) не codified тестом: показал мутацией, что удаление
`timeout=` не красит ни один тест, а дешёвый способ его протестировать
(мок `TimeoutExpired` без сна) уже есть в кодовой базе как прецедент.
Один minor — недокументированный бамп `schema_version` в трёх шаблонах,
не влияет на поведение, но заявленный в PLAN состав protected-paths уже
диффу не соответствует буквально. Остальное (требования 1–4, 7, 8, оба
minor из итерации 1) — без изменений или закрыто, не трогать.
