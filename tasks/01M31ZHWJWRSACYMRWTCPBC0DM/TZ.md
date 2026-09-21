---
task: 01M31ZHWJWRSACYMRWTCPBC0DM
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Токены рядом с долларами: status, RETRO, report

Родительская задача: 01M31Y3RXXKS1BGC6JH3527FN0 — Интерфейс исполнителя, часть 2: вывод, стоимость и провалы у провайдера, токены рядом с долларами
Зоны: orchestrator/catalog.py, orchestrator/report.py, orchestrator/retro.py, orchestrator/retro_corpus.py, docs/stack.md, tests/
Порядок: после части 1
Рамка: $40

Часть 2 линии «Интерфейс исполнителя, часть 2» (план провайдеров ролей,
`docs/research/providers-codex-plan.md`, задача 3; решение Оператора
20.09: единица гейтов — доллар, токены показываются рядом). Часть 1
нарезки к этому моменту смержена: строка журнала «agent cost
KNOWN/PARTIAL» несёт `provider=` рядом с `model=` и датой тарифа.

Факты: токены учтены в журнале (разбивка по видам в строке «agent cost
KNOWN», суммарное число в «agent run finished»), но показаны скупо —
`status` (`orchestrator/catalog.py::cmd_status`) печатает только
«$spent/budget»; RETRO (`orchestrator/retro.py`, блок стоимости) —
доллары и одно суммарное число токенов по роли, разбивки по видам нет;
`report` (`orchestrator/report.py`) — доллары и калибровку курса по
модели. `orchestrator/retro_corpus.py` собирает поля RETRO
(`RETRO_FIELDS` = operator, model, artel_sha) в кэш корпуса.

Требуется:
1. `status`: по каждой задаче суммарные токены рядом с «$spent/budget»,
   одна строка на задачу сохраняется.
2. RETRO: по каждой роли доллары, токены суммарно и разбивка по четырём
   видам (`input`/`output`/`cache_write`/`cache_read`), плюс провайдер и
   модель шагов роли.
3. `report`: токены по видам рядом с долларами в разрезе задач и ролей.
4. Задача (роль, строка) без записей токенов показывает прочерк, а не
   ноль — во всех трёх местах показа.
5. `orchestrator/retro_corpus.py` добавляет в собираемые поля
   провайдера, если RETRO его несёт; RETRO без провайдера по-прежнему
   попадает в кэш на прежних полях.
6. `docs/stack.md`: абзац «Вывод и стоимость у провайдера», написанный
   частью 1, дополняется тем, где показаны токены.
7. Тесты (tests/): `status`/RETRO/`report` показывают токены по видам и
   прочерк без данных; существующие `tests/test_report.py`,
   `tests/test_retro.py` остаются зелёными; перечень обновлённых
   ожиданий — в PLAN.

Только чтение (не менять): `orchestrator/spend.py` (разбор строк журнала
`known_cost_breakdown`/`known_cost_pairs` уже умеет обе формы после
части 1), `orchestrator/store.py`, `orchestrator/snapshot.py`
(frontmatter RETRO), `orchestrator/agent_log.py`,
`orchestrator/budget.py`.

Не входит: разбор вывода и стоимость у провайдера (часть 1 нарезки);
провайдер `codex` (задача 4 плана); отчёт по провайдеру и бейзлайны
канарейки (задача 6); смена единицы бюджета — доллар остаётся.