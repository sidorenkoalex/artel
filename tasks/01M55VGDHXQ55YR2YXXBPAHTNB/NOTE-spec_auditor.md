# Записка spec_auditor — 01M55VGDHXQ55YR2YXXBPAHTNB

## Выяснено
- Визит 3, SPEC sha 4f1ebd1d: Д1–Д5 перенесены; факты верны (HEAD 0180d1df).
- Новое О-1 → concerns: чекпоинты developer (checkpoint.py:231, 895, 1531) не передают own_zones; _zone_paths (1583) у внешнего проекта не покрывает backend/tests → незакоммиченный новый файл developer по шаблону (паритет Д1) снимается как stray, гейт зон при этом зелёный (довесок untracked). Тр.4 SPEC разбирает только test_author.

## Не сработало
- grep | xargs требует подтверждения — использовать прямые grep с абсолютными путями.

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: concerns), guard прогнан.

## Чего не хватило
- Нет карточек по checkpoint.py: какие чекпоинты получают own_zones — читал _commit_worktree_change и вызовы вручную.
