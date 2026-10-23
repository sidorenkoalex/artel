---
task: 01M5M675F6K2TE7TTJN3AET4PP
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Расширение зон разрешено: orchestrator/pin.py

мандат Оператора: orchestrator/pin.py

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| orchestrator/pin.py — после успешного сдвига пина `git remote prune origin` в главной копии | инвариант 40: git главной копии меняют только pin-update/pin --to/doctor --fix — docs/invariants.md:70, tests/test_invariants.py:3155 | да: правка внутри pin-update, мерж и prune git главной копии не трогают | tests/test_invariants.py (MainCopyGitUnchangedDuringTaskTest — не меняется) | ок |
| orchestrator/pin.py — порядок проверок pin-update (fetch, канарейка, CI, сдвиг) | отказ без зелёной канарейки и без зелёного CI — orchestrator/pin.py:132–150 | да: prune ссылок — только после успешного сдвига; сбой prune — строка предупреждения, на сдвиг пина не влияет | tests/test_pin.py (отказы pin-update без канарейки и без CI — не меняются); новый долгоживущий тест задачи tests/test_01m5m675f6k2te7ttjn3aet4pp_*.py (сбой prune не отменяет сдвиг; отказ pin-update — prune не вызывается) | ок |
