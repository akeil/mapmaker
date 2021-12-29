import unittest
from unittest import TestCase


from mapmaker import dms, decimal


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
