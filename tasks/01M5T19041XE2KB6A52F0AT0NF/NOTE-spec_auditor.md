# Записка spec_auditor (визит 2, SPEC f6eeb3a8)

## Выяснено
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок.
- 12 отклонений прошлого аудита закрыты ANSWER-2 и правкой SPEC.
- Новое Б1: тр. 4 называет слой репозитория `.artel/targets.yaml`. На
  деле слой репозитория — `targets.yaml` (config.py:20), а
  `.artel/targets.yaml` — локальный слой (config.py:27, targets.py:152).
- Мелкое: github_adapter.py:94 → :96; targets.py:280 → :283.
- knowledge_brief-тест несёт в `knowledge` только корневые
  CLAUDE/AGENTS и docs/ — от тр. 8 не краснеет.
- Роль внешнего проекта: Bash(git:*) + python3 artel.py
  (providers/claude.py:122). Факт ТЗ про Bash(python3:*) устарел.

## Не сработало
- `ls` в шелле нет; `$`-подстановки и опыт с git в /tmp политика шелла
  не пускает.

## Где остановился
- Готово.

## Чего не хватило
- Прогона `git add -A` в sparse-копии на неотслеживаемом файле под
  исключением — поведение git не проверено опытом (его покрывает AC-20).
