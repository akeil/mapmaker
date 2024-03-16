from unittest import TestCase

from mapmaker.geo import BBox
from mapmaker.geo import BRG_NORTH, BRG_EAST, BRG_SOUTH, BRG_WEST
from mapmaker.geo import destination_point
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

    def test_distance_basic(self):
        # distance() can be calculated for any two points
        # when points are not identical, it is always > 0
        lat0 = 10.0
        lon0 = 10.0
        lat1 = 11.0
        lon1 = 11.0
        self.assertGreater(distance(lat0, lon0, lat1, lon1), 0)


class TestDestinationPoint(TestCase):

    def assertValidCoordinates(self, lat, lon):
        self.assertGreater(lat, -90)
        self.assertLess(lat, 90)
        self.assertGreater(lon, -180)
        self.assertLess(lon, 180)

    def assertDifferentPoints(self, lat0, lon0, lat1, lon1):
        d_lat = abs(lat0 - lat1)
        d_lon = abs(lon0 - lon1)

        if (d_lat + d_lon) == 0:
            self.fail(('expected points to be different:'
                       ' (%s, %s) and (%s, %s)') % (lat0, lon0, lat1, lon1))

    def test_validate_distance(self):
        self.assertRaises(ValueError, destination_point, 10.0, 10.0, 90, -1)

    def test_validate_bearing(self):
        self.assertRaises(ValueError, destination_point, 10.0, 10.0, -1, 50)
        self.assertRaises(ValueError, destination_point, 10.0, 10.0, 361, 50)

    def test_distance_zero_is_same_point(self):
        lat0, lon0 = 10.0, 20.0
        # should hold true for any bearing
        lat1, lon1 = destination_point(lat0, lon0, 90, 0)
        self.assertEqual(lat0, lat1)
        self.assertEqual(lon0, lon1)

    def test_axis_longitude(self):
        # lat (lon) does not change for certain bearings
        lat0, lon0 = 10.0, 20.0
        for brg in (BRG_NORTH, BRG_SOUTH):
            lat1, lon1 = destination_point(lat0, lon0, brg, 1000)
            self.assertAlmostEqual(lon0, lon1, places=5)
            self.assertNotAlmostEqual(lat0, lat1, places=5)

    def test_axis_latitude(self):
        # lat (lon) does not change for certain bearings
        lat0, lon0 = 10.0, 20.0
        for brg in (BRG_EAST, BRG_WEST):
            lat1, lon1 = destination_point(lat0, lon0, brg, 1000)
            self.assertAlmostEqual(lat0, lat1, places=5)
            self.assertNotAlmostEqual(lon0, lon1, places=5)

    # fails, not sure if it should
    def test_wrap_east(self):
        '''Make sure that we do not produce coordinates that are out of the
        valid range for lat/lon.'''
        lat, lon = destination_point(0, 180, BRG_EAST, 100_000)
        self.assertValidCoordinates(lat, lon)

    def test_wrap_west(self):
        '''Make sure that we do not produce coordinates that are out of the
        valid range for lat/lon.'''
        lat, lon = destination_point(0, -180, BRG_WEST, 100_000)
        self.assertValidCoordinates(lat, lon)

    def test_wrap_north(self):
        '''Make sure that we do not produce coordinates that are out of the
        valid range for lat/lon.'''
        lat, lon = destination_point(90, 0, BRG_NORTH, 100_000)
        self.assertValidCoordinates(lat, lon)

    def test_wrap_south(self):
        '''Make sure that we do not produce coordinates that are out of the
        valid range for lat/lon.'''
        lat, lon = destination_point(-90, 0, BRG_SOUTH, 100_000)
        self.assertValidCoordinates(lat, lon)

    def test_distance_vs_destination(self):
        '''If we determine a ``destination_point)=`` that in a given DISTANCE,
        then the calculated ``disctance()`` to that point should be the same.
        '''
        # should hold true for any valid destination params
        lat0, lon0 = 10.0, 20.0
        d0 = 1_000
        brg = 60
        lat1, lon1 = destination_point(lat0, lon0, brg, d0)
        d1 = distance(lat0, lon0, lat1, lon1)

        self.assertAlmostEqual(d0, d1)

    def test_destination_basics(self):
        # should hold true for any valid destination params
        # with distance >0
        lat0, lon0 = 10.0, 20.0
        d0 = 1_000
        brg = 60
        lat1, lon1 = destination_point(lat0, lon0, brg, d0)

        self.assertValidCoordinates(lat1, lon1)
        self.assertDifferentPoints(lat0, lon0, lat1, lon1)
