#!/bin/python
'''The command line interface for mapmaker.'''


import argparse
from collections import namedtuple
import configparser
import io
from pathlib import Path
from pkg_resources import resource_stream
import sys

from . import __author__
from . import __version__
from .core import Map
from .geo import distance
from . import geojson
from . import icons
from . import parse
from .parse import BBoxAction
from .parse import FrameAction
from .parse import MarginAction
from .parse import TextAction
from .service import Cache
from .service import TileService

import appdirs


APP_NAME = 'mapmaker'
APP_DESC = 'Create map images from tile servers.'

Config = namedtuple('Config', ('urls'
                               ' keys'
                               ' copyrights'
                               ' cache_limit'
                               ' parallel_downloads'
                               ' icons_base'))


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

    parser.add_argument('--version',
                        action='version',
                        version=__version__,
                        help='Print version number and exit')

    parser.add_argument('bbox',
                        metavar='AREA',
                        action=BBoxAction,
                        nargs=2,
                        help=('Bounding box coordinates. Either two lat,lon'
                              ' pairs ("47.437,10.953 47.374,11.133")'
                              ' or a center point and a radius'
                              ' ("47.437,10.953 4km").'))

    default_dst = 'map.png'
    parser.add_argument('dst',
                        metavar='PATH',
                        nargs='?',
                        default=default_dst,
                        help=('Where to save the generated image'
                              ' (default: %r).') % default_dst)

    def zoom(raw):
        v = int(raw)
        if v < 0 or v > 19:
            raise ValueError('Zoom value must be in interval 0..19')
        return v

    default_zoom = 8
    parser.add_argument('-z', '--zoom',
                        default=default_zoom,
                        type=zoom,
                        help=('Zoom level (0..19), higher means more detailed'
                              ' (default: %s).') % default_zoom)

    default_style = 'osm'
    parser.add_argument('-s', '--style',
                        choices=styles,
                        default=default_style,
                        help='Map style (default: %r)' % default_style)

    parser.add_argument('-a', '--aspect',
                        type=parse.aspect,
                        default=1.0,
                        help=(
                            'Aspect ratio (e.g. "16:9") for the generated map.'
                            ' Extends the bounding box to match the given'
                            ' aspect ratio.'))

    parser.add_argument('--copyright',
                        action='store_true',
                        help='Add copyright notice')

    parser.add_argument('--title',
                        action=TextAction,
                        metavar='ARGS',
                        help=('Add a title to the map'
                              ' (optional args: PLACEMENT, COLOR, BORDER'
                              ' followed by title string)'))

    parser.add_argument('--comment',
                        action=TextAction,
                        help='Add a comment to the map')

    parser.add_argument('--margin',
                        action=MarginAction,
                        default=(0, 0, 0, 0),
                        help=('Add a margin (white space) around the map'
                              ' ("TOP RIGHT BOTTOM LEFT" or "ALL")'))

    parser.add_argument('--background',
                        type=parse.color,
                        metavar='RGBA',
                        default=(255, 255, 255, 255),
                        help=('Background color for map margin'
                              ' (default: white)'))

    parser.add_argument('--frame',
                        action=FrameAction,
                        metavar='ARGS',
                        help=('Draw a frame around the map area'
                              ' (any of: WIDTH, COLOR, ALT_COLOR and STYLE)'))

    # TODO: placement, color, marker "N"
    parser.add_argument('--compass',
                        action='store_true',
                        help='Draw a compass rose on the map')

    parser.add_argument('--geojson',
                        nargs='+',
                        help=('Draw GeoJSON elements on the map.'
                              ' Path or JSON string'))

    parser.add_argument('--gallery',
                        action='store_true',
                        help=(
                            'Create a map image for each available style.'
                            ' WARNING: generates a lot of images.'))

    parser.add_argument('--dry-run',
                        action='store_true',
                        help='Show map info, do not download tiles')

    parser.add_argument('--silent',
                        action='store_true',
                        help='Do not output messages to the console')

    args = parser.parse_args()

    reporter = _no_reporter if args.silent else _print_reporter
    bbox = args.bbox.with_aspect(args.aspect)

    reporter('Using configuration from %r', str(conf_file))

    try:
        if args.gallery:
            base = Path(args.dst)
            base.mkdir(exist_ok=True)
            for style in styles:
                dst = base.joinpath(style + '.png')
                try:
                    _run(bbox, args.zoom, dst, style, reporter, conf, args,
                         dry_run=args.dry_run)
                except Exception as err:
                    # on error, continue with next service
                    reporter('ERROR for %r: %s', style, err)
        else:
            _run(bbox, args.zoom, args.dst, args.style, reporter, conf, args,
                 dry_run=args.dry_run)
    except Exception as err:
        reporter('ERROR: %s', err)
        raise
        return 1

    return 0


def _run(bbox, zoom, dst, style, report, conf, args, dry_run=False):
    '''Build the tilemap, download tiles and create the image.'''
    map = Map(bbox)
    map.set_background(args.background)
    map.set_margin(*args.margin)
    if args.frame:
        map.set_frame(width=args.frame.width or 5,
                      color=args.frame.color or (0, 0, 0, 255),
                      alt_color=args.frame.alt_color or (255, 255, 255, 255),
                      style=args.frame.style or 'solid')
    if args.title:
        placement, border, color, bg_color, text = args.title
        map.add_title(text,
                      placement=placement or 'N',
                      color=color or (0, 0, 0, 255),
                      background=bg_color,
                      border_color=color or (0, 0, 0, 255),
                      border_width=border or 0,
                      font_name='DejaVuSans',
                      font_size=16)
    if args.comment:
        placement, border, color, bg_color, text = args.comment
        map.add_comment(text,
                        placement=placement or 'SSE',
                        color=color or (0, 0, 0, 255),
                        background=bg_color,
                        border_color=color or (0, 0, 0, 255),
                        border_width=border or 0,
                        font_name='DejaVuSans',
                        font_size=10)

    if args.compass:
        map.add_compass_rose()

    if args.geojson:
        for x in args.geojson:
            elem = geojson.read(x)
            map.add_element(elem)

    service = TileService(style, conf.urls[style], conf.keys)
    cache_dir = appdirs.user_cache_dir(appname=APP_NAME, appauthor=__author__)
    service = Cache(service, cache_dir, limit=conf.cache_limit)

    if args.copyright:
        copyright = conf.copyrights.get(service.top_level_domain)
        map.add_comment(copyright, placement='ENE', font_size=8)

    if dry_run:
        return

    img = map.render(service,
                     zoom,
                     icons=icons.IconProvider(conf.icons_base),
                     parallel_downloads=8,
                     reporter=report)
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

    # built-in defaults
    cfg.readfp(io.TextIOWrapper(resource_stream('mapmaker', 'default.ini')))

    # user settings
    cfg.read([path, ])

    parallel = cfg.getint('mapmaker', 'parallel_downloads', fallback=1)

    icons_base = cfg.get('icons', 'base', fallback=None)
    if icons_base:
        icons_base = Path(icons_base)
        # TODO: check is_abs, only join if relative
        data_dir = Path(appdirs.user_data_dir(appname=APP_NAME))
        icons_base = data_dir.joinpath(icons_base)

    return Config(urls={k: v for k, v in cfg.items('services')},
                  keys={k: v for k, v in cfg.items('keys')},
                  copyrights={k: v for k, v in cfg.items('copyright')},
                  cache_limit=cfg.getint('cache', 'limit', fallback=None),
                  parallel_downloads=parallel,
                  icons_base=icons_base)


if __name__ == '__main__':
    sys.exit(main())
