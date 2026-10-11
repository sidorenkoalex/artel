---
task: 01M4P4ZP37WV81410YTZHKQC8D
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/preflight.py, orchestrator/artel.py, orchestrator/suite_run.py, orchestrator/acceptance.py, orchestrator/fsm_advance.py, docs/codebase-map.md, tests/
budget_usd: 50
---

# SPEC: Предпроверка гейтов перехода для роли и общий итог полного набора у suite-run и гейтов (шаг 1 порядка работ по тестам)

## Контекст
Роль узнаёт об отказе перехода только после сдачи шага: за 6 недель на
выходе `tests_writing` ~50 содержательных отказов, отказ «замечания ревью
не отработаны» — 327. Режима «сухого» перехода нет: `artel.py advance` →
`fsm.cmd_advance` идёт под lease и пишет журнал; `acceptance-dry-run`
(`orchestrator/dry_run.py`) проверяет только планку. Кроме того, полный
набор `tests/` для одного дерева гоняется дважды: `suite-run`
(`orchestrator/suite_run.py` ~465–524) итог головы (вид `gate`) не
сохраняет и не читает, хотя гейты кэшируют его в `acceptance.full_suite`
по ключу `suite_result_key` (хеш дерева с приложениями и незакоммиченными
правками, версия Python, пакеты, argv pytest; срок
`FULL_SUITE_REUSE_MAX_AGE_SEC`).

## Требования

1. Новая команда `artel.py preflight <id>`: для задачи в состоянии
   `tests_writing` или `in_dev` исполняет чистые гейты выхода из этого
   состояния (`orchestrator/fsm_advance.py`) в том же порядке, что
   переход, и печатает по каждому строку «пройден» либо «отказ: <текст
   отказа>», где текст отказа совпадает с текстом, который даёт переход.
2. Гейты с побочными эффектами (для `tests_writing` — манифест
   долгоживущих тестов, `dry_collect`, `set_state`; для `in_dev` —
   `_acceptance_lock_refuses`, подтяжка main, `_long_lived_manifest_refuses`,
   `_zones_gate` при мандате, `_plan_appendix_gate`, `_origin_push_gate`,
   `_acceptance_run_refuses`) `preflight` не исполняет и печатает по
   каждому «не проверяется предпроверкой: <почему>».
3. Для гейта неослабления тестов (`_test_integrity_gate`) `preflight`
   исполняет его чистое ядро (`_evaluate`) без двустороннего прогона и без
   записи в журнал.
4. `preflight` только читает: не берёт lease, не пишет журнал, не делает
   коммитов и push, не создаёт и не меняет worktree, не меняет состояние
   задачи.
5. Код выхода `preflight`: 0 — все исполненные гейты пройдены; 1 — есть
   хотя бы один отказ; 2 — состояние задачи без предпроверки (любое, кроме
   `tests_writing` и `in_dev`).
6. `preflight` входит в `_ROLE_ALLOWED_COMMANDS` (`orchestrator/artel.py`)
   — разрешена из окружения роли.
7. Приложением PLAN к `skills/conventions-core.md` (или иному общему
   скилу ролей) — указание роли запускать `preflight` перед сдачей шага.
8. Порядок и тексты гейтов `preflight` берёт из той же цепочки, что
   переход (одна точка правды): чистый гейт, добавленный в цепочку
   перехода, попадает в `preflight` без правки `preflight`. Правка
   `orchestrator/fsm_advance.py` ограничена выносом списка гейтов в эту
   общую точку, поведение перехода не меняется. Тест-сторож сверяет
   цепочки перехода и `preflight`.
9. `suite-run` сохраняет итог полного прогона головы и читает его тем же
   ключом `suite_result_key` и тем же хранилищем, что гейты: гейт на том
   же дереве берёт итог прогона роли, `suite-run` — итог гейта, без нового
   прогона.
10. Повтор (взятый без прогона итог) назван в выводе `suite-run` и в
    журнале.
11. `suite-run --fresh` принуждает новый прогон; у гейтов принуждение
    по-прежнему даёт `--fresh-suite`.
12. Итог переиспользуется только при совпадении полного ключа (дерево с
    приложениями, окружение, команда) и в пределах срока
    `FULL_SUITE_REUSE_MAX_AGE_SEC`; переходы, гейты и их отказы не
    меняются.

## Критерии приёмки

AC-1. В песочнице задача в `in_dev` с нарушением ровно одного чистого
гейта: `preflight <id>` печатает отказ этого гейта тем же текстом, что
`advance` той же задачи, и завершается с кодом 1.

AC-2. В сценарии AC-1 после `preflight` журнал задачи, lease, состояние
задачи и ветка задачи (голова и рабочее дерево) не изменились; коммитов
и push нет.

AC-3. Задача в `tests_writing` с нарушением одного чистого гейта выхода
`tests_writing`: `preflight` печатает отказ тем же текстом, что `advance`,
код 1.

AC-4. Задача в `in_dev`, все чистые гейты пройдены: `preflight` печатает
«пройден» по каждому чистому гейту и завершается с кодом 0; гейты с
побочными эффектами перечислены строками «не проверяется предпроверкой:
<почему>».

AC-5. Задача в `in_dev` с ослаблением теста в `tests/`: `preflight`
печатает отказ гейта неослабления (ядро `_evaluate`), двусторонний прогон
не запускается, журнал задачи не изменился.

AC-6. Задача в состоянии вне `tests_writing`/`in_dev` (например,
`spec_writing`, `review`, `verifying`): `preflight` завершается с кодом 2.

AC-7. Мутация «новый чистый гейт добавлен в цепочку перехода, но не
попадает в `preflight`» ловится тестом-сторожем.

AC-8. `preflight` из окружения роли разрешена (`_ROLE_ALLOWED_COMMANDS`).

AC-9. PLAN несёт приложение к `skills/conventions-core.md` (или иному
общему скилу ролей) с указанием роли запускать `preflight` перед сдачей
шага; приложение проходит `git apply --check` на main.

AC-10. `suite-run` на дереве, где гейт уже прогнал полный набор, берёт
итог без прогона; вывод и журнал называют повтор.

AC-11. Гейт на дереве, где `suite-run` уже прогнал полный набор, берёт
итог роли без прогона.

AC-12. Изменение файла дерева или приложения PLAN после прогона — следующий
`suite-run` и следующий гейт гоняют набор заново.

AC-13. `suite-run --fresh` и гейт с `--fresh-suite` гоняют набор заново
при наличии подходящего сохранённого итога.

AC-14. Сохранённый итог с другим окружением или командой pytest либо
старше `FULL_SUITE_REUSE_MAX_AGE_SEC` `suite-run` не переиспользует.

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны ≥ 5 (`orchestrator/preflight.py`,
`orchestrator/artel.py`, `orchestrator/suite_run.py`,
`orchestrator/acceptance.py`, `orchestrator/fsm_advance.py`, плюс
`docs/codebase-map.md` и `tests/`); критериев приёмки ≥ 10 (14);
`budget_usd` ≥ $30 (рамка ТЗ $50).

Решение — **нарезка на 2 части**. Задача состоит из двух независимых
механик, общие у них только сгенерированная карта и `tests/`:
- предпроверка (требования 1–8, AC-1–AC-9) — зоны
  `orchestrator/preflight.py`, `orchestrator/artel.py`,
  `orchestrator/fsm_advance.py`; сама по себе мержима: новая команда только
  читает, переход не меняется (вынос цепочки — без смены поведения), её
  планка зелёная без второй части;
- общий итог полного набора (требования 9–12, AC-10–AC-14) — зоны
  `orchestrator/suite_run.py`, `orchestrator/acceptance.py`; сама по себе
  мержима: `suite-run` начинает писать и читать уже существующее
  хранилище гейтов, предпроверка для этого не нужна.
Ни одна часть не опирается на механику другой; порядок задан только
общими зонами (`docs/codebase-map.md`, `tests/`) — первой идёт
предпроверка как основная цель ТЗ.

Цена: по калибровке предпроверка (9 критериев, 3 файла кода) — ~$40,
общий итог (5 критериев, 2 файла) — ~$25; сумма ~$65 выше рамки ТЗ $50
(лишний проход analyst/test_author). Если Оператор предпочтёт рамку
нарезке — альтернатива монолитом с `budget_usd: 50`; это решение
Оператора на гейте SPEC.

## Деление

### Предпроверка гейтов перехода для роли

Зоны: orchestrator/preflight.py, orchestrator/artel.py, orchestrator/fsm_advance.py, docs/codebase-map.md, tests/
Порядок: первая, без зависимостей
Рамка: $40

Цель: роль узнаёт об отказе перехода до сдачи шага, а не после (отказы
на выходе tests_writing ~50 содержательных за 6 недель, «замечания
ревью не отработаны» — 327).

Факты (origin/main, сверка 11.10):
- Режима «сухого» перехода нет: `artel.py advance` → `fsm.cmd_advance`
  (`fsm.py` ~589) под lease. Есть `acceptance-dry-run`
  (`orchestrator/dry_run.py`, только чтение, без журнала и lease).
- Гейты выхода `orchestrator/fsm_advance.py`:
  - tests_writing (~458–575): чистые функции, возвращающие `GateRefusal`
    (журнал пишет только `_run_gates` при отказе, `advance_gates/_base.py`
    ~34): `_project_profile_gate`, `_tests_writing_code_diff`,
    `stray_plank`, `code_copy`, `test_groups`, `long_lived`; с
    побочными эффектами — манифест (коммит в ссылку документов),
    `dry_collect` (выкладка планки), `set_state`.
  - in_dev (~664–768): чистые — `_answer_gate`, `_capacity_gate`,
    `_mutation_claim_gate`, `_review_rework_gate`,
    `_network_address_gate`; с побочными — `_acceptance_lock_refuses`,
    подтяжка main (`pull.py`), `_long_lived_manifest_refuses`,
    `_zones_gate` при мандате, `_plan_appendix_gate` (worktree),
    `_test_integrity_gate` (журнал, worktree; ядро `_evaluate` чистое),
    `_origin_push_gate` (push), `_acceptance_run_refuses` (прогон планки).
- Команды роли: `_ROLE_ALLOWED_COMMANDS` (`artel.py` ~1796) — закрытый
  по умолчанию список.

Требуется:
1. Команда `artel.py preflight <id>`: для текущего состояния задачи
   (tests_writing, in_dev) исполняет чистые гейты выхода в том же
   порядке, что переход, и печатает по каждому «пройден / отказ:
   <текст отказа, как у перехода>». Гейты с побочными эффектами не
   исполняются: печатается «не проверяется предпроверкой: <почему>»;
   для гейта неослабления исполняется чистое ядро (`_evaluate`) без
   двустороннего прогона и без журнала.
2. `preflight` только читает: без lease, без журнала, без коммитов,
   push, worktree и смены состояния; код выхода 0 — все чистые гейты
   пройдены, 1 — есть отказ, 2 — состояние без предпроверки.
3. `preflight` доступна роли (`_ROLE_ALLOWED_COMMANDS`); скил
   `skills/conventions-core.md` (или иной общий скил ролей — приложением)
   говорит роли запускать её перед сдачей шага.
4. Порядок и тексты гейтов `preflight` берёт из той же цепочки, что
   переход (одна точка правды): добавленный в переход чистый гейт
   попадает в `preflight` без правки `preflight`; тест-сторож сверяет
   цепочки. `orchestrator/fsm_advance.py` — только вынос списка чистых
   гейтов в общую точку, без смены поведения.
5. Ослабления нет: переходы, гейты и их отказы не меняются.

Критерии приёмки (направление): в песочнице задача в in_dev с
нарушением одного чистого гейта — `preflight` печатает отказ тем же
текстом, что `advance`, код 1; журнал, lease, состояние и ветка не
изменились; все чистые гейты пройдены — код 0, гейты с побочными
эффектами перечислены как «не проверяется»; мутация «новый чистый гейт
добавлен в переход, но не в preflight» ловится сторожем; `preflight` из
окружения роли разрешена.

Приложением: skills/conventions-core.md.

Только чтение (не менять): orchestrator/dry_run.py,
orchestrator/advance_gates/test_integrity.py,
orchestrator/advance_gates/two_sided.py, orchestrator/answer.py,
orchestrator/advance_gates/mandate.py, scripts/guard.py,
orchestrator/fsm.py, orchestrator/config.py (кроме новой константы,
если нужна), tests/test_invariants.py, docs/invariants.md, docs/adr/,
docs/operator-gates.md, docs/backlog.md, templates/, CLAUDE.md,
roles.yaml, .github/, .artel/.

Не входит: предпроверка состояний spec_writing, verifying, review;
общий итог полного набора у suite-run и гейтов (вторая часть деления).

### Общий итог полного набора у suite-run и гейтов

Зоны: orchestrator/suite_run.py, orchestrator/acceptance.py, docs/codebase-map.md, tests/
Порядок: после части 1
Рамка: $25

Цель: полный набор для одного дерева не гоняется дважды ролью и гейтом.

Факты (origin/main, сверка 11.10): кэш полного набора —
`acceptance.full_suite` (~1659) с ключом `suite_result_key` (~1571–1601:
хеш дерева с приложениями и незакоммиченными правками `suite_tree_hash`
~1497, версия Python, пакеты, argv pytest), срок
`FULL_SUITE_REUSE_MAX_AGE_SEC = 86400`; итог базы — `base=True`.
`suite-run` (`orchestrator/suite_run.py` ~465–524) итог головы (вид
`gate`) не сохраняет и не читает.

Требуется:
1. `suite-run` сохраняет итог полного прогона головы и читает его тем
   же ключом `suite_result_key`, что гейты: гейт на том же дереве
   берёт итог роли, роль — итог гейта; повтор назван в выводе и
   журнале; `--fresh` (у `suite-run`) и `--fresh-suite` (у гейтов)
   принуждают прогон.
2. Ослабления нет: переходы, гейты и их отказы не меняются; итог
   переиспользуется только при совпадении полного ключа (дерево с
   приложениями, окружение, команда) и в пределах срока.

Критерии приёмки (направление): `suite-run` на дереве, где гейт уже
гонял полный набор, берёт итог без прогона (запись «повтор»); и
наоборот; изменение файла дерева или приложения — новый прогон.

Только чтение (не менять): orchestrator/fsm.py,
orchestrator/advance_gates/test_integrity.py, scripts/guard.py,
orchestrator/config.py (кроме новой константы, если нужна),
tests/test_invariants.py, docs/invariants.md, docs/adr/, templates/,
CLAUDE.md, roles.yaml, .github/, .artel/.

Не входит: дедупликация прогонов CI push/pull_request (строка бэклога
«CI ветки задачи — полный набор один раз на sha», отдельно, `ci.yml`
приложением).

## Не входит

- Дедупликация прогонов CI push/pull_request (строка бэклога «CI ветки
  задачи — полный набор один раз на sha» — отдельная задача, `ci.yml`
  приложением).
- Предпроверка состояний `spec_writing`, `verifying`, `review`.
- Исполнение `preflight` гейтов с побочными эффектами и двустороннего
  прогона гейта неослабления.
- Смена поведения переходов, гейтов и их отказов.
- Правка `skills/conventions-core.md` в ветке задачи: защищённый путь,
  меняется только приложением PLAN (требование 7).
- Повторное использование записи `--failed` по одному sha
  (`acceptance.save_failures`) как итога гейта: она не несёт полного
  ключа, ожидание
  `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py::SuiteReuseTest::test_ac12_suite_run_record_is_not_gate_result`
  не меняется.
- Правка путей «только чтение» ТЗ: `orchestrator/dry_run.py`,
  `orchestrator/advance_gates/test_integrity.py`,
  `orchestrator/advance_gates/two_sided.py`, `orchestrator/answer.py`,
  `orchestrator/advance_gates/mandate.py`, `scripts/guard.py`,
  `orchestrator/fsm.py`, `orchestrator/config.py` (кроме новой
  константы, если нужна), `tests/test_invariants.py`,
  `docs/invariants.md`, `docs/adr/`, `docs/operator-gates.md`,
  `docs/backlog.md`, `templates/`, `CLAUDE.md`, `roles.yaml`,
  `.github/`, `.artel/`.

## Материалы

- ТЗ: очередь Оператора 11.10 «Порядок работ по тестам конвейера», шаг 1;
  строка бэклога «Повторное использование итога полного прогона на
  гейтах» (сверка 11.10: остаток — suite-run).
- `orchestrator/fsm_advance.py`, `orchestrator/advance_gates/_base.py`
  (`_run_gates`), `orchestrator/acceptance.py` (`full_suite`,
  `suite_result_key`, `save_suite_result`, `saved_suite_result`),
  `orchestrator/suite_run.py`.
