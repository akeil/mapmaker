from unittest import TestCase

from mapmaker.geo import BBox
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
