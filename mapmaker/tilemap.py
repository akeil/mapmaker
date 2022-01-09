import io
from math import asinh
from math import ceil
from math import log
from math import pi as PI
from math import pow
from math import radians
from math import sin
from math import tan
import queue
import threading

from .geo import BBox
from .geo import mercator_to_lat

from PIL import Image


# supported lat bounds for slippy map
MAX_LAT = 85.0511
MIN_LAT = -85.0511

# Most (all?) services will return tiles this size
DEFAULT_TILESIZE = (256, 256)


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
        lat_off = self.tiles[nw].bbox.minlat
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
        globe_px = pow(2, self.zoom)
        pixel_x = ((lon + 180.0) / 360.0) * globe_px

        sinlat = sin(lat * PI / 180.0)
        pixel_y = (0.5 - log((1 + sinlat) / (1 - sinlat)) / (4 * PI)) * globe_px
        return pixel_x, pixel_y

    def __repr__(self):
        return '<TileMap a=%s,%s b=%s,%s>' % (self.ax, self.ay, self.bx, self.by)

    @classmethod
    def from_bbox(cls, bbox, zoom):
        '''Set up a map with tiles that will *contain* the given bounding box.
        The map may be larger than the bounding box.'''
        ax, ay = _tile_coordinates(bbox.minlat, bbox.minlon, zoom)  # top left
        bx, by = _tile_coordinates(bbox.maxlat, bbox.maxlon, zoom)  # bottom right
        return cls(ax, ay, bx, by, zoom, bbox)


# TODO: private?
class Tile:
    '''Represents a single slippy map tile for a given zoom level.'''

    def __init__(self, x, y, zoom):
        self.x = x
        self.y = y
        self.zoom = zoom

    @property
    def bbox(self):
        '''The bounding box coordinates of this tile.'''
        north, south = self._lat_edges()
        west, east = self._lon_edges()
        # TODO havin North/South and West/East as min/max might be slightly wrong?
        return BBox(
            minlat=north,
            minlon=west,
            maxlat=south,
            maxlon=east
        )

    def contains(self, point):
        '''Tell if the given Point is within the bounds of this tile.'''
        bbox = self.bbox
        if point.lat < bbox.minlat or point.lat > bbox.maxlat:
            return False
        elif point.lon < bbox.minlon or point.lon > bbox.maxlon:
            return False

        return True

    def _lat_edges(self):
        n = pow(2.0, self.zoom)
        unit = 1.0 / n
        relative_y0 = self.y * unit
        relative_y1 = relative_y0 + unit
        lat0 = mercator_to_lat(PI * (1 - 2 * relative_y0))
        lat1 = mercator_to_lat(PI * (1 - 2 * relative_y1))
        return(lat0, lat1)

    def _lon_edges(self):
        n = pow(2.0, self.zoom)
        unit = 360 / n
        lon0 = -180 + self.x * unit
        lon1 = lon0 + unit
        return lon0, lon1

    def __repr__(self):
        return '<Tile %s,%s>' % (self.x, self.y)


def _tile_coordinates(lat, lon, zoom):
    '''Calculate the X and Y coordinates for the map tile that contains the
    given point at the given zoom level.'''
    if lat <= MIN_LAT or lat >= MAX_LAT:
        raise ValueError('latitude must be %s..%s' % (MIN_LAT, MAX_LAT))

    # taken from https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
    n = pow(2.0, zoom)

    x = (lon + 180.0) / 360.0 * n

    if lat == -90:
        y = 0
    else:
        lat_rad = radians(lat)
        a = asinh(tan(lat_rad))
        y = (1.0 - a / PI) / 2.0 * n

    return int(x), int(y)


class RenderContext:
    '''Renders a map, downloading required tiles on the fly.'''

    def __init__(self, service, map, overlays=None, parallel_downloads=None, reporter=None):
        self._service = service
        self._map = map
        self._overlays = overlays or []
        self._parallel_downloads = parallel_downloads or 1
        self._report = reporter or _no_reporter
        self._queue = queue.Queue()
        self._lock = threading.Lock()
        # will be set to the actual size once the first tile is downloaded
        self._tile_size = DEFAULT_TILESIZE
        self._img = None
        self._total_tiles = 0
        self._downloaded_tiles = 0

    def _tile_complete(self):
        self._downloaded_tiles += 1
        percentage = int(self._downloaded_tiles / self._total_tiles * 100.0)
        self._report('%3d%%  %4d / %4d',
            percentage,
            self._downloaded_tiles,
            self._total_tiles)

    @property
    def crop_box(self):
        '''Get the crop box that will be applied to the stitched map.'''
        bbox = self._map.bbox
        left, bottom = self.to_pixels(bbox.minlat, bbox.minlon)
        right, top = self.to_pixels(bbox.maxlat, bbox.maxlon)

        return (left, top, right, bottom)

    @property
    def bbox(self):
        '''The maps bounding box coordinates.'''
        return self._map.bbox

    def build(self):
        '''Download tiles on the fly and render them into an image.'''
        # fill the task queue
        for tile in self._map.tiles.values():
            self._queue.put(tile)

        self._total_tiles = self._queue.qsize()
        self._report('Download %d tiles (parallel downloads: %d)', self._total_tiles, self._parallel_downloads)

        # start parallel downloads
        for w in range(self._parallel_downloads):
            threading.Thread(daemon=True, target=self._work).run()

        self._queue.join()

        self._report('Download complete, create map image')

        if self._overlays:
            self._report('Draw %d overlays', len(self._overlays))
            self._draw_overlays()

        self._crop()
        return self._img

    def to_pixels(self, lat, lon):
        '''Convert the given lat,lon coordinates to pixels on the map image.

        This method can only be used after the first tiles have been downloaded
        and the tile size is known.
        '''
        frac_x, frac_y = self._map.to_pixel_fractions(lat, lon)
        w, h = self._tile_size

        def px(v):
            return int(ceil(v))

        return px(frac_x * w), px(frac_y * h)

    def _draw_overlays(self):
        '''Draw overlay layers on the map image.'''
        # For transparent overlays, we cannot paint directly on the image.
        # Instead, paint on a separate overlay image and compose the results.
        for layer in self._overlays:
            overlay = Image.new('RGBA', self._img.size, color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay, mode='RGBA')
            layer._draw(self, draw)
            self._img.alpha_composite(overlay)

    def _crop(self):
        '''Crop the map image to the bounding box.'''
        self._img = self._img.crop(self.crop_box)

    def _work(self):
        '''Download map tiles and paste them onto the result image.'''
        while True:
            try:
                tile = self._queue.get(block=False)
                try:
                    _, data = self._service.fetch(tile)
                    tile_img = Image.open(io.BytesIO(data))
                    with self._lock:
                        self._paste_tile(tile_img, tile.x, tile.y)
                        self._tile_complete()
                finally:
                    self._queue.task_done()
            except queue.Empty:
                return

    def _paste_tile(self, tile_img, x, y):
        '''Paste a tile image on the main map image.'''
        w, h = tile_img.size
        self._tile_size = w, h  # assume that all tiles have the same size
        if self._img is None:
            xtiles = self._map.bx - self._map.ax + 1
            width = w * xtiles
            ytiles = self._map.by - self._map.ay + 1
            height = h * ytiles
            self._img = Image.new('RGBA', (width, height))

        top = (x - self._map.ax) * w
        left = (y - self._map.ay) * h
        box = (top, left)
        self._img.paste(tile_img, box)
