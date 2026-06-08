import math

import pytest

from gpmi.core.aggregation import geometric_mean, median


def test_median_odd():
    assert median([3, 1, 2]) == 2


def test_median_even():
    assert median([1, 2, 3, 4]) == 2.5


def test_geometric_mean_known():
    # geometric mean of 1, 2, 4 = (8)^(1/3) = 2
    assert math.isclose(geometric_mean([1, 2, 4]), 2.0, rel_tol=1e-12)


def test_geometric_mean_all_ones():
    assert math.isclose(geometric_mean([1.0] * 50), 1.0, rel_tol=1e-12)


def test_geometric_mean_resists_single_spike():
    # one 5x asset barely moves a 100-pair index
    values = [1.0] * 99 + [5.0]
    result = geometric_mean(values)
    assert result < 1.02


def test_geometric_mean_rejects_nonpositive():
    with pytest.raises(ValueError):
        geometric_mean([1.0, -2.0])
    with pytest.raises(ValueError):
        geometric_mean([])
