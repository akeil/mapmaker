import unittest
from unittest import TestCase

import mapmaker


class TestParseCoordinates(TestCase):

    def test_should_fail(self):
        cases = (
            '',
            'xxx',
            '12,34,56',  # too many values
            '123.45.56, 123',  # 2x decimal separator
            "47° 25'', 10°59''",  # missing "Minutes"
            '48°15°,6°7°',
            '500,456',  # bounds
            '360°, -500°',  # bounds
        )
        for case in cases:
            self.assertRaises(ValueError, mapmaker._parse_coordinates, case)

    def test_dms(self):
        cases = {
            '48°, 6°': (48, 6),
            '48° N, 6° E': (48, 6),
            '48°N, 6°E':  (48, 6),
            "47° 30', 10°15'":  (47.5, 10.25),
            "63° 4' 10.2'' N, 151° 0' 26.64'' W": (63.0695, -151.0074),
            "63°4'10.2''N,151°0'26.64''W": (63.0695, -151.0074),
            "43°21'18'', 42°26'21''": (43.355, 42.439167),
        }
        self._do_test(cases)

    def test_decimal(self):
        cases = {
            '47.437,10.953': (47.437, 10.953),
            '47.437N,10.953E': (47.437, 10.953),
            '47.437 N, 10.953 E': (47.437, 10.953),

            '63.0695, -151.0074': (63.0695, -151.0074),
            '63.0695N, 151.0074W': (63.0695, -151.0074),
        }
        self._do_test(cases)

    def _do_test(self, cases):
        for raw, expected in cases.items():
            actual_lat, actual_lon = mapmaker._parse_coordinates(raw)
            expected_lat, expected_lon = expected
            self.assertAlmostEqual(actual_lat, expected_lat, places=5)
            self.assertAlmostEqual(actual_lon, expected_lon, places=5)


if __name__ == "__main__":
    unittest.main()
