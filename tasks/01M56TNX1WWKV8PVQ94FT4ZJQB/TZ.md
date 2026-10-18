---
task: 01M56TNX1WWKV8PVQ94FT4ZJQB
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Гейт неослабления: async-тесты и пропуски через метку и модуль

Родительская задача: 01M56P60XS9AP4BH01YK35220D — Гейт неослабления на чужом стеке: пропуск через метку, помощники, параметризация, async
Зоны: scripts/guard.py, orchestrator/advance_gates/test_integrity.py, tests/
Порядок: после части 1
Рамка: $25

Часть задачи 01M56P60XS9AP4BH01YK35220D (требования 1–5, 9, 11 её SPEC).

Факты: `guard.SKIP_DECORATOR_NAMES` (`scripts/guard.py:649-650`) опознаёт
декоратор по последнему сегменту имени; `requires_pg =
pytest.mark.skipif(...)` и `@requires_pg` — не пропуск (так прошла задача
01M55SKHZ293CCAK0N7T4H7ZMR). Модульные `pytest.skip(...,
allow_module_level=True)`, `pytestmark = …skip…` и `pytest.importorskip` на
уровне модуля не ловятся (`guard.py:675-697` смотрит декораторы и тела
функций). Маркер в сравнении — текст (`test_integrity.py:450`): смена
значения метки при прежнем `@requires_pg` не видна. `async def test_` не
считает только `guard.TEST_METHOD` (`guard.py:178`).

Требуется:
1. Имя-метка на методе или классе — пропуск тем же классом находки, что
   прямой декоратор. Формы связывания — ровно две: присваивание на уровне
   модуля `name = pytest.mark.skipif/skip/xfail(...)` или
   `name = unittest.skip*(...)` и `from <модуль тестов> import name` такого
   имени. Модуль импортированной метки разрешается по правилам помощника
   части 1: у артели (`repo_context.is_artel`) — только `tests/sandbox.py`,
   у внешнего проекта — любой модуль `weakening_scope`. Послабление условной метке с причиной — только методу,
   которого нет в базе (`test_integrity.py:447-449`), с журналом; метка на
   классе — находка всегда (`test_integrity.py:442-446`).
2. Смена значения связанного имени при прежнем тексте маркера — находка
   на методах базы с этой меткой, в том числе когда меняется только
   модуль импортированной метки.
3. Модульные пропуски (`pytestmark`, `pytest.skip(allow_module_level=True)`,
   `importorskip` уровня модуля) — пропуск всех методов файла тем же
   классом находки; послабление — только методам, которых нет в базе;
   условность `pytestmark` — по правилу декоратора, модульного вызова — по
   правилу вызова в теле (внутри `if`/`else`, причина-константа).
4. Для артели — то же (усиление).
5. `async def test_…` учитывается `guard.TEST_METHOD`.
6. Тесты детерминированы, без сети, на учебном проекте с `workdir:
   backend` и `weakening_scope: [backend/tests/**/*.py]`.

Критерии приёмки: AC-1…AC-8 и AC-15 SPEC задачи 01M56P60XS9AP4BH01YK35220D.

Только чтение: `orchestrator/project_profile.py`, `orchestrator/advance_gates/mandate.py`,
`orchestrator/acceptance.py`, `orchestrator/repo_context.py`, `targets.yaml`,
`docs/backlog.md`. Правка вне зон — эскалация.
Не входит: правило импортов долгоживущих файлов (01M5633WZ3Y3A0P4KKBZDB3KER);
не-Python стек; прочие формы связывания метки (цепочки имён `a = b`,
функции, возвращающие метку, `pytestmark += …`/`.append(…)`) — известный
пробел; помощники и параметризация (другие части).