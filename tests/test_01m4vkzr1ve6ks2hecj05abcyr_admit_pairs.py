"""Команда `admit`: несколько пар за один вызов, правка набора `--set` и
одна запись на весь вызов.

Группа: долгоживущий

Красен до реализации: `admit` разбирает ровно одну позиционную пару и не знает флага `--set` — вызовы AC-2..AC-5 с несколькими парами и с `--set` отказывают разбором, `ADMIT_USAGE` и справка (AC-9) показывают старую форму; зелёными с рождения остаются AC-1 (одна пара — прежнее поведение) и отказы AC-6, AC-7, AC-8 (сегодня их даёт отказ разбора).

Планка провалидирована временным стабом реализации: все методы зелёные;
на стабе внесены мутации из строк «Ловит мутацию» (проверка набора только
по названным парам, без приостановок пультом, выход на первой недобравшей
паре, запись на каждую пару, перезапись набора целиком, отброшенный
нечётный хвост, форма перечня для одной пары) — каждая краснит свой
метод; стаб удалён, код репозитория не тронут.

Публичная поверхность: команда `artel.py admit …` через диспетчер
`artel.main()` тем же argv, что набирает Оператор; `models.ADMIT_USAGE`;
справка `artel.py --help`. Запись наблюдается подменой публичного
`notes.doc_commit_content` (путь, текст файла, сообщение коммита) — число
её вызовов и есть число коммитов и прогонов гейта полного набора.

Песочница — `RealGitSandbox`: корень пульта — настоящий git-репозиторий с
закоммиченным `model_sets.yaml`; «файл и HEAD не тронуты» — снимок
(HEAD, `git status`, текст файла). Карта исполнителей и каталог моделей —
фикстуры `tests/sandbox.py`: боевая модель каждой agent-роли —
`FIXTURE_TIER_MODEL`, «другая модель каталога» — `FIXTURE_OTHER_MODEL`.
Прогоны канарейки пишутся публичным `store.insert_canary_run`,
приостановка пары пультом — `store.insert_pair_suspension`.

Роли пар, их порядок в вызове, имена набора и шаблонов, основание и
выбор «набравшей» пары — случайные; зерно печатается и входит в текст
провала.
"""
import contextlib
import inspect
import io
import os
import random
import re
import sys
import unittest
from datetime import date
from unittest import mock

from orchestrator import artel, config, models, notes, store, yamlmini
from tests.sandbox import (FIXTURE_OTHER_MODEL, FIXTURE_TIER_MODEL,
                           RealGitSandbox)

#: agent-роли фикстуры карты исполнителей — сводка прогона называет каждую.
AGENT_ROLES = ("analyst", "test_author", "developer", "reviewer",
               "spec_auditor")

#: Роли пар сценариев: у analyst своё дополнительное условие допуска
#: (прогон с неясностью ТЗ) — не предмет этого файла.
PLAIN_ROLES = ("test_author", "developer", "reviewer", "spec_auditor")

OTHER = FIXTURE_OTHER_MODEL
TIER = FIXTURE_TIER_MODEL

#: Сигнатура записи — снята до подмены: аргументы вызова подмены
#: разбираются по ней независимо от того, позиционные они или именованные.
DOC_COMMIT_SIGNATURE = inspect.signature(notes.doc_commit_content)


def run_summary(overrides: dict) -> str:
    """Сводка `models_summary` прогона: боевая модель каждой agent-роли,
    поверх — `overrides`; формат канарейки."""
    pairs = {role: TIER for role in AGENT_ROLES}
    pairs.update(overrides)
    named = ", ".join(f"{role} → {model}" for role, model in pairs.items())
    return f"{named}; источник: слой пульта"


def usage_form(text: str) -> list:
    """Отрезки «admit … --basis» текста (без разрывов `|` и обратных
    кавычек) — форма команды в справке."""
    collapsed = " ".join(text.split())
    return re.findall(r"admit\b[^|`]*?--basis", collapsed)


def shows_multi_pair_set_form(text: str) -> bool:
    """Форма команды в тексте несёт флаг `--set` и повтор пары."""
    return any("--set" in form and ("..." in form or "…" in form)
               for form in usage_form(text))


class AdmitPairsSandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        self.use_role_map()
        self.use_catalog_fixture()
        stem = f"canary-{self.rnd.randrange(10 ** 6)}"
        self.medium = f"{stem}-sredniy"
        self.fast = f"{stem}-bystryy"
        self.hard = f"{stem}-trudnyy"
        self.templates = {self.medium: "средний", self.fast: "быстрый",
                          self.hard: "трудный"}
        self.header = f"# Наборы моделей песочницы {self.seed}\n"
        self.conn = store.db()
        self.run_no = 0
        self.suspensions = []
        self.put_model_sets()
        commit = mock.patch.object(notes, "doc_commit_content")
        self.commit = commit.start()
        self.addCleanup(commit.stop)

    # ------------------------------------------------------------ сценарий

    def note(self, extra: str = "") -> str:
        return f"зерно {self.seed}. {extra}"

    def roles(self, n: int) -> list:
        return self.rnd.sample(PLAIN_ROLES, n)

    def basis(self) -> str:
        return f"прогоны канарейки {self.rnd.randrange(10 ** 6)}"

    def set_name(self) -> str:
        return f"nabor-{self.rnd.randrange(10 ** 6)}"

    def put_model_sets(self, pairs: dict = None, sets: dict = None) -> None:
        """`model_sets.yaml` в каноническом виде записи пульта; `pairs` —
        `{роль: {модель: state}}`, `sets` — `{имя: {роль: модель}}`."""
        document = {"sets": sets or {}, "pairs": {}, "canary_templates":
                    dict(self.templates)}
        for role, entries in (pairs or {}).items():
            document["pairs"][role] = {
                model: {"date": "2026-10-01", "basis": "решение Оператора",
                        "state": state}
                for model, state in entries.items()}
        text = models.render_model_sets(document, self.header)
        path = config.ROOT / config.MODEL_SETS_REL
        path.write_text(text, encoding="utf-8")
        self.git("add", config.MODEL_SETS_REL)
        self.git("commit", "-q", "--allow-empty", "-m", "наборы моделей")

    def fresh(self, pairs: dict = None, sets: dict = None) -> None:
        """Чистый сценарий внутри метода: файл, пустая таблица прогонов,
        снятые приостановки, сброшенная подмена записи."""
        self.put_model_sets(pairs, sets)
        exists = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND "
            "name='canary_runs'").fetchone()
        if exists:
            self.conn.execute("DELETE FROM canary_runs")
            self.conn.commit()
        for suspension_id in self.suspensions:
            store.resume_pair_suspension(self.conn, suspension_id, "сброс")
        self.suspensions = []
        self.commit.reset_mock()

    def add_run(self, title: str, overrides: dict) -> None:
        """Чистая строка `canary_runs` с моделями `overrides`."""
        self.run_no += 1
        store.insert_canary_run(
            self.conn, f"stamp-{self.run_no}", title, f"T-RUN-{self.run_no}",
            10, 1.0, 0, 0, "merge_gate", None, False, False,
            main_sha="0" * 40, verdict="green",
            models_summary=run_summary(overrides))

    def add_sufficient_runs(self, role: str, model: str) -> None:
        """Три чистых прогона пары на среднем, быстром и трудном шаблонах —
        ровно числа ADR-0019 п.5."""
        for title in (self.medium, self.fast, self.hard):
            self.add_run(title, {role: model})

    def suspend(self, role: str, model: str) -> None:
        self.suspensions.append(store.insert_pair_suspension(
            self.conn, role, model, "nabor-pulta", "T-SUSP", "три красных"))

    def admission(self, role: str, model: str) -> tuple:
        """(строки сводки, недостающее) пары по текущему состоянию."""
        return models.pair_admission(self.conn, role, model,
                                     models.load_model_sets())

    def admit(self, *argv: str) -> tuple:
        """(код выхода, stdout, stderr, текст отказа) `artel.py admit`."""
        out, err = io.StringIO(), io.StringIO()
        code, refusal = 0, ""
        with mock.patch.object(sys, "argv", ["artel.py", "admit", *argv]), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (0, None):
                    code = exc.code if isinstance(exc.code, int) else 1
                    refusal = "" if isinstance(exc.code, int) else exc.code
        return code, out.getvalue(), err.getvalue(), refusal

    # ---------------------------------------------------------- наблюдение

    def snapshot(self) -> tuple:
        return (self.git("rev-parse", "HEAD").strip(),
                self.git("status", "--porcelain"),
                (config.ROOT / config.MODEL_SETS_REL).read_text(
                    encoding="utf-8"))

    def written(self) -> tuple:
        """(путь, текст, сообщение) единственного вызова записи."""
        self.assertEqual(self.commit.call_count, 1,
                         self.note(f"вызовы записи: {self.commit.call_args_list}"))
        call = self.commit.call_args
        bound = DOC_COMMIT_SIGNATURE.bind(*call.args, **call.kwargs)
        args = list(bound.arguments.values())
        return args[0], args[1], args[2]

    def written_document(self) -> dict:
        path, text, _ = self.written()
        self.assertEqual(str(path), config.MODEL_SETS_REL, self.note())
        return yamlmini.mapping(text)

    def assert_refused_untouched(self, result: tuple, before: tuple,
                                 extra: str = "") -> None:
        code, out, err, refusal = result
        self.assertNotEqual(code, 0, self.note(f"{extra} запись прошла:\n{out}"))
        self.commit.assert_not_called()
        self.assertEqual(before, self.snapshot(),
                         self.note(f"{extra} отказ тронул файл или HEAD"))


class SinglePairTest(AdmitPairsSandbox):

    def test_ac1_single_pair_grant_and_revoke_byte_for_byte(self):
        """Одна пара — прежние stdout, stderr, код, текст файла и сообщение.

        Сценарий (подтесты): (выдача) рядом — допущенная пара другой роли,
        у пары три чистых прогона; `admit <роль> <модель> --basis`;
        (снятие) пара записана допущенной; `admit --revoke <роль> <модель>
        --basis`. Ожидаемое собрано по прежней форме команды: stdout —
        сводка `pair_admission` и строка «допуск пары R → M: state:
        допущена» (у снятия — только строка «снятие допуска …»), stderr
        пуст, код 0, текст файла — прежний документ с записью пары
        (date — сегодня, basis, state) в каноническом виде записи, сообщение
        — «<действие> пары R → M: <основание>».

        Ловит мутацию: для одной пары печатается заголовок перечня пар или
        «пара 1 из 1» (stdout другой); сообщение коммита переходит на форму
        перечня («допуск пар: …») — сообщение расходится; запись пары
        несёт поле набора или иной порядок полей — текст файла расходится."""
        role, neighbour = self.roles(2)
        for revoke in (False, True):
            with self.subTest(revoke=revoke):
                if revoke:
                    self.fresh(pairs={role: {OTHER: models.PAIR_ADMITTED},
                                      neighbour: {OTHER: models.PAIR_ADMITTED}})
                    state, action = models.PAIR_SUSPENDED, "снятие допуска"
                    summary = ""
                else:
                    self.fresh(pairs={neighbour: {OTHER: models.PAIR_ADMITTED}})
                    self.add_sufficient_runs(role, OTHER)
                    state, action = models.PAIR_ADMITTED, "допуск"
                    lines, missing = self.admission(role, OTHER)
                    self.assertEqual(missing, [], self.note("фикстура"))
                    summary = "\n".join(lines) + "\n"
                document = models.load_model_sets()
                document["pairs"].setdefault(role, {})[OTHER] = {
                    "date": date.today().isoformat(), "basis": None,
                    "state": state}
                basis = self.basis()
                document["pairs"][role][OTHER]["basis"] = basis
                expected_text = models.render_model_sets(document, self.header)

                argv = (["--revoke"] if revoke else []) + [
                    role, OTHER, "--basis", basis]
                code, out, err, refusal = self.admit(*argv)

                self.assertEqual((code, refusal), (0, ""), self.note(out))
                self.assertEqual(err, "", self.note())
                self.assertEqual(
                    out, f"{summary}{action} пары {role} → {OTHER}: "
                         f"state: {state}\n", self.note())
                path, text, message = self.written()
                self.assertEqual(str(path), config.MODEL_SETS_REL)
                self.assertEqual(text, expected_text, self.note())
                self.assertEqual(
                    message, f"{action} пары {role} → {OTHER}: {basis}",
                    self.note())


class MultiPairTest(AdmitPairsSandbox):

    def test_ac2_two_admitted_pairs_one_write(self):
        """Две набравшие пары — обе допущены одной записью с общим основанием.

        Сценарий: у первой роли три чистых прогона на «другой» модели, у
        второй — на боевой (её дают прогоны первой); пары в вызове в
        случайном порядке. stdout несёт сводку `pair_admission` каждой
        пары; ровно один вызов записи; в записанном файле обе пары
        `state: допущена` с основанием `--basis`; сообщение называет роль
        и модель каждой пары.

        Ловит мутацию: пишется только первая пара (вторая без записи);
        запись зовётся на каждую пару (два вызова); основание пишется
        только первой паре; сводка печатается только по первой паре;
        сообщение называет одну пару — второй роли или модели в нём нет."""
        first, second = self.roles(2)
        self.add_sufficient_runs(first, OTHER)
        pairs = [(first, OTHER), (second, TIER)]
        self.rnd.shuffle(pairs)
        summaries = []
        for role, model in pairs:
            lines, missing = self.admission(role, model)
            self.assertEqual(missing, [], self.note(f"фикстура {role}"))
            summaries.append("\n".join(lines))
        basis = self.basis()
        argv = [item for pair in pairs for item in pair] + ["--basis", basis]

        code, out, err, refusal = self.admit(*argv)

        self.assertEqual(code, 0, self.note(f"{out}\n{err}\n{refusal}"))
        for block in summaries:
            self.assertIn(block, out, self.note())
        document = self.written_document()
        _, _, message = self.written()
        for role, model in pairs:
            entry = (document.get("pairs") or {}).get(role, {}).get(model)
            self.assertIsNotNone(entry, self.note(f"{role} → {model}"))
            self.assertEqual(entry.get("state"), models.PAIR_ADMITTED,
                             self.note(role))
            self.assertEqual(entry.get("basis"), basis, self.note(role))
            self.assertIn(role, message, self.note(message))
            self.assertIn(model, message, self.note(message))

    def test_ac3_two_shortfalls_of_three_refuse_without_write(self):
        """Две недобравшие пары из трёх — отказ с перечнем каждой, без записи.

        Сценарий: три роли на «другой» модели в случайном порядке; одна
        набрала числа (три чистых прогона), у второй прогонов нет, у
        третьей два чистых прогона (среднего и быстрого шаблонов). Сводка
        `pair_admission` каждой из трёх пар есть в stdout; текст отказа
        называет обе недобравшие роли и всё недостающее каждой; записи нет,
        файл и HEAD прежние.

        Ловит мутацию: выход на первой недобравшей паре (второй нет в
        отказе или сводки третьей пары нет в stdout); набравшая пара
        записывается до отказа (вызов записи есть); перечень печатается
        общий без пары — роли нет в тексте отказа."""
        full, empty, partial = self.roles(3)
        self.add_sufficient_runs(full, OTHER)
        self.add_run(self.medium, {partial: OTHER})
        self.add_run(self.fast, {partial: OTHER})
        order = [full, empty, partial]
        self.rnd.shuffle(order)
        summaries, shortfall = [], {}
        for role in order:
            lines, missing = self.admission(role, OTHER)
            summaries.append("\n".join(lines))
            if role != full:
                self.assertTrue(missing, self.note(f"фикстура {role}"))
                shortfall[role] = missing
        before = self.snapshot()
        argv = [item for role in order for item in (role, OTHER)]

        result = self.admit(*argv, "--basis", self.basis())

        self.assert_refused_untouched(result, before)
        _, out, err, refusal = result
        for block in summaries:
            self.assertIn(block, out, self.note(out))
        text = refusal + err
        for role, missing in shortfall.items():
            self.assertIn(role, text, self.note(text))
            for item in missing:
                self.assertIn(item, text, self.note(f"{role}: {text}"))

    def test_ac4_revoke_several_pairs_one_write(self):
        """`--revoke` нескольких пар — все приостановлены одной записью.

        Сценарий: две-три роли с допущенной парой на «другой» модели;
        `admit --revoke` всех их в случайном порядке. Ровно один вызов
        записи; в записанном файле каждая названная пара
        `state: приостановлена`.

        Ловит мутацию: `--revoke` переводит только первую пару (вторая
        остаётся допущенной); запись зовётся на каждую пару (вызовов
        больше одного)."""
        named = self.roles(self.rnd.choice((2, 3)))
        self.fresh(pairs={role: {OTHER: models.PAIR_ADMITTED}
                          for role in named})
        argv = [item for role in named for item in (role, OTHER)]

        code, out, err, refusal = self.admit("--revoke", *argv, "--basis",
                                             self.basis())

        self.assertEqual(code, 0, self.note(f"{out}\n{err}\n{refusal}"))
        document = self.written_document()
        for role in named:
            entry = (document.get("pairs") or {}).get(role, {}).get(OTHER)
            self.assertEqual((entry or {}).get("state"), models.PAIR_SUSPENDED,
                             self.note(f"{role}: {entry}"))


class SetWriteTest(AdmitPairsSandbox):

    def test_ac5_set_written_with_pairs_in_one_write(self):
        """`--set` записывает модели пар в набор той же записью.

        Сценарий (подтесты): (новый) набора нет, две роли набирают числа
        на «другой» модели — набор создан с ровно этими ролями; (прежний)
        набор уже есть: роль на «другой» модели с допущенной парой и роль
        на своей боевой модели без записи в `pairs:`; вызов называет третью
        роль, набравшую числа — в наборе три роли, две прежние с прежними
        моделями. В обоих — один вызов записи, пары вызова допущены,
        сообщение называет набор.

        Ловит мутацию: набор перезаписывается целиком (прежние роли
        потеряны); несуществующий набор не создаётся (отказ или раздела
        нет); проверка набора требует записи `pairs:` и для роли на боевой
        модели (прежний — отказ); набор пишется вторым вызовом записи;
        сообщение без имени набора."""
        for existing in (False, True):
            with self.subTest(existing=existing):
                name = self.set_name()
                if existing:
                    named, kept_other, kept_tier = self.roles(3)
                    named = [named]
                    old = {kept_other: OTHER, kept_tier: TIER}
                    self.fresh(pairs={kept_other: {OTHER: models.PAIR_ADMITTED}},
                               sets={name: old})
                else:
                    named = self.roles(2)
                    old = {}
                    self.fresh()
                for role in named:
                    self.add_sufficient_runs(role, OTHER)
                argv = [item for role in named for item in (role, OTHER)]

                code, out, err, refusal = self.admit(
                    "--set", name, *argv, "--basis", self.basis())

                self.assertEqual(code, 0, self.note(f"{out}\n{err}\n{refusal}"))
                document = self.written_document()
                expected = dict(old, **{role: OTHER for role in named})
                self.assertEqual((document.get("sets") or {}).get(name),
                                 expected, self.note())
                for role in named:
                    entry = (document.get("pairs") or {}).get(role, {}).get(OTHER)
                    self.assertEqual((entry or {}).get("state"),
                                     models.PAIR_ADMITTED, self.note(role))
                _, _, message = self.written()
                self.assertIn(name, message, self.note(message))

    def test_ac6_set_with_unadmitted_pair_refused(self):
        """`--set`, после которого пара набора не допущена, — отказ без записи.

        Сценарий (подтесты, каждый с чистого состояния): прежний набор
        несёт роль, не названную в вызове, на «другой» модели, а названная
        роль числа набрала: (1а) пары этой роли нет в `pairs:`; (1б) пара
        `state: приостановлена`; (1в) то же, что (1а), но вызов —
        `--revoke --set` пары названной роли на её боевой модели (сама
        такая пара допуска не требует); (2а) названная пара набрала числа,
        но приостановлена пультом; (2б) пара не названной роли допущена в
        `pairs:`, но приостановлена пультом. Каждый раз — отказ, записи
        нет, файл и HEAD прежние.

        Ловит мутацию: проверяются только пары, названные в вызове ((1а),
        (1б), (1в) записываются); проверка идёт только по `pairs:` без
        приостановок пультом ((2а), (2б) записываются); при `--revoke`
        проверка набора пропускается ((1в) записывается)."""
        named, other = self.roles(2)
        cases = {
            "1а": ({}, False, False, False),
            "1б": ({other: {OTHER: models.PAIR_SUSPENDED}}, False, False,
                   False),
            "1в": ({}, True, False, False),
            "2а": ({other: {OTHER: models.PAIR_ADMITTED}}, False, True, False),
            "2б": ({other: {OTHER: models.PAIR_ADMITTED}}, False, False, True),
        }
        for case, (pairs, revoke, suspend_named, suspend_other) in \
                cases.items():
            with self.subTest(case=case):
                name = self.set_name()
                self.fresh(pairs=pairs, sets={name: {other: OTHER}})
                if revoke:
                    argv = ["--revoke", "--set", name, named, TIER]
                else:
                    self.add_sufficient_runs(named, OTHER)
                    self.assertEqual(self.admission(named, OTHER)[1], [],
                                     self.note("фикстура"))
                    argv = ["--set", name, named, OTHER]
                if suspend_named:
                    self.suspend(named, OTHER)
                if suspend_other:
                    self.suspend(other, OTHER)
                before = self.snapshot()

                result = self.admit(*argv, "--basis", self.basis())

                self.assert_refused_untouched(result, before, f"({case})")

    def test_ac8_two_pairs_of_one_role_with_set_refused(self):
        """`--set` с двумя парами одной роли — отказ без записи.

        Сценарий: одна роль названа дважды — на «другой» и на боевой
        модели (порядок случайный); обе пары числа набрали, набора нет.
        Отказ, записи нет, файл и HEAD прежние.

        Ловит мутацию: последняя пара роли молча перекрывает первую в
        наборе — набор с одной моделью роли записывается (вызов записи
        есть)."""
        role, helper = self.roles(2)
        self.add_sufficient_runs(role, OTHER)
        self.add_sufficient_runs(helper, OTHER)
        pairs = [(role, OTHER), (role, TIER)]
        self.rnd.shuffle(pairs)
        for pair in pairs:
            self.assertEqual(self.admission(*pair)[1], [],
                             self.note(f"фикстура {pair}"))
        before = self.snapshot()
        argv = [item for pair in pairs for item in pair]

        result = self.admit("--set", self.set_name(), *argv, "--basis",
                            self.basis())

        self.assert_refused_untouched(result, before, f"{pairs}")


class ParseRefusalTest(AdmitPairsSandbox):

    def test_ac7_odd_or_zero_positionals_refused_with_usage(self):
        """Нечётное число позиционных и ноль пар — отказ разбора со справкой.

        Сценарий (подтесты): одна роль; пара и лишняя роль; ни одной пары;
        ни одной пары с `--set <имя>`. У первой роли пары числа набраны —
        запись была бы возможна. Каждый раз — отказ, текст которого несёт
        `models.ADMIT_USAGE`, записи нет, файл и HEAD прежние.

        Ловит мутацию: нечётный хвост молча отбрасывается (пара записана);
        ноль пар с `--set` даёт пустую запись (вызов записи есть); отказ
        иным текстом без образца команды — `ADMIT_USAGE` нет в отказе."""
        first, second = self.roles(2)
        self.add_sufficient_runs(first, OTHER)
        cases = {
            "одна роль": [first],
            "пара и роль": [first, OTHER, second],
            "ноль пар": [],
            "ноль пар с --set": ["--set", self.set_name()],
        }
        for case, argv in cases.items():
            with self.subTest(case=case):
                before = self.snapshot()
                result = self.admit(*argv, "--basis", self.basis())
                self.assert_refused_untouched(result, before, case)
                _, _, err, refusal = result
                self.assertIn(models.ADMIT_USAGE, refusal + err,
                              self.note(f"{case}: {refusal}{err}"))


class HelpTest(unittest.TestCase):

    def test_ac9_usage_and_help_show_multi_pair_set_form(self):
        """`ADMIT_USAGE` и справка `artel.py` — форма с `--set` и повтором пары.

        Сценарий: в тексте `models.ADMIT_USAGE` и в справке `artel.py`
        (докстринг модуля — его печатает `artel.py --help`) берётся форма
        команды «admit … --basis»; хотя бы одна форма несёт флаг `--set`
        и знак повтора пары («...» или «…»).

        Ловит мутацию: `ADMIT_USAGE` обновлён, а строка `admit` справки
        `artel.py` осталась старой (или наоборот) — в одном из текстов нет
        формы с `--set` и повтором."""
        for where, text in (("ADMIT_USAGE", models.ADMIT_USAGE),
                            ("справка artel.py", artel.__doc__ or "")):
            with self.subTest(where=where):
                self.assertTrue(shows_multi_pair_set_form(text),
                                f"{where}: {usage_form(text)}")


if __name__ == "__main__":
    unittest.main()
