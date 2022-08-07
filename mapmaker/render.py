from collections import defaultdict
import io
from math import ceil
from math import sqrt
import queue
import threading

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


# Most (all?) services will return tiles this size
DEFAULT_TILESIZE = (256, 256)


class MapBuilder:
    '''Renders map content, downloading required tiles on the fly.

    ``service`` is an instance of ``TileService`` and is used to obtain the map
    tiles.
    ``map`` is a ``TileMap`` which describes the mapped area.

    Optional ``overlay`` is a list of map elements.

    ``icons`` is an _IconProvider_ from the ``icons`` module.
    '''

    def __init__(self, service, map,
                 overlays=None,
                 icons=None,
                 parallel_downloads=None,
                 reporter=None):
        self._service = service
        self._map = map
        self._overlays = overlays or []
        self._icons = icons
        self._parallel_downloads = parallel_downloads or 1
        self._report = reporter or _no_reporter
        # State that is created during `build()`
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

    def get_icon(self, name, width=None, height=None):
        '''Returns a named icon (from the ``IconProvider``) as a PIL image.

        The image is an RGBA that can be used as a mask to draw the icon.

        Used by drawable elements or decorations to obtain an icon
        by name.

        If width and height is given, the icon is resized to that dimensions.
        '''
        if not self._icons:
            raise LookupError('No icon provider set for this MapBuilder')

        icon_data = self._icons.get(name, width=width, height=height)
        return Image.open(io.BytesIO(icon_data))

    def build(self):
        '''Download tiles on the fly and render them into a PIL image.'''
        # fill the task queue
        self._stitch()

        self._report('Download complete, create map image')

        if self._overlays:
            self._report('Draw %d overlays', len(self._overlays))
            self._draw_overlays()

        self._crop()
        return self._img

    def _draw_overlays(self):
        '''Draw overlay layers on the map image.'''
        drawables = []
        for elem in self._overlays:
            drawables += elem.drawables()

        # sort by layer
        # if an element does not specifiy a layer index, assume "0"
        def layer(obj):
            z = getattr(obj, 'layer', 0)
            try:
                z = int(z)
            except TypeError:
                z = 0

            return z

        drawables.sort(key=layer)

        # For transparent overlays, we cannot paint directly on the image.
        # Instead, paint on a separate overlay image and compose the results.

        # TODO: optimize? do not create a new Image for each element?
        for drawable in drawables:
            overlay = Image.new('RGBA', self._img.size, color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay, mode='RGBA')
            drawable.draw(self, draw)
            self._img.alpha_composite(overlay)

    def _crop(self):
        '''Crop the map image to the bounding box.'''
        self._img = self._img.crop(self.crop_box)

    def _stitch(self):
        '''Fetch map tiles and combine them to a single map image.'''
        for tile in self._map.tiles.values():
            self._queue.put(tile)

        self._total_tiles = self._queue.qsize()
        self._report('Download %d tiles (parallel downloads: %d)',
                     self._total_tiles,
                     self._parallel_downloads)

        # start parallel downloads
        for w in range(self._parallel_downloads):
            threading.Thread(daemon=True, target=self._work).run()

        self._queue.join()

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

    def __repr__(self):
        return '<MapBuilder>'


# placement slots on the map MARGIN
_NORTHERN = ('NW', 'NNW', 'N', 'NNE', 'NE')
_SOUTHERN = ('SW', 'SSW', 'S', 'SSE', 'SE')
_WESTERN = ('NW', 'WNW', 'W', 'WSW', 'SW')
_EASTERN = ('NE', 'ENE', 'E', 'ESE', 'SE')


class Composer:
    '''Builds a fully-fledged map with additional decorations into an image.

    The ``add_xxx`` methods add decorations (e.g. title or compass rose) to the
    map.
    Decorations can be placed on the ``MAP`` area or on the ``MARGIN`` area
    beside the map.

    Within each area, decorations are placed in predefined slots::

        +------------------------------+
        |                              |
        |  NW      NNW  N  NNE    NE   |
        |       +--------------+       |
        |  WNW  |  NW   N  NE  |  ENE  |
        |       |              |       |
        |  W    |  W    C  E   |  E    |
        |       |              |       |
        |  WSW  |  SW   S  SE  |  ESE  |
        |       +--------------+       |
        |  SW      SSW  S  SSE    SE   |
        |                              |
        +------------------------------+

    There are 9 slots within the MAP and 12 slots on the MARGIN.
    '''

    def __init__(self, map_builder,
                 margin=None,
                 frame=None,
                 decorations=None,
                 background=None):
        '''Set up a decorated map based on the given ``MapBuilder`` with added
        ``frame`` around the map, additional whitespace ``margin`` and a
        ``background`` color.

        Decorations can be specified using a dict with entries for ``MAP``
        and ``MARGIN`` and lists with decorations for each placement area.
        '''
        self._map_builder = map_builder
        self._margins = margin or (0, 0, 0, 0)
        self._frame = frame
        self._decorations = decorations or defaultdict(list)
        self._background = background or (255, 255, 255, 255)

    def build(self):
        '''Create the map image including decorations.'''
        map_img = self._map_builder.build()

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

        base = Image.new('RGBA', (w, h), color=self._background)

        # add the map content
        map_box = (map_left, map_top, map_left + map_w, map_top + map_h)
        base.paste(map_img, map_box)

        # add frame around the map
        frame_box = map_box
        if self._frame:
            frame_w = map_w + 2 * self._frame.width
            frame_h = map_h + 2 * self._frame.width
            frame_size = (frame_w, frame_h)
            frame_box = (left, top, left+frame_w, top + frame_h)

            frame_img = Image.new('RGBA', frame_size, color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(frame_img, mode='RGBA')
            self._frame.draw(self._map_builder, draw, frame_size)
            base.alpha_composite(frame_img, dest=(left, top))

        # add decorations for different areas
        for area in ('MAP', 'MARGIN'):
            for deco in self._decorations[area]:
                deco_size = deco.calc_size((map_w, map_h))
                deco_pos = None
                if area == 'MAP':
                    deco_pos = self._calc_map_pos(deco.placement,
                                                  map_box,
                                                  deco_size)
                elif area == 'MARGIN':
                    deco_pos = self._calc_margin_pos(deco.placement,
                                                     (w, h),
                                                     frame_box,
                                                     deco_size)

                deco_img = Image.new('RGBA', deco_size, color=(0, 0, 0, 0))
                draw = ImageDraw.Draw(deco_img, mode='RGBA')
                deco.draw(draw, deco_size)

                base.alpha_composite(deco_img, dest=deco_pos)

        return base

    def _calc_margins(self, map_size):
        '''Calculate the margins, including the space required for decorations.
        '''
        # TODO: optio to keep left and right margins the same size

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

    def __repr__(self):
        return '<Composer>'


def _no_reporter(*args):
    pass


def load_font(font_name, font_size):
    '''Load the given true type font, return fallback on failure.'''
    try:
        return ImageFont.truetype(font=font_name, size=font_size)
    except OSError:
        return ImageFont.load_default()


def is_dark(color):
    '''Tell if the given color is dark.'''
    # https://alienryderflex.com/hsp.html
    r, g, b = color[0], color[1], color[2]
    brightness = sqrt(0.299 * r * r + 0.587 * g * g + 0.114 * b * b)
    # _, _, brightness = colorsys.rgb_to_hsv(r, g, b)

    return brightness <= 127


def contrast_color(color):
    alpha = 255
    if len(color) == 4:
        alpha = color[3]

    if is_dark(color):
        return (255, 255, 255, alpha)
    else:
        return (0, 0, 0, alpha)
