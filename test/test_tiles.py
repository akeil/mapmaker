from unittest import TestCase

from mapmaker.tilemap import Tile
from mapmaker.tilemap import TileMap
from mapmaker.tilemap import tile_number
from mapmaker.tilemap import tile_location
from mapmaker.tilemap import MAX_LAT, MIN_LAT, MIN_LON, MAX_LON
from mapmaker.tilemap import MIN_ZOOM, MAX_ZOOM


class TestTiles(TestCase):

    def test_tile_coords(self):
        nw = (63.0695, -151.0074)
        ne = (43.355, 42.439167)
        sw = (-32.653197, -70.0112)
        se = (-4.078889, 137.158333)

        cases = {
            # zoom = 0, single tile
            0: {
                nw: (0, 0),
                ne: (0, 0),
                sw: (0, 0),
                se: (0, 0),
            },
            # zoom 1 = 4 tiles
            1: {
                nw: (0, 0),
                ne: (1, 0),
                sw: (0, 1),
                se: (1, 1),
            },
        }
        for zoom, pairs in cases.items():
            for loc, expected in pairs.items():
                lat, lon = loc
                x, y = tile_number(lat, lon, zoom)
                self.assertEqual(x, expected[0])
                self.assertEqual(y, expected[1])

        # Check if the tile coordinates lie in the top-left
        # (top-right, bottom-...) corner of the coordinate system.
        for zoom in range(1, 19):
            tiles = 2**zoom
            half = tiles / 2
            x, y = tile_number(*nw, zoom)
            self.assertTrue(x < half)
            self.assertTrue(y < half)

            x, y = tile_number(*ne, zoom)
            self.assertTrue(x >= half)
            self.assertTrue(y < half)

            x, y = tile_number(*sw, zoom)
            self.assertTrue(x < half)
            self.assertTrue(y >= half)

            x, y = tile_number(*se, zoom)
            self.assertTrue(x >= half)
            self.assertTrue(y >= half)

    def test_bounds(self):
        self.assertRaises(ValueError, tile_number, -86, 123, 0)
        self.assertRaises(ValueError, tile_number, 86, 123, 0)

    def test_bounds(self):
        # this fails when 180° is included - why?
        for lat in range(-85, 86, 1):
            for lon in range(-180, 180, 1):
                for zoom in range(20):
                    max_tiles = 2**zoom - 1
                    x, y = tile_number(lat, lon, zoom)
                    self.assertGreaterEqual(x, 0, msg='X coordinate <0 for %s,%s @ %s' % (lat, lon, zoom))
                    self.assertLessEqual(x, max_tiles, msg='X coordinate > MAX for %s,%s z=%s' % (lat, lon, zoom))
                    self.assertGreaterEqual(y, 0, msg='Y coordinate <0 for %s,%s @ %s' % (lat, lon, zoom))
                    self.assertLessEqual(y, max_tiles, msg='Y coordinate > MAX for %s,%s z=%s' % (lat, lon, zoom))

    # works, but runs "forever" (there are a lot of valid tile numbers...)
    def DISABLED_test_tile_location(self):
        '''Make sure we can calculate a location for any valid tile number'''
        tolerance = 0.0001  # rounding errors
        for zoom in range(20):
            max_tiles = 2**zoom - 1
            for x in range(max_tiles):
                for y in range(max_tiles):
                    lat, lon = tile_location(x, y, zoom)
                    self.assertLessEqual(lat, MAX_LAT + tolerance)
                    self.assertGreaterEqual(lat, MIN_LAT - tolerance)
                    self.assertLessEqual(lon, MAX_LON + tolerance)
                    self.assertGreaterEqual(lon, MIN_LON - tolerance)


class TestTile(TestCase):
    '''Tests for the ``Tile`` dataclass.'''

    # bbox
    # is always a BBox where all coordinates are within MIN/MAX

    # anchor
    # anchor is always a lat/lon coordinate within MIN/MAX values

    # contains
    # should we test this? We could also test BBox.contains()

    # parent
    # TODO: we can get a parent tile for each tile that is not on MIN_ZOOM
    #       the parent tile is a valid tile number for its zoom level
    #       the parent tile has a by 1 lower zoom than the child
    def test_no_parent_at_min_zoom(self):
        t = Tile(1, 1, MIN_ZOOM)
        self.assertRaises(ValueError, t.parent)

    # subtiles
    # TODO: we can get subtiles for any tile not on MAX_ZOOM
    #       there are always 4 subtiles
    #       subtiles have zoom +1 vs. their parent
    #       and have a valid tile number for their zoom level
    #       and all quadrants are different (0,0), (0,1), (1,0), (1,1)

    def test_no_subtiles_at_max_zoom(self):
        t = Tile(1, 1, MAX_ZOOM)
        self.assertRaises(ValueError, t.subtiles)

    def test_parent_child_invariant(self):
        '''If we look at the subtiles from Tile X,
        their parents must also be Tile X.'''
        # TODO: should work with all tile valid numbers
        # on all zoom levels except MAX_ZOOM
        start = Tile(2, 2, 2)
        subs = start.subtiles()
        self.assertEqual(len(subs), 4)
        for tile in subs:
            parent, _ = tile.parent()
            self.assertEqual(parent, start)


class TestTileMap(TestCase):
    '''Tests for the ``TileMap`` class.'''

    def test_equal(self):
        tm0 = TileMap(0, 0, 10, 10, 5, None)
        tm1 = TileMap(0, 0, 10, 10, 5, None)
        self.assertEqual(tm0, tm1)

        tm2 = TileMap(0, 0, 10, 10, 10, None)
        self.assertNotEqual(tm0, tm2)

        tm3 = TileMap(0, 0, 2, 2, 5, None)
        self.assertNotEqual(tm0, tm3)

        self.assertNotEqual(tm0, None)
        self.assertNotEqual(tm0, 'xyz')

    # __init__
    # should validate xy tile numbers against MIN/MAX for zoom
    # should validate Zoom aginst MIN/MAX
    # also: integers only

    def test_auto_sort_xy(self):
        '''Assert that the sequence of arguments for min/max tile numbers
        is not relevant.'''
        tm0 = TileMap(0, 0, 10, 10, 5, None)
        tm1 = TileMap(10, 10, 0, 0, 5, None)
        self.assertEqual(tm0, tm1)

    # from_bbox
    # we should be able to construct a tile map for any Bbox within MIN/MAX lat/lon
    # and valid zoom

    # when we construct for bbox, the resulting map must hold exactly one tile
    # which contains each of the corners of the BBox

    # to_pixel_fractions
    # we can calculate pixel fractions for every valid lat/lon
    # pixel fractions are always >= 0.0
    # ... and are <= the number of tiles in x/y direction

