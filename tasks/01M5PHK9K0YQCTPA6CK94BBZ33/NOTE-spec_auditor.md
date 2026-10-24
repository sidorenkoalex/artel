## Выяснено
- Визит 2 (spec_sha 608c1aa5). Все 5 отклонений визита 1 (fail) в SPEC закрыты: AC-8 переформулирован, перечень имён верен (3 разных: GATE_ACTIONS/VITEST_KIND/spec_text; 17 дословных — подтверждено ast.dump), AC-18 разрешает регенерацию карты, AC-3 покрывает setUp «до» и требует файл:строку из лога (-vv, длинный traceback есть), :516, prepared/broken_task, refusal голым именем.
- Остаточные мелочи: тело id_no_gate_refusal читает GATE_ACTIONS (дословно) против ID_GATE_ACTIONS (переименование употреблений); AC-18 «совпадает с выводом генератора» — строка built_at_sha всегда разная (CI сверяет без неё); шапка --ref worktree печатает HEAD рабочей копии (mutation_run.py:298), незакоммиченные правки orchestrator/ в «после» git diff по шапкам не видит.
## Не сработало
- Bash: читать через python3 heredoc / sed, относительные пути.
## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready; guard прогнан.
## Чего не хватило
- Какой sha печатает шапка mutation-run для worktree — mutation_run.py:292–298.
