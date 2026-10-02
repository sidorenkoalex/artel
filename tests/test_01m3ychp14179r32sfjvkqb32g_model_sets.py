"""Наборы моделей: защита `model_sets.yaml`, команда допуска пары `admit`,
определение чистого прогона канарейки, правило вины отказа автогейта и
проверка допуска набора.

Группа: долгоживущий

Красен до реализации: команды `admit` в диспетчере `artel.main` нет («Неизвестная команда admit»), `model_sets.yaml` нет ни в `config.PROTECTED_PATHS`, ни в `notes.DOC_COMMIT_CONFIG_PATHS`, функций `models.autogate_refusal_blame`/`models.set_admitted` нет — AttributeError.

Планка провалидирована временным стабом реализации (все методы зелёные,
стаб удалён, репозиторий не тронут).

Публичная поверхность, которую читает этот файл (SPEC называет функции
требований 4 и 6 «одной функцией», но не называет имён — имена ниже
выбраны планкой и становятся интерфейсом частей 2-3 деления):

- команда `artel.py admit <роль> <модель> --basis <текст>` и
  `artel.py admit --revoke <роль> <модель> --basis <текст>` — через
  диспетчер `artel.main()`, тем же argv, что набирает Оператор;
- `models.autogate_refusal_blame(<текст autogate_refusal>)` — один из
  трёх исходов SPEC дословно: «роль», «пульт/пул», «не установлена»;
- `models.set_admitted(conn, <имя набора>)` — допущен ли набор из
  раздела `sets:`; результат — `bool` (либо кортеж, первый элемент
  которого `bool`: планка не навязывает форму пояснения).

Чистота прогона (требование 5) наблюдается через исход `admit`: сценарий
собран так, что ровно один прогон решает, хватает ли чистых прогонов, и
его свойство — предмет метода.

Песочница — настоящий git: главная копия пульта (`config.ROOT`) с
`model_sets.yaml` и тривиально зелёным `tests/` (гейт полного набора
`doc-commit` на путях конфигурации Оператора), синхронный bare `origin`.
Каталог моделей — фикстура `tests/sandbox.py` (`use_catalog_fixture`),
карта исполнителей — фикстура процесса: боевая модель каждой agent-роли —
`FIXTURE_TIER_MODEL`, «другая модель каталога» — `FIXTURE_OTHER_MODEL`.
Строки `canary_runs` пишутся публичным `store.insert_canary_run` со
сводкой «роль → модель» в формате канарейки.

Роль пары, имена шаблонов, основание `--basis` и место «решающего»
прогона среди прочих выбираются случайно; зерно печатается и входит в
текст провала.
"""
import contextlib
import io
import os
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, config, models, notes, store, yamlmini
from tests.sandbox import (FIXTURE_OTHER_MODEL, FIXTURE_TIER_MODEL,
                           RealGitSandbox)

MODEL_SETS_REL = "model_sets.yaml"

#: Путь файла в НАСТОЯЩЕМ корне пульта — снят до любой песочницы: если
#: реализация заведёт для файла свой атрибут `config` (вычисленный от
#: `ROOT` при импорте), песочница переадресует его во временный корень.
_REAL_MODEL_SETS = Path(config.ROOT) / MODEL_SETS_REL

#: agent-роли фикстуры карты исполнителей (`tests/sandbox.py::
#: FIXTURE_ROLES`) — сводка прогона канарейки называет модель каждой.
AGENT_ROLES = ("analyst", "test_author", "developer", "reviewer")

#: Роли пары в общих сценариях: у analyst своё дополнительное условие
#: (прогон с неясностью ТЗ), он проверяется отдельным методом.
PLAIN_ROLES = ("test_author", "developer", "reviewer")

GREEN_SUITE_REL = "tests/test_green.py"
GREEN_SUITE_TEXT = '''"""Набор стенда: зелёный при любом содержимом дерева."""


def test_green():
    assert True
'''

#: Причины отказа автогейта по вине пульта/пула — тексты, которые пишет
#: `fsm_autogate` (строка журнала -> `canary_runs.autogate_refusal`).
PULT_REFUSALS = (
    "автогейт: бюджет задачи исчерпан",
    "автогейт: полный набор tests/ не проверен — worktree задачи не заведён",
    "автогейт: каталог приёмочных тестов пуст или отсутствует "
    "(источник планки: ветка artifacts/x, sha 0123abc)",
    "автогейт: tests/ нет в worktree — полный набор не проверен",
)

#: Причины отказа по вине роли.
ROLE_REFUSALS = (
    "автогейт: полный набор tests/ красный: 1 failed, 40 passed "
    "(лог прогона: /tmp/x-fullsuite-1.log)",
    "автогейт: критерии manual — AC-2 (источник планки: ветка "
    "artifacts/x, sha 0123abc)",
    "автогейт: критерии skip — AC-4, AC-5 (источник планки: ветка "
    "artifacts/x, sha 0123abc)",
    "автогейт: критерий ci не пройден — AC-3 (CI красный; источник "
    "планки: ветка artifacts/x, sha 0123abc)",
)

#: Причины вне обоих перечней правила вины.
UNKNOWN_REFUSALS = (
    "автогейт: луна в неподходящей фазе",
    "что-то совсем другое без префикса",
)


def summary(overrides: dict) -> str:
    """Сводка `models_summary` строки прогона: боевая модель каждой
    agent-роли, поверх — `overrides`; формат — как пишет канарейка."""
    pairs = {role: FIXTURE_TIER_MODEL for role in AGENT_ROLES}
    pairs.update(overrides)
    named = ", ".join(f"{role} → {model}" for role, model in pairs.items())
    return f"{named}; источник: слой пульта"


def model_sets_text(templates: dict, pairs: dict = None,
                    sets: dict = None) -> str:
    """Текст `model_sets.yaml` в подмножестве `yamlmini`."""
    lines = ["sets:"]
    for name, members in (sets or {}).items():
        lines.append(f"  {name}:")
        lines += [f"    {role}: {model}" for role, model in members.items()]
    lines.append("pairs:")
    for role, entries in (pairs or {}).items():
        lines.append(f"  {role}:")
        for model, state in entries.items():
            lines += [f"    {model}:", "      date: 2026-10-01",
                      "      basis: решение Оператора", f"      state: {state}"]
    lines.append("canary_templates:")
    lines += [f"  {title}: {cls}" for title, cls in templates.items()]
    return "\n".join(lines) + "\n"


def verdict_of(result) -> bool:
    """`bool` из ответа проверки допуска набора (bool или кортеж)."""
    if isinstance(result, tuple):
        result = result[0]
    return result


class ModelSetsProtectionTest(unittest.TestCase):

    def test_ac2_model_sets_is_protected_and_doc_commit_config_path(self):
        """Файл решений Оператора закрыт от ролей и открыт `doc-commit`.

        Сценарий: путь `model_sets.yaml` сверяется единой формулой
        защищённых путей и перечнем конфигурации Оператора `doc-commit`.

        Ловит мутацию: файл добавлен только в один из двух кортежей
        (например, в `DOC_COMMIT_CONFIG_PATHS`, но не в `PROTECTED_PATHS`) —
        `is_protected_path` вернёт False либо путь не найдётся в перечне,
        и роль сможет править файл решений Оператора."""
        self.assertTrue(config.is_protected_path(MODEL_SETS_REL))
        self.assertIn(MODEL_SETS_REL, notes.DOC_COMMIT_CONFIG_PATHS)


class AdmitSandbox(RealGitSandbox):
    """Главная копия с `model_sets.yaml` и зелёным `tests/`, синхронный
    bare `origin`, каталог моделей фикстуры, БД песочницы с таблицей
    `canary_runs`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        # Боевая модель роли — разрешение моделей пульта без набора: карта
        # исполнителей и локальный слой — фикстура (`RealGitSandbox`, в
        # отличие от `TmpRootTest`, сам их не кладёт), каталог — тоже.
        self.use_role_map()
        self.use_catalog_fixture()
        self._redirect_model_sets_attrs()
        self.role = self.rnd.choice(PLAIN_ROLES)
        self.model = FIXTURE_OTHER_MODEL
        stem = f"canary-{self.rnd.randrange(10 ** 6)}"
        self.medium = f"{stem}-sredniy"
        self.fast = f"{stem}-bystryy"
        self.fast2 = f"{stem}-bystryy-2"
        self.hard = f"{stem}-trudnyy"
        self.unclassified = f"{stem}-bez-klassa"
        self.templates = {self.medium: "средний", self.fast: "быстрый",
                          self.fast2: "быстрый", self.hard: "трудный"}
        for rel, text in ((MODEL_SETS_REL, model_sets_text(self.templates)),
                          (GREEN_SUITE_REL, GREEN_SUITE_TEXT)):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "наборы моделей")
        self.origin = str(self.add_synced_origin())
        self.conn = store.db()
        self.run_no = 0

    def _redirect_model_sets_attrs(self) -> None:
        """Публичный атрибут `config`, указывающий на настоящий
        `model_sets.yaml` пульта, — во временный корень песочницы."""
        for name, value in list(vars(config).items()):
            if name.startswith("_") or not isinstance(value, Path):
                continue
            if value == _REAL_MODEL_SETS:
                patcher = mock.patch.object(config, name,
                                            self.root / MODEL_SETS_REL)
                patcher.start()
                self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ сценарий

    def note(self, extra: str = "") -> str:
        return f"зерно {self.seed}, роль {self.role}. {extra}"

    def put_model_sets(self, text: str) -> None:
        """Файл решений Оператора в главной копии и в origin."""
        (self.root / MODEL_SETS_REL).write_text(text, encoding="utf-8")
        self.git("add", MODEL_SETS_REL)
        self.git("commit", "-q", "-m", "правка наборов")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def add_run(self, title: str, overrides: dict = None, *,
                verdict: str = "green", review_iterations: int = 0,
                escalations: int = 0, expected_escalation: str = None,
                actual_escalation: bool = False,
                marker_mismatch: bool = False,
                autogate_refusal: str = None) -> None:
        """Строка `canary_runs`; по умолчанию — чистый прогон пары
        сценария (`self.role` -> `self.model`) на шаблоне `title`."""
        self.run_no += 1
        if overrides is None:
            overrides = {self.role: self.model}
        store.insert_canary_run(
            self.conn, f"stamp-{self.run_no}", title, f"T-RUN-{self.run_no}",
            10, 1.0, review_iterations, escalations, "merge_gate",
            expected_escalation, actual_escalation, marker_mismatch,
            main_sha="0" * 40, verdict=verdict,
            models_summary=summary(overrides),
            autogate_refusal=autogate_refusal)

    def clear_runs(self) -> None:
        """Пустая таблица прогонов (её заводит первая запись прогона)."""
        exists = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND "
            "name='canary_runs'").fetchone()
        if exists:
            self.conn.execute("DELETE FROM canary_runs")
            self.conn.commit()

    def add_sufficient_runs(self, special: dict = None) -> None:
        """Три прогона пары на трёх шаблонах (средний, быстрый, трудный) —
        ровно столько, сколько требует ADR-0019 п.5. `special` —
        свойства, которые получает ОДИН из трёх, выбранный случайно: от
        его чистоты зависит, хватает ли чистых прогонов."""
        titles = [self.medium, self.fast, self.hard]
        pick = self.rnd.randrange(len(titles))
        for i, title in enumerate(titles):
            self.add_run(title, **(special if (special and i == pick) else {}))

    def cli(self, *argv: str) -> tuple[bool, str]:
        """(успех, stdout + текст отказа) команды `artel.py <argv>`."""
        out = io.StringIO()
        ok = True
        tail = ""
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (0, None):
                    ok = False
                    tail = f"\n{exc.code}"
        return ok, out.getvalue() + tail

    def admit(self, role: str = None, model: str = None,
              basis: str = None) -> tuple[bool, str]:
        return self.cli("admit", role or self.role, model or self.model,
                        "--basis", basis or self.basis())

    def basis(self) -> str:
        return f"прогоны канарейки {self.rnd.randrange(10 ** 6)}"

    # ---------------------------------------------------------- наблюдение

    def origin_git(self, *args: str) -> str:
        return self.git("-C", self.origin, *args)

    def origin_head(self) -> str:
        return self.origin_git("rev-parse", config.MAIN_BRANCH).strip()

    def origin_model_sets(self) -> str:
        return self.origin_git("show",
                               f"{config.MAIN_BRANCH}:{MODEL_SETS_REL}")

    def snapshot(self) -> tuple:
        """Всё, что отказ `admit` обязан оставить нетронутым."""
        return (self.origin_head(), self.origin_model_sets(),
                self.git("rev-parse", "HEAD").strip(),
                self.git("status", "--porcelain"),
                (self.root / MODEL_SETS_REL).read_text(encoding="utf-8"))

    def pair_entry(self, role: str = None, model: str = None) -> dict:
        document = yamlmini.mapping(self.origin_model_sets())
        pairs = document.get("pairs") or {}
        return (pairs.get(role or self.role) or {}).get(model or self.model)

    def assert_isolated_commit(self, before_head: str) -> None:
        """Ровно один новый коммит в origin, и он трогает только файл
        наборов; главная копия (HEAD и дерево) не тронута."""
        after = self.origin_head()
        self.assertNotEqual(before_head, after, self.note("коммита нет"))
        commits = self.origin_git("rev-list", f"{before_head}..{after}").split()
        self.assertEqual(len(commits), 1, self.note(f"коммиты: {commits}"))
        names = self.origin_git("diff", "--name-only", before_head,
                                after).split()
        self.assertEqual(names, [MODEL_SETS_REL], self.note())

    def assert_refused_untouched(self, ok: bool, output: str,
                                 before: tuple, extra: str = "") -> None:
        self.assertFalse(ok, self.note(f"{extra} допуск выдан:\n{output}"))
        self.assertEqual(before, self.snapshot(),
                         self.note(f"{extra} отказ изменил файл или HEAD"))
        self.assertIsNone(self.pair_entry(), self.note(extra))


class AdmitShortfallTest(AdmitSandbox):

    def test_ac3_shortfall_refuses_and_leaves_file_and_head(self):
        """Три вида недобора — три отказа, файл и HEAD прежние.

        Сценарии (каждый на чистой таблице прогонов): (а) два чистых
        прогона пары на среднем и быстром шаблонах плюс красный прогон на
        трудном — чистых меньше трёх; (б) три чистых прогона на одном
        среднем шаблоне — шаблонов меньше двух; (в) три чистых прогона на
        двух быстрых шаблонах плюс чистые прогоны ДРУГОЙ модели этой роли
        на среднем — ни одного чистого прогона пары на среднем; отказ в
        (в) называет недостающий средний класс.

        Ловит мутацию: счёт ведётся по всем строкам пары, а не по чистым
        (красный прогон засчитан — (а) выдаёт допуск); число шаблонов не
        сверяется ((б) выдаёт допуск); прогон относится к паре по роли
        без сверки модели ((в) засчитывает средний шаблон чужой модели);
        отказ пишет файл до проверки чисел — снимок origin/главной копии
        расходится."""
        before = self.snapshot()
        self.add_run(self.medium)
        self.add_run(self.fast)
        self.add_run(self.hard, verdict="red")
        ok, output = self.admit()
        self.assert_refused_untouched(ok, output, before, "(а)")

        self.clear_runs()
        for _ in range(3):
            self.add_run(self.medium)
        ok, output = self.admit()
        self.assert_refused_untouched(ok, output, before, "(б)")

        self.clear_runs()
        self.add_run(self.fast)
        self.add_run(self.fast2)
        self.add_run(self.fast)
        for _ in range(2):
            self.add_run(self.medium, {self.role: FIXTURE_TIER_MODEL})
        ok, output = self.admit()
        self.assert_refused_untouched(ok, output, before, "(в)")
        self.assertIn("средн", output, self.note(output))

    def test_ac4_unclassified_template_not_medium_and_named(self):
        """Шаблон без класса не засчитан в «средний» и назван в отказе.

        Сценарий: три чистых прогона пары — на двух быстрых шаблонах и на
        шаблоне, которого нет в `canary_templates:`; чисел прогонов и
        шаблонов хватает, среднего — нет.

        Ловит мутацию: класс отсутствующего шаблона берётся по умолчанию
        «средний» (или шаблон без записи засчитывается в любой класс) —
        `admit` выдаёт допуск; либо отказ перечисляет только недостающий
        класс без имени шаблона — имени нет в выводе."""
        before = self.snapshot()
        self.add_run(self.fast)
        self.add_run(self.unclassified)
        self.add_run(self.fast2)
        ok, output = self.admit()
        self.assert_refused_untouched(ok, output, before)
        self.assertIn(self.unclassified, output, self.note(output))

    def test_ac5_analyst_needs_run_with_correct_tz_ambiguity_outcome(self):
        """analyst без прогона с правильной эскалацией — отказ.

        Сценарий: пара analyst; три чистых прогона на среднем, быстром и
        трудном шаблонах без эскалаций — отказ, перечень называет прогон
        с неясностью ТЗ; добавлен прогон с заданным
        `expected_escalation`, но `marker_mismatch = 1` — по-прежнему
        отказ; добавлен прогон с `expected_escalation`,
        `actual_escalation = 1`, `marker_mismatch = 0` — допуск выдан.

        Ловит мутацию: для analyst дополнительное условие не проверяется
        (первый вызов выдаёт допуск); прогоном с неясностью засчитывается
        любой с заданным `expected_escalation` без сверки
        `marker_mismatch` (второй вызов выдаёт допуск); перечень не
        называет недостающую неясность ТЗ — слова нет в выводе."""
        self.role = "analyst"
        before = self.snapshot()
        self.add_run(self.medium)
        self.add_run(self.fast)
        self.add_run(self.hard)
        ok, output = self.admit()
        self.assert_refused_untouched(ok, output, before, "без эскалации")
        self.assertIn("неясност", output.lower(), self.note(output))

        marker = f"ESCALATE-{self.rnd.randrange(1000)}"
        self.add_run(self.rnd.choice([self.medium, self.fast]),
                     escalations=1, expected_escalation=marker,
                     actual_escalation=True, marker_mismatch=True)
        ok, output = self.admit()
        self.assert_refused_untouched(ok, output, before, "маркер разошёлся")

        self.add_run(self.rnd.choice([self.medium, self.fast]),
                     escalations=1, expected_escalation=marker,
                     actual_escalation=True, marker_mismatch=False)
        ok, output = self.admit()
        self.assertTrue(ok, self.note(output))
        self.assertEqual((self.pair_entry() or {}).get("state"), "допущена",
                         self.note(output))

    def test_ac6_summary_says_developer_retries_no_data(self):
        """Сводка `admit` прямо пишет, что о повторах developer данных нет.

        Сценарий: `admit` при недоборе (один прогон) и при достаточных
        прогонах — оба вывода несут строку «повторы developer: нет
        данных».

        Ловит мутацию: строка печатается только в одной ветке (лишь при
        выдаче или лишь при отказе) либо условие молча опущено из
        сводки — строки нет в одном из выводов."""
        self.add_run(self.medium)
        ok, output = self.admit()
        self.assertFalse(ok, self.note(output))
        self.assertIn("повторы developer: нет данных", output,
                      self.note(output))
        self.clear_runs()
        self.add_sufficient_runs()
        ok, output = self.admit()
        self.assertTrue(ok, self.note(output))
        self.assertIn("повторы developer: нет данных", output,
                      self.note(output))


class AdmitWriteTest(AdmitSandbox):

    def test_ac7_sufficient_runs_admit_pair_isolated_commit(self):
        """Достаточные прогоны — пара допущена изолированным коммитом.

        Сценарий: три чистых прогона пары на среднем, быстром и трудном
        шаблонах; `admit` с основанием. В origin ровно один новый коммит,
        трогающий только `model_sets.yaml`; в `pairs:` пара с
        `state: допущена`, основанием из `--basis` и непустой датой;
        раздел `canary_templates:` сохранён; главная копия не тронута.

        Ловит мутацию: файл переписывается с нуля только разделом
        `pairs:` (шаблоны потеряны); коммит делается в главной копии
        `config.ROOT` мимо механизма `doc-commit` (HEAD главной копии
        сдвинулся, origin нет); основание не записывается или пишется
        `state` иным словом — расхождение в разобранном файле origin."""
        self.add_sufficient_runs()
        basis = self.basis()
        before_origin = self.origin_head()
        main_before = (self.git("rev-parse", "HEAD").strip(),
                       self.git("status", "--porcelain"))

        ok, output = self.admit(basis=basis)

        self.assertTrue(ok, self.note(output))
        self.assert_isolated_commit(before_origin)
        entry = self.pair_entry()
        self.assertIsNotNone(entry, self.note(self.origin_model_sets()))
        self.assertEqual(entry.get("state"), "допущена", self.note())
        self.assertEqual(entry.get("basis"), basis, self.note())
        self.assertTrue(str(entry.get("date") or "").strip(), self.note())
        document = yamlmini.mapping(self.origin_model_sets())
        self.assertEqual(document.get("canary_templates"), self.templates,
                         self.note())
        self.assertEqual(main_before, (self.git("rev-parse", "HEAD").strip(),
                                       self.git("status", "--porcelain")),
                         self.note("главная копия тронута"))

    def test_ac7_silence_window_holds_admission_like_doc_commit(self):
        """Окно тишины удерживает запись допуска, флаш её отправляет.

        Сценарий: открыто окно тишины (задача в состоянии из
        `config.NOTE_SILENCE_WINDOW_STATES`); `admit` при достаточных
        прогонах — origin не меняется, среди удержанных записей
        (`notes.pending_notes`) есть запись пути `model_sets.yaml`; окно
        закрыто, `doc-commit --flush` — пара допущена в origin одним
        коммитом, трогающим только файл наборов.

        Ловит мутацию: `admit` пишет в origin собственным push мимо
        механизма `doc-commit` (окно тишины не соблюдено — origin
        сдвинулся при открытом окне), либо удержанная запись не
        самодостаточна и флаш её не воспроизводит — пары в origin нет."""
        self.add_sufficient_runs()
        store.insert_task(store.db(), "T-WIN", "окно тишины",
                          config.NOTE_SILENCE_WINDOW_STATES[0], "task/T-WIN",
                          config.DEFAULT_TARGET, 10.0)
        before_origin = self.origin_head()

        self.admit()

        self.assertEqual(before_origin, self.origin_head(),
                         self.note("окно тишины не удержало запись"))
        held = [p for p in notes.pending_notes()
                if p.get("path") == MODEL_SETS_REL]
        self.assertTrue(held, self.note(f"{notes.pending_notes()}"))

        conn = store.db()
        conn.execute("DELETE FROM tasks WHERE id=?", ("T-WIN",))
        conn.commit()
        self.cli("doc-commit", "--flush")

        self.assert_isolated_commit(before_origin)
        self.assertEqual((self.pair_entry() or {}).get("state"), "допущена",
                         self.note(self.origin_model_sets()))

    def test_ac8_revoke_suspends_pair_isolated_commit(self):
        """`--revoke` переводит пару в «приостановлена» изолированным коммитом.

        Сценарий: пара записана Оператором с `state: допущена` (рядом —
        другая допущенная пара); `admit --revoke` с новым основанием. В
        origin ровно один новый коммит, только `model_sets.yaml`; у пары
        `state: приостановлена` и новое основание; соседняя пара
        по-прежнему допущена.

        Ловит мутацию: `--revoke` удаляет пару вместо смены состояния
        (записи нет), не обновляет основание, или перезаписывает
        состояние всех пар роли — соседняя пара становится
        приостановленной."""
        other = self.rnd.choice([r for r in PLAIN_ROLES if r != self.role])
        self.put_model_sets(model_sets_text(
            self.templates, pairs={self.role: {self.model: "допущена"},
                                   other: {self.model: "допущена"}}))
        basis = self.basis()
        before_origin = self.origin_head()

        ok, output = self.cli("admit", "--revoke", self.role, self.model,
                              "--basis", basis)

        self.assertTrue(ok, self.note(output))
        self.assert_isolated_commit(before_origin)
        entry = self.pair_entry()
        self.assertIsNotNone(entry, self.note(self.origin_model_sets()))
        self.assertEqual(entry.get("state"), "приостановлена", self.note())
        self.assertEqual(entry.get("basis"), basis, self.note())
        self.assertEqual((self.pair_entry(role=other) or {}).get("state"),
                         "допущена", self.note(f"соседняя пара {other}"))


class CleanRunTest(AdmitSandbox):

    def test_ac9_pult_blamed_refusal_keeps_run_clean(self):
        """Отказ автогейта по вине пульта/пула не портит прогон.

        Сценарий: три прогона пары ровно в меру ADR-0019 п.5, один из них
        (случайный) зелёный без итераций и эскалаций, но с
        `autogate_refusal` из перечня пульта/пула (случайная причина:
        исчерпанный бюджет, незаведённый worktree, пустой каталог
        приёмочных тестов, отсутствие `tests/`) — допуск выдан.

        Ловит мутацию: чистым считается только прогон с пустым
        `autogate_refusal` (правило вины не применяется) — прогонов
        становится два, `admit` отказывает."""
        reason = self.rnd.choice(PULT_REFUSALS)
        self.add_sufficient_runs({"autogate_refusal": reason})
        ok, output = self.admit()
        self.assertTrue(ok, self.note(f"причина {reason!r}:\n{output}"))
        self.assertEqual((self.pair_entry() or {}).get("state"), "допущена",
                         self.note(reason))

    def test_ac10_role_blamed_or_unknown_refusal_makes_run_unclean(self):
        """Отказ по вине роли и отказ с неустановленной причиной портят прогон.

        Сценарий: правило вины относит причины роли (красный полный
        набор, критерии manual/skip, непройденный ci) к «роль», причины
        вне обоих перечней — к «не установлена»; затем три прогона пары
        в меру ADR-0019 п.5, один из которых несёт такую причину, —
        `admit` отказывает, файл не меняется (по одному сценарию на
        причину роли и неустановленную).

        Ловит мутацию: правило вины по умолчанию относит неизвестную
        причину к пульту (исход «пульт/пул» вместо «не установлена» — и
        прогон засчитан); чистым признаётся любой прогон с
        `verdict = green` независимо от отказа автогейта — допуск выдан."""
        for text in ROLE_REFUSALS:
            self.assertEqual(models.autogate_refusal_blame(text), "роль",
                             self.note(text))
        for text in PULT_REFUSALS:
            self.assertEqual(models.autogate_refusal_blame(text),
                             "пульт/пул", self.note(text))
        for text in UNKNOWN_REFUSALS:
            self.assertEqual(models.autogate_refusal_blame(text),
                             "не установлена", self.note(text))

        before = self.snapshot()
        for reason in (self.rnd.choice(ROLE_REFUSALS),
                       self.rnd.choice(UNKNOWN_REFUSALS)):
            self.clear_runs()
            self.add_sufficient_runs({"autogate_refusal": reason})
            ok, output = self.admit()
            self.assert_refused_untouched(ok, output, before, repr(reason))

    def test_ac11_review_iterations_or_unexpected_escalation_unclean(self):
        """Итерации ревью и неожиданная эскалация портят прогон.

        Сценарий: три прогона пары в меру ADR-0019 п.5, один из которых
        (случайный) — по очереди: `review_iterations > 0`;
        `escalations > 0` без `expected_escalation`; ожидаемая эскалация
        не случилась (`actual_escalation = 0`); эскалация случилась, но
        маркер разошёлся (`marker_mismatch = 1`). Каждый раз `admit`
        отказывает и файл не меняется. Контрольный сценарий: тот же
        прогон с ОЖИДАЕМОЙ эскалацией (`expected_escalation` задан,
        `actual_escalation = 1`, `marker_mismatch = 0`) — чистый, допуск
        выдан.

        Ловит мутацию: сверка `review_iterations` пропущена; любая
        эскалация с заданным `expected_escalation` (или любая вовсе)
        считается ожидаемой без сверки `actual_escalation`/
        `marker_mismatch` — соответствующий сценарий выдаёт допуск;
        чистым считается только прогон с `escalations = 0` — контрольный
        сценарий отказывает."""
        marker = f"ESCALATE-{self.rnd.randrange(1000)}"
        cases = (
            {"review_iterations": self.rnd.randint(1, 3)},
            {"escalations": self.rnd.randint(1, 2)},
            {"escalations": 1, "expected_escalation": marker,
             "actual_escalation": False, "marker_mismatch": False},
            {"escalations": 1, "expected_escalation": marker,
             "actual_escalation": True, "marker_mismatch": True},
        )
        before = self.snapshot()
        for special in cases:
            self.clear_runs()
            self.add_sufficient_runs(special)
            ok, output = self.admit()
            self.assert_refused_untouched(ok, output, before, repr(special))

        self.clear_runs()
        self.add_sufficient_runs(
            {"escalations": 1, "expected_escalation": marker,
             "actual_escalation": True, "marker_mismatch": False})
        ok, output = self.admit()
        self.assertTrue(ok, self.note(f"ожидаемая эскалация:\n{output}"))


class SetAdmissionTest(AdmitSandbox):

    def setUp(self):
        super().setUp()
        roles = self.rnd.sample(PLAIN_ROLES, 2)
        self.set_name = f"nabor-{self.rnd.randrange(10 ** 6)}"
        self.members = {role: FIXTURE_OTHER_MODEL for role in roles}

    def write_set(self, pair_states: dict) -> None:
        """Файл: набор `self.set_name` и пары с заданными состояниями
        (`{роль: состояние}`; роли вне словаря в `pairs:` не записаны)."""
        self.put_model_sets(model_sets_text(
            self.templates,
            pairs={role: {FIXTURE_OTHER_MODEL: state}
                   for role, state in pair_states.items()},
            sets={self.set_name: self.members}))

    def admitted(self) -> bool:
        return verdict_of(models.set_admitted(store.db(), self.set_name))

    def test_ac12_no_green_hard_run_of_whole_set_not_admitted(self):
        """Допущенные пары без зелёного трудного прогона набором — не допущен.

        Сценарий: все не-боевые пары набора допущены; в `canary_runs` —
        зелёный прогон набором целиком на среднем шаблоне, красный
        прогон набором на трудном и зелёный прогон на трудном, где
        набору соответствует только часть ролей, — «не допущен»; затем
        зелёный прогон набором целиком на шаблоне без записи класса —
        по-прежнему «не допущен».

        Ловит мутацию: класс шаблона не сверяется (засчитан средний);
        вердикт не сверяется (засчитан красный); сводка сверяется по
        одной роли набора, а не по всем; шаблон без записи класса
        считается трудным — функция возвращает «допущен»."""
        self.write_set({role: "допущена" for role in self.members})
        partial = dict(self.members)
        partial[next(iter(partial))] = FIXTURE_TIER_MODEL
        self.add_run(self.medium, self.members)
        self.add_run(self.hard, self.members, verdict="red")
        self.add_run(self.hard, partial)
        self.assertIs(self.admitted(), False, self.note(f"{self.members}"))

        self.add_run(self.unclassified, self.members)
        self.assertIs(self.admitted(), False,
                      self.note("шаблон без класса засчитан трудным"))

    def test_ac13_admitted_only_when_all_non_combat_pairs_admitted(self):
        """Набор допущен, когда допущены все его не-боевые пары и есть
        трудный зелёный прогон набором.

        Сценарий: зелёный прогон набором целиком на трудном шаблоне;
        (а) все пары набора допущены — «допущен»; (б) одна пара (случайная)
        отсутствует в `pairs:` — «не допущен»; (в) та же пара записана
        `state: приостановлена` — «не допущен»; (г) одна роль набора
        названа боевой моделью и в `pairs:` не записана, прогон набором
        с ней есть — «допущен» (боевая пара допуска не требует).

        Ловит мутацию: состояние пары не сверяется (приостановленная
        засчитана); допуск требуется от каждой пары набора, включая
        боевую (случай (г) — «не допущен»); отсутствие пары трактуется
        как допуск — расхождение исхода в соответствующем случае."""
        self.add_run(self.hard, self.members)
        all_admitted = {role: "допущена" for role in self.members}
        self.write_set(all_admitted)
        self.assertIs(self.admitted(), True, self.note("(а)"))

        victim = self.rnd.choice(sorted(self.members))
        missing = {r: s for r, s in all_admitted.items() if r != victim}
        self.write_set(missing)
        self.assertIs(self.admitted(), False, self.note(f"(б) {victim}"))

        self.write_set({**all_admitted, victim: "приостановлена"})
        self.assertIs(self.admitted(), False, self.note(f"(в) {victim}"))

        self.members[victim] = FIXTURE_TIER_MODEL
        self.clear_runs()
        self.add_run(self.hard, self.members)
        self.write_set(missing)
        self.assertIs(self.admitted(), True,
                      self.note(f"(г) боевая пара {victim}"))


if __name__ == "__main__":
    unittest.main()
