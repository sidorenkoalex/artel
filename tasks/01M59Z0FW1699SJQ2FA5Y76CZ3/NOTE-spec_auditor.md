## Выяснено
- Четвёртый аудит (spec_sha 064a7329…): решения №3 п. 1–3 в SPEC перенесены (треб. 1, 2, 5, AC-3, AC-5, «Не входит» SPEC.md:81). Код orchestrator/scripts/tests с c2dc427f не менялся.
- Новое противоречие: `pytest-own` без `report` с `plank_layout`. Треб. 2 и «Не входит» его `plank_layout` не читают, а треб. 5 (п. 1), треб. 7 и AC-6 требуют `--ignore=<родитель <id>>` в ветке acceptance.py:2299-2313.
- SPEC.md:81 «pult-pytest — выкладка прежняя под long_lived_dir» неверно: `_own` есть только у pytest-own (acceptance.py:120-123), у pult-pytest выкладки нет.
- Порядок «refusal правила» против «нет plank_layout» у pult-vitest без tests не задан. Правило с отказом = умолчание (`components` пуст, guard.py:2627).

## Не сработало
- `cd <dir> && git …` в Bash отвергается — нужны абсолютные пути без cd.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready, guard ок.

## Чего не хватило
- Ветка полного набора acceptance.py:2299 — это pytest-own без report; с report уходит в :2288. Это ключ к противоречию AC-6 и «Не входит».
