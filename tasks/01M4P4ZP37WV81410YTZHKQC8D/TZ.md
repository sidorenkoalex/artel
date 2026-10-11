---
task: 01M4P4ZP37WV81410YTZHKQC8D
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Предпроверка гейтов перехода для роли и общий итог полного набора у suite-run и гейтов (шаг 1)

# ТЗ: Предпроверка гейтов перехода для роли и общий итог полного набора у suite-run и гейтов (шаг 1 порядка работ по тестам)

Источник: очередь Оператора 11.10 «Порядок работ по тестам конвейера»,
шаг 1; строка бэклога «Повторное использование итога полного прогона на
гейтах» (сверка 11.10: остаток — suite-run); решение Оператора
11.10.2026 — вести в волне.

Цель: роль узнаёт об отказе перехода до сдачи шага, а не после
(отказы на выходе tests_writing ~50 содержательных за 6 недель,
«замечания ревью не отработаны» — 327); полный набор для одного дерева
не гоняется дважды ролью и гейтом.

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
- Команды роли: `_ROLE_ALLOWED_COMMANDS` (`artel.py` ~1759–1761) —
  `status`, `show`, `log`, `version`, `models`, `report`,
  `acceptance-dry-run`, `plank-run`, `suite-run`; список закрыт по
  умолчанию (~1771–1786).
- Кэш полного набора: `acceptance.full_suite` (~1659) с ключом
  `suite_result_key` (~1571–1601: хеш дерева с приложениями и
  незакоммиченными правками `suite_tree_hash` ~1497, версия Python,
  пакеты, argv pytest), срок `FULL_SUITE_REUSE_MAX_AGE_SEC = 86400`;
  итог базы — `base=True`. `suite-run` (`orchestrator/suite_run.py`
  ~465–524) итог головы (вид `gate`) не сохраняет и не читает.

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
   цепочки.
5. `suite-run` сохраняет итог полного прогона головы и читает его тем
   же ключом `suite_result_key`, что гейты: гейт на том же дереве
   берёт итог роли, роль — итог гейта; повтор назван в выводе и
   журнале; `--fresh` (у `suite-run`) и `--fresh-suite` (у гейтов)
   принуждают прогон.
6. Ослабления нет: переходы, гейты и их отказы не меняются; итог
   переиспользуется только при совпадении полного ключа (дерево с
   приложениями, окружение, команда) и в пределах срока.

Критерии приёмки (направление; планку пишет test_author):
- В песочнице: задача в in_dev с нарушением одного чистого гейта —
  `preflight` печатает отказ тем же текстом, что `advance`, код 1;
  журнал, lease, состояние и ветка не изменились.
- Все чистые гейты пройдены — код 0; гейты с побочными эффектами
  перечислены как «не проверяется».
- Мутация «новый чистый гейт добавлен в переход, но не в preflight»
  ловится сторожем.
- `preflight` из окружения роли разрешена.
- `suite-run` на дереве, где гейт уже гонял полный набор, берёт итог
  без прогона (запись «повтор»); и наоборот; изменение файла дерева
  или приложения — новый прогон.

Зоны: orchestrator/preflight.py (новый), orchestrator/artel.py,
orchestrator/suite_run.py, orchestrator/acceptance.py,
orchestrator/fsm_advance.py (только вынос списка чистых гейтов в общую
точку, без смены поведения), docs/codebase-map.md, tests/.

Приложением: skills/conventions-core.md.

Только чтение (не менять): orchestrator/dry_run.py, orchestrator/advance_gates/test_integrity.py,
orchestrator/advance_gates/two_sided.py, orchestrator/answer.py,
orchestrator/advance_gates/mandate.py, scripts/guard.py,
orchestrator/fsm.py, orchestrator/config.py (кроме новой константы,
если нужна), tests/test_invariants.py, docs/invariants.md, docs/adr/,
docs/operator-gates.md, docs/backlog.md, templates/, CLAUDE.md,
roles.yaml, .github/, .artel/.

Не входит: дедупликация прогонов CI push/pull_request (строка бэклога
«CI ветки задачи — полный набор один раз на sha», отдельно, `ci.yml`
приложением); предпроверка состояний spec_writing, verifying, review.

Рамка: $50.

Набор моделей: по умолчанию.
