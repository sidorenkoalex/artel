"""Допуск набора сверяет роли сводки вне набора с боевыми моделями.

Группа: долгоживущий

Красен до реализации: `models.set_admitted` засчитывает трудный зелёный прогон по одним ролям набора — прогон с не-боевыми моделями у ролей вне набора даёт «допущен» (AC-1, AC-3 называет не тот прогон), а отказ по отсутствующей роли набора несёт прежний текст без «(роли вне набора — на боевых моделях)» (AC-4); AC-2 и AC-5 (прежние условия допуска) зелены и до правки.

Планка провалидирована временным стабом реализации (все методы зелёные,
стаб удалён, репозиторий не тронут).

Публичная поверхность: `models.set_admitted(conn, <имя набора>)` —
кортеж (допущен ли, пояснение); `models.resolve_role(<роль>).model` —
боевая модель роли (разрешение моделей пульта без набора).

Песочница — `tests/sandbox.py::SchemaConnTmpRootTest`: БД со схемой, корень пульта и
локальный слой моделей во временном каталоге, карта исполнителей —
фикстура (`use_role_map`), каталог моделей — фикстура
(`use_catalog_fixture`). Файл наборов пишется по `models.model_sets_path()`
(корень песочницы); строки `canary_runs` — публичным
`store.insert_canary_run` со сводкой «роль → модель» в формате канарейки.

Состав набора (роли, какие из них на не-боевой модели), какая роль вне
набора уходит на чужую модель и на какую, метки прогонов и порядок строк
выбираются случайно; зерно печатается и входит в текст провала.
"""
import os
import random
import unittest
from unittest import mock

from orchestrator import config, models, store
from tests.sandbox import (FIXTURE_CODEX_MODEL, FIXTURE_OTHER_MODEL,
                           SchemaConnTmpRootTest)

#: agent-роли фикстуры карты исполнителей (`tests/sandbox.py::
#: FIXTURE_ROLES`) — сводка прогона канарейки называет модель каждой.
AGENT_ROLES = ("analyst", "test_author", "developer", "reviewer")

#: Причина отказа по условию задачи — дословно из SPEC (требование 2).
REFUSAL = (f"нет зелёного прогона набором целиком на шаблоне класса "
           f"«{models.TEMPLATE_HARD}» (роли вне набора — на боевых моделях)")


def model_sets_text(templates: dict, pairs: dict, sets: dict) -> str:
    """Текст `model_sets.yaml` в подмножестве `yamlmini`."""
    lines = [f"{models.SETS_KEY}:"]
    for name, members in sets.items():
        lines.append(f"  {name}:")
        lines += [f"    {role}: {model}" for role, model in members.items()]
    lines.append(f"{models.PAIRS_KEY}:")
    for role, entries in pairs.items():
        lines.append(f"  {role}:")
        for model, state in entries.items():
            lines += [f"    {model}:", "      date: 2026-10-01",
                      "      basis: решение Оператора", f"      state: {state}"]
    lines.append(f"{models.CANARY_TEMPLATES_KEY}:")
    lines += [f"  {title}: {cls}" for title, cls in templates.items()]
    return "\n".join(lines) + "\n"


class SetAdmissionSandbox(SchemaConnTmpRootTest):
    """Набор `self.set_name` со случайным составом, его не-боевые пары
    допущены в `pairs:`, шаблоны всех трёх классов и шаблон без класса."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        self.use_catalog_fixture()
        self.combat = {role: models.resolve_role(role).model
                       for role in AGENT_ROLES}

        stem = f"canary-{self.rnd.randrange(10 ** 6)}"
        self.hard = f"{stem}-trudnyy"
        self.medium = f"{stem}-sredniy"
        self.fast = f"{stem}-bystryy"
        self.unclassified = f"{stem}-bez-klassa"
        self.templates = {self.hard: models.TEMPLATE_HARD,
                          self.medium: models.TEMPLATE_MEDIUM,
                          self.fast: models.TEMPLATE_FAST}

        # Набор: от одной до трёх ролей (вне набора всегда остаётся хотя бы
        # одна), хотя бы одна — на не-боевой модели.
        size = self.rnd.randint(1, len(AGENT_ROLES) - 1)
        roles = self.rnd.sample(AGENT_ROLES, size)
        self.members = {}
        for i, role in enumerate(roles):
            other = self.non_combat(role, FIXTURE_OTHER_MODEL)
            on_combat = i > 0 and self.rnd.random() < 0.3
            self.members[role] = self.combat[role] if on_combat else other
        self.outside = [r for r in AGENT_ROLES if r not in self.members]
        self.set_name = f"nabor-{self.rnd.randrange(10 ** 6)}"
        self.pair_states = {
            role: models.PAIR_ADMITTED for role, model in self.members.items()
            if model != self.combat[role]}
        self.write_model_sets()
        # Таблицу прогонов заводит первое обращение к ней.
        self.assertEqual(list(store.all_canary_runs(self.conn)), [])
        self.stamps = set()

    # ------------------------------------------------------------ сценарий

    def non_combat(self, role: str, preferred: str = None) -> str:
        """Модель, отличная от боевой модели роли."""
        candidates = [preferred] if preferred else [
            FIXTURE_OTHER_MODEL, FIXTURE_CODEX_MODEL,
            f"model-chuzhaya-{self.rnd.randrange(10 ** 6)}"]
        candidates = [m for m in candidates if m != self.combat[role]]
        if not candidates:
            candidates = [f"model-chuzhaya-{self.rnd.randrange(10 ** 6)}"]
        return self.rnd.choice(candidates)

    def write_model_sets(self) -> None:
        pairs = {}
        for role, state in self.pair_states.items():
            pairs[role] = {self.members[role]: state}
        path = models.model_sets_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(model_sets_text(self.templates, pairs,
                                        {self.set_name: self.members}),
                        encoding="utf-8")

    def summary(self, overrides: dict = None, drop: tuple = ()) -> dict:
        """«роль → модель» прогона: роли набора — модели набора, роли вне
        набора — боевые; поверх — `overrides`, без ролей `drop`."""
        pairs = dict(self.combat)
        pairs.update(self.members)
        pairs.update(overrides or {})
        return {r: m for r, m in pairs.items() if r not in drop}

    def stamp(self) -> str:
        while True:
            value = (f"2026{self.rnd.randrange(10 ** 4):04d}T"
                     f"{self.rnd.randrange(10 ** 6):06d}Z")
            if value not in self.stamps:
                self.stamps.add(value)
                return value

    def add_run(self, pairs: dict, title: str = None,
                verdict: str = "green") -> str:
        """Строка `canary_runs` со сводкой `pairs`; возвращает её метку."""
        run_stamp = self.stamp()
        named = ", ".join(f"{role} → {model}" for role, model in pairs.items())
        store.insert_canary_run(
            self.conn, run_stamp, title or self.hard,
            f"T-RUN-{len(self.stamps)}", 10, 1.0, 0, 0, "merge_gate",
            None, False, False, main_sha="0" * 40, verdict=verdict,
            models_summary=f"{named}; источник: слой пульта")
        return run_stamp

    def foreign_outside(self) -> dict:
        """Случайное непустое подмножество ролей вне набора — на моделях,
        отличных от их боевых."""
        count = self.rnd.randint(1, len(self.outside))
        return {role: self.non_combat(role)
                for role in self.rnd.sample(self.outside, count)}

    def decision(self) -> tuple:
        result = models.set_admitted(store.db(), self.set_name)
        self.assertIsInstance(result, tuple, self.note())
        return result

    def note(self, extra: str = "") -> str:
        return (f"зерно {self.seed}; набор {self.members}; вне набора "
                f"{self.outside}. {extra}")


class OutsideRolesTest(SetAdmissionSandbox):

    def test_ac1_foreign_models_outside_set_not_counted(self):
        """Трудный зелёный прогон с чужими моделями у ролей вне набора — не
        засчитан.

        Сценарий: сводка прогона совпадает с набором по всем его ролям,
        но случайная непустая часть ролей вне набора шла на модели,
        отличной от боевой; других прогонов нет — `set_admitted`
        возвращает «не допущен» с причиной SPEC о прогоне набором
        целиком (роли вне набора — на боевых моделях).

        Ловит мутацию: прогон с другими моделями у ролей вне набора засчитан."""
        foreign = self.foreign_outside()
        self.add_run(self.summary(foreign))
        admitted, text = self.decision()
        self.assertIs(admitted, False, self.note(f"чужие {foreign}: {text}"))
        self.assertIn(REFUSAL, text, self.note(f"чужие {foreign}"))

    def test_ac2_combat_models_outside_set_counted_and_named(self):
        """Трудный зелёный прогон с боевыми моделями вне набора — засчитан.

        Сценарий: сводка совпадает с набором по его ролям, каждая роль
        вне набора — на своей боевой модели; `set_admitted` возвращает
        «допущен», и пояснение называет `run_stamp` этого прогона.

        Ловит мутацию: роль вне набора сверяется не с её боевой моделью, а
        с моделью набора (или условие требует, чтобы все роли сводки
        были в наборе) — правильный прогон не засчитан, «не допущен»;
        пояснение собрано без метки прогона — `run_stamp` в тексте нет."""
        run_stamp = self.add_run(self.summary())
        admitted, text = self.decision()
        self.assertIs(admitted, True, self.note(text))
        self.assertIn(run_stamp, text, self.note())

    def test_ac3_both_runs_names_the_combat_one(self):
        """Из двух трудных зелёных прогонов засчитан тот, где роли вне набора
        на боевых моделях.

        Сценарий: в `canary_runs` — прогон с чужими моделями у ролей вне
        набора и прогон с боевыми; оба порядка строк разыгрываются по
        очереди на чистой таблице; `set_admitted` допускает набор,
        пояснение называет метку прогона с боевыми моделями и не
        называет метку второго.

        Ловит мутацию: прогон с другими моделями у ролей вне набора засчитан
        (при его первой строке пояснение называет его метку); условие
        вне набора отбрасывает весь набор при первом же неподходящем
        прогоне вместо перехода к следующей строке — «не допущен»."""
        for order in (("foreign", "combat"), ("combat", "foreign")):
            self.conn.execute("DELETE FROM canary_runs")
            self.conn.commit()
            summaries = {"combat": self.summary(),
                         "foreign": self.summary(self.foreign_outside())}
            stamps = {kind: self.add_run(summaries[kind]) for kind in order}
            admitted, text = self.decision()
            self.assertIs(admitted, True,
                          self.note(f"порядок {order}: {text}"))
            self.assertIn(stamps["combat"], text,
                          self.note(f"порядок {order}"))
            self.assertNotIn(stamps["foreign"], text,
                             self.note(f"порядок {order}: {text}"))

    def test_ac4_set_role_missing_from_summary_not_counted(self):
        """Трудный зелёный прогон без роли набора в сводке — не засчитан.

        Сценарий: сводка совпадает с набором по остальным его ролям, роли
        вне набора — на боевых моделях, но случайная роль набора в сводке
        не названа вовсе; других прогонов нет — «не допущен» с причиной
        SPEC из AC-1.

        Ловит мутацию: сверка ведётся только по ролям, которые есть в
        сводке (отсутствующая роль набора пропускается), — «допущен»;
        отказ по этому случаю несёт прежний текст без уточнения о ролях
        вне набора — причины SPEC в тексте нет."""
        victim = self.rnd.choice(sorted(self.members))
        self.add_run(self.summary(drop=(victim,)))
        admitted, text = self.decision()
        self.assertIs(admitted, False, self.note(f"без {victim}: {text}"))
        self.assertIn(REFUSAL, text, self.note(f"без {victim}"))


class OtherConditionsTest(SetAdmissionSandbox):

    def test_ac5_other_admission_conditions_unchanged(self):
        """Пара и прогон по-прежнему сверяются прежними условиями.

        Сценарий: в `canary_runs` — прогон, удовлетворяющий AC-2 (роли
        набора — модели набора, роли вне набора — боевые), на трудном
        шаблоне. По очереди: (а) случайная не-боевая пара набора не
        записана в `pairs:`, (б) записана `state: приостановлена`,
        (в) допущена, но приостановлена пультом (строка
        `pair_suspensions`) — «не допущен» с прежней причиной о паре;
        затем при допущенных парах единственный такой прогон (г) на
        шаблоне класса средний/быстрый/без записи класса, (д) на трудном
        шаблоне с вердиктом не `green` — «не допущен».

        Ловит мутацию: новое условие о ролях вне набора переписало цикл
        `set_admitted` и потеряло сверку пары, вердикта или класса
        шаблона — в соответствующем случае «допущен»; отказ по паре
        заменён общей причиной о прогоне — имени пары в тексте нет."""
        run = self.summary()
        victim = self.rnd.choice(sorted(self.pair_states))
        model = self.members[victim]
        pair = f"пара {victim} → {model}"
        self.add_run(run)

        admitted_states = dict(self.pair_states)
        for case, state in (("а", None), ("б", models.PAIR_SUSPENDED)):
            self.pair_states = {r: s for r, s in admitted_states.items()
                                if r != victim}
            if state is not None:
                self.pair_states[victim] = state
            self.write_model_sets()
            admitted, text = self.decision()
            self.assertIs(admitted, False, self.note(f"({case}) {victim}"))
            self.assertIn(pair, text, self.note(f"({case})"))
            self.assertIn("не допущена", text, self.note(f"({case})"))

        self.pair_states = admitted_states
        self.write_model_sets()
        self.assertIs(self.decision()[0], True, self.note("пары допущены"))
        store.insert_pair_suspension(self.conn, victim, model, self.set_name,
                                     "T-SUSP", "возврат ревью")
        admitted, text = self.decision()
        self.assertIs(admitted, False, self.note(f"(в) {victim}"))
        self.assertIn(pair, text, self.note("(в)"))
        self.assertIn("приостановлена пультом", text, self.note("(в)"))

        title = self.rnd.choice([self.medium, self.fast, self.unclassified])
        verdict = self.rnd.choice(["red", "yellow", None])
        for case, kwargs in (("г", {"title": title}),
                             ("д", {"verdict": verdict})):
            # Чистая БД: ни прогонов, ни приостановки пары.
            self.conn.execute("DELETE FROM canary_runs")
            self.conn.execute("DELETE FROM pair_suspensions")
            self.conn.commit()
            self.add_run(run, **kwargs)
            admitted, text = self.decision()
            self.assertIs(admitted, False,
                          self.note(f"({case}) {kwargs}: {text}"))


if __name__ == "__main__":
    unittest.main()
