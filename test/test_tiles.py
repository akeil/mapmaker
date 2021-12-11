import unittest
from unittest import TestCase

from mapmaker import tile_coordinates


class TestTiles(TestCase):

    def test_tile_coords(self):
        nw = (63.0695, -151.0074)
        ne = (43.355, 42.439167)
        sw = (-32.653197, -70.0112)
        se = (-4.078889, 137.158333)

        cases = {
            # zoom = 0, single tile
            0: {
                nw: (0,0),
                ne: (0,0),
                sw: (0,0),
                se: (0,0),
            },
            # zoom 1 = 4 tiles
            1: {
                nw: (0,0),
                ne: (1,0),
                sw: (0,1),
                se: (1,1),
            },
        }
        for zoom, pairs in cases.items():
            for loc, expected in pairs.items():
                lat, lon = loc
                x,y = tile_coordinates(lat, lon, zoom)
                self.assertEqual(x, expected[0])
                self.assertEqual(y, expected[1])

        # Check if the tile coordinates lie in the top-left (top-right, bottom-...)
        # corner of the coordinate system.
        for zoom in range(1, 19):
            tiles = 2**zoom
            half = tiles / 2
            x, y = tile_coordinates(*nw, zoom)
            self.assertTrue(x < half)
            self.assertTrue(y < half)

            x, y = tile_coordinates(*ne, zoom)
            self.assertTrue(x >= half)
            self.assertTrue(y < half)

            x, y = tile_coordinates(*sw, zoom)
            self.assertTrue(x < half)
            self.assertTrue(y >= half)

            x, y = tile_coordinates(*se, zoom)
            self.assertTrue(x >= half)
            self.assertTrue(y >= half)
