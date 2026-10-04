---
task: 01M42NBCADGSGTCBZB8NKBVDVH
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Мелкие дефекты пульта: amend-tests, гонка fetch, observe add, сверка путей SPEC в guard

# ТЗ: мелкие дефекты пульта из копилки 03-04.10 — amend-tests, гонка fetch, observe add, сверка путей SPEC в guard

Источник: копилка 03-04.10.2026 (строки П2/П3). Решение Оператора
04.10.2026 «1 и 2».

Факты (пин 9afc1792):
- `amend-tests` (`orchestrator/amend.py::_materialize_tests_if_missing`,
  `tdir = <рабочая копия>/tasks/<id>`) материализует
  `tasks/<id>/acceptance_tests/` в рабочую копию кода задачи для правки
  Оператора и после фиксации правки в ссылку документов его не убирает.
  Неотслеживаемый каталог остаётся (случай 01M41W15BK20WBTD9TMBTSXNZA,
  03.10 22:05Z, убран руками сессии); гейт зон считает неотслеживаемые
  файлы рабочей копии.
- `orchestrator/workspace.py` (стр. ~72-79): при заведении рабочего
  каталога роли `gitcmd.fetch_head_sha("origin", MAIN_BRANCH)`; 03.10
  22:54Z fetch упал «cannot lock ref 'refs/remotes/origin/main'» — в ту
  же секунду `note` той же сессии пушил и обновлял ту же ссылку
  отслеживания. Шаг analyst задачи 01M41VTSE5N15P5P2WZF4GF2BQ пропущен
  (SKIPPED), повторён вручную.
- `artel.py observe add <obs> --tasks A B` (`orchestrator/artel.py::
  _cmd_observe`, справка: `--tasks <id[,id...]>`) добавил только A и
  вернул 0; лишний позиционный аргумент молча проигнорирован (03.10).
- Сверку путей SPEC с зонами (`guard.spec_unclassified_paths`) делает
  только `approve` на `spec_gate` (`orchestrator/fsm.py:~862`);
  `scripts/guard.py <SPEC.md>`, который роль analyst гоняет перед сдачей,
  её не делает. 03.10 21:47Z: guard «ок», approve отказал
  «путь генератора карты не классифицирован» — круг reject +
  перезапуск analyst.

Требуется:
1. `amend-tests` после успешной фиксации правки убирает из рабочей копии
   кода материализованный им `tasks/<id>/` (только его; отказ команды —
   каталог не трогается, правка Оператора сохраняется).
2. Заведение рабочего каталога роли не падает на занятой ссылке
   отслеживания: fetch базы ветки не обновляет
   `refs/remotes/origin/*` либо повторяет попытку при «cannot lock ref»
   (способ — в SPEC); прочие отказы fetch — прежний именованный отказ.
3. `observe add|remove` отказывает с именованной причиной на лишних
   позиционных аргументах (подсказка: номера через запятую) и не
   выполняет частичное действие.
4. `scripts/guard.py` по SPEC.md выдаёт ту же находку о
   неклассифицированных путях, что approve на `spec_gate` (один узел
   `guard.spec_unclassified_paths`); approve сохраняет свою проверку.
5. Тесты в `tests/` с заявками «Ловит мутацию» на каждый пункт.

Зоны: orchestrator/, scripts/guard.py, tests/, docs/codebase-map.md.

Только чтение (не менять): docs/adr/, docs/backlog.md, skills/,
templates/, CLAUDE.md, .github/workflows/ci.yml, conftest.py.

Не входит: мандат на тесты (отдельная задача); команда «монолит
принят»; режим сохранения ссылок в `artifact-branches-cleanup`.

Рамка: $20.
