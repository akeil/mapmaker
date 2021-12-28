#!/bin/python
import argparse
import base64
from collections import defaultdict
from collections import namedtuple
import configparser
import io
import math
from math import asin, asinh
from math import atan2
from math import ceil
from math import cos
from math import degrees
from math import pi as PI
from math import radians
from math import sin
from math import sqrt
from math import tan
import os
from pathlib import Path
import queue
import sys
import threading
from urllib.parse import urlparse

import appdirs
from PIL import Image, ImageDraw, ImageFont
import requests


__version__ = '1.4.0dev1'
__author__ = 'akeil'

APP_NAME = 'mapmaker'
APP_DESC = 'Create map images from tile servers.'

BRG_NORTH = 0
BRG_EAST = 90
BRG_SOUTH = 180
BRG_WEST = 270
EARTH_RADIUS = 6371.0 * 1000.0

# supported lat bounds for slippy map
MAX_LAT = 85.0511
MIN_LAT = -85.0511

# Most (all?) services will return tiles this size
DEFAULT_TILESIZE = (256, 256)
HILLSHADE = 'hillshading'

_DEFAULT_CONFIG = '''[mapmaker]
parallel_downloads = 8

[services]
# see: https://wiki.openstreetmap.org/wiki/Tile_servers
osm         = https://tile.openstreetmap.org/{z}/{x}/{y}.png
topo        = https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png
human       = http://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png
hillshading = http://tiles.wmflabs.org/hillshading/{z}/{x}/{y}.png
bw          = https://tiles.wmflabs.org/bw-mapnik/{z}/{x}/{y}.png
nolabels    = https://tiles.wmflabs.org/osm-no-labels/{z}/{x}/{y}.png

# Stamen, http://maps.stamen.com/
toner        = https://stamen-tiles-{s}.a.ssl.fastly.net/toner/{z}/{x}/{y}.png
toner-hybrid = https://stamen-tiles-{s}.a.ssl.fastly.net/toner-hybrid/{z}/{x}/{y}.png
toner-bg     = https://stamen-tiles-{s}.a.ssl.fastly.net/toner-background/{z}/{x}/{y}.png
toner-lite   = https://stamen-tiles-{s}.a.ssl.fastly.net/toner-lite/{z}/{x}/{y}.png
watercolor   = https://stamen-tiles-{s}.a.ssl.fastly.net/watercolor/{z}/{x}/{y}.jpg
terrain      = https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}.png
terrain-bg   = https://stamen-tiles-{s}.a.ssl.fastly.net/terrain-background/{z}/{x}/{y}.png

# Carto, https://carto.com/help/building-maps/basemap-list/
voyager            = https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}.png
voyager-nolabel    = https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}.png
positron           = https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png
positron-nolabel   = https://{s}.basemaps.cartocdn.com/rastertiles/light_nolabels/{z}/{x}/{y}.png
darkmatter         = https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png
darkmatter-nolabel = https://{s}.basemaps.cartocdn.com/rastertiles/dark_nolabels/{z}/{x}/{y}.png

# Thunderforest
landscape   = http://tile.thunderforest.com/landscape/{z}/{x}/{y}.png?apikey={api}
outdoors    = http://tile.thunderforest.com/outdoors/{z}/{x}/{y}.png?apikey={api}
atlas       = https://tile.thunderforest.com/atlas/{z}/{x}/{y}.png?apikey={api}

# Geoapify
grey        = https://maps.geoapify.com/v1/tile/osm-bright-grey/{z}/{x}/{y}.png?apiKey={api}
smooth      = https://maps.geoapify.com/v1/tile/osm-bright-smooth/{z}/{x}/{y}.png?apiKey={api}
toner-grey  = https://maps.geoapify.com/v1/tile/toner-grey/{z}/{x}/{y}.png?apiKey={api}
blue        = https://maps.geoapify.com/v1/tile/positron-blue/{z}/{x}/{y}.png?apiKey={api}
red         = https://maps.geoapify.com/v1/tile/positron-red/{z}/{x}/{y}.png?apiKey={api}
brown       = https://maps.geoapify.com/v1/tile/dark-matter-brown/{z}/{x}/{y}.png?apiKey={api}
darkgrey    = https://maps.geoapify.com/v1/tile/dark-matter-dark-grey/{z}/{x}/{y}.png?apiKey={api}
purple      = https://maps.geoapify.com/v1/tile/dark-matter-dark-purple/{z}/{x}/{y}.png?apiKey={api}
klokantech  = https://maps.geoapify.com/v1/tile/klokantech-basic/{z}/{x}/{y}.png?apiKey={api}

# Mapbox
satellite           = https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{z}/{x}/{y}?access_token={api}
satellite-streets   = https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v11/tiles/{z}/{x}/{y}?access_token={api}
streets             = https://api.mapbox.com/styles/v1/mapbox/streets-v11/tiles/{z}/{x}/{y}?access_token={api}
light               = https://api.mapbox.com/styles/v1/mapbox/light-v10/tiles/{z}/{x}/{y}?access_token={api}
dark                = https://api.mapbox.com/styles/v1/mapbox/dark-v10/tiles/{z}/{x}/{y}?access_token={api}
hike                = https://api.mapbox.com/styles/v1/mapbox/outdoors-v11/tiles/{z}/{x}/{y}?access_token={api}

[keys]
tile.thunderforest.com  = <YOUR_API_KEY>
maps.geoapify.com       = <YOUR_API_KEY>
api.mapbox.com          = <YOUR_API_KEY>

[copyright]
openstreetmap.org = \u00A9 OpenStreetMap contributors
openstreetmap.fr = \u00A9 OpenStreetMap contributors
opentopomap.org = \u00A9 OpenStreetMap contributors
wmflabs.org = \u00A9 OpenStreetMap contributors
cartocdn.com = Maps \u00A9 Carto, Data \u00A9 OpenStreetMap contributors
geoapify.com = Powered by Geoapify | \u00A9 OpenStreetMap contributors
thunderforest.com = Maps \u00A9 Thunderforest, Data \u00A9 OpenStreetMap contributors
stamen.com = Maps \u00A9 Stamen Design, Data \u00A9 OpenStreetMap contributors

[cache]
# 256 MB
limit = 256000000
'''

BBox = namedtuple('BBox', 'minlat minlon maxlat maxlon')

Config = namedtuple('Config', 'urls keys copyrights cache_limit parallel_downloads')


# CLI -------------------------------------------------------------------------


def main():
    '''Parse arguments and run the program.'''
    conf_dir = appdirs.user_config_dir(appname=APP_NAME)
    conf_file = Path(conf_dir).joinpath('config.ini')
    conf = read_config(conf_file)
    styles = sorted(x for x in conf.urls.keys())

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
            'Bounding box coordinates. Either two lat,lon pairs'
            ' ("47.437,10.953 47.374,11.133") or a center point'
            ' and a radius ("47.437,10.953 4km").'
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
        type=aspect,
        default=1.0,
        help=(
            'Aspect ratio (e.g. "16:9") for the generated map. Extends the'
            ' bounding box to match the given aspect ratio.'
        ),
    )
    parser.add_argument(
        '--shading',
        action='store_true',
        help='Add hillshading',
    )
    parser.add_argument(
        '--copyright',
        action='store_true',
        help='Add copyright notice',
    )
    # TODO: placement, color and border
    parser.add_argument(
        '--title',
        help='Add a title to the map',
    )
    # TODO: placement, color and border
    parser.add_argument(
        '--comment',
        help='Add a comment to the map',
    )
    # TODO: sizes, background color
    parser.add_argument(
        '--margin',
        action='store_true',
        help='Add a margin (white space) around the map',
    )
    # TODO: color, width
    parser.add_argument(
        '--frame',
        action='store_true',
        help='Draw a frame around the map area',
    )
    # TODO: placement, color, marker "N"
    parser.add_argument(
        '--compass',
        action='store_true',
        help='Draw a compass rose on the map',
    )
    parser.add_argument(
        '--gallery',
        action='store_true',
        help=(
            'Create a map image for each available style.'
            ' WARNING: generates a lot of images.'
        ),
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show map info, do not download tiles',
    )
    parser.add_argument(
        '--silent',
        action='store_true',
        help='Do not output messages to the console',
    )

    args = parser.parse_args()

    reporter = _no_reporter if args.silent else _print_reporter
    bbox = with_aspect(args.bbox, args.aspect)

    reporter('Using configuration from %r', str(conf_file))

    print(bbox)

    try:
        if args.gallery:
            base = Path(args.dst)
            base.mkdir(exist_ok=True)
            for style in styles:
                dst = base.joinpath(style + '.png')
                try:
                    _run(bbox, args.zoom, dst, style, reporter, conf, args,
                        hillshading=args.shading,
                        dry_run=args.dry_run,
                    )
                except Exception as err:
                    # on error, continue with next service
                    reporter('ERROR for %r: %s', style, err)
        else:
            _run(bbox, args.zoom, args.dst, args.style, reporter, conf, args,
                hillshading=args.shading,
                dry_run=args.dry_run,
            )
    except Exception as err:
        reporter('ERROR: %s', err)
        raise
        return 1

    return 0


def _run(bbox, zoom, dst, style, report, conf, args, hillshading=False,
    dry_run=False):
    '''Build the tilemap, download tiles and create the image.'''
    map = TileMap.from_bbox(bbox, zoom)

    service = TileService(style, conf.urls[style], conf.keys)
    service = Cache.user_dir(service, limit=conf.cache_limit)

    rc = RenderContext(service, map,
        reporter=report,
        parallel_downloads=8)

    _show_info(report, service, map, rc)
    if dry_run:
        return

    decorated = Composer(rc)
    if args.margin:
        decorated.add_margin()
    if args.frame:
        decorated.add_frame()
    if args.title:
        decorated.add_title(args.title)
    if args.comment:
        decorated.add_comment(args.comment, font_size=8)
    if args.copyright:
        copyright = conf.copyrights.get(service.top_level_domain)
        decorated.add_comment(copyright, placement='ENE', font_size=8)
    if args.compass:
        decorated.add_compass_rose()

    img = decorated.build()

    if hillshading:
        shading = TileService(HILLSHADE, conf.urls[HILLSHADE], conf.keys)
        shading = Cache.user_dir(shading, limit=conf.cache_limit)
        shade = RenderContext(shading, map, reporter=report, parallel_downloads=conf.parallel_downloads).build()
        img.paste(shade.convert('RGB'), mask=shade)

    with open(dst, 'wb') as f:
        img.save(f, format='png')

    report('Map saved to %s', dst)


class _BBoxAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        # expect one of;
        #
        # A: two lat/lon pairs
        #    e.g. 47.437,10.953 47.374,11.133
        #
        # B: lat/lon and radius
        #    e.g. 47.437,10.953 2km
        try:
            bbox = self._parse_bbox(values)
            setattr(namespace, self.dest, bbox)
        except ValueError as err:
            msg = 'failed to parse bounding box from %r: %s' % (' '.join(values), err)
            raise argparse.ArgumentError(self, msg)

    def _parse_bbox(self, values):
        lat0, lon0 = _parse_coordinates(values[0])

        # simple case, BBox from lat,lon pairs
        if ',' in values[1]:
            lat1, lon1 = _parse_coordinates(values[1])
            bbox = BBox(
                minlat=min(lat0, lat1),
                minlon=min(lon0, lon1),
                maxlat=max(lat0, lat1),
                maxlon=max(lon0, lon1),
            )
        # bbox from point and radius
        else:
            s = values[1].lower()
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

            bbox = _bbox_from_radius(lat0, lon0, value)

        # TODO: clamp to MINLAT / MAXLAT

        # Validate
        if bbox.minlat < MIN_LAT or bbox.minlat > MAX_LAT:
            raise ValueError
        if bbox.maxlat < MIN_LAT or bbox.maxlat > MAX_LAT:
            raise ValueError
        if bbox.minlon < -180.0 or bbox.minlon > 180.0:
            raise ValueError
        if bbox.maxlon < -180.0 or bbox.maxlon > 180.0:
            raise ValueError

        return bbox


def _parse_coordinates(raw):

    def _parse_dms(dms):
        d, remainder = dms.split('°')
        d = float(d)

        m = 0
        if remainder and "'" in remainder:
            m, remainder = remainder.split("'", 1)
            m = float(m)

        s = 0
        if remainder and "''" in remainder:
            s, remainder = remainder.split("''")
            s = float(s)

        if remainder.strip():
            raise ValueError('extra content for DMS coordinates: %r' % remainder)

        # combine + return
        m += s / 60.0  # seconds to minutes
        d += m / 60.0  # minutes to degrees

        return d

    if not raw:
        raise ValueError

    parts = raw.lower().split(',')
    if len(parts) != 2:
        raise ValueError('Expected two values separated by ","')

    a, b = parts

    # Optional N/S and E/W suffix to sign
    # 123 N => 123
    # 123 S => -123
    sign_lat = 1
    sign_lon = 1
    if a.endswith('n'):
        a = a[:-1]
    elif a.endswith('s'):
        a = a[:-1]
        sign_lat = -1

    if b.endswith('e'):
        b = b[:-1]
    elif b.endswith('w'):
        b = b[:-1]
        sign_lon = -1

    # try to parse floats (decimal)
    try:
        lat, lon = float(a), float(b)
    except ValueError:
        # assume DMS
        lat, lon = _parse_dms(a), _parse_dms(b)

    lat, lon = lat * sign_lat, lon * sign_lon
    # check bounds
    if lat < -90.0 or lat > 90.0:
        raise ValueError('latitude must be in range -90.0..90.0')
    if lon < -180.0 or lon > 180.0:
        raise ValueError('longitude must be in range -180.0..180.0')

    return lat, lon


def _parse_color(raw):
    '''Parse an RGBA tuple from a astring in format:

    - R,G,B     / 255,255,255
    - R,G,B,A   / 255,255,255,255
    - RRGGBB    / #aa20ff
    - #RRGGBBAA / #0120ab90
    '''
    if not raw or not raw.strip():
        raise ValueError('invalid color %r' % raw)

    rgba = None
    parts = [p.strip() for p in raw.split(',')]
    if len(parts) == 3:
        r, g, b = parts
        rgba = int(r), int(g), int(b), 255
    elif len(parts) == 4:
        r, g, b, a = parts
        rgba = int(r), int(g), int(b), int(a)

    # Hex value
    if raw.startswith('#') and len(raw) < 10:
        r, g, b = int(raw[1:3], 16), int(raw[3:5], 16), int(raw[5:7], 16)
        if raw[7:9]:
            a = int(raw[7:9], 16)
        else:
            a = 255
        rgba = r, g, b, a

    if not rgba:
        raise ValueError('invalid color %r' % raw)

    for v in rgba:
        if v < 0 or v > 255:
            raise ValueError('invalid color value %s in %r' % (v, raw))
    return rgba



def aspect(raw):
    '''Parse an aspect ratio given in the form of "19:9" into a float.'''
    if not raw:
        raise ValueError('Invalid argument (empty)')

    parts = raw.split(':')
    if len(parts) != 2:
        raise ValueError('Invalid aspect ratio %r, expected format "W:H"' % raw)

    w, h = parts
    w, h = float(w), float(h)
    if w <= 0 or h <= 0:
        raise ValueError

    return w / h


def with_aspect(bbox, aspect):
    '''Extend the given bounding box so that it adheres to the given aspect
    ratio (given as a floating point number).
    Returns a new bounding box with the desired aspect ratio that contains
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


def _bbox_from_radius(lat, lon, radius):
    lat_n, lon_n = _destination_point(lat, lon, BRG_NORTH, radius)
    lat_e, lon_e = _destination_point(lat, lon, BRG_EAST, radius)
    lat_s, lon_s = _destination_point(lat, lon, BRG_SOUTH, radius)
    lat_w, lon_w = _destination_point(lat, lon, BRG_WEST, radius)

    return BBox(
        minlat=min(lat_n, lat_e, lat_s, lat_w),
        minlon=min(lon_n, lon_e, lon_s, lon_w),
        maxlat=max(lat_n, lat_e, lat_s, lat_w),
        maxlon=max(lon_n, lon_e, lon_s, lon_w),
    )


def _print_reporter(msg, *args):
    print(msg % args)


def _no_reporter(msg, *args):
    pass


def _show_info(report, service, map, rc):
    bbox = map.bbox
    area_w = int(_distance(bbox.minlat, bbox.minlon, bbox.maxlat, bbox.minlon))
    area_h = int(_distance(bbox.minlat, bbox.minlon, bbox.minlat, bbox.maxlon))
    unit = 'm'
    if area_w > 1000 or area_h > 1000:
        area_w = int(area_w / 100) / 10
        area_h = int(area_h / 100) / 10
        unit = 'km'

    x0, y0, x1, y1 = rc.crop_box
    w = x1 - x0
    h = y1 - y0
    report('-------------------------------')
    report('Area:        %s x %s %s', area_w, area_h, unit)
    report('Zoom Level:  %s', map.zoom)
    report('Dimensions:  %s x %s px', w, h)
    report('Tiles:       %s', map.num_tiles)
    report('Map Style:   %s', service.name)
    report('URL Pattern: %s', service.url_pattern)
    report('-------------------------------')


def read_config(path):
    '''Read configuration from the given file in .ini format.
    Returns names and url patterns for services and API keys, combined from
    built-in configuration and the specified file.'''
    cfg = configparser.ConfigParser()

    # built-in from code
    cfg.read_string(_DEFAULT_CONFIG)

    # user settings
    cfg.read([path, ])

    return Config(
        urls={k: v for k, v in cfg.items('services')},
        keys={k: v for k, v in cfg.items('keys')},
        copyrights={k: v for k, v in cfg.items('copyright')},
        cache_limit=cfg.getint('cache', 'limit', fallback=None),
        parallel_downloads=cfg.getint('mapmaker', 'parallel_downloads', fallback=1),
    )


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
    if lat <= MIN_LAT or lat >= MAX_LAT:
        raise ValueError('latitude must be %s..%s' % (MIN_LAT, MAX_LAT))

    # taken from https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
    n = math.pow(2.0, zoom)

    x = (lon + 180.0) / 360.0 * n

    if lat == -90:
        y = 0
    else:
        lat_rad = radians(lat)
        a = asinh(tan(lat_rad))
        y = (1.0 - a / PI) / 2.0 * n

    return int(x), int(y)


class DrawLayer:
    '''Keeps data for map overlays.'''

    def __init__(self, waypoints, points, box, shape, line_color=None,
        line_width=None, fill_color=None, size=None):
        self.waypoints = waypoints
        self.points = points
        self.box = box
        self.shape = shape
        self.line_color = line_color
        self.line_width = line_width
        self.fill_color = fill_color
        self.size = size

    def _draw(self, rc, draw):
        ''''Internal draw method, used by the rendering context.'''
        self._draw_points(rc, draw)
        self._draw_shape(rc, draw)

    def _draw_shape(self, rc, draw):
        if not self.shape:
            return

        xy = [rc.to_pixels(lat, lon) for lat, lon in self.shape]
        draw.polygon(xy,
            fill=self.fill_color,
            outline=self.line_color)

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
                    stroke_fill=(255, 255, 255, 255))

    def _dot(self, draw, x, y):
        d = self.size / 2
        xy = [x-d, y-d, x+d, y+d]
        draw.ellipse(xy,
            fill=self.fill_color,
            outline=self.line_color,
            width=self.line_width)

    def _square(self, draw, x, y):
        d = self.size / 2
        xy = [x-d, y-d, x+d, y+d]
        draw.rectangle(xy,
            fill=self.fill_color,
            outline=self.line_color,
            width=self.line_width)

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
            outline=self.line_color)

    @classmethod
    def for_track(cls, waypoints, color=(0, 0, 0, 255), width=1):
        return Track(waypoints, color=color, width=width)

    @classmethod
    def for_points(cls, points, color=(0, 0, 0, 255), fill=(255, 255, 255, 255), border=0, size=4):
        return cls(None, points, None, None,
            line_color=color,
            line_width=border,
            fill_color=fill,
            size=size,
        )

    @classmethod
    def for_box(cls, bbox, color=(0, 0, 0, 255), fill=None, border=1, style=None):
        '''Draw a rectangle for a bounding box.'''
        return Box(bbox, color=color, fill=fill, width=border, style=style)

    @classmethod
    def for_shape(cls, points, color=(0, 0, 0, 255), fill=None):
        '''Draw a closed shape (polygon) with optional fill.

        ``points`` is a list of coordinate pairs with at least three
        coordinates.'''
        if len(points) < 3:
            raise ValueError('points must be a list with at least three entries')

        return cls(None, None, None, points,
            line_color=color,
            fill_color=fill,
        )


class Track(DrawLayer):
    '''Draw a path along the given list of coordinates (``waypoints``).

    ``color`` and ``width`` control the border.
    '''

    def __init__(self, waypoints, color=(0, 0, 0, 255), width=1):
        self.waypoints = waypoints
        self.color = color
        self.width = width

    def _draw(self, rc, draw):
        xy = [rc.to_pixels(lat, lon) for lat, lon in self.waypoints]
        draw.line(xy,
            fill=self.color,
            width=self.width,
            joint='curve'
        )


class Box(DrawLayer):
    '''Draw a rectangular box on the map as defined by the given bounding box.

    ``color`` and ``width`` control the border, ``fill`` determines the fill
    color (box will not be filled if *None*).

    Style can be ``Box.REGULAR`` for a normal rectangle
    or ``Box.BRACKET`` for painting only the "edges" of the box.
    '''

    REGULAR = 'regular'
    BRACKET = 'bracket'

    def __init__(self, bbox, color=(0, 0, 0, 255), fill=None, width=1, style=None):
        self.bbox = bbox
        self.style = style or Box.REGULAR
        self.color = color
        self.fill = fill
        self.width = width

    def _draw(self, rc, draw):
        if self.style == Box.BRACKET:
            self._draw_fill(rc, draw)
            self._draw_bracket(rc, draw)
        else:
            self._draw_regular(rc, draw)

    def _draw_regular(self, rc, draw):
        xy = [
            rc.to_pixels(self.bbox.minlat, self.bbox.minlon),
            rc.to_pixels(self.bbox.maxlat, self.bbox.maxlon),
        ]

        draw.rectangle(xy,
            outline=self.color,
            fill=self.fill,
            width=self.width
        )

    def _draw_bracket(self, rc, draw):
        if not self.color or not self.width:
            return

        left, top = rc.to_pixels(self.bbox.maxlat, self.bbox.minlon)
        right, bottom = rc.to_pixels(self.bbox.minlat, self.bbox.maxlon)

        # make the "arms" of the bracket so that the *shortest* side of the
        # rectangle is 1/2 bracket and 1/2 free:
        w = right - left
        h = bottom - top
        shortest = min(w, h)
        length = shortest // 4

        #  +---      ---+
        #  |            |   ya
        #
        #  |            |   yb
        #  +---      ---+
        #     xa     xb
        xa = left + length
        xb = right - length
        ya = top + length
        yb = bottom - length

        brackets = [
            [left, ya, left, top, xa, top],  # top left bracket
            [xb, top, right, top, right, ya],  # top right bracket
            [right, yb, right, bottom, xb, bottom],  # bottom right bracket
            [xa, bottom, left, bottom, left, yb],  # bottom left bracket
        ]
        for xy in brackets:
            draw.line(xy, fill=self.color, width=self.width)

    def _draw_fill(self, rc, draw):
        if not self.fill:
            return

        xy = [
            rc.to_pixels(self.bbox.minlat, self.bbox.minlon),
            rc.to_pixels(self.bbox.maxlat, self.bbox.maxlon),
        ]

        draw.rectangle(xy,
            outline=None,
            fill=self.fill,
            width=0,
        )


class Circle(DrawLayer):
    '''Draw a circle around a given center in ``lat, lon``
    with a ``radius`` is defined in meters.

    ``color`` and ``width`` control the border, ``fill`` determines the fill
    color (box will not be filled if *None*).

    If ``marker`` is *True*, a small marker is drawn in the center.
    '''

    def __init__(self, lat, lon, radius, color=(0, 0, 0, 255), fill=None, width=1, marker=False):
        self.lat = lat
        self.lon = lon
        self.radius = radius
        self.color = color
        self.fill = fill
        self.width = width
        self.marker = marker

    def _draw(self, rc, draw):
        bbox = _bbox_from_radius(self.lat, self.lon, self.radius)
        xy = [
            rc.to_pixels(bbox.maxlat, bbox.minlon),
            rc.to_pixels(bbox.minlat, bbox.maxlon),
        ]

        draw.ellipse(xy,
            outline=self.color,
            fill=self.fill,
            width=self.width,
        )

        if self.marker:
            center_x, center_y = rc.to_pixels(self.lat, self.lon)
            self._draw_dot(draw, center_x, center_y)

    def _draw_dot(self, draw, x, y):
        r = 2
        xy = [x-r, y-r, x+r, y+r]
        draw.ellipse(xy,
            fill=self.color,
            outline=self.color,
            width=self.width)


class TextLayer:
    '''A map layer which places text on the map.
    The text is relative to the maps *pixel values*.'''

    CENTER = 0
    TOP_LEFT = 1
    TOP_CENTER = 2
    TOP_RIGHT = 3
    CENTER_RIGHT = 4
    BOTTOM_RIGHT = 5
    BOTTOM_CENTER = 6
    BOTTOM_LEFT = 7
    CENTER_LEFT = 8

    _ANCHOR = {
        CENTER: 'mm',
        TOP_LEFT: 'la',
        TOP_CENTER: 'ma',
        TOP_RIGHT: 'ra',
        CENTER_RIGHT: 'rm',
        BOTTOM_LEFT: 'ld',
        BOTTOM_CENTER: 'md',
        BOTTOM_RIGHT: 'rd',
        CENTER_LEFT: 'lm',
    }

    def __init__(self, text, align=CENTER, padding=2, color=None, outline=None, background=None):
        self.text = text
        self.align = align or TextLayer.CENTER
        self.padding = padding or 0
        self.color = color or (0, 0, 0, 255)
        self.outline = outline
        self.background = background

    def _draw(self, rc, draw):
        ''''Internal draw method, used by the rendering context.'''
        if not self.text:
            # erly exit
            return

        try:
            font = ImageFont.truetype(font='DejaVuSans.ttf', size=10)
        except OSError:
            font = ImageFont.load_default()

        text_w, text_h = font.getsize(self.text)
        text_w += 2 * self.padding
        text_h += 2 * self.padding
        left, top, right, bottom = rc.crop_box
        total_w = right - left
        total_h = bottom - top

        x, y = None, None
        rect = [None, None, None, None]

        if self.align in (TextLayer.TOP_LEFT, TextLayer.CENTER_LEFT, TextLayer.BOTTOM_LEFT):
            x = 0
            x_pad = x + self.padding
            rect[0] = 0
            rect[2] = text_w
        elif self.align in (TextLayer.TOP_RIGHT, TextLayer.CENTER_RIGHT, TextLayer.BOTTOM_RIGHT):
            x = total_w
            x_pad = x - self.padding
            rect[0] = total_w - text_w
            rect[2] = total_w
        else:  # CENTER
            x = total_w // 2
            x_pad = x
            rect[0] = x - text_w // 2
            rect[2] = x + text_w // 2

        if self.align in (TextLayer.TOP_LEFT, TextLayer.TOP_CENTER, TextLayer.TOP_RIGHT):
            y = 0
            y_pad = y + self.padding
            rect[1] = 0
            rect[3] = text_h
        elif self.align in (TextLayer.BOTTOM_LEFT, TextLayer.BOTTOM_CENTER, TextLayer.BOTTOM_RIGHT):
            y = total_h
            y_pad = y - self.padding
            rect[1] = total_h - text_h
            rect[3] = total_h
        else:  # CENTER
            y = total_h // 2
            y_pad = y
            rect[1] = y - text_h // 2
            rect[3] = y + text_h // 2

        # apply offset from crop box
        x += left
        y += top
        x_pad += left
        y_pad += top
        rect[0] += left

        rect[1] += top
        rect[2] += left
        rect[3] += top

        if self.background:
            draw.rectangle(rect, fill=self.background)

        draw.text([x_pad, y_pad], self.text,
            font=font,
            anchor=TextLayer._ANCHOR[self.align],
            fill=self.color,
            stroke_width=1,
            stroke_fill=self.outline)


# Rendering -------------------------------------------------------------------


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


# Placments
_NORTHERN = ('NW', 'NNW', 'N', 'NNE', 'NE')
_SOUTHERN = ('SW', 'SSW', 'S', 'SSE', 'SE')
_WESTERN = ('NW', 'WNW', 'W', 'WSW', 'SW')
_EASTERN = ('NE', 'ENE', 'E', 'ESE', 'SE')


class Composer:
    '''Compose a fully-fledged map with additional elements into an image.'''

    def __init__(self, rc):
        self._rc = rc
        self._margins = (0, 0, 0, 0)
        self._frame = None
        self._decorations = defaultdict(list)
        self.background = (255, 255, 255, 255)

    def build(self):
        map_img = self._rc.build()

        map_w, map_h, = map_img.size
        top, right, bottom, left = self._calc_margins((map_w, map_h))
        w = left + map_w + right
        h = top + map_h + bottom

        map_top = top
        map_left = left
        if self._frame:
            map_top += self._frame.width
            map_left += self._frame.width
            w += 2 * self._frame.width
            h += 2 * self._frame.width


        base = Image.new('RGBA', (w, h), color=self.background)

        # add the map content
        map_box = (map_left, map_top, map_left + map_w, map_top + map_h)
        print('Map size:  ', map_w, map_h)
        print('Margins:   ', top, right, bottom, left)
        print('Frame:     ', self._frame.width if self._frame else 0)
        print('Image size:', w, h)
        print('Map Box:   ', map_box)
        base.paste(map_img, map_box)


        # add frame around the map
        frame_box = map_box
        if self._frame:
            frame_w = map_w + 2 * self._frame.width
            frame_h = map_h + 2 *self._frame.width
            frame_size = (frame_w, frame_h)
            frame_box = (left, top, left+frame_w, top + frame_h)

            frame_img = Image.new('RGBA', frame_size, color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(frame_img, mode='RGBA')
            self._frame.draw(self._rc, draw, frame_size)
            base.alpha_composite(frame_img, dest=(left, top))

        for area in ('MAP', 'MARGIN'):
            for deco in self._decorations[area]:
                deco_size = deco.calc_size((map_w, map_h))
                deco_pos = None
                if area == 'MAP':
                    deco_pos = self._calc_map_pos(deco.placement, map_box, deco_size)
                elif area == 'MARGIN':
                    deco_pos = self._calc_margin_pos(deco.placement, (w, h), frame_box, deco_size)

                deco_img = Image.new('RGBA', deco_size, color=(0, 0, 0, 0))
                draw = ImageDraw.Draw(deco_img, mode='RGBA')
                deco.draw(draw, deco_size)

                base.alpha_composite(deco_img, dest=deco_pos)

        return base

    def _calc_margins(self, map_size):

        top, right, bottom, left = 0, 0, 0, 0

        for deco in self._decorations['MARGIN']:
            w, h = deco.calc_size(map_size)
            if deco.placement in _NORTHERN:
                top = max(h, top)
            elif deco.placement in _SOUTHERN:
                bottom = max(h, bottom)

            if deco.placement in _WESTERN:
                left = max(w, left)
            elif deco.placement in _EASTERN:
                right = max(w, right)

        m = self._margins
        return top + m[0], right + m[1], bottom + m[2], left + m[3]

    def _calc_margin_pos(self, placement, img_size, frame_box, deco_size):
        '''Determine the top-left placement for a decoration.'''
        total_w, total_h = img_size
        deco_w, deco_h = deco_size
        frame_left, frame_top, frame_right, frame_bottom = frame_box
        top, right, bottom, left = self._margins

        x, y = None, None

        # top area: y is top margin
        if placement in _NORTHERN:
            # align bottom edge of decoration with top of map/frame
            y = frame_top - deco_h
        elif placement in _SOUTHERN:
            # align top edge of decoration with bottom edge of map/frame
            y = frame_bottom
        elif placement in ('WNW', 'ENE'):
            # align top edge of decoration with top of map/frame
            y = frame_top
        elif placement in ('W', 'E'):
            # W, E. center vertically
            y = total_h // 2 - deco_h // 2
        elif placement in ('WSW', 'ESE'):
            # align bottom edge of decoration with bottom of map/frame
            y = frame_bottom - deco_h
        else:
            raise ValueError('invalid placement %r' % placement)

        if placement in _WESTERN:
            # align right edge of decoration with left edge of frame
            x = frame_left - deco_w
        elif placement in _EASTERN:
            # align left edge of decoration with right edge of frame
            x = frame_right
        elif placement in ('NNW', 'SSW'):
            # align left edge of decoration with left edge of frame
            x = frame_left
        elif placement in ('N', 'S'):
            # center horizontally
            x = total_w // 2 - deco_w // 2
        elif placement in ('NNE', 'SSE'):
            # align right edge of decoration with right edge of frame
            x = frame_right - deco_w
        else:
            raise ValueError('invalid placement %r' % placement)

        return x, y

    def _calc_map_pos(self, placement, map_box, deco_size):
        '''Calculate the top-left placement for a decoration within the map
        content.
        The position referes to the map image.
        '''
        map_left, map_top, map_right, map_bottom = map_box
        map_w = map_right - map_left
        map_h = map_bottom - map_top
        deco_w, deco_h = deco_size

        x, y = None, None

        if placement in ('NW', 'N', 'NE'):
            # align top of decoration wit htop of map
            y = map_top
        elif placement in ('W', 'C', 'E'):
            # center vertically
            y = map_top + map_h // 2 - deco_h // 2
        elif placement in ('SW', 'S', 'SE'):
            # align bottom of decoration to bottom of map
            y = map_bottom - deco_h
        else:
            raise ValueError('invalid placement %r' % placement)

        if placement in ('NW', 'W', 'SW'):
            # align left edge of decortation with left edge of map
            x = map_left
        elif placement in ('N', 'C', 'S'):
            # center vertically
            x = map_left + map_w // 2 - deco_w // 2
        elif placement in ('NE', 'E', 'SE'):
            # align right edges
            x = map_right - deco_w
        else:
            raise ValueError('invalid placement %r' % placement)

        return x, y

    def add_decoration(self, area, decoration):
        if area not in ('MAP', 'MARGIN'):
            raise ValueError('invalid area %r' % area)

        # TODO validate decoration.placement w/ placements for area
        self._decorations[area].append(decoration)

    def add_title(self, text, area='MARGIN', placement='N', color=(0, 0, 0, 255), font_size=16, background=None, border_width=0, border_color=None):
        self.add_decoration(area, Cartouche(text,
            placement=placement,
            color=color,
            border_width=border_width,
            border_color=border_color,
            background=background,
            font_size=font_size,
        ))

    def add_comment(self, text, area='MARGIN', placement='SSE', color=(0, 0, 0, 255), font_size=12):
        self.add_decoration(area, Cartouche(text,
            placement=placement,
            color=color,
            font_size=font_size,
        ))

    def add_scale(self):
        deco = Scale()

    def add_compass_rose(self, area='MAP', placement='SE', color=(0, 0, 0, 255), outline=None, marker=False):
        self.add_decoration(area, CompassRose(
            placement=placement,
            color=color,
            outline=outline,
            marker=marker,
        ))

    def add_margin(self, top=16, right=16, bottom=16, left=16):
        self._margins = (top, right, bottom, left)

    def add_frame(self, width=8, color=(0, 0, 0, 255)):
        # coordinate markers
        # coordinate labels
        self._frame = Frame(width=width, color=color)


class Decoration:
    '''Base class for decorations.'''

    def __init__(self, placement):
        # TODO: validate pos
        self.placement = placement
        self.margin = (4, 4, 4, 4)

    def calc_size(self, map_size):
        raise ValueError('Not implemented')

    def draw(self, draw, size):
        raise ValueError('Not implemented')


class Cartouche(Decoration):

    _MARGIN_MASK = {
        'NW': (1, 1, 1, 1),
        'NNW': (1, 1, 1, 0),
        'N': (1, 1, 1, 1),
        'NNE': (1, 0, 1, 1),
        'NE': (1, 1, 1, 1),
        'ENE': (0, 1, 1, 1),
        'E': (1, 1, 1, 1),
        'ESE': (1, 1, 0, 1),
        'SE': (1, 1, 1, 1),
        'SSE': (1, 0, 1, 1),
        'S': (1, 1, 1, 1),
        'SSW': (1, 1, 1, 0),
        'SW': (1, 1, 1, 1),
        'WSW': (1, 1, 0, 1),
        'W': (1, 1, 1, 1),
        'WNW': (0, 1, 1, 1),
    }

    # on the western and southern sides, rotate by 90^
    _ROTATION = {
        'NW': 0,
        'NNW': 0,
        'N': 0,
        'NNE': 0,
        'NE': 0,
        'ENE': 90,
        'E': 90,
        'ESE': 90,
        'SE': 0,
        'SSE': 0,
        'S': 0,
        'SSW': 0,
        'SW': 0,
        'WSW': 90,
        'W': 90,
        'WNW': 90,
    }

    # [horizontal][vertical]
    # horizontal:
    # - [l]eft
    # - [m]iddle  | ba[s]eline for vertical text
    # - [r]ight
    #
    # vertival:
    # - [t]op or [ascender]
    # - [m]iddle or ba[s]eline
    # - [b]ottom or [d]escender
    _TEXT_ANCHOR = {
        'NW': 'rd',
        'NNW': 'ld',
        'N': 'md',
        'NNE': 'rd',
        'NE': 'ld',
        'ENE': 'la',
        'E': 'lm',
        'ESE': 'ld',
        'SE': 'la',
        'SSE': 'ra',
        'S': 'ma',
        'SSW': 'la',
        'SW': 'ra',
        'WSW': 'rd',
        'W': 'rm',
        'WNW': 'ra',
    }

    def __init__(self, title,
        placement='N',
        color=(0, 0, 0, 255),
        background=None,
        border_width=0,
        border_color=None,
        font_size=12,
    ):
        '''Initialize a Text area.'''
        super().__init__(placement)
        self.title = title
        self.color = color
        self.background = background
        self.border_width = border_width
        self.border_color = border_color
        self.font = 'DejaVuSans.ttf'
        self.font_size = font_size
        self.padding = (4, 8, 4, 8)

    def calc_size(self, map_size):
        if not self.title or not self.title.strip():
            return 0, 0

        font = _load_font(self.font, self.font_size)

        # TODO: use ImageDraw.textbox() instead?
        w, h = font.getsize(self.title)
        m_top, m_right, m_bottom, m_left = self.margin
        p_top, p_right, p_bottom, p_left = self.padding

        w += m_left + m_right + p_left + p_right
        h += m_top + m_bottom + p_top + p_bottom

        w += self.border_width * 2
        h += self.border_width * 2

        return w, h

    def draw(self, draw, size):
        if not self.title or not self.title.strip():
            return

        w, h = size
        font = _load_font(self.font, self.font_size)

        # adjust margins for proper alignment with frame
        # TODO: this belongs into calc_margin_pos
        mask = self._MARGIN_MASK[self.placement]
        masked_margins = [v * m for v, m in zip(self.margin, mask)]
        m_top, m_right, m_bottom, m_left = masked_margins
        p_top, p_right, p_bottom, p_left = self.padding

        # border/decoration
        draw.rectangle([m_left, m_top, w - m_right - 1, h - m_bottom - 1],
            fill=self.background,
            outline=self.border_color or self.color,
            width=self.border_width
        )
        # text
        anchor = self._TEXT_ANCHOR[self.placement]
        x = {
            'l': 0 + p_left + m_left,
            'm': w // 2,
            's': w // 2,
            'r': w - p_right - m_right,
        }[anchor[0]]
        y = {
            't': 0 + p_top + m_top,
            'a': 0 + p_top + m_top,
            'm': h // 2,
            's': h // 2,
            'b': h - p_bottom - m_bottom,
            'd': h - p_bottom - m_bottom,
        }[anchor[1]]
        draw.text((x, y), self.title,
            font=font,
            anchor=anchor,
            fill=self.color,
            #stroke_width=1,
            #stroke_fill=(255, 0, 0, 255),
        )


class Scale:

    def __init__(self):
        self.placement = 'SW'
        self.anchor = 'bottom left'

    def draw(self):
        pass


class CompassRose(Decoration):

    def __init__(self, placement='SE', color=(0, 0, 0, 255), outline=None, marker=False):
        super().__init__(placement)
        self.color = color
        self.outline = outline
        self.marker = marker

        self.font = 'DejaVuSans.ttf'  # for Marker ("N")
        self.margin = (12, 12, 12, 12)

    def calc_size(self, map_size):
        map_w, map_h = map_size
        w = int(map_w * 0.05)
        h = int(map_h * 0.1)

        m_top, m_right, m_bottom, m_left = self.margin
        w += m_left + m_right
        h += m_top + m_bottom

        return w, h

    def draw(self, draw, size):
        # basic arrow
        #        a
        #       /\
        #     /   \
        #   /      \    <-- head
        # b ---  --- c
        #    d| |e
        #     | |       <- tail
        #     |_|
        #   f  i  g
        w, h = size
        m_top, m_right, m_bottom, m_left = self.margin
        w -= m_left + m_right
        h -= m_top + m_bottom

        # subtract vertical space for "N" marker
        font = None
        marker_pad = 0
        marker_h = 0
        if self.marker:
            font_size = size[1] // 5
            font = _load_font(self.font, self.font_size)
            marker_w, marker_h = font.getsize('N')
            marker_pad = marker_h // 16  # padding between marker and arrowhead
            h -= marker_h
            h -= marker_pad

        head_h = h // 2.2
        tail_h = h - head_h
        tail_w = w // 4

        ax = w // 2
        ay = 0

        bx = 0
        by = head_h
        by += (head_h // 4)  # pull down the outer points of the arrow
        cx = w
        cy = by

        dx = w // 2 - tail_w // 2
        dy = head_h
        ex = w // 2 + tail_w // 2
        ey = head_h

        fx = tail_w
        fx -= tail_w // 6  # make the base of the tail a bit wider
        fy = h
        gx = w - tail_w
        gx += tail_w // 6  # make the base of the tail a bit wider
        gy = fy

        ix = w // 2
        iy = h
        iy -= tail_h // 3  # pull base line inwards

        points = [
            (ax, ay),
            (cx, cy),
            (ex, ey),
            (gx, gy),
            (ix, iy),
            (fx, fy),
            (dx, dy),
            (bx, by),
        ]
        x_offset = m_left
        y_offset = m_top + marker_h + marker_pad
        draw.polygon([(x + x_offset, y + y_offset) for x, y in points],
            fill=self.color,
            outline=self.outline,
        )

        if self.marker:
            w, h = size
            x = w // 2
            y = m_top
            draw.text((x, y), 'N',
                font=font,
                anchor='mt',
                fill=self.color,
                stroke_width=1,
                stroke_fill=self.outline,
            )


class Frame:

    def __init__(self, width=8, color=(0, 0, 0, 255)):
        self.width = width
        self.color = color
        # TODO: style, color(s)

    def draw(self, rc, draw, size):
        # simple one-color border
        # bottom right pixel for rectangle is *just outside* xy
        w, h = size
        xy = (0, 0, w - 1, h - 1)
        draw.rectangle(xy, outline=self.color, width=self.width)


def _load_font(font_name, font_size):
    '''Load the given true type font, return fallback on failure.'''
    try:
        return ImageFont.truetype(font=font_name, size=font_size)
    except OSError:
        return ImageFont.load_default()


# Tile Service ----------------------------------------------------------------


class TileService:

    def __init__(self, name, url_pattern, api_keys):
        self.name = name
        self.url_pattern = url_pattern
        self._api_keys = api_keys or {}

    @property
    def top_level_domain(self):
        parts = self.domain.split('.')
        # TODO: not quite correct, will fail e.g. for 'foo.co.uk'
        return '.'.join(parts[-2:])

    @property
    def domain(self):
        parts = urlparse(self.url_pattern)
        return parts.netloc

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
        return self._api_keys.get(self.domain, '')


class Cache:

    def __init__(self, service, basedir, limit=None):
        self._service = service
        self._base = Path(basedir)
        self._limit = limit
        self._lock = threading.Lock()

    @property
    def name(self):
        return self._service.name

    @property
    def url_pattern(self):
        return self._service.url_pattern

    @property
    def top_level_domain(self):
        return self._service.top_level_domain

    @property
    def domain(self):
        return self._service.domain

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
                        except Exception:
                            # Errors if we encounter unexpected filenames
                            pass

        except FileNotFoundError:
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

        self._vacuum()

    def _clean(self, tile, current):
        '''Remove outdated cache entries for a given tile.'''
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

    def _vacuum(self):
        '''Trim the cache up to or below the limit.
        Deletes older tiles before newer ones.'''
        if not self._limit:
            return

        with self._lock:
            used = 0
            entries = []
            for base, dirname, filenames in os.walk(self._base):
                for filename in filenames:
                    path = Path(base).joinpath(filename)
                    stat = path.stat()
                    used += stat.st_size
                    entries.append((stat.st_ctime, stat.st_size, path))

            excess = used - self._limit
            if excess <= 0:
                return

            # delete some additional entries to avoid frequent deletes
            excess *= 1.1

            entries.sort()  # oldest first
            for _, size, path in entries:
                path.unlink()
                excess -= size
                if excess <= 0:
                    break

    @classmethod
    def user_dir(cls, service, limit=None):
        cache_dir = appdirs.user_cache_dir(appname=APP_NAME, appauthor=__author__)
        return cls(service, cache_dir, limit=limit)


if __name__ == '__main__':
    sys.exit(main())
