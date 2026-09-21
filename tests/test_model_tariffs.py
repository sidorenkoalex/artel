"""Юнит-тесты тарифа на модель, истории тарифов и проверок `doctor`
(SPEC 01M300A14KRHCFB0DQXVCBJEKF, требования 1, 5-6, 8-9).

Углы, которые не закрывает планка задачи: разрешение тарифа ПО МОДЕЛИ
(`models.resolve_model`), деградация неразрешимого тарифа вместо отказа
(требование 9), возврат и состав записи `store.record_model_tariff`,
нечитаемая дата тарифа и провязка обеих новых проверок в
`doctor.all_checks`.

Каталог здесь временный, с двумя моделями разной цены: предмет проверок —
поведение на смене модели и тарифа, а боевой `models.yaml` репозитория
меняется своим чередом и такой сценарий не изображает.
"""
import inspect
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, doctor, models, spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

MODEL_ALFA = "model-alfa"
MODEL_BETA = "model-beta"

PRICES = {MODEL_ALFA: (3.0, 15.0, 3.75, 0.30),
          MODEL_BETA: (7.0, 35.0, 8.75, 0.70)}

CATALOG_PRICE_DATE = (date.today() - timedelta(days=30)).isoformat()

OVERRIDE_CALIBRATED_AT = "2026-02-03"
OVERRIDE_SOURCE = "сверено с фактом CLI"

TOKENS = {"input_tokens": 40_000, "output_tokens": 20_000,
          "cache_creation_input_tokens": 60_000,
          "cache_read_input_tokens": 2_000_000}

# Ярус `strong` -> model-alfa (developer, reviewer), `standard` ->
# model-beta (test_author): две роли на одной модели и одна на другой.
ROLES_TEXT = """\
roles:
  developer:
    executor: agent
    token_slot: artel-developer
    skills: [conventions-core]
    model_tier: strong
  reviewer:
    executor: agent
    token_slot: artel-reviewer
    skills: [conventions-core]
    model_tier: strong
  test_author:
    executor: agent
    token_slot: artel-test-author
    skills: [conventions-core]
    model_tier: standard
token_fallback: artel-token
"""

ROLE_ON_ALFA = "developer"
ROLE_ON_BETA = "test_author"


def catalog_text(price_date: str = None, prices: dict = None,
                 skip_kind: str = None) -> str:
    """Каталог с двумя моделями; `skip_kind` — вид цены, который НЕ
    записывается (сценарий неполного прейскуранта)."""
    price_date = price_date or CATALOG_PRICE_DATE
    prices = prices or PRICES
    lines = ["providers:", "  claude:", "    cli: claude",
             "    min_cli_version: 1.0.0", "    cost_from_cli: true",
             "    models:"]
    for model_id in (MODEL_ALFA, MODEL_BETA):
        lines += [f"      {model_id}:", "        min_cli_version: 1.0.0",
                  f"        status: {models.STATUS_SUPPORTED}",
                  f"        {models.LIST_PRICE_KEY}:"]
        lines += [f"          {kind}: {price}"
                  for kind, price in zip(models.PRICE_KINDS, prices[model_id])
                  if kind != skip_kind]
        lines.append(f"        {models.PRICE_DATE_KEY}: {price_date}")
    return "\n".join(lines) + "\n"


def local_text(overrides: dict = None) -> str:
    """Локальный слой: ярусы и, по желанию, собственный тариф."""
    lines = [f"{models.TIERS_KEY}:", f"  strong: {MODEL_ALFA}",
             f"  standard: {MODEL_BETA}", f"  cheap: {MODEL_ALFA}"]
    if overrides:
        lines.append(f"{models.OVERRIDES_KEY}:")
        for model_id, prices in overrides.items():
            lines.append(f"  {model_id}:")
            lines += [f"    {kind}: {price}"
                      for kind, price in zip(models.PRICE_KINDS, prices)]
            lines.append(f"    {models.CALIBRATED_AT_KEY}: "
                         f"{OVERRIDE_CALIBRATED_AT}")
            lines.append(f"    {models.SOURCE_KEY}: {OVERRIDE_SOURCE}")
    return "\n".join(lines) + "\n"


class _TariffSandbox(TaskSeededTmpRootTest):
    """Пульт с временным каталогом двух моделей, локальным слоем и картой
    исполнителей; `self.conn` — БД с заведённой задачей `self.TASK`."""

    def setUp(self):
        super().setUp()
        self.catalog_path = self.root / "models-under-test.yaml"
        self.roles_path = self.root / "roles-under-test.yaml"
        self.patch_config("MODELS", self.catalog_path)
        self.patch_config("ROLES", self.roles_path)
        self.roles_path.write_text(ROLES_TEXT, encoding="utf-8")
        self.use_catalog()
        self.use_local()
        self.conn = store.db()

    def patch_config(self, attr: str, value) -> None:
        patcher = mock.patch.object(config, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def use_catalog(self, **kwargs) -> None:
        self.catalog_path.write_text(catalog_text(**kwargs), encoding="utf-8")

    def use_local(self, **kwargs) -> None:
        config.MODELS_LOCAL.write_text(local_text(**kwargs), encoding="utf-8")

    def numbered(self, attempt: int = 1, model_id: str = MODEL_ALFA) -> str:
        return f"попытка {attempt}/3, model={model_id}"

    def charge(self, role: str = ROLE_ON_ALFA, model_id: str = MODEL_ALFA,
               actual_usd: float = 1.0, attempt: int = 1) -> None:
        spend.charge_step(self.conn, self.TASK, role,
                          {"usd": actual_usd, "tokens": sum(TOKENS.values()),
                           "tokens_by_type": dict(TOKENS)},
                          self.numbered(attempt, model_id))

    def tariff_rows(self, model_id: str = MODEL_ALFA) -> list:
        return self.conn.execute(
            "SELECT * FROM model_tariffs WHERE model=? ORDER BY id",
            (model_id,)).fetchall()


class ResolveModelTest(_TariffSandbox):
    """Требование 1: действующий тариф разрешается и по идентификатору
    модели, не только по цепочке роли."""

    def test_catalog_price_is_the_effective_tariff_without_an_override(self):
        """Ловит мутацию: `resolve_model` отдаёт тариф первой попавшейся
        модели (например, модели яруса `strong`) вместо запрошенной —
        шаги обеих моделей считались бы по одной цене, и разрез по
        моделям, ради которого тариф и переехал на модель, исчез бы."""
        effective = models.resolve_model(MODEL_BETA)

        self.assertEqual(effective.model, MODEL_BETA)
        self.assertEqual(tuple(effective.tariff), PRICES[MODEL_BETA])
        self.assertEqual(effective.calibrated_at, CATALOG_PRICE_DATE)
        self.assertEqual(effective.tariff_source,
                         models.TARIFF_SOURCE_CATALOG)

    def test_override_of_the_local_layer_wins_with_its_own_date(self):
        """Ловит мутацию: `resolve_model` читает только каталог и не
        смотрит в локальный слой — собственный тариф Оператора (прокси,
        скидка, свой счёт) не влиял бы на разбор журнала, и прошлые шаги
        считались бы по прейскуранту, по которому их не считали."""
        self.use_local(overrides={MODEL_ALFA: (1.0, 2.0, 3.0, 4.0)})

        effective = models.resolve_model(MODEL_ALFA)

        self.assertEqual(tuple(effective.tariff), (1.0, 2.0, 3.0, 4.0))
        self.assertEqual(effective.calibrated_at, OVERRIDE_CALIBRATED_AT)
        self.assertEqual(effective.source, OVERRIDE_SOURCE)
        self.assertEqual(effective.tariff_source,
                         models.TARIFF_SOURCE_OVERRIDE)

    def test_model_outside_the_catalog_is_a_named_refusal(self):
        """Ловит мутацию: модель вне каталога отдаёт пустой тариф или
        `None` — учёт считал бы шаг по нулю вместо того, чтобы признать
        цену неизвестной (тот же класс, что и молчаливый дефолт CLI)."""
        with self.assertRaises(models.ModelNotInCatalogError):
            models.resolve_model("model-which-is-not-in-the-catalog")

        self.assertIsNone(spend.model_tariff(
            "model-which-is-not-in-the-catalog"))


class UnresolvableTariffDoesNotBreakAccountingTest(_TariffSandbox):
    """Требование 9: отказ разрешения тарифа не роняет учёт шага."""

    def test_incomplete_price_set_is_a_named_refusal_and_degrades_to_none(self):
        """Неполный прейскурант — именованный отказ разбора каталога, а
        расчёт стоимости на нём деградирует в `None`, не в исключение.

        Ловит мутацию: расчёт берёт недостающую цену нулём (`get(kind,
        0)`) — вид токена тарифицировался бы бесплатно, и частичная
        стоимость занижалась бы молча; обратная мутация — исключение
        наружу из `partial_cost_usd` — роняла бы учёт таймаута шага
        вместе со сверкой."""
        self.use_catalog(skip_kind="cache_read")

        with self.assertRaises(models.IncompletePriceError):
            models.load_catalog()

        self.assertIsNone(spend.partial_cost_usd(ROLE_ON_ALFA, TOKENS))
        self.assertIsNone(spend.rate_calibrated_at(ROLE_ON_ALFA))

    def test_step_with_an_unresolvable_tariff_is_still_charged(self):
        """Шаг с нечитаемым каталогом всё равно попадает в `spent_usd`, а
        строка KNOWN пишется без даты тарифа и коэффициента.

        Ловит мутацию: неразрешимый тариф поднимает исключение из
        `charge_step` — деньги шага утекли бы мимо бюджета целиком, как в
        инциденте с недоучётом PARTIAL."""
        self.catalog_path.write_text("providers:\n  - claude\n",
                                     encoding="utf-8")

        self.charge(actual_usd=2.5)

        row = self.conn.execute("SELECT * FROM tasks WHERE id=?",
                                (self.TASK,)).fetchone()
        self.assertAlmostEqual(row["spent_usd"], 2.5, places=6)
        detail = [r["detail"] for r in store.task_steps(self.conn, self.TASK)
                  if r["action"] == spend.KNOWN_COST_JOURNAL_ACTION][-1]
        self.assertNotIn("тариф модели с", detail)


class TariffHistoryTest(_TariffSandbox):
    """Требования 5-6: история тарифов пополняется ровно при смене
    тарифа."""

    def test_row_carries_the_model_four_prices_date_and_source(self):
        """Ловит мутацию: строка истории пишется без цен (или с ценами,
        сложенными в одну колонку) — пересчитать прошлый шаг по
        действовавшей цене снова нечем, ради чего таблица и заведена."""
        self.charge()

        row = self.tariff_rows()[0]

        self.assertEqual(row["model"], MODEL_ALFA)
        self.assertEqual(
            (row["input_usd_per_mtok"], row["output_usd_per_mtok"],
             row["cache_write_usd_per_mtok"], row["cache_read_usd_per_mtok"]),
            PRICES[MODEL_ALFA])
        self.assertEqual(row["valid_from"], CATALOG_PRICE_DATE)
        self.assertEqual(row["source"], str(self.catalog_path))

    def test_same_tariff_of_another_role_adds_no_second_row(self):
        """Две роли одного яруса разрешают ОДИН тариф — запись остаётся
        одна.

        Ловит мутацию: история ключуется парой «роль, модель» (или
        пишется на каждое разрешение) — таблица пухла бы строкой на шаг и
        перестала быть историей ТАРИФОВ."""
        self.charge(role=ROLE_ON_ALFA, attempt=1)
        self.charge(role="reviewer", attempt=2)

        self.assertEqual(len(self.tariff_rows()), 1)

    def test_only_the_date_changed_is_still_a_new_tariff(self):
        """Пересверка тех же цен с новой датой — новая запись истории.

        Ловит мутацию: сравнение идёт только по ценам — дата, с которой
        считается сверка расхождения, менялась бы, не оставляя следа, и
        ответить «с какого числа действует эта цена» стало бы нечем."""
        self.charge()
        newer = (date.today() - timedelta(days=1)).isoformat()
        self.use_catalog(price_date=newer)

        self.charge(attempt=2)

        rows = self.tariff_rows()
        self.assertEqual([row["valid_from"] for row in rows],
                         [CATALOG_PRICE_DATE, newer])

    def test_record_returns_whether_it_wrote_a_row(self):
        """`store.record_model_tariff` отвечает, писала ли она строку.

        Ловит мутацию: функция всегда возвращает `True` (или `None`) —
        вызывающий код и тесты перестают отличать «тариф сменился» от
        «тариф тот же», а сама вставка при этом может идти каждый раз."""
        first = store.record_model_tariff(self.conn, MODEL_BETA,
                                          PRICES[MODEL_BETA], "2026-09-20",
                                          "прейскурант")
        again = store.record_model_tariff(self.conn, MODEL_BETA,
                                          PRICES[MODEL_BETA], "2026-09-20",
                                          "прейскурант")
        changed = store.record_model_tariff(self.conn, MODEL_BETA,
                                            (1.0, 2.0, 3.0, 4.0),
                                            "2026-09-20", "прейскурант")

        self.assertIs(first, True)
        self.assertIs(again, False)
        self.assertIs(changed, True)
        self.assertEqual(len(self.tariff_rows(MODEL_BETA)), 2)

    def test_partial_step_records_the_tariff_too(self):
        """Шаг без финального события потока считается ПО ТАРИФУ — тариф,
        по которому он посчитан, обязан попасть в историю.

        Ловит мутацию: запись истории сделана только в ветке KNOWN —
        пульт, у которого шаг оборвался на первом же прогоне новой
        модели, посчитал бы его по цене, следа которой в истории нет."""
        spend.charge_missing_result(
            self.conn, self.TASK, ROLE_ON_ALFA, self.numbered(),
            "таймаут шага", partial_tokens=dict(TOKENS), saw_usage_event=True)

        self.assertEqual(len(self.tariff_rows()), 1)


class DoctorTariffChecksTest(_TariffSandbox):
    """Требование 8: две проверки `doctor` — свежесть тарифа и его
    давность относительно смены модели у роли."""

    def test_fresh_tariff_is_ok_and_names_the_models(self):
        """Ловит мутацию: проверка красная (жёлтая) на свежем
        прейскуранте — Оператор перестаёт читать её строки, и настоящая
        протухшая цена тонет в шуме."""
        check = doctor.check_model_tariff_freshness()

        self.assertEqual(check.status, "ok", check.detail)
        self.assertIn(MODEL_ALFA, check.detail)
        self.assertIn(MODEL_BETA, check.detail)

    def test_tariff_older_than_the_horizon_warns_with_model_and_date(self):
        """Ловит мутацию: сравнение с потолком потеряно (или
        перевёрнуто) — `doctor` молчал бы о цене, которой год, и учёт
        расхода продолжал бы расходиться с фактом молча."""
        stale = (date.today()
                 - timedelta(days=config.MODEL_TARIFF_MAX_AGE_DAYS + 5)
                 ).isoformat()
        self.use_catalog(price_date=stale)

        check = doctor.check_model_tariff_freshness()

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn(MODEL_ALFA, check.detail)
        self.assertIn(stale, check.detail)

    def test_unreadable_tariff_date_warns_instead_of_crashing(self):
        """Дата тарифа, которая не читается как дата, — предупреждение, а
        не трейсбек.

        Ловит мутацию: разбор даты не обёрнут — `doctor` падал бы целиком
        на одной кривой записи каталога, унося с собой все остальные
        проверки прогона."""
        self.use_catalog(price_date="позавчера")

        check = doctor.check_model_tariff_freshness()

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn("позавчера", check.detail)

    def test_no_foreign_model_steps_is_ok(self):
        """Ловит мутацию: проверка предупреждает о любой строке KNOWN, не
        сверяя модель строки с моделью роли, — `doctor` жёлтый всегда."""
        self.charge()

        check = doctor.check_model_tariff_vs_model_change(self.conn)

        self.assertEqual(check.status, "ok", check.detail)

    def test_step_of_another_model_newer_than_the_tariff_warns(self):
        """Ловит мутацию: сравнение с датой тарифа потеряно либо
        предупреждения нет вовсе — пульт снова молча считает деньги по
        тарифу модели, на которой роль уже не ходит (инцидент
        13.09-20.09)."""
        self.charge(role=ROLE_ON_ALFA, model_id=MODEL_BETA)

        check = doctor.check_model_tariff_vs_model_change(self.conn)

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn(MODEL_BETA, check.detail)
        self.assertIn(ROLE_ON_ALFA, check.detail)

    def test_foreign_model_step_older_than_the_tariff_stays_ok(self):
        """Шаг на другой модели, записанный ДО даты действующего тарифа,
        предупреждения не даёт: тариф уже пересверен после той смены.

        Ловит мутацию: проверка смотрит на сам факт чужой модели в
        журнале когда-либо — предупреждение висело бы вечно после любой
        смены модели, даже когда цена давно пересверена, и Оператор
        перестал бы на него реагировать."""
        self.charge(role=ROLE_ON_ALFA, model_id=MODEL_BETA)
        older = (date.fromisoformat(CATALOG_PRICE_DATE)
                 - timedelta(days=1)).isoformat()
        self.conn.execute("UPDATE steps SET ts=? WHERE action=?",
                          (f"{older} 12:00:00Z",
                           spend.KNOWN_COST_JOURNAL_ACTION))
        self.conn.commit()

        check = doctor.check_model_tariff_vs_model_change(self.conn)

        self.assertEqual(check.status, "ok", check.detail)

    def test_unlabelled_steps_do_not_warn(self):
        """Строка без опознаваемой модели («дефолт CLI», формат до 19.09)
        в сверку не входит.

        Ловит мутацию: строка без `model=` считается шагом чужой модели —
        любой пульт с журналом старше 19.09 получал бы вечное
        предупреждение, не связанное ни с какой сменой модели."""
        spend.charge_step(self.conn, self.TASK, ROLE_ON_ALFA,
                          {"usd": 1.0, "tokens": sum(TOKENS.values()),
                           "tokens_by_type": dict(TOKENS)},
                          "попытка 1/3, model=дефолт CLI")

        check = doctor.check_model_tariff_vs_model_change(self.conn)

        self.assertEqual(check.status, "ok", check.detail)

    def test_both_checks_are_wired_into_all_checks(self):
        """Ловит мутацию: проверки реализованы, но забыты в
        `doctor.all_checks` — Оператору они не видны вовсе, и обе
        стерегут пустоту."""
        wired = inspect.getsource(doctor.all_checks)

        self.assertIn("check_model_tariff_freshness", wired)
        self.assertIn("check_model_tariff_vs_model_change", wired)


class CatalogIsAProtectedPathTest(unittest.TestCase):
    """Требование 12: `models.yaml` — защищённый путь."""

    def test_models_yaml_is_in_protected_paths(self):
        """Ловит мутацию: путь выпал из списка при следующей правке —
        роль конвейера снова смогла бы поменять модель яруса или
        прейскурант своей веткой, минуя приложение Оператора."""
        self.assertIn("models.yaml", config.PROTECTED_PATHS)


if __name__ == "__main__":
    unittest.main()
