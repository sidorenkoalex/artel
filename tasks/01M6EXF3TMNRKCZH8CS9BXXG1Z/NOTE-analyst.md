# Записка analyst — 01M6EXF3TMNRKCZH8CS9BXXG1Z (GitLab Б2.3)

## Выяснено
- Зависимость 01M6AB4VE2R0Q2V5D4MMJGNGH7 (Б2.2) — done.
- Строки ТЗ сверены по коду (сдвиги небольшие): `targets.py:23-24` FORGES=("github","gitlab"), MERGE_GATES=("operator","target-human"); `:29-30` SUPPORTED_*; `unsupported_reason` `:283`, текст «адаптера нет (ADR-0029)» `:299`; `forge.py:184` «адаптера нет»; `fsm_merge_gate.py:1516` people_entry, `:1661` _mr_incident_stops (state вне merged/closed/opened проходит, `:1695`), `:1789` _awaiting_limit_refuses (TargetsError → False, `:1796`); `gitcmd.py:774` max_in_flight `sqlite3.Error`, `:1244-1245` in_repo `refusal = None`; `github_adapter.py:173` различение по stderr; `ci.py:28` подстановка `targets.hosting_registry`, читается `targets.py:1098`; `mr_sync.py:356` `mr.state == "merged"`.
- После открытия списки поддержки == FORGES/MERGE_GATES; неподдержанным по ТЗ остаётся только github+target-human; gitlab+operator по букве списков становится поддержанным — в ТЗ не сказано.
- ТЗ п.6/AC: «отказ загрузки» для github+target-human — сейчас загрузка записи НЕ отказывает (A0, требование 2: отказ ставят действия new/run/auto/approve; тест ac1 «entry_loads…», ac7 doctor читает запись).
- Сторож A0 `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`: `:41` GITLAB_REASON, `:45` строка параметров (gitlab, operator), `:165-166` assert кортежей SUPPORTED_* (контейнер — в «Меняемое поведение» не оформить), `:406` «ADR-0029» not in out. Мандат 26.10 машинной строкой ANSWER не оформлен.
- Объём: >15 критериев, 13 зон → сигналы деления; рамка ТЗ $85.

## Не сработало
- `ls` в Bash недоступен (command not found), `grep`/`sed` работают.

## Где остановился
- Решение: QUESTIONS.md (3 блокирующих вопроса + деление), guard — ок. SPEC не писал. После ANSWER: писать SPEC (при делении — секция «## Деление», 4 части, порядок п.7 первым, открытие последним), затем удалить QUESTIONS.md; merge_after: 01M6AB4VE2R0Q2V5D4MMJGNGH7.

## Чего не хватило
- Как мандат «по решению 26.10» из ТЗ превращается в машинную строку для гейта SPEC без ANSWER — искал в docs/operator-gates.md:82-123.
