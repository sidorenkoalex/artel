---
task: 01M4M68557TT4KYN814H8AZ01A
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Этап 4 ADR-0021, часть B: исторические снимки для каталогов tasks/ без refs/artifacts

# ТЗ: Этап 4 ADR-0021, часть B — исторические снимки для каталогов tasks/ без refs/artifacts

Источник: ADR-0018 условия уборки `tasks/` (~74: «вторая копия для
каталогов, у которых нет ни снимка, ни ветки»); ADR-0021 этап 4 (~223);
строка бэклога 27.09 «Отмена наложения снимка на main и уборка каталога
tasks/»; сверка сессии 11.10 по origin/main 415f1de4; решение Оператора
11.10.2026 — отдельная задача B, после неё и задачи A Оператор убирает
`tasks/*` из main своим коммитом.

Факты (origin/main 415f1de4, сверка 11.10):
- В main 367 каталогов `tasks/<id>/`; на origin 413 ссылок
  `refs/artifacts/<id>`, веток `artifact/*` нет.
- 101 каталог main без `refs/artifacts/<id>`: 93 задачи T001–T102 и 8
  ранних (01M1GCHKG8DDK4DCZWCE3DYKWC, 01M1GCN1FPSC1A6WK9WD1Q1V8X,
  01M1GHZTX9YEPF0TY46QWZAGD8, 01M1GJ3ZP1YGG5QRB6FQ44NN8D,
  01M1GS5HZ1JXFGKVR95HEW0AEZ, 01M1GV6H5DDDCWW4G3GW1D3A1X,
  01M1H186VEVG6NF40YKH1338MD, 01M1H224X5A8W159MKF1Q24R5Y). После уборки
  их документы читались бы только из истории main.
- У 266 каталогов со снимком снимок полнее или новее main, кроме 6
  файлов в 4 задачах, где main новее снимка (правки после мержа):
  `tasks/01M1SHJTT0V516BWHYXWS50F3G/ANSWER-1.md`,
  `tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/ANSWER-2.md`,
  `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/test_ac3_unknown_rate_alert_and_estimate.py`,
  `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/test_ac2_known_rate_partial_charge.py`,
  `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/test_ac3_entry_points_ignore_local_pin.py`,
  `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/_sandbox.py`.
- Ссылки документов пишет только пульт (правило «артефактные ветки пишет
  только пульт»); закрытая ссылка неизменна, её сверяет `doctor` по
  коммиту закрытия из журнала (`orchestrator/snapshot.py`,
  `CLOSING_ACTION`, `closing_sha`). Читатели документов
  (`orchestrator/docs_fetch.py`, `catalog`, `retro_corpus` и др.) уже
  берут `refs/artifacts/<id>` и падают на main как запасной путь.
- Команды для создания ссылки документов из дерева main нет — сегодня это
  был бы обход пульта.

Требуется:
1. Команда пульта Оператора создаёт `refs/artifacts/<id>` для каждого
   каталога `tasks/<id>/` текущего `origin/main`, у которого ссылки нет ни
   локально, ни на origin: дерево ссылки — `tasks/<id>/` из main как
   есть, коммит помечен как исторический снимок (источник — sha main);
   ссылка отправляется на origin. Пробный режим печатает перечень без
   записи.
2. Существующие ссылки `refs/artifacts/<id>` команда не меняет ни при
   каких условиях (закрытая ссылка неизменна); файлы, где main новее
   существующего снимка, команда только перечисляет в отчёте (путь, sha
   main, sha снимка) — решение о них за Оператором.
3. Повторный запуск идемпотентен: созданная ссылка второй раз не
   создаётся и не переписывается.
4. Журнал: созданный исторический снимок записывается так, чтобы
   `doctor` сверял его неизменность так же, как ссылку закрытой задачи;
   для задачи, которой нет в БД (T-серия может отсутствовать), — запись
   без задачи либо иной способ, названный в SPEC; ложных тревог `doctor`
   нет.
5. После создания ссылок читатели документов находят документы
   исторической задачи через `refs/artifacts/<id>` без main (проверяется
   на песочнице с убранным `tasks/`).
6. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- Песочница: два каталога в main без ссылки и один со ссылкой —
  команда создаёт ровно две ссылки, деревья совпадают с main, третью не
  трогает; пробный режим ничего не пишет.
- Повторный запуск — ноль новых ссылок.
- Каталог со снимком, где файл в main новее, — строка отчёта, ссылка не
  изменена.
- `doctor` после создания: тревог о неизменности нет; подмена
  исторической ссылки — тревога.
- Документ исторической задачи читается через `docs_fetch` при
  отсутствующем `tasks/` в main.
- Мутация «команда переписывает существующую ссылку» ловится.

Зоны: orchestrator/artel.py, orchestrator/snapshot.py, orchestrator/doctor/,
docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/fsm_merge_gate.py,
orchestrator/fsm_postmerge.py, orchestrator/retro.py, orchestrator/cleanup.py,
orchestrator/artifact_branch.py, orchestrator/docs_fetch.py, orchestrator/store.py,
orchestrator/config.py, orchestrator/catalog.py, scripts/,
.github/workflows/ci.yml, tests/test_invariants.py, docs/invariants.md,
docs/adr/, docs/roadmap.md, docs/backlog.md, docs/operator-session.md,
templates/, skills/, CLAUDE.md, models.yaml, roles.yaml, targets.yaml,
tasks/, docs/retro/, .artel/.

Не входит: запуск команды на настоящем репозитории (делает Оператор
после мержа); удаление `tasks/*` из main и правка ссылок на
`tasks/<id>/` в документах (коммит Оператора); отмена наложения снимка
на main (задача A, 01M4M67SGNEYMN9F1C7XVX24XE); изменение существующих
снимков, в том числе шести файлов, где main новее.

Рамка: $25.

Набор моделей: по умолчанию.
