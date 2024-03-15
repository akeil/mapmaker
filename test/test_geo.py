from unittest import TestCase

from mapmaker.geo import BBox
from mapmaker.geo import distance
from mapmaker.geo import dms, decimal


class TestConvert(TestCase):

    def test_dms(self):
        self.assertEqual(dms(0.0), (0, 0, 0))
        self.assertEqual(dms(10.0), (10, 0, 0))
        self.assertEqual(dms(10.5), (10, 30, 0))
        self.assertEqual(dms(10.75), (10, 45, 0))

    def test_roundtrip(self):
        v = 12.22335
        d, m, s = dms(v)
        self.assertEqual(decimal(d=d, m=m, s=s), v)


class TestBBox(TestCase):

    def test_validation(self):
        self.assertRaises(ValueError, BBox,
                          minlat=-90.1,
                          maxlat=20.0,
                          minlon=30.0,
                          maxlon=40.0)
        self.assertRaises(ValueError, BBox,
                          minlat=-10.0,
                          maxlat=90.1,
                          minlon=30.0,
                          maxlon=40.0)
        self.assertRaises(ValueError, BBox,
                          minlat=-10.0,
                          maxlat=20.0,
                          minlon=-180.1,
                          maxlon=40.0)
        self.assertRaises(ValueError, BBox,
                          minlat=10.0,
                          maxlat=20.0,
                          minlon=30.0,
                          maxlon=180.1)

        # valid min/max
        BBox(minlat=-90, maxlat=90, minlon=-180, maxlon=180)
        BBox()  # no args uses min/max values
        # ... but None is not allowed
        self.assertRaises(Exception, BBox, None, None, None, None)
        self.assertRaises(Exception, BBox, 'a', 'b', 'c', 'd')

    def test_equals(self):
        a = BBox(minlat=10.0, maxlat=20.0, minlon=30.0, maxlon=40.0)
        b = BBox(minlat=10.0, maxlat=20.0, minlon=30.0, maxlon=40.0)
        self.assertEqual(a, b)

        c = BBox(minlat=10.0, maxlat=20.0, minlon=30.0, maxlon=99.0)
        self.assertNotEqual(a, c)
        self.assertNotEqual(b, c)

    def test_constrained(self):
        box = BBox(minlat=10.0, maxlat=20.0, minlon=30.0, maxlon=40.0)

        same = box.constrained()
        self.assertEqual(box, same)

        different = box.constrained(minlat=12.0,
                                    maxlat=18.0,
                                    minlon=32.0,
                                    maxlon=38.0)
        self.assertNotEqual(box, different)
        self.assertEqual(different, BBox(minlat=12.0,
                                         maxlat=18.0,
                                         minlon=32.0,
                                         maxlon=38.0))

    def test_from_radius_validation(self):
        # lat/lon can be value within min/max
        # radius must be positive
        # for any valid params, we gat a BBox where
        # ...maxlat > minlat
        # ...maxlon > minlon
        self.assertRaises(ValueError, BBox.from_radius, 91, 181, 10)
        self.assertRaises(ValueError, BBox.from_radius, 10, 10, -10)
        self.assertRaises(ValueError, BBox.from_radius, 10, 10, 0)

        # valid
        BBox.from_radius(10, 10, 10)
        BBox.from_radius(10, 10, 0.1)

    def test_padded_validation(self):
        # box cannot be padded to exceed max/min
        largest = BBox(minlat=-90, maxlat=90, minlon=-180, maxlon=180)
        self.assertRaises(ValueError, largest.padded, 1)

    def test_aspect_validation(self):
        # box cannot be padded to exceed max/min
        largest = BBox(minlat=-90, maxlat=90, minlon=-180, maxlon=180)
        self.assertRaises(ValueError, largest.with_aspect, 2)
        self.assertRaises(ValueError, largest.with_aspect, 0.5)

    def test_aspect_unexpected(self):
        box = BBox(minlat=-10, maxlat=10, minlon=-10, maxlon=10)
        # must not be negative
        self.assertRaises(ValueError, box.with_aspect, -2)
        # or zero
        self.assertRaises(ValueError, box.with_aspect, 0)

    def test_padded(self):
        box0 = BBox(minlat=-10, maxlat=10, minlon=-10, maxlon=10)
        box1 = box0.padded(1)
        self.assertNotEqual(box0, box1)

        # the padded box fully contains the originial one
        # thus, combining both yields a box equal to the larger one
        self.assertEqual(box1, box1.combine(box0))
        # ... and constraining to the smaller one yields the smaller box
        self.assertEqual(box0, box1.constrained(minlat=box0.minlat,
                                                maxlat=box0.maxlat,
                                                minlon=box0.minlon,
                                                maxlon=box0.maxlon))


class TestDistance(TestCase):

    def test_no_distance_between_identical_points(self):
        # should hold True for any two points with identical coords
        lat = 10.0
        lon = 10.0
        self.assertEqual(distance(lat, lon, lat, lon), 0)

        # distance() can be calculated for any two valid points
        # its always >= 0
        # when points are not identical, it is always > 0
