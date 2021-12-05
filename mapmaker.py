#!/bin/python
import argparse
import base64
from collections import namedtuple
import configparser
import io
import math
from math import asin
from math import atan2
from math import ceil
from math import cos
from math import degrees
from math import floor
from math import log
from math import pi as PI
from math import radians
from math import sin
from math import tan
from pathlib import Path
import queue
import sys
import threading
from urllib.parse import urlparse

import appdirs
from PIL import Image
import requests


__version__ = '1.0.0'
__author__ = 'akeil'

APP_NAME = 'mapmaker'
APP_DESC = 'Create map images from tile servers.'

BRG_NORTH = 0
BRG_EAST = 90
BRG_SOUTH = 180
BRG_WEST = 270
EARTH_RADIUS = 6371.0 * 1000.0

HILLSHADE = 'hillshading'

_DEFAULT_CONFIG = '''[services]
# see: https://wiki.openstreetmap.org/wiki/Tile_servers
osm         = https://tile.openstreetmap.org/{z}/{x}/{y}.png
topo        = https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png
human       = http://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png
hillshading = http://tiles.wmflabs.org/hillshading/{z}/{x}/{y}.png
bw          = https://tiles.wmflabs.org/bw-mapnik/{z}/{x}/{y}.png
nolabels    = https://tiles.wmflabs.org/osm-no-labels/{z}/{x}/{y}.png
toner       = http://{s}.tile.stamen.com/toner/{z}/{x}/{y}.png
watercolor  = http://c.tile.stamen.com/watercolor/{z}/{x}/{y}.jpg
positron    = https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png
darkmatter  = https://cartodb-basemaps-a.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png
landscape   = http://tile.thunderforest.com/landscape/{z}/{x}/{y}.png?apikey={api}
outdoors    = http://tile.thunderforest.com/outdoors/{z}/{x}/{y}.png?apikey={api}
atlas       = https://tile.thunderforest.com/atlas/{z}/{x}/{y}.png?apikey={api}
grey        = https://maps.geoapify.com/v1/tile/osm-bright-grey/{z}/{x}/{y}.png?apiKey={api}
smooth      = https://maps.geoapify.com/v1/tile/osm-bright-smooth/{z}/{x}/{y}.png?apiKey={api}
toner-grey  = https://maps.geoapify.com/v1/tile/toner-grey/{z}/{x}/{y}.png?apiKey={api}
blue        = https://maps.geoapify.com/v1/tile/positron-blue/{z}/{x}/{y}.png?apiKey={api}
red         = https://maps.geoapify.com/v1/tile/positron-red/{z}/{x}/{y}.png?apiKey={api}
brown       = https://maps.geoapify.com/v1/tile/dark-matter-brown/{z}/{x}/{y}.png?apiKey={api}
darkgrey    = https://maps.geoapify.com/v1/tile/dark-matter-dark-grey/{z}/{x}/{y}.png?apiKey={api}
purple      = https://maps.geoapify.com/v1/tile/dark-matter-dark-purple/{z}/{x}/{y}.png?apiKey={api}
klokantech  = https://maps.geoapify.com/v1/tile/klokantech-basic/{z}/{x}/{y}.png?apiKey={api}


[keys]
tile.thunderforest.com  = <YOUR_API_KEY>
maps.geoapify.com       = <YOUR_API_KEY>
'''

BBox = namedtuple('BBox', 'minlat minlon maxlat maxlon')


# CLI -------------------------------------------------------------------------


def main():
    '''Parse arguments and run the program.'''
    conf_dir = appdirs.user_config_dir(appname=APP_NAME)
    conf_file = Path(conf_dir).joinpath('config.ini')

    patterns, api_keys = _read_config(conf_file)
    styles = sorted(x for x in patterns.keys())

    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description=APP_DESC,
        epilog='{p} version {v} -- {author}'.format(
            p=APP_NAME,
            v=__version__,
            author=__author__,
        ),
    )
    parser.add_argument(
        'bbox',
        metavar='AREA',
        action=_BBoxAction,
        nargs=2,
        help=(
            'Bounding box coordinates. Either two lat,lon pairs ("47.437,10.953 47.374,11.133")'
            ' or a center point and a radius ("47.437,10.953 4km").'
        )
    )
    default_dst = 'map.png'
    parser.add_argument(
        'dst',
        metavar='PATH',
        nargs='?',
        default=default_dst,
        help='Where to save the generated image (default: %r).' % default_dst
    )

    def zoom(raw):
        v = int(raw)
        if v < 0 or v > 19:
            raise ValueError
        return v

    default_zoom = 8
    parser.add_argument(
        '-z', '--zoom',
        default=default_zoom,
        type=zoom,
        help='Zoom level (0..19), higher means more detailed (default: %s).' % default_zoom
    )
    default_style = 'osm'
    parser.add_argument(
        '-s', '--style',
        choices=styles,
        default=default_style,
        help='Map style (default: %r)' % default_style,
    )
    parser.add_argument(
        '--gallery',
        action='store_true',
        help='Create a map image for each available style. WARNING: generates a lot of images.',
    )
    parser.add_argument(
        '--shading',
        action='store_true',
        help='Add hillshading',
    )
    parser.add_argument(
        '--silent',
        action='store_true',
        help='Do not output messages to the console',
    )

    args = parser.parse_args()

    reporter = _no_reporter if args.silent else _print_reporter

    reporter('Using configuration from %r', str(conf_file))

    try:
        if args.gallery:
            base = Path(args.dst)
            base.mkdir(exist_ok=True)
            for style in styles:
                dst = base.joinpath(style + '.png')
                try:
                    run(args.bbox, args.zoom, dst, style, reporter, patterns, api_keys, hillshading=args.shading)
                except Exception as err:
                    # on error, continue with next service
                    reporter('ERROR for %r: %s', style, err)
        else:
            run(args.bbox, args.zoom, args.dst, args.style, reporter, patterns, api_keys, hillshading=args.shading)
    except Exception as err:
        reporter('ERROR: %s', err)
        return 1

    return 0



def run(bbox, zoom, dst, style, report, patterns, api_keys, hillshading=False):
    '''Build the tilemap, download tiles and create the image.'''
    cache_dir = appdirs.user_cache_dir(appname='mapmaker', appauthor='akeil')
    map = TileMap.from_bbox(bbox, zoom)

    service = Cache(TileService(style, patterns[style], api_keys), cache_dir)
    img = RenderContext(service, map, report).build()

    if hillshading:
        shading = Cache(TileService(HILLSHADE, patterns[HILLSHADE], api_keys), cache_dir)
        shade = RenderContext(shading, map, report).build()
        img.paste(shade.convert('RGB'), mask=shade)

    with open(dst, 'wb') as f:
        img.save(f, format='png')

    report('Map saved to %r', dst)


class _BBoxAction(argparse.Action):

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super(_BBoxAction, self).__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # expect one of;
        #
        # A: two lat/lon pairs
        #    e.g. 47.437,10.953 47.374,11.133
        #
        # B: lat/lon and radius
        #    e.g. 47.437,10.953 2km
        a = values[0].split(',')
        lat0 = float(a[0])
        lon0 = float(a[1])

        b = values[1].split(',')

        # simple case, BBox from lat,lon pairs
        if len(b) == 2:
            bbox = BBox(
                minlat=lat0,
                minlon=lon0,
                maxlat=float(b[0]),
                maxlon=float(b[1]),
            )
        # bbox from point and radius
        else:
            s = b[0].lower()
            unit = None
            value = None
            allowed_units = ('km', 'm')
            for u in allowed_units:
                if s.endswith(u):
                    unit = u
                    value = float(s[:-len(u)])
                    break

            if value is None:  # no unit specified
                value = float(s)
                unit = 'm'

            # convert to meters,
            if unit == 'km':
                value *= 1000.0

            lat_n, lon_n = _destination_point(lat0, lon0, BRG_NORTH, value)
            lat_e, lon_e = _destination_point(lat0, lon0, BRG_EAST, value)
            lat_s, lon_s = _destination_point(lat0, lon0, BRG_SOUTH, value)
            lat_w, lon_w = _destination_point(lat0, lon0, BRG_WEST, value)

            bbox = BBox(
                minlat=min(lat_n, lat_e, lat_s, lat_w),
                minlon=min(lon_n, lon_e, lon_s, lon_w),
                maxlat=max(lat_n, lat_e, lat_s, lat_w),
                maxlon=max(lon_n, lon_e, lon_s, lon_w),
            )

        # Validate
        if bbox.minlat < -90.0 or bbox.minlat > 90.0:
            raise ValueError
        if bbox.maxlat < -90.0 or bbox.maxlat > 90.0:
            raise ValueError
        if bbox.minlon < -180.0 or bbox.minlon > 180.0:
            raise ValueError
        if bbox.maxlon < -180.0 or bbox.maxlon > 180.0:
            raise ValueError

        setattr(namespace, self.dest, bbox)


def _print_reporter(msg, *args):
    print(msg % args)


def _no_reporter(msg, *args):
    pass


def _read_config(path):
    cfg = configparser.ConfigParser()
    # we cannot package default.ini if we distribute as a single .py file.
    # from pkg_resources import resource_stream
    ## built-in, defaults
    #cfg.read_file(io.TextIOWrapper(
    #    resource_stream('mapmaker', 'default.ini'))
    #)

    # built-in from code
    cfg.read_string(_DEFAULT_CONFIG)

    # user settings
    cfg.read([path, ])

    patterns = {k: v for k, v in cfg.items('services')}
    keys = {k: v for k, v in cfg.items('keys')}

    return patterns, keys


# Tile Map --------------------------------------------------------------------


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
        #se = (self.bx, self.by)
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
        globe_px = math.pow(2, self.zoom)
        pixel_x = ((lon + 180.0) / 360.0) * globe_px

        sinlat = math.sin(lat * PI / 180.0)
        pixel_y = (0.5 - math.log((1 + sinlat) / (1 - sinlat)) / (4 * PI)) * globe_px
        return pixel_x, pixel_y

    def __repr__(self):
        return '<TileMap a=%s,%s b=%s,%s>' % (self.ax, self.ay, self.bx, self.by)

    @classmethod
    def from_bbox(cls, bbox, zoom):
        '''Set up a map with tiles that will *contain* the given bounding box.
        The map may be larger than the bounding box.'''
        ax, ay = tile_coordinates(bbox.minlat, bbox.minlon, zoom)  # top left
        bx, by = tile_coordinates(bbox.maxlat, bbox.maxlon, zoom)  # bottom right
        return cls(ax, ay, bx, by, zoom, bbox)


class Tile:
    '''Represents a single slippy map tile  for a given zoom level.'''

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
        n = math.pow(2.0, self.zoom)
        unit = 1.0 / n
        relative_y0 = self.y * unit
        relative_y1 = relative_y0 + unit
        lat0 = _mercator_to_lat(PI * (1 - 2 * relative_y0))
        lat1 = _mercator_to_lat(PI * (1 - 2 * relative_y1))
        return(lat0, lat1)

    def _lon_edges(self):
        n = math.pow(2.0, self.zoom)
        unit = 360 / n
        lon0 = -180 + self.x * unit
        lon1 = lon0 + unit
        return lon0, lon1

    def __repr__(self):
        return '<Tile %s,%s>' % (self.x, self.y)


def _mercator_to_lat(mercator_y):
    return math.degrees(math.atan(math.sinh(mercator_y)))


def _destination_point(lat, lon, bearing, distance):
    '''Determine a destination point from a start location, a bearing and a distance.

    Distance is given in METERS.
    Bearing is given in DEGREES
    '''
    # http://www.movable-type.co.uk/scripts/latlong.html
    # search for destinationPoint
    d = distance / EARTH_RADIUS  # angular distance
    brng = radians(bearing)

    lat = radians(lat)
    lon = radians(lon)

    a = sin(lat) * cos(d) + cos(lat) * sin(d) * cos(brng)
    lat_p = asin(a)

    x = cos(d) - sin(lat) * a
    y = sin(brng) * sin(d) * cos(lat)
    lon_p = lon + atan2(y, x)

    return degrees(lat_p), degrees(lon_p)


def tile_coordinates(lat, lon, zoom):
    '''Calculate the X and Y coordinates for the map tile that contains the
    given point at the given zoom level.'''
    # taken from https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
    n = math.pow(2.0, zoom)
    x_rel, y_rel = _to_relative_xy(lat, lon, zoom)

    x = int(x_rel * n)
    y = int(y_rel * n)
    return x, y


def _to_relative_xy(lat, lon, zoom):
    '''Calculate the x,y indices for a tile'''
    x = (lon + 180.0) / 360.0

    lat_rad = radians(lat)
    lat_sec = 1 / cos(lat_rad)
    a = log(tan(lat_rad) + lat_sec)
    y = (1.0 - a / PI) / 2.0

    return x, y


# Rendering -------------------------------------------------------------------


class RenderContext:
    '''Renders a map, downloading required tiles on the fly.'''

    def __init__(self, service, map, report):
        self._service = service
        self._map = map
        self._report = report or _no_reporter
        self._queue = queue.Queue()
        self._lock = threading.Lock()
        self._tile_size = None
        self._img = None
        self._total_tiles = 0
        self._downloaded_tiles = 0

    def _tile_complete(self):
        self._downloaded_tiles += 1
        percentage = self._downloaded_tiles / self._total_tiles * 100.0
        self._report('% 3.0f%%, %d / %d tiles for %r',
            percentage,
            self._downloaded_tiles,
            self._total_tiles,
            self._service.name
        )

    def build(self):
        '''Download tiles on the fly and render them into an image.'''
        num_workers = 8
        # fill the task queue
        for tile in self._map.tiles.values():
            self._queue.put(tile)

        self._total_tiles = self._queue.qsize()
        self._report('Download %s tiles for map style %r', self._total_tiles, self._service.name)
        self._report('Parallel downloads: %s', num_workers)

        # start parallel downloads
        for w in range(num_workers):
            threading.Thread(daemon=True, target=self._work).run()

        self._queue.join()

        self._report('Download complete, create map image')

        self._crop()
        return self._img

    def _crop(self):
        '''Crop the map image to the bounding box.'''
        bbox = self._map.bbox
        af = self._map.to_pixel_fractions(bbox.minlat, bbox.minlon)
        bf = self._map.to_pixel_fractions(bbox.maxlat, bbox.maxlon)

        w, h = self._tile_size
        px = lambda v: int(ceil(v))

        left, bottom = px(af[0] * w), px(af[1] * h)
        right, top = px(bf[0] * w), px(bf[1] * h)

        self._img = self._img.crop((left, top, right, bottom))

    def _work(self):
        '''Download map tiles and paste them onto the result image.'''
        while True:
            try:
                tile = self._queue.get(block=False)
                try:
                    _, data = self._service.fetch(tile)
                    tile_img = Image.open(io.BytesIO(data))
                    with self._lock:
                        self._paste(tile_img, tile.x, tile.y)
                        self._tile_complete()
                finally:
                    self._queue.task_done()
            except queue.Empty:
                return

    def _paste(self, tile_img, x, y):
        '''Implementation for pasting'''
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


# Tile Service ----------------------------------------------------------------


class TileService:

    def __init__(self, name, url_pattern, api_keys):
        self.name = name
        self.url_pattern=url_pattern
        self._api_keys = api_keys or {}

    def fetch(self, tile, etag=None):
        '''Fetch the given tile from the Map Tile Service.

        If an etag is specified, it will be sent to the server. If the server
        replies with a status "Not Modified", this method returns +None*.'''
        url = self.url_pattern.format(
            x=tile.x,
            y=tile.y,
            z=tile.zoom,
            s='a',  # TODO: abc
            api=self._api_key(),
        )

        headers = None
        if etag:
            headers = {
                'If-None-Match': etag
            }

        res = requests.get(url, headers=headers)
        res.raise_for_status()

        if res.status_code == 304:
            return etag, None

        recv_etag = res.headers.get('etag')
        return recv_etag, res.content

    def _api_key(self):
        parts = urlparse(self.url_pattern)
        host = parts.netloc
        return self._api_keys.get(host, '')


class Cache:

    def __init__(self, service, basedir):
        self._service = service
        self._base = Path(basedir)

    @property
    def name(self):
        return self._service.name

    def fetch(self, tile, etag=None):
        '''Attempt to serve the tile from the cache, if that fails, fetch it
        from the backing service.
        On a successful service call, put the result into the cache.'''
        # etag is likely to be None
        if etag is None:
            etag = self._find(tile)

        recv_etag, data = self._service.fetch(tile, etag=etag)
        if data is None:
            try:
                cached = self._get(tile, etag)
                return etag, cached
            except LookupError:
                pass

        if data is None:
            # cache lookup failed
            recv_etag, data = self._service.fetch(tile)

        self._put(tile, recv_etag, data)
        return recv_etag, data


        try:
            return etag, self._get(tile, etag)
        except LookupError:
            etag, data = self._service.fetch(tile)
            self._put(tile, etag, data)
            return etag, data

    def _get(self, tile, etag):
        if not etag:
            raise LookupError

        try:
            return self._path(tile, etag).read_bytes()
        except Exception:
            raise LookupError

    def _find(self, tile):
        # expects filename pattern:  Y.BASE64(ETAG).png
        p = self._path(tile, '')
        d = p.parent
        match = '%06d.' % tile.y

        try:
            for entry in d.iterdir():
                if entry.name.startswith(match):
                    if entry.is_file():
                        try:
                            safe_etag = entry.name.split('.')[1]
                            etag_bytes = base64.b64decode(safe_etag)
                            return etag_bytes.decode('ascii')
                        except Exception as err:
                            # Errors if we encounter unexpected filenames
                            pass

        except FileNotFoundError as err:
            pass

    def _put(self, tile, etag, data):
        if not etag:
            return

        p = self._path(tile, etag)
        if p.is_file():
            return

        self._clean(tile, etag)

        d = p.parent
        d.mkdir(parents=True, exist_ok=True)

        with p.open('wb') as f:
            f.write(data)

    def _clean(self, tile, current):
        existing = self._find(tile)
        if existing and existing != current:
            p = self._path(tile, existing)
            p.unlink(missing_ok=True)

    def _path(self, tile, etag):
        safe_etag = base64.b64encode(etag.encode()).decode('ascii')
        filename = '%06d.%s.png' % (tile.y, safe_etag)

        return self._base.joinpath(
            self._service.name,
            '%02d' % tile.zoom,
            '%06d' % tile.x,
            filename,
        )


if __name__ == '__main__':
    sys.exit(main())
