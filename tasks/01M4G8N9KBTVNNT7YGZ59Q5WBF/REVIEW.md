---
task: 01M4G8N9KBTVNNT7YGZ59Q5WBF
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 5
---

# REVIEW: Гейт неослабления тестов видит утверждения в унаследованных помощниках и в tests/sandbox.py

## Фаза A — план
- Таблица покрытия полна (1–6 → шаги 1–6); шаг 6 описывает правки по
  ревью итерации 2.
- «Влияние на систему» теперь называет оба условия запуска `git grep`
  (`weakened_helpers`, `changed_classes`) и слои наследников; «Риски» —
  стоимость гейта на правке импортов `tests/sandbox.py` (6 классов
  семейства `RealGitSandbox`, ~200 файлов). Соответствует коду.
- Полный набор после правки итерации 2 разработчиком не прогнан (отказ
  `suite-run` из-за чужого прогона) — честно отмечено; CI коммита
  3256fe2b зелёный (16 проверок), это закрывает полный набор.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1. |
| 2 | OK | R2-F1 закрыт: файл диффа, найденный поиском по изменённому классу, не пересравнивается, но его наследники из головного текста продолжают поиск (`_compare`, цикл вызывающих). Сценарий «промежуточный модуль в диффе с комментарием» закреплён тестом. |
| 3 | OK | AC-3 зелёный. |
| 4 | OK | Без изменений. |
| 5 | OK | 15 → 2 (проверено в итерации 1). |
| 6 | OK | Абзац п.4 о наследниках теперь верен и для промежуточного модуля в диффе. |

## Замечания

Новых замечаний нет. Разбор правки итерации 3:
- `orchestrator/advance_gates/test_integrity.py` `_compare`: файл диффа
  берётся из `side_sources[1]` (голова); удалённый в голове файл `git grep`
  по голове не вернёт, ветка `text is None → continue` — защитная.
  Файл диффа больше не сравнивается повторно (наблюдение не задваивается),
  `visited` предотвращает повторный обход. Путь переименования: `git grep`
  отдаёт головной путь, `side_sources[1]` проиндексирован им же.
- Тест `HeirOutsideDiffTest::test_heir_through_intermediate_module_in_diff_is_reached`:
  заявка «Ловит мутацию» наблюдаема (пропуск файла диффа до сбора
  наследников → эскалации нет) и подтверждена временной мутацией (ниже).
- Дифф `tests/` всей ветки — только добавления в трёх новых файлах;
  существующие тесты не изменены, долгоживущий файл задачи не дублируется.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R2-F1 | accepted | orchestrator/advance_gates/test_integrity.py::_compare (цикл поиска) | Наследники изменённого класса не искались через промежуточный модуль, лежащий в диффе | — | Принято: `continue` по `in_diff` снят, наследники файла диффа берутся из головного текста; тест на сценарий ревьювера, временная мутация (возврат `in_diff` в условие `continue`) красит именно его. |
| R2-F2 | accepted | PLAN.md «Влияние на систему» / «Риски» | Условие запуска `git grep` было описано как «только при ослабленном помощнике» | — | Принято: оба условия и стоимость на правке `tests/sandbox.py` названы. |

## Вердикт
approved — R2-F1 и R2-F2 приняты, новых blocker/major нет; реестр закрыт целиком.

## Проверено исполнением
- `python3 -m pytest -q tests/test_test_integrity_helper_heirs.py tests/test_guard_helper_scope.py tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py tests/test_test_integrity_gate.py tests/test_guard_assertion_changes.py tests/test_class_mandate_units.py tests/test_answer_mandate.py tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py` — 118 passed, 30 subtests passed.
- Временная мутация (возвращено `git checkout`): в `_compare` условие `continue` снова `path in in_diff or path in visited or not in_scope(path)` → `tests/test_test_integrity_helper_heirs.py`: 1 failed (`test_heir_through_intermediate_module_in_diff_is_reached`), 8 passed.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет (карта свежа), изменение откачено.
- `git diff main...HEAD --stat -- tests/` — только три новых файла, 928 добавлений, удалений 0.
- CI коммита 3256fe2b — зелёный (из пакета).

## Предложения системе
- Инкрементальный diff пакета включал автокоммит пульта (`3256fe2b`), правку
  `docs/codebase-map.md` пакет исключает — удобно; стоит в пакете также
  отмечать, что автокоммит трогает только карту, чтобы ревьюверу не
  проверять это `git show --stat` каждую итерацию.
