#!/bin/python
'''The command line interface for mampmaker.'''
import argparse
from collections import namedtuple
import configparser
from pathlib import Path
import sys

from . import __author__
from . import __version__
from .decorations import Composer
from .geo import distance
from .geo import with_aspect
from .parse import aspect
from .parse import parse_color
from .parse import BBoxAction
from .parse import FrameAction
from .parse import MarginAction
from .parse import TextAction
from .service import Cache
from .service import TileService
from .tilemap import RenderContext
from .tilemap import TileMap

import appdirs


APP_NAME = 'mapmaker'
APP_DESC = 'Create map images from tile servers.'


Config = namedtuple('Config', 'urls keys copyrights cache_limit parallel_downloads')


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
        action=BBoxAction,
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
    parser.add_argument(
        '--title',
        action=TextAction,
        metavar='ARGS',
        help='Add a title to the map (optional args: PLACEMENT, COLOR, BORDER followed by title string)',
    )
    parser.add_argument(
        '--comment',
        action=TextAction,
        help='Add a comment to the map',
    )
    parser.add_argument(
        '--margin',
        action=MarginAction,
        default=(0, 0, 0, 0),
        help='Add a margin (white space) around the map ("TOP RIGHT BOTTOM LEFT" or "ALL")',
    )
    parser.add_argument(
        '--background',
        type=parse_color,
        metavar='RGBA',
        default=(255, 255, 255, 255),
        help='Background color for map margin (default: white)'
    )
    parser.add_argument(
        '--frame',
        action=FrameAction,
        metavar='ARGS',
        help='Draw a frame around the map area (any of: WIDTH, COLOR, ALT_COLOR and STYLE)',
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

    decorated = Composer(rc)
    decorated.set_background(args.background)
    decorated.set_margin(*args.margin)
    if args.frame:
        width, color, alt_color, style = args.frame
        decorated.set_frame(
            width=width or 5,
            color=color or (0, 0, 0, 255),
            alt_color=alt_color or (255, 255, 255, 255),
            style=style or 'solid'
        )
    if args.title:
        placement, border, color, bg_color, text = args.title
        decorated.add_title(
            text,
            placement=placement or 'N',
            color=color or (0, 0, 0, 255),
            background=bg_color,
            border_color=color or (0, 0, 0, 255),
            border_width=border or 0,
        )
    if args.comment:
        placement, border, color, bg_color, text = args.comment
        decorated.add_comment(
            text,
            placement=placement or 'SSE',
            color=color or (0, 0, 0, 255),
            background=bg_color,
            border_color=color or (0, 0, 0, 255),
            border_width=border or 0,
        )
    if args.copyright:
        copyright = conf.copyrights.get(service.top_level_domain)
        decorated.add_comment(copyright, placement='ENE', font_size=8)
    if args.compass:
        decorated.add_compass_rose()

    if dry_run:
        return
    img = decorated.build()

    if hillshading:
        shading = TileService(HILLSHADE, conf.urls[HILLSHADE], conf.keys)
        shading = Cache.user_dir(shading, limit=conf.cache_limit)
        shade = RenderContext(shading, map, reporter=report, parallel_downloads=conf.parallel_downloads).build()
        img.paste(shade.convert('RGB'), mask=shade)

    with open(dst, 'wb') as f:
        img.save(f, format='png')

    report('Map saved to %s', dst)


def _print_reporter(msg, *args):
    print(msg % args)


def _no_reporter(msg, *args):
    pass


def _show_info(report, service, map, rc):
    bbox = map.bbox
    area_w = int(distance(bbox.minlat, bbox.minlon, bbox.maxlat, bbox.minlon))
    area_h = int(distance(bbox.minlat, bbox.minlon, bbox.minlat, bbox.maxlon))
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


# TODO: move to file
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


if __name__ == '__main__':
    sys.exit(main())
