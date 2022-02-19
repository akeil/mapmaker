import argparse
import unittest
from unittest import TestCase

from mapmaker.geo import BBox
from mapmaker import parse
from mapmaker.parse import BBoxAction
from mapmaker.parse import FrameAction
from mapmaker.parse import MarginAction
from mapmaker.parse import TextAction
from mapmaker.parse import _parse_coordinates
from mapmaker.parse import _parse_placement


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
                msg = '%r != %r, parsed from %r' % (f(raw), expected, raw)
                self.assertEqual(f(raw), expected, msg=msg)


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

    parse_func = parse.color
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
    parse_func = parse.aspect
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


class _ActionTest(TestCase):

    action = None
    fail = []
    valid = []

    def test_should_fail(self):
        if not self.action:
            return

        factory = self.__class__.action
        action = factory(None, 'result')
        for values in self.fail:
            ns = argparse.Namespace()
            self.assertRaises(Exception, action, None, ns, values)

    def test_valid(self):
        if not self.action:
            return

        factory = self.__class__.action
        action = factory(None, 'result')
        for values, expected in self.valid:
            ns = argparse.Namespace()
            action(None, ns, values)
            self.assertEqual(ns.result, expected)


class TestTextAction(_ActionTest):
    action = TextAction
    fail = (
        [],
        ['', ],
        ['N', ],
        ['NW', '5'],
        ['120,120,120', '50,50,50,200'],
        ['120,120,120', '50,50,50,200', 'SW', '12'],
        ['-8', 'My', 'Title'],
    )
    valid = (
        (['My', 'Title'], (None, None, None, None, 'My Title')),
        (['NW', 'My', 'Title'], ('NW', None, None, None, 'My Title')),
        (['8', 'My', 'Title'], (None, 8, None, None, 'My Title')),
        (['120,120,120', 'My', 'Title'], (None, None, (120, 120, 120, 255), None, 'My Title')),
        (['120,120,120', '50,50,50,200', 'My', 'Title'], (None, None, (120, 120, 120, 255), (50, 50, 50, 200), 'My Title')),
        (['120,120,120', '50,50,50,200', 'SW', '12', 'My', 'Title'], ('SW', 12, (120, 120, 120, 255), (50, 50, 50, 200), 'My Title')),
    )


class TestFrameAction(_ActionTest):
    action = FrameAction
    fail = (
        ['', ],
        ['unrecognized', ],
        ['8', 'unrecognized'],
        ['8', '120,120,120', '220,220,220', 'solid', 'extra'],
        ['500,500,500'],
        ['-5'],
    )
    valid = (
        ([], (None, None, None, None)),
        (['8'], (8, None, None, None)),
        (['200,200,200'], (None, (200, 200, 200, 255), None, None)),
        (['coordinates'], (None, None, None, 'coordinates')),
        (['200,200,200', '220,220,220'], (None, (200, 200, 200, 255), (220, 220, 220, 255), None)),
        (['200,200,200', '220,220,220', '5', 'solid'], (5, (200, 200, 200, 255), (220, 220, 220, 255), 'solid')),
    )


class TestMarginAction(_ActionTest):
    action = MarginAction
    fail = (
        [],
        ['', ],
        ['2', '2', '2'],
        ['2', '2', '2', '2', '2'],
        ['-2', ],
        ['-2', '2', ],
        ['-2', '2', '2', '2'],
    )
    valid = (
        (['2', ], (2, 2, 2, 2)),
        (['2', '4'], (2, 4, 2, 4)),
        (['2', '4', '6', '8'], (2, 4, 6, 8)),
        (['2', '0'], (2, 0, 2, 0)),
    )


class TestParseBBox(_ActionTest):
    action = BBoxAction
    fail = (
        ['', ''],
        ['47.1,6.5', ''],
        ['47.1,6.5', '4 miles'],
        ['47.1,6.5', 'foo'],
        ['123', '4km'],
        ['abc', '4km'],
    )
    valid = (
        (['47.1,6.5', '47.2,6.6'], BBox(minlat=47.1, minlon=6.5, maxlat=47.2, maxlon=6.6)),
        (['47.1, 6.5', '4km'], BBox(minlat=47.064027135763254, minlon=6.447154758428375, maxlat=47.135972864236756, maxlon=6.552845241571626)),
        (['47.1,6.5', '4'], BBox(minlat=47.09996402713577, minlon=6.499947154750387, maxlat=47.10003597286424, maxlon=6.500052845249614)),
        (["43°21'18'', 42°26'21''", '4km'], BBox(minlat=43.31902713576325, minlon=42.38969319226943, maxlat=43.39097286423675, maxlon=42.488640141063904)),
    )


if __name__ == "__main__":
    unittest.main()
