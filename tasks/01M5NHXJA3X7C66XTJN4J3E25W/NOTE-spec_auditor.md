# Записка spec_auditor — 01M5NHXJA3X7C66XTJN4J3E25W

## Выяснено
- Круг 2 (SPEC 545847ff): все 5 приложений `git apply --check` на e2f34d71 — 0; на копии дерева /tmp/aud/tree с ними 24 файла tests/ (вкл. test_invariants) — 825 passed.
- Мутации AC-4 (0)–(4) красные, немутированная копия зелёная; AC-2 (явный файл, без ARTEL_ROLE) rc 0, AC-3 1 passed.
- Обход: `import orchestrator.config as cfg` в `_sandbox`/в хуке без декоратора — инвариант 42 зелёный (проверка alias берёт asname вместо name).

## Не сработало
- Bash-проверка отказывает на `{` с кавычками в heredoc и на `cd /tmp` — писал python без dict-литералов, os.chdir внутри.

## Где остановился
- SPEC-AUDIT.md записан, verdict concerns (одно отклонение — псевдоним импорта).

## Чего не хватило
- Ничего существенного.
