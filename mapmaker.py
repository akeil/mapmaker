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
from math import sqrt
from math import tan
from pathlib import Path
import queue
import sys
import threading
from urllib.parse import urlparse

import appdirs
from PIL import Image, ImageDraw, ImageFont
import requests


__version__ = '1.2.0'
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

    patterns, api_keys = read_config(conf_file)
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
            raise ValueError('Zoom value must be in interval 0..19')
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
        '-a', '--aspect',
        type=_aspect,
        default=1.0,
        help=('Aspect ratio (e.g. "16:9") for the generated map. Extends the'
            ' bounding box to match the given aspect ratio.'),
    )
    parser.add_argument(
        '--shading',
        action='store_true',
        help='Add hillshading',
    )
    parser.add_argument(
        '--gallery',
        action='store_true',
        help='Create a map image for each available style. WARNING: generates a lot of images.',
    )
    parser.add_argument(
        '--silent',
        action='store_true',
        help='Do not output messages to the console',
    )

    args = parser.parse_args()

    reporter = _no_reporter if args.silent else _print_reporter
    bbox = _apply_aspect(args.bbox, args.aspect)

    reporter('Using configuration from %r', str(conf_file))

    try:
        if args.gallery:
            base = Path(args.dst)
            base.mkdir(exist_ok=True)
            for style in styles:
                dst = base.joinpath(style + '.png')
                try:
                    run(bbox, args.zoom, dst, style, reporter, patterns, api_keys, hillshading=args.shading)
                except Exception as err:
                    # on error, continue with next service
                    reporter('ERROR for %r: %s', style, err)
        else:
            run(bbox, args.zoom, args.dst, args.style, reporter, patterns, api_keys, hillshading=args.shading)
    except Exception as err:
        reporter('ERROR: %s', err)
        return 1

    return 0


def run(bbox, zoom, dst, style, report, patterns, api_keys, hillshading=False):
    '''Build the tilemap, download tiles and create the image.'''
    map = TileMap.from_bbox(bbox, zoom)

    service = Cache.user_dir(TileService(style, patterns[style], api_keys))
    img = RenderContext(service, map, reporter=report).build()

    if hillshading:
        shading = Cache.user_dir(TileService(HILLSHADE, patterns[HILLSHADE], api_keys))
        shade = RenderContext(shading, map, reporter=report).build()
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


def _aspect(raw):
    '''Parse an aspect ration given in the form of "19:9" into a float.'''
    if not raw:
        raise ValueError('Invalid argument (empty)')

    parts = raw.split(':')
    if len(parts) != 2:
        raise ValueError('Invalid aspect ratio %r, expected format "W:H"' % raw)

    w, h = parts
    return float(w) / float(h)


def _apply_aspect(bbox, aspect):
    '''Extend the given bounding box so that it adheres to the given aspect
    ratio (given as a floating point number).
    Returns a new bounding box with the desired aspect ration that contains
    the initial box in its center'''
    #  4:3  =>  1.32  width > height, aspect is > 1.0
    #  2:3  =>  0.66  width < height, aspect is < 1.0
    if aspect == 1.0:
        return bbox

    lat = bbox.minlat
    lon = bbox.minlon
    width = _distance(bbox.minlat, lon, bbox.maxlat, lon)
    height = _distance(lat, bbox.minlon, lat, bbox.maxlon)

    if aspect < 1.0:
        # extend "height" (latitude)
        target_height = width / aspect
        extend_height = (target_height - height) / 2
        new_minlat, _ = _destination_point(bbox.minlat, lon, BRG_SOUTH, extend_height)
        new_maxlat, _ = _destination_point(bbox.maxlat, lon, BRG_NORTH, extend_height)
        return BBox(
            minlat=new_minlat,
            minlon=bbox.minlon,
            maxlat=new_maxlat,
            maxlon=bbox.maxlon
        )
    else:  # aspect > 1.0
        # extend "width" (longitude)
        target_width = height * aspect
        extend_width = (target_width - width) / 2
        _, new_minlon = _destination_point(lat, bbox.minlon, BRG_WEST, extend_width)
        _, new_maxlon = _destination_point(lat, bbox.maxlon, BRG_EAST, extend_width)
        return BBox(
            minlat=bbox.minlat,
            minlon=new_minlon,
            maxlat=bbox.maxlat,
            maxlon=new_maxlon
        )


def _print_reporter(msg, *args):
    print(msg % args)


def _no_reporter(msg, *args):
    pass


def read_config(path):
    '''Read configuration from the given file in .ini format.
    Returns names and url patterns for services and API keys, combined from
    built-in configuration and the specified file.'''
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


def _distance(lat0, lon0, lat1, lon1):
    '''Calculate the distance as-the-crow-flies between two points in meters.

        P0 ------------> P1

    '''
    lat0 = radians(lat0)
    lon0 = radians(lon0)
    lat1 = radians(lat1)
    lon1 = radians(lon1)

    d_lat = lat1 - lat0
    d_lon = lon1 - lon0

    a = sin(d_lat / 2) * sin(d_lat / 2)
    b = cos(lat0) * cos(lat1) * sin(d_lon / 2) * sin(d_lon / 2)
    c = a + b

    d = 2 * atan2(sqrt(c), sqrt(1 - c))

    return d * EARTH_RADIUS


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


class DrawLayer:
    '''Keeps data for map overlays.'''

    def __init__(self, waypoints, points, line_color, line_width, fill_color, size):
        # for tracks
        self.waypoints = waypoints
        self.points = points
        self.line_color = line_color
        self.line_width = line_width
        self.fill_color = fill_color
        self.size = size

    def _draw(self, rc, draw):
        ''''Internal draw method, used by the rendering contet.'''
        self._draw_waypoints(rc, draw)
        self._draw_points(rc, draw)

    def _draw_waypoints(self, rc, draw):
        if not self.waypoints:
            return

        xy = [rc.to_pixels(lat, lon) for lat, lon in self.waypoints]
        draw.line(xy,
            fill=self.line_color,
            width=self.line_width,
            joint='curve'
        )

    def _draw_points(self, rc, draw):
        if not self.points:
            return

        symbols = {
            'dot': self._dot,
            'square': self._square,
            'triangle': self._triangle,
        }

        # attempt to open a font
        try:
            font = ImageFont.truetype(font='DejaVuSans.ttf', size=12)
        except OSError:
            font = None

        for pt in self.points:
            lat, lon, sym, label = pt
            x, y = rc.to_pixels(lat, lon)
            brush = symbols.get(sym, self._dot)
            brush(draw, x, y)

            if label:
                # place label below marker
                loc = (x, y + self.size / 2 + 2)
                draw.text(loc, label,
                    font=font,
                    anchor='ma',  # middle ascender
                    fill=(0, 0, 0, 255),
                    stroke_width=1,
                    stroke_fill=(255, 255, 255, 255),
                )

    def _dot(self, draw, x, y):
        d = self.size / 2
        xy = [x-d, y-d, x+d, y+d]
        draw.ellipse(xy,
            fill=self.fill_color,
            outline=self.line_color,
            width=self.line_width
        )

    def _square(self, draw, x, y):
        d = self.size / 2
        xy = [x-d, y-d, x+d, y+d]
        draw.rectangle(xy,
            fill=self.fill_color,
            outline=self.line_color,
            width=self.line_width
        )

    def _triangle(self, draw, x, y):
        '''Draw a triangle with equally sized sides and the center point on the XY location.'''
        h = self.size
        angle = radians(60.0)  # all angles are the same

        # Formula for the Side
        # b = h / sin(alpha)
        side = h / sin(angle)

        top = (x, y - h / 2)
        left = (x - side / 2, y + h / 2)
        right = (x + side / 2, y + h / 2)

        draw.polygon([top, right, left],
            fill=self.fill_color,
            outline=self.line_color,
            # width=self.line_width  # not supported with ploygon
        )

    @classmethod
    def for_track(cls, waypoints, color=(0, 0, 0, 255), width=1):
        return cls(waypoints, None, color, width, None, None)

    @classmethod
    def for_points(cls, points, color=(0, 0, 0, 255), fill=(255, 255, 255, 255), border=0, size=4):
        return cls(None, points, color, border, fill, size)


# Rendering -------------------------------------------------------------------


class RenderContext:
    '''Renders a map, downloading required tiles on the fly.'''

    def __init__(self, service, map, overlays=None, reporter=None):
        self._service = service
        self._map = map
        self._overlays = overlays or []
        self._report = reporter or _no_reporter
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

        px = lambda v: int(ceil(v))

        return px(frac_x * w), px(frac_y * h)

    def _draw_overlays(self):
        draw = ImageDraw.Draw(self._img, mode='RGBA')
        for layer in self._overlays:
            layer._draw(self, draw)

    def _crop(self):
        '''Crop the map image to the bounding box.'''
        bbox = self._map.bbox
        left, bottom = self.to_pixels(bbox.minlat, bbox.minlon)
        right, top = self.to_pixels(bbox.maxlat, bbox.maxlon)

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

    @classmethod
    def user_dir(cls, service):
        cache_dir = appdirs.user_cache_dir(appname=APP_NAME, appauthor=__author__)
        return cls(service, cache_dir)

if __name__ == '__main__':
    sys.exit(main())
