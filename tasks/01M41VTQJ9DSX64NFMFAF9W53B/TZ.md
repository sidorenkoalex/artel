---
task: 01M41VTQJ9DSX64NFMFAF9W53B
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Отмена CI на документах и режима guard --artifact-branch

Родительская задача: 01M41VCKTEB1SRTD2VW4X2Y6HM — ADR-0021, этап 1 (в): команда чтения документов задачи, отмена CI на artifact/**, уборка веток artifact/**
Зоны: scripts/guard.py, scripts/ci_push_class.py, tests/, docs/codebase-map.md
Порядок: первая, без зависимостей
Рамка: $25

Источник: ADR-0021 (принят 29.09.2026), пп. 4, 12, 13 (этап 1); часть (в)
этапа 1; SPEC задачи-родителя 01M41VCKTEB1SRTD2VW4X2Y6HM (требования 6,
7, 8, 10 — перечень гейтов, проверяющих артефакты, приведён там).

Факты (пин d860c974):
- пушей в `artifact/**` пульт больше не делает;
- `.github/workflows/ci.yml` запускается на push в `["main", "task/**",
  "artifact/**"]`, задание `guard` на `artifact/*` зовёт
  `scripts/guard.py --all --artifact-branch`, задание `canary-guid-leak`
  исключает `refs/heads/artifact/` условием;
- `scripts/ci_push_class.py` относит `artifact/` к отдельному классу;
- инвариант 36 в `docs/invariants.md` занят дважды: первый — «прогон CI
  существует для каждого пуша в `main`, `task/**`, `artifact/**`»
  (`CiJobsByPushClassInvariantTest`), второй — порядок состояний FSM.

Требуется:
1. Приложением к PLAN для `.github/workflows/ci.yml`:
   - `artifact/**` убирается из `on.push.branches`;
   - развилка `--artifact-branch` задания `guard` убирается;
   - условия заданий со ссылкой на `refs/heads/artifact/` убираются.
2. `scripts/ci_push_class.py` теряет класс `artifact/`: пуш в
   `artifact/<x>` классифицируется общим правилом не-`main` ветки.
3. Режим `--artifact-branch` в `scripts/guard.py` убирается вместе с
   ключом, параметром `check_content(..., artifact_branch_mode)` и
   функциями режима, если они больше нигде не нужны; докстринг и
   комментарии правятся. `guard.py <файлы>` и `guard.py --all` без флага
   не меняются. Новых гейтов не вводится: все проверки режима уже
   исполняют гейты переходов и гейт мержа (перечень — требование 8 SPEC
   родителя). Существующие гейты не ослабляются.
4. Приложением к PLAN, проверенным `git apply --check`, для
   `docs/invariants.md` и `tests/test_invariants.py`:
   - первый инвариант 36 снимает требование CI на `artifact/**` с
     заменой гейтами переходов (ADR-0021 п.12) и называет `python-min`
     наравне с `python`;
   - `CiJobsByPushClassInvariantTest` проверяет `ci.yml` после
     приложения 1;
   - второй инвариант 36 получает следующий свободный номер, ссылки на
     него поправлены.
5. Существующие тесты (`tests/test_guard_artifact_branch_mode.py`,
   тесты класса `artifact/` в `tests/test_ci_push_class.py`, вызовы
   режима в `tests/test_guard_extraneous_acceptance_files.py`) меняются
   или удаляются только в объёме, прямо требуемом ADR-0021, — перечнем в
   PLAN. Гейт неослабления тестов потребует на это мандат Оператора.

Критерии — AC-12…AC-15 SPEC родителя.

Не входит: команда `docs` и уборка веток `artifact/**` (вторая часть);
правка `docs/operator-session.md` и `docs/backlog.md` (только чтение);
этапы 2–4 ADR-0021.