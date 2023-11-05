from dataclasses import dataclass
from functools import cached_property
from math import asinh
from math import atan
from math import degrees
from math import floor
from math import log
from math import pi as PI
from math import pow
from math import radians
from math import sin
from math import sinh
from math import tan

from .geo import BBox
from .geo import mercator_to_lat


# supported lat/lon bounds for slippy map
MAX_LAT = 85.0511
MIN_LAT = -85.0511
MIN_LON = -180.0
MAX_LON = 180.0

# https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Zoom_levels
MIN_ZOOM = 0
MAX_ZOOM = 19


class TileMap:
    '''A slippy tile map with a given set of tiles and a fixed zoom level.

    The bounding box is fully contained within this map.
    '''

    def __init__(self, ax, ay, bx, by, zoom, bbox):
        self.ax = min(ax, bx)
        self.ay = min(ay, by)
        self.bx = max(ax, bx)
        self.by = max(ay, by)
        self.zoom = zoom
        self.bbox = bbox
        self.tiles = None
        self._generate_tiles()

    @property
    def num_tiles(self):
        x = self.bx - self.ax + 1
        y = self.by - self.ay + 1
        return x * y

    def _generate_tiles(self):
        self.tiles = {}
        for x in range(self.ax, self.bx + 1):
            for y in range(self.ay, self.by + 1):
                self.tiles[(x, y)] = Tile(x, y, self.zoom)

    def to_pixel_fractions(self, lat, lon):
        '''Get the X,Y coordinates in pixel fractions on *this map*
        for a given coordinate.

        Pixel fractions need to be multiplied with the tile size
        to get the actual pixel coordinates.'''
        nw = (self.ax, self.ay)
        lat_off = self.tiles[nw].bbox.maxlat
        lon_off = self.tiles[nw].bbox.minlon
        offset_x, offset_y = self._project(lat_off, lon_off)

        abs_x, abs_y = self._project(lat, lon)
        local_x = abs_x - offset_x
        local_y = abs_y - offset_y

        return local_x, local_y

    def _project(self, lat, lon):
        '''Project the given lat-lon to pixel fractions on the *world map*
        for this zoom level. Uses spherical mercator projection.

        Pixel fractions need to be multiplied with the tile size
        to get the actual pixel coordinates.

        see http://msdn.microsoft.com/en-us/library/bb259689.aspx
        '''
        globe = pow(2, self.zoom)
        pixel_x = ((lon + 180.0) / 360.0) * globe

        sinlat = sin(lat * PI / 180.0)
        pixel_y = (0.5 - log((1 + sinlat) / (1 - sinlat)) / (4 * PI)) * globe
        return pixel_x, pixel_y

    def __repr__(self):
        return '<TileMap a=%s,%s b=%s,%s, zoom=%s>' % (self.ax,
                                                       self.ay,
                                                       self.bx,
                                                       self.by,
                                                       self.zoom)

    @classmethod
    def from_bbox(cls, bbox, zoom):
        '''Set up a map with tiles that will *contain* the given bounding box.
        The map may be larger than the bounding box.'''
        ax, ay = tile_number(bbox.minlat, bbox.minlon, zoom)  # top left
        bx, by = tile_number(bbox.maxlat, bbox.maxlon, zoom)  # btm right
        return cls(ax, ay, bx, by, zoom, bbox)


@dataclass(frozen=True, order=True)
class Tile:
    '''Represents a single slippy map tile for a given zoom level.'''

    x: int
    y: int
    z: int

    @cached_property
    def bbox(self):
        '''The bounding box coordinates of this tile.'''
        return tile_bounds(self.x, self.y, self.z)

    @cached_property
    def anchor(self):
        '''Returns the lat/lon coordinates for the top-left corner of this
        tile.
        '''
        return tile_location(self.x, self.y, self.z)

    def contains(self, point):
        '''Tell if the given Point is within the bounds of this tile.'''
        bbox = self.bbox
        if point.lat < bbox.minlat or point.lat > bbox.maxlat:
            return False
        elif point.lon < bbox.minlon or point.lon > bbox.maxlon:
            return False

        return True

    def parent(self):
        '''Get the parent tile, i.e. the tile at the next lower zoom level
        which contains this tile.

        Returns a tuple ``(tile, pos)``.

        ``pos`` is position of this tile within its parent::

            0,0 | 1,0
            ----+----
            0,1 | 1,1

        *ValueError* is raised if there is no parent tile (if this tile is
        already at zoom level 0).
        '''
        if self.z == MIN_ZOOM:
            raise ValueError('Minimum zoom level reached')

        x = floor(self.x / 2)
        y = floor(self.y / 2)
        z = self.z - 1

        # Quadrant of this tile within its parent
        a = int(self.x % 2)
        b = int(self.y % 2)

        return Tile(x, y, z), (a, b)

    def subtiles(self):
        '''Get the four tiles which represent this tile in the next higher zoom
        level.

        *ValueError* is raised if this tile is already at the maximum zoom
        level.
        '''
        if self.z == MAX_ZOOM:
            raise ValueError('Maximim zoom level reached')

        x = self.x * 2
        y = self.y * 2
        z = self.z + 1

        return (Tile(x, y, z),
                Tile(x + 1, y, z),
                Tile(x, y + 1, z),
                Tile(x + 1, y + 1, z))


def tile_number(lat, lon, zoom):
    '''Calculate the X and Y coordinate for the map tile that contains the
    given point at the given zoom level.

    Returns a tuple (x, y).

    Raises *ValueError* if lat or lon are outside the allowed range.
    '''
    if lat < MIN_LAT or lat > MAX_LAT:
        raise ValueError('latitude must be %s..%s, got %s' % (MIN_LAT, MAX_LAT, lat))
    if lon < MIN_LON or lon > MAX_LON:
        raise ValueError('longitude must be %s..%s, got %s' % (MIN_LON, MAX_LON, lon))

    # taken from https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
    n = pow(2.0, zoom)

    x = (lon + 180.0) / 360.0 * n

    lat_rad = radians(lat)
    a = asinh(tan(lat_rad))
    y = (1.0 - a / PI) / 2.0 * n

    return int(x), int(y)


def tile_location(x, y, z):
    '''Determines the lat/lon location of the top-left corner of the given
    tile at the given zoom level.
    '''
    # from https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
    n = 2.0 ** z

    lon = x / n * 360.0 - 180.0

    lat_rad = atan(sinh(PI * (1 - 2 * y / n)))
    lat = degrees(lat_rad)

    return lat, lon


def tile_bounds(x, y, z):
    '''Calculates the bounding box of the given tile at the given zoom level.
    Returns a BBox with ``maxlat, minlon, minlat, maxlon`` coordinates set to
    the top left (nortwestern) and bottom-right (southeastern) corner of the
    tile.
    '''
    maxlat, minlon = tile_location(x, y, z)  # top left
    minlat, maxlon = tile_location(x + 1, y + 1, z)  # bottom right
    return BBox(maxlat=maxlat,
                minlon=minlon,
                minlat=minlat,
                maxlon=maxlon)
