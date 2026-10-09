"""Independent numerical checks for statewide interval propagation."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_data


class ModelScalingTest(unittest.TestCase):
    def test_constant_and_nonfinite_outcomes_are_not_models(self):
        x = [0, 20, 40, 60, 80, 100]
        for y in [[50]*6, [0]*6, [10, 20, np.nan, 40, 50, 60],
                  [10, 20, 30, np.inf, 50, 60]]:
            with self.subTest(outcomes=y), self.assertRaises(ValueError):
                prepare_data.fit_model(x, y, [0]*6)

    def test_perfect_linear_fit_has_no_studentization_scale(self):
        x = np.array([0, 20, 40, 60, 80, 100.])
        y = 100-x
        X = np.column_stack([np.ones(len(x)), x])
        error = y-X@np.linalg.lstsq(X, y, rcond=None)[0]
        self.assertLess(np.linalg.norm(error), 1e-12)
        with self.assertRaisesRegex(ValueError, 'Perfect or numerically degenerate'):
            prepare_data.fit_model(x, y, np.zeros(len(x)))

    def test_deleting_only_distinct_income_makes_design_singular(self):
        x = np.array([30, 30, 30, 30, 80.])
        X = np.column_stack([np.ones(len(x)), x])
        self.assertEqual(np.linalg.matrix_rank(X), 2)
        self.assertEqual(np.linalg.matrix_rank(X[:-1]), 1)
        with self.assertRaisesRegex(ValueError, 'Deleting a school'):
            prepare_data.fit_model(x, [5, 11, 17, 23, 29], np.zeros(len(x)))

    def test_deleted_perfect_fit_is_undefined_even_with_nonzero_full_error(self):
        x = np.array([0, 10, 20, 30, 40, 50.])
        y = 100-x
        y[-1] = 99
        X = np.column_stack([np.ones(len(x)), x])
        full_error = y-X@np.linalg.lstsq(X, y, rcond=None)[0]
        deleted_error = y[:-1]-X[:-1]@np.linalg.lstsq(X[:-1], y[:-1], rcond=None)[0]
        self.assertGreater(full_error@full_error, 1)
        self.assertLess(deleted_error@deleted_error, 1e-22)
        with self.assertRaisesRegex(ValueError, 'Deleted-school residual variance'):
            prepare_data.fit_model(x, y, np.zeros(len(x)))

    def test_small_positive_deleted_variance_uses_real_scale_without_floor(self):
        x = np.arange(8, dtype=float)
        y = 1e-4 + 1e-5*x + 1e-9*np.array([0, 2, -1, 4, 2, -3, 1, -2])
        _, results = prepare_data.fit_model(x, y, np.zeros(len(x)))
        X = np.column_stack([np.ones(len(x)), x])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        for i, result in enumerate(results):
            keep = np.arange(len(x)) != i
            deleted_beta = np.linalg.lstsq(X[keep], y[keep], rcond=None)[0]
            error = y[keep]-X[keep]@deleted_beta
            scale = error@error/(len(x)-3)
            self.assertGreater(scale, 0)
            self.assertLess(scale, 1e-12)
            leverage = X[i]@np.linalg.inv(X.T@X)@X[i]
            external = (y[i]-X[i]@beta)/np.sqrt(scale*(1-leverage))
            self.assertAlmostEqual(result['studentized'], external, places=9)

    def test_history_explains_undefined_model_truthfully(self):
        assessments, incomes = [], []
        for i in range(6):
            incomes.append(dict(school_id=str(i), year='2025', percentage=20*i,
                                enrollment=100, low_income=None))
            assessments.append(dict(school_id=str(i), year='2025', level='ES',
                assessment='Native point total', subject='math', proficiency=50, tested=None))
        records, models = prepare_data.build_history(pl.DataFrame(assessments), pl.DataFrame(incomes),
            point_only_assessments=['Native point total'])
        self.assertFalse(models)
        for record in records:
            self.assertNotIn('math', record['subjects'])
            self.assertIn('Outcome variation', record['exclusions']['math'])
            self.assertNotIn('Insufficient schools', record['exclusions']['math'])

    def test_history_preserves_existing_insufficient_population_reason(self):
        for x in [[10, 20, 30], [10]*6]:
            with self.subTest(incomes=x):
                incomes = pl.DataFrame([dict(school_id=str(i), year='2025', percentage=v,
                    enrollment=100, low_income=None) for i, v in enumerate(x)])
                assessments = pl.DataFrame([dict(school_id=str(i), year='2025', level='ES',
                    assessment='Native point total', subject='math', proficiency=30+3*i,
                    tested=None) for i in range(len(x))])
                records, models = prepare_data.build_history(assessments, incomes,
                    point_only_assessments=['Native point total'])
                self.assertFalse(models)
                for record in records:
                    self.assertEqual(record['exclusions']['math'],
                        'Insufficient schools or income variation for regression')

    def test_linear_propagation_matches_dense_hat_matrix(self):
        rng = np.random.default_rng(904)
        x = rng.uniform(0, 100, 83)
        y = 76 - .48*x + rng.normal(0, 6, len(x))
        variance = rng.uniform(0, 70, len(x))
        variance[::7] = 0
        X = np.column_stack([np.ones(len(x)), x])
        inverse = np.linalg.inv(X.T @ X)
        hat = X @ inverse @ X.T
        errors = y - hat @ y
        leverage = np.diag(hat)
        deleted_scale = (errors @ errors - errors**2/(1-leverage)) / (len(x)-3)
        denominator = np.sqrt(deleted_scale*(1-leverage))
        expected_se = np.sqrt(((np.eye(len(x))-hat)**2) @ variance) / denominator

        with patch.object(prepare_data, 'DENSE_INTERVAL_MAX_SCHOOLS', 0):
            _, results = prepare_data.fit_model(x, y, variance)
        actual_se = np.array([(r['high']-r['low'])/(2*1.96) for r in results])
        np.testing.assert_allclose(actual_se, expected_se, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose([r['studentized'] for r in results], errors/denominator,
                                   rtol=1e-12, atol=1e-12)

    def test_large_cohort_avoids_dense_matrices_and_matches_individual_hat_rows(self):
        rng = np.random.default_rng(502)
        n = 12000
        x = rng.uniform(0, 100, n)
        y = 74 - .4*x + rng.normal(0, 7, n)
        variance = rng.uniform(.05, 45, n)
        with patch.object(prepare_data.np, 'eye', side_effect=AssertionError('Dense allocation')):
            model, results = prepare_data.fit_model(x, y, variance)
        self.assertEqual(model['n'], n)
        self.assertTrue(np.isfinite([r[k] for r in results for k in ['low', 'high', 'studentized']]).all())

        X = np.column_stack([np.ones(n), x])
        inverse = np.linalg.inv(X.T @ X)
        # Compute selected complete hat rows as an independent O(n) oracle.
        for i in [0, 141, 6000, n-1]:
            hat_row = X[i] @ inverse @ X.T
            remaining = -hat_row
            remaining[i] += 1
            expected_variance = np.dot(remaining**2, variance)
            expected_errors = y - X @ (inverse @ X.T @ y)
            deleted_scale = (expected_errors @ expected_errors - expected_errors[i]**2/(1-hat_row[i]))/(n-3)
            denominator = np.sqrt(deleted_scale*(1-hat_row[i]))
            expected_se = np.sqrt(expected_variance)/denominator
            actual_se = (results[i]['high']-results[i]['low'])/(2*1.96)
            self.assertAlmostEqual(actual_se, expected_se, places=12)

    def test_linear_path_keeps_regression_and_residuals_unchanged(self):
        rng = np.random.default_rng(128)
        x = rng.uniform(0, 100, 42)
        y = rng.uniform(0, 100, len(x))
        variance = rng.uniform(.1, 50, len(x))
        dense_model, dense = prepare_data.fit_model(x, y, variance)
        with patch.object(prepare_data, 'DENSE_INTERVAL_MAX_SCHOOLS', 0):
            linear_model, linear = prepare_data.fit_model(x, y, variance)
        self.assertEqual(linear_model, dense_model)
        for actual, expected in zip(linear, dense):
            for field in ['actual', 'predicted', 'residual', 'studentized', 'leverage']:
                self.assertEqual(actual[field], expected[field])

    def test_linear_path_preserves_zero_sampling_variance(self):
        x = np.array([3, 8, 20, 35, 55, 65, 88, 96.])
        y = np.array([75, 61, 66, 48, 21, 32, 18, 4.])
        with patch.object(prepare_data, 'DENSE_INTERVAL_MAX_SCHOOLS', 0):
            _, results = prepare_data.fit_model(x, y, np.zeros(len(x)))
        for result in results:
            self.assertEqual(result['low'], result['studentized'])
            self.assertEqual(result['high'], result['studentized'])


if __name__ == '__main__':
    unittest.main()
