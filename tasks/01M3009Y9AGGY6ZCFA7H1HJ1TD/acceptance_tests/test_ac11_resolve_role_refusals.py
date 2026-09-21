"""AC-11: `models.resolve_role(role)` отказывает именованно на каждом
звене по отдельности — ярус не назван в `tiers:`, модель яруса не найдена
в каталоге, модель `experimental` не разрешена явно; ни один случай не
даёт запустить агента.

Красен до реализации: фикстура падает на отсутствующем `models.yaml`
(каталог создаёт эта задача), а звеньев, на которых отказывает
fail-closed, нет ни одного — `models.resolve_role` не существует.
"""
import unittest

import _models
from _sandbox import TierStepSandbox, CatalogSandbox

ROLE = "developer"
MISSING_MODEL = "claude-modeli-kotoroy-net-v-kataloge"


def _tiers_without_strong() -> dict:
    return {"standard": _models.SONNET, "cheap": _models.SONNET}


def _tiers_to(model: str) -> dict:
    return {tier: model for tier in _models.TIERS}


class ResolveRefusalsTest(CatalogSandbox):
    """Каталог и локальный слой во временном корне; роль — на ярусе
    `strong`."""

    def setUp(self):
        super().setUp()
        self.write_catalog()
        self.set_roles_tiers({ROLE: "strong"})

    def refusal(self, local_text: str, catalog_text: str = None) -> Exception:
        if catalog_text is not None:
            self.write_catalog(catalog_text)
        self.write_local(local_text)
        try:
            resolved = _models.resolve(ROLE)
        except Exception as exc:  # noqa: BLE001 — предмет проверки
            return exc
        self.fail(f"разрешение не отказало, вернуло: {resolved!r}")

    def assert_named(self, exc: Exception, *named: str) -> None:
        self.assertNotEqual(
            type(exc).__module__, "builtins",
            f"отказ не именован — встроенное исключение "
            f"{type(exc).__name__}: {exc}")
        for name in named:
            self.assertIn(name, str(exc))

    def test_ac11_tier_missing_in_the_local_layer_is_refused_by_name(self):
        """Ярус роли не назван в `tiers:` локального слоя — именованный
        отказ, называющий ярус.

        Ловит мутацию: ненайденный ярус подставляет первую попавшуюся
        модель из `tiers:` (или дефолт `claude-opus-5`) — Оператор,
        забывший дописать ярус в локальный слой, получает шаг на чужой
        модели вместо отказа, и fail-closed цепочки перестаёт быть
        fail-closed.
        """
        exc = self.refusal(_models.local_texts(_tiers_without_strong())[0])

        self.assert_named(exc, "strong")

    def test_ac11_model_missing_in_the_catalog_is_refused_by_name(self):
        """Модель яруса не найдена в каталоге — именованный отказ,
        называющий модель.

        Ловит мутацию: модель из локального слоя берётся как есть, без
        сверки с каталогом — опечатка в идентификаторе уезжает флагом
        `--model` в CLI, и шаг падает «API Error 400» за деньги вместо
        отказа до старта.
        """
        exc = self.refusal(_models.local_texts(_tiers_to(MISSING_MODEL))[0])

        self.assert_named(exc, MISSING_MODEL)

    def test_ac11_experimental_model_without_explicit_allowance_is_refused(self):
        """Модель со статусом `experimental`, не разрешённая локальным
        слоем явно, — именованный отказ, называющий модель.

        Ловит мутацию: статус читается, но на разрешение не влияет
        (`experimental` идёт наравне с `supported`) — экспериментальная
        модель уходит в работу без явного решения Оператора, ради
        которого статус в каталоге и заведён.
        """
        exc = self.refusal(_models.local_texts(_tiers_to(_models.FABLE))[0],
                           _models.with_experimental(_models.FABLE))

        self.assert_named(exc, _models.FABLE)

    def test_ac11_three_links_are_told_apart_by_the_refusal_text(self):
        """Три отказа различимы по тексту — каждый называет своё звено.

        Ловит мутацию: все звенья свёрнуты в один текст «модель роли не
        разрешена» — Оператор не видит, где рвётся цепочка: в локальном
        слое, в каталоге или в статусе модели.
        """
        texts = [
            str(self.refusal(_models.local_texts(_tiers_without_strong())[0])),
            str(self.refusal(_models.local_texts(_tiers_to(MISSING_MODEL))[0])),
            str(self.refusal(_models.local_texts(_tiers_to(_models.FABLE))[0],
                             _models.with_experimental(_models.FABLE))),
        ]

        self.assertEqual(len(set(texts)), 3,
                         "тексты отказов не различают звено цепочки:\n"
                         + "\n".join(texts))


class NoAgentStartsOnBrokenChainTest(TierStepSandbox):
    """Шаг роли на каждом из трёх разорванных звеньев."""

    def setUp(self):
        super().setUp()
        self.set_cli_version("9.9.9")

    def test_ac11_none_of_the_broken_links_starts_the_agent(self):
        """Ни ярус без модели, ни модель вне каталога, ни неразрешённая
        `experimental` не доводят шаг до запуска агента.

        Ловит мутацию: отказ разрешения ловится в `runner` и
        деградирует к запуску без `--model` (дефолт CLI) — шаг всё равно
        стартует, просто на модели, которую пульт не выбирал; инвариант
        «агент не стартует без явного `--model`» держится только на
        отказе цепочки.
        """
        scenarios = {
            "ярус не назван в tiers:": (
                None, _models.local_texts(_tiers_without_strong())[0]),
            "модель вне каталога": (
                None, _models.local_texts(_tiers_to(MISSING_MODEL))[0]),
            "experimental без разрешения": (
                _models.with_experimental(_models.FABLE),
                _models.local_texts(_tiers_to(_models.FABLE))[0]),
        }
        for name, (catalog_text, local_text) in scenarios.items():
            with self.subTest(scenario=name):
                self.seed_chain(tier="strong", catalog_text=catalog_text,
                                local_text=local_text)

                self.run_step()

                self.spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
