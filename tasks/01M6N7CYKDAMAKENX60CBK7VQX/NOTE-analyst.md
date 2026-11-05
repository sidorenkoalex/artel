# Записка analyst — 01M6N7CYKDAMAKENX60CBK7VQX

## Выяснено
- ANSWER-1: мандат A на три файла тестов, монолит, budget_usd 85.
- Шаг 2 (возврат аудита 1 из 2): закрыты все шесть отклонений SPEC-AUDIT.md:
  1. AC-13/AC-2/треб. 10: вид утверждений как на main — равенство для `unsupported_reason`/констант/`*_reason_exact`, вхождение полного текста в выводе действий (unsupported_project.py:200,231,259,291,314,391; epic_draft_promote:87; pair_support:131).
  2. AC-7: «gh не вызван» — только прямой вызов `trigger_rerun` и `ci-rerun`; на approve — нет `run rerun`/`run watch`, `api`-чтения статуса допустимы.
  3. Треб. 7: отказ `ci-rerun` после проверок `--reason` (ci_rerun.py:136-151), до `verifying_status` (:156), в любом состоянии; текст вне verifying меняется (названо).
  4. Треб. 3/AC-4: «для каждого имени файла»; проверено опытом `config.is_protected_path`: ok — префиксы `.github/workflows/` (вкл. `.github`), `**/workflows/`, `**/.github/`; fail — `.github/*`, `**/ci.yml`, `.github/workflows/c`, `.github/workflows/ci.yml`.
  5. Треб. 8/AC-8: случай с подменой реализаций в `forge.IMPLEMENTATIONS` (forge.py:365).
  6. Треб. 9/AC-9/AC-10: «PR не тронут» для GitHub до и после отправки; после — в дополнение к прежнему тексту cleanup.py:297-299; GitLab — прежние записи до и после.

## Не сработало
- `ls`/`rm` нет в PATH роли; чтение — инструментом Read.

## Где остановился
- SPEC.md исправлен, status: ready, guard ок.

## Чего не хватило
- Где `gh` зовётся на пути статуса CI и в ci-rerun до trigger_rerun — пришло только из аудита.
