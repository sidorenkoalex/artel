# Записка spec_auditor — 01M5FRYVP4NF81VT00FYPHPWJH

## Выяснено
- Круг 2 (spec_sha 4ef61473…): все 9 решений Оператора круга 1 перенесены в SPEC (треб. 3, 4, 6; AC-4, AC-5, AC-7, AC-8, AC-10, AC-12, AC-13; «Не входит»).
- Адреса SPEC сверены повторно: acceptance.py:37/:709/:725/:3170, fsm.py:792 (ленивый импорт)/:1266, tests_writing.py:623, auto.py:314, outcome_integrity.py:65-66/:364/:556/:564, two_sided.py:452/:457, refusal_classes.py:92, orphans.py:25/:38/:82/:106/:118, liveness.py:27-41, mandate.py:392/:402/:495-510 — совпадают.
- Цикл импорта подтверждён: advance_gates/acceptance.py:17-18 (fsm на уровне модуля) ↔ tests_writing.py:15 (`from .acceptance import blob_sha256`). Сейчас все три порядка импорта проходят.
- Существующие тесты, которые изменение не ломает: AC-17/18/19 (tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py:784-890) — пути `src/…test.ts` полностью совпадают с новой регуляркой; argv-тесты компонента — только vitest/pytest-own без from_components (test_component_report_gates.py:141,164); ключ компонента в тестах не захардкожен; уборка в тестах изолирована песочницей (test_sandbox_determinism_helpers.py:130-160).
- Новые мелочи: (1) AC-8 «тест проверяет, что подмена вызвана» неоднозначен для случая без удалений; (2) поведение при ошибке shlex на несбалансированных кавычках PYTEST_ADDOPTS не задано; (3) обёртка-команда (sh -c / скрипт) обходит и флаги, и проверку — вне ТЗ.

## Не сработало
- `$VAR` в Bash и `ls` недоступны — пути писать литералом.

## Где остановился
- SPEC-AUDIT.md: status ready, verdict concerns (2 мелких пункта + 1 к сведению).

## Чего не хватило
- Ничего существенного; поведение `-p` pytest — по памяти из круга 1.
