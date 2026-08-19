#!/usr/bin/python3

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer import convert_to_human_readable, merge_dict_values
from data import StockData
from projections import DEFAULT_ASSUMPTIONS, StockProjections, derive_assumptions


class TestCalcCagrEquation(unittest.TestCase):
    def test_normal_growth(self):
        self.assertAlmostEqual(StockData.calc_cagr_equation(3, 100, 133.1), 0.10, places=5)

    def test_no_growth(self):
        self.assertAlmostEqual(StockData.calc_cagr_equation(3, 100, 100), 0.0, places=5)

    def test_decline(self):
        self.assertAlmostEqual(StockData.calc_cagr_equation(2, 100, 64), -0.20, places=5)

    def test_zero_start_raises(self):
        with self.assertRaises(ValueError):
            StockData.calc_cagr_equation(3, 0, 133.1)

    def test_zero_years_raises(self):
        with self.assertRaises(ValueError):
            StockData.calc_cagr_equation(0, 100, 133.1)

    def test_negative_base_returns_none(self):
        self.assertIsNone(StockData.calc_cagr_equation(3, -8, 8))


class TestCalcFutureValue(unittest.TestCase):
    def test_growth(self):
        self.assertAlmostEqual(StockProjections.calc_future_value(100, 10, 2), 121.0)

    def test_none_current_value(self):
        self.assertIsNone(StockProjections.calc_future_value(None, 10, 2))

    def test_none_growth_rate(self):
        self.assertIsNone(StockProjections.calc_future_value(100, None, 2))

    def test_zero_years(self):
        self.assertIsNone(StockProjections.calc_future_value(100, 10, 0))


class TestConvertToHumanReadable(unittest.TestCase):
    def test_units(self):
        self.assertEqual(convert_to_human_readable(999), "999")
        self.assertEqual(convert_to_human_readable(1000), "1K")
        self.assertEqual(convert_to_human_readable(1500), "1.5K")
        self.assertEqual(convert_to_human_readable(2_500_000), "2.5M")
        self.assertEqual(convert_to_human_readable(3_000_000_000), "3B")
        self.assertEqual(convert_to_human_readable(4_000_000_000_000), "4T")

    def test_none_passthrough(self):
        self.assertIsNone(convert_to_human_readable(None))

    def test_string_passthrough(self):
        self.assertEqual(convert_to_human_readable("N/A"), "N/A")


class TestMergeDictValues(unittest.TestCase):
    def test_shape(self):
        data = {"AAA": {"m1": 1000, "m2": None}, "BBB": {"m1": 2000, "m2": "x"}}
        self.assertEqual(merge_dict_values(data), [["m1", "1K", "2K"], ["m2", None, "x"]])

    def test_empty(self):
        self.assertEqual(merge_dict_values({}), [])


class TestStockProjections(unittest.TestCase):
    def setUp(self):
        self.summary = {
            "ttm_revenue": 1_000_000_000,
            "shares_outstanding": 100_000_000,
            "current_price": 100.0,
        }
        self.assumptions = {
            "yoy_growth_revenue": 10.0,
            "num_of_years": 1,
            "yoy_growth_share_count": 0.0,
            "estimated_pe": 20,
            "net_margin": 0.10,
        }

    def test_projection_pipeline(self):
        projections = StockProjections("TEST", self.summary, self.assumptions)
        self.assertAlmostEqual(projections.project_revenue(), 1_100_000_000)
        self.assertAlmostEqual(projections.project_net_income(), 110_000_000)
        self.assertAlmostEqual(projections.project_shares_outstanding(), 100_000_000)
        self.assertAlmostEqual(projections.project_eps(), 1.10)
        self.assertAlmostEqual(projections.calc_stock_valuation(), 22.0)
        self.assertAlmostEqual(projections.calc_stock_market_cap(), 2_200_000_000)
        self.assertAlmostEqual(projections.calc_upside_downside_potential(), -78.0)

    def test_missing_fields_return_none(self):
        projections = StockProjections("TEST", {}, self.assumptions)
        self.assertIsNone(projections.project_revenue())
        self.assertIsNone(projections.project_eps())
        self.assertIsNone(projections.calc_stock_valuation())
        self.assertIsNone(projections.calc_stock_market_cap())
        self.assertIsNone(projections.calc_upside_downside_potential())

    def test_missing_current_price_returns_none(self):
        summary = dict(self.summary)
        del summary["current_price"]
        projections = StockProjections("TEST", summary, self.assumptions)
        self.assertIsNone(projections.calc_upside_downside_potential())

    def test_default_assumptions_used(self):
        projections = StockProjections("TEST", self.summary)
        self.assertEqual(projections.user_assumptions, DEFAULT_ASSUMPTIONS)


class TestDeriveAssumptions(unittest.TestCase):
    def setUp(self):
        self.summary = {
            "cagr_revenue_3y_in%": 20.0,
            "net_margin_in%": 10.0,
            "pe_ratio": 50.0,
            "cagr_share_count_3y_in%": -5.0,
        }

    def test_derives_all_from_data(self):
        assumptions = derive_assumptions(self.summary)
        self.assertAlmostEqual(assumptions["yoy_growth_revenue"], 16.0)
        self.assertAlmostEqual(assumptions["net_margin"], 0.08)
        self.assertEqual(assumptions["estimated_pe"], DEFAULT_ASSUMPTIONS["estimated_pe"])
        self.assertAlmostEqual(assumptions["yoy_growth_share_count"], -4.0)
        self.assertEqual(assumptions["num_of_years"], DEFAULT_ASSUMPTIONS["num_of_years"])

    def test_config_overrides_derived(self):
        user = {"yoy_growth_revenue": 5.0, "net_margin": 0.15, "estimated_pe": 30}
        assumptions = derive_assumptions(self.summary, user)
        self.assertEqual(assumptions["yoy_growth_revenue"], 5.0)
        self.assertEqual(assumptions["net_margin"], 0.15)
        self.assertEqual(assumptions["estimated_pe"], 30)

    def test_falls_back_when_data_missing(self):
        assumptions = derive_assumptions({})
        self.assertEqual(assumptions["yoy_growth_revenue"], DEFAULT_ASSUMPTIONS["yoy_growth_revenue"])
        self.assertEqual(assumptions["net_margin"], DEFAULT_ASSUMPTIONS["net_margin"])
        self.assertEqual(assumptions["estimated_pe"], DEFAULT_ASSUMPTIONS["estimated_pe"])
        self.assertEqual(assumptions["yoy_growth_share_count"], DEFAULT_ASSUMPTIONS["yoy_growth_share_count"])


if __name__ == "__main__":
    unittest.main()