import argparse
import unittest
from unittest import TestCase

from mapmaker import aspect
from mapmaker import _BBoxAction
from mapmaker import _parse_color
from mapmaker import _parse_coordinates
from mapmaker import _parse_margin
from mapmaker import _parse_placement


class _ParseTest(TestCase):
    parse_func = None
    places = None
    valid = []
    fail = []

    def test_should_fail(self):
        cls = self.__class__
        f = cls.parse_func
        for raw in self.fail:
            self.assertRaises(ValueError, f, raw)

    def test_valid(self):
        cls = self.__class__
        f = cls.parse_func
        for raw, expected in self.valid:
            if self.places:
                self.assertAlmostEqual(f(raw), expected, places=self.places)
            else:
                self.assertEqual(f(raw), expected, msg='%r != %r, parsed from %r' % (f(raw), expected, raw))


class TestParseCoordinates(_ParseTest):
    parse_func = _parse_coordinates
    fail = (
        '',
        'xxx',
        '12,34,56',  # too many values
        '123.45.56, 123',  # 2x decimal separator
        "47° 25'', 10°59''",  # missing "Minutes"
        '48°15°,6°7°',
        '500,456',  # bounds
        '360°, -500°',  # bounds
    )
    valid = (
        ('48°, 6°', (48, 6)),
        ('48° N, 6° E', (48, 6)),
        ('48°N, 6°E',  (48, 6)),
        ("47° 30', 10°15'",  (47.5, 10.25)),
        ("63° 4' 10.2'' N, 151° 0' 26.64'' W", (63.0695, -151.0074)),
        ("63°4'10.2''N,151°0'26.64''W", (63.0695, -151.0074)),
        ("43°21'18'', 42°26'21''", (43.355, 42.439167)),
        ('47.437,10.953', (47.437, 10.953)),
        ('47.437N,10.953E', (47.437, 10.953)),
        ('47.437 N, 10.953 E', (47.437, 10.953)),
        ('63.0695, -151.0074', (63.0695, -151.0074)),
        ('63.0695N, 151.0074W', (63.0695, -151.0074)),
    )

    # override, alomstEqual cannot compare tuples
    def test_valid(self):
        for raw, expected in self.valid:
            actual_lat, actual_lon = _parse_coordinates(raw)
            expected_lat, expected_lon = expected
            self.assertAlmostEqual(actual_lat, expected_lat, places=5)
            self.assertAlmostEqual(actual_lon, expected_lon, places=5)


class TestParseColor(_ParseTest):

    parse_func = _parse_color
    fail = (
        None,
        '',
        '   ',
        '\n',
        '0,0,a0',
        '0xff,0xff,0xff',
        '1,2',
        '10',
        '10,20,30,40,50',
        '255 255 255',
        '255;255;255',
        '300,50,50',
        '256,50,50',
        '-1,50,50',
        '1.5,22,33',
        '#00',
        '#00ff',
        '#foobar',
        '#0010203040',
        '#'
    )
    valid = (
        ('0,0,0', (0, 0, 0, 255)),
        ('255,255,255', (255, 255, 255, 255)),
        ('10,20,30', (10, 20, 30, 255)),
        ('10,20,30,255', (10, 20, 30, 255)),
        ('10,20,30,128', (10, 20, 30, 128)),
        ('10,20,30,0', (10, 20, 30, 0)),
        ('010,020,030', (10, 20, 30, 255)),
        ('#5090aa', (80, 144, 170, 255)),
        ('#5090aaff', (80, 144, 170, 255)),
        ('#5090aabb', (80, 144, 170, 187)),
    )


# TODO: not needed?
class TestParseMargin(_ParseTest):
    parse_func = _parse_margin
    fail = (
        None,
        '',
        '  ',
        '\n',
        'xyz',
        'N*',
        'x',
        '10px,10px',
        '10px,10px,10px',
        '10px,10px,10px,10px,10px',
        '10px,10px,10px,-5px',
        '-1px',
        '5.5px',
        '10 px',
        '10cm',
    )
    valid = (
        ('2px', (2, 2, 2, 2)),
        ('0px,0px,0px,0px', (0, 0, 0, 0)),
        ('1px,2px,3px,4px', (1, 2, 3, 4)),
        ('2PX', (2, 2, 2, 2)),
    )
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
            self.assertRaises(ValueError, _parse_coordinates, case)


class TestParsePlacement(_ParseTest):
    parse_func = _parse_placement
    fail = (
        None,
        '',
        '  ',
        '\n',
        'xyz',
        '-N-',
        'xNEx',
        'N*',
        'x',
    )
    valid = (
        ('SSW', 'SSW'),
        ('n', 'N'),
        (' ne ', 'NE'),
    )


class TestParseAspect(_ParseTest):
    parse_func = aspect
    places = 4
    fail = (
        '',
        '123',
        'abc:def',
        '4:3:4',
        '4-3',
        '4/3',
        '-16:9',
        '0:2',
        '2:0',
    )
    valid = (
        ('4:2', 2.0),
        ('16:9', 1.77777),
        ('2:3', 0.66666),
    )


class TestParseBBox(TestCase):

    def test_valid(self):
        cases = (
            ['47.1,6.5', '47.2,6.6'],
            ['47.1, 6.5', '4km'],
            ['47.1,6.5', '4'],
            ["43°21'18'', 42°26'21''", '4km'],
        )

        action = _BBoxAction(None, 'bbox')
        for values in cases:
            ns = argparse.Namespace()
            action(None, ns, values)
            self.assertIsNotNone(ns.bbox)

    def test_should_fail(self):
        cases = (
            ['', ''],
            ['47.1,6.5', ''],
            ['47.1,6.5', '4 miles'],
            ['47.1,6.5', 'foo'],
            ['123', '4km'],
            ['abc', '4km'],
        )
        action = _BBoxAction(None, 'bbox')
        for values in cases:
            ns = argparse.Namespace()
            self.assertRaises(Exception, action, None, ns, values)


if __name__ == "__main__":
    unittest.main()
