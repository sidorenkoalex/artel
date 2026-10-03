---
task: 01M41VTQJ9DSX64NFMFAF9W53B
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: scripts/guard.py, scripts/ci_push_class.py, tests/, docs/codebase-map.md
budget_usd: 25
---

# SPEC: Отмена CI на документах и режима `guard --artifact-branch`

## Контекст
Подзадача (первая часть деления) задачи 01M41VCKTEB1SRTD2VW4X2Y6HM —
ADR-0021, этап 1 (в); источник — ADR-0021 (принят 29.09.2026), пп. 4, 12,
13. На пине d860c974 пульт больше не пушит в `artifact/**`, но
`.github/workflows/ci.yml` всё ещё запускается на push в `artifact/**`:
задание `guard` на таких ветках зовёт `scripts/guard.py --all
--artifact-branch`, задание `canary-guid-leak` исключает
`refs/heads/artifact/` условием. `scripts/ci_push_class.py` держит под
`artifact/` отдельный класс. Первый инвариант 36 в `docs/invariants.md`
(«прогон CI существует для каждого пуша в `main`, `task/**`,
`artifact/**`», `CiJobsByPushClassInvariantTest`) требует такого прогона,
а номер 36 занят дважды: второй — порядок состояний FSM. Задача снимает
эти хвосты; проверку документов уже исполняют гейты переходов и гейт
мержа (перечень — требование 8 SPEC родителя).

## Требования

1. **Приложение к PLAN для `.github/workflows/ci.yml`** (путь защищён,
   правка — приложением, применяет Оператор):
   - `artifact/**` убирается из `on.push.branches`;
   - развилка `--artifact-branch` задания `guard` убирается (на `main`
     остаётся вызов `--all`);
   - условия заданий со ссылкой на `refs/heads/artifact/` убираются.
2. **`scripts/ci_push_class.py` теряет класс `artifact/`:** пуш в
   `artifact/<x>` классифицируется общим правилом не-`main` ветки.
3. **Режим `--artifact-branch` в `scripts/guard.py` убирается** вместе с
   ключом, параметром `check_content(..., artifact_branch_mode)` и
   функциями режима (`_artifact_branch_report`, `basic_frontmatter_errors`,
   `is_draft_lenient`, `DRAFT_LENIENT_TYPES`, `ARTIFACT_BRANCH_FLAG`), если
   они больше нигде не нужны. Модульный докстринг и комментарии,
   описывающие режим, правятся. Поведение `guard.py <файлы>` и
   `guard.py --all` без флага не меняется.
4. **Новых гейтов не вводится, существующие не ослабляются.** Все
   проверки режима уже исполняют гейты переходов и гейт мержа (перечень —
   требование 8 SPEC родителя 01M41VCKTEB1SRTD2VW4X2Y6HM).
5. **Приложение к PLAN для `docs/invariants.md` и
   `tests/test_invariants.py`,** проверенное `git apply --check` на
   чистом дереве (подтверждение — в PLAN):
   - первый инвариант 36 снимает требование CI на `artifact/**` с заменой
     гейтами переходов (ADR-0021 п.12) и называет задание `python-min`
     наравне с `python`;
   - `CiJobsByPushClassInvariantTest` проверяет `ci.yml` после приложения
     требования 1;
   - второй инвариант 36 (порядок состояний FSM) получает следующий
     свободный номер сквозной нумерации, ссылки на него поправлены.
6. **Существующие тесты** — `tests/test_guard_artifact_branch_mode.py`,
   тесты класса `artifact/` в `tests/test_ci_push_class.py`, вызовы режима
   в `tests/test_guard_extraneous_acceptance_files.py` — меняются или
   удаляются только в объёме, прямо требуемом ADR-0021. Перечень
   изменённых и удалённых тестов приводится в PLAN; гейт неослабления
   тестов потребует на это мандат Оператора.

## Критерии приёмки

AC-1. `scripts/ci_push_class.py::classify("push",
"refs/heads/artifact/<x>", …)` не выделяет артефактную ветку в отдельный
класс. Исход совпадает с исходом для любой другой не-`main` ветки, и
причина не называет артефактную ветку.

AC-2. `scripts/guard.py` не знает режима `--artifact-branch`. Вызов с
этим ключом не печатает сводку «сдано N / черновиков M / нарушений K» и
не понижает нарушение содержания черновика до предупреждения: черновик
SPEC с нарушением содержания даёт код 1. `check_content` не принимает
параметр `artifact_branch_mode`.

AC-3. PLAN несёт приложение к `.github/workflows/ci.yml`. После него
`on.push.branches` не содержит `artifact/**`, задание `guard` не содержит
развилки `--artifact-branch`, ни одно условие задания не ссылается на
`refs/heads/artifact/`. Приложение проходит `git apply --check` на
чистом дереве, это подтверждено в PLAN.

AC-4. PLAN несёт приложение к `docs/invariants.md` и
`tests/test_invariants.py`, проходящее `git apply --check`. После его
применения:
- в таблице нет двух инвариантов с одним номером;
- первый инвариант 36 не требует прогона CI на `artifact/**`, называет
  замену гейтами переходов и задание `python-min` наравне с `python`;
- бывший второй инвариант 36 несёт новый номер;
- `CiJobsByPushClassInvariantTest` зелёный на `ci.yml` после приложения
  AC-3.

## Оценка объёма и деление

Прогноз диффа: 45 КиБ (основная доля — удаление режима из
`scripts/guard.py` и удаление/сокращение
`tests/test_guard_artifact_branch_mode.py` ~14 КиБ; приложения к
`ci.yml`, `docs/invariants.md`, `tests/test_invariants.py` — единицы КиБ;
ниже половины потолка гейта ёмкости 256 КиБ).

Сработавший сигнал: зона задевает механизм, на который опирается запись
`docs/invariants.md` (первый инвариант 36, `CiJobsByPushClassInvariantTest`,
ADR-0016). Остальные сигналы не срабатывают: 4 критерия приёмки, 4 зоны,
`budget_usd` 25.

**Обоснование монолита** (материал для решения Оператора). Задача уже
является частью нарезки родителя 01M41VCKTEB1SRTD2VW4X2Y6HM. Дальнейший
разрез неработоспособен: инвариант 36 и его тест проверяют `ci.yml`, поэтому
приложения к `ci.yml` и к `docs/invariants.md`/`tests/test_invariants.py`
обязаны примениться одним мержем (ADR-0021 п.12) — иначе
`CiJobsByPushClassInvariantTest` краснеет на промежуточном состоянии.
Снятие режима guard без снятия развилки `--artifact-branch` в `ci.yml`
оставило бы CI с вызовом несуществующего режима; снятие класса
`artifact/` в `ci_push_class.py` — часть той же смены CI. Объём (4 AC,
$25) не даёт оснований делить.

## Не входит

- Команда `artel.py docs` и уборка веток `artifact/**` — вторая часть
  деления родителя.
- Правка `docs/operator-session.md` и `docs/backlog.md` — только чтение.
- Этапы 2–4 ADR-0021.
- Новые гейты проверки документов — их роль уже исполняют существующие
  гейты (требование 8 SPEC родителя).
- Непосредственная правка `.github/workflows/ci.yml`, `docs/invariants.md`
  и `tests/test_invariants.py` в ветке задачи — только приложениями к
  PLAN; применяет Оператор.

## Материалы

- ADR-0021, пп. 4, 12, 13.
- SPEC родителя 01M41VCKTEB1SRTD2VW4X2Y6HM: требования 6–8, 10; критерии
  AC-12…AC-15 (здесь — AC-1…AC-4).
- Места на пине: `scripts/guard.py:3048-3227` (режим), `ci.yml:14,51,101`,
  `docs/invariants.md:66`, `tests/test_invariants.py:2034-2142`,
  `tests/test_ci_push_class.py:32-44,229`.
