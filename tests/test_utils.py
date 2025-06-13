import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest
from battle_royale_sim.utils import point_in_poly, distance, random_position


def test_point_inside_triangle():
    triangle = [(0, 0), (2, 0), (1, 2)]
    assert point_in_poly((1, 1), triangle) is True


def test_point_outside_triangle():
    triangle = [(0, 0), (2, 0), (1, 2)]
    assert point_in_poly((2, 2), triangle) is False


def test_polygon_with_horizontal_edges():
    rectangle = [(0, 0), (2, 0), (2, 2), (0, 2)]  # top and bottom edges horizontal
    # Points well inside and outside should be handled without error
    assert point_in_poly((1, 1), rectangle) is True
    assert point_in_poly((3, 1), rectangle) is False


def test_distance_same_point():
    assert distance((0, 0), (0, 0)) == 0


def test_distance_3_4_5_triangle():
    assert distance((0, 0), (3, 4)) == pytest.approx(5)


def test_random_position_within_bounds():
    width, height = 10, 20
    for _ in range(100):
        x, y = random_position(width, height)
        assert 0 <= x <= width
        assert 0 <= y <= height

