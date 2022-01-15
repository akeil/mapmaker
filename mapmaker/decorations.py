from collections import defaultdict
from math import floor

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from .geo import decimal
from .geo import dms

# draw with pixels ------------------------------------------------------------

# Placment locations on the MAP and MARGIN area.
PLACEMENTS = (
    'NW', 'NNW', 'N', 'NNE', 'NE',
    'WNW', 'W', 'WSW',
    'ENE', 'E', 'ESE',
    'SW', 'SSW', 'S', 'SSE', 'SE',
    'C',
)
_NORTHERN = ('NW', 'NNW', 'N', 'NNE', 'NE')
_SOUTHERN = ('SW', 'SSW', 'S', 'SSE', 'SE')
_WESTERN = ('NW', 'WNW', 'W', 'WSW', 'SW')
_EASTERN = ('NE', 'ENE', 'E', 'ESE', 'SE')

class Composer:
    '''Compose a fully-fledged map with additional elements into an image.

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

    MAP = 'MAP'
    MARGIN = 'MARGIN'

    _SLOTS = {
        'MAP': (
            'NW', 'N', 'NE',
            'W', 'C', 'E',
            'SW', 'S', 'SE',
        ),
        'MARGIN': (
            'NW', 'NNW', 'N', 'NNE', 'NE',
            'WNW', 'W', 'WSW',
            'ENE', 'E', 'ESE',
            'SW', 'SSW', 'S', 'SSE', 'SE',
        ),
    }

    def __init__(self, rc):
        self._rc = rc
        self._margins = (0, 0, 0, 0)
        self._frame = None
        self._decorations = defaultdict(list)
        self.background = (255, 255, 255, 255)

    def build(self):
        '''Create the map image including decorations.'''
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

        # add decorations for different areas
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

    def add_decoration(self, area, decoration):
        '''Add a decoration to the given map area.

        ``area is one of ``MAP`` or ``MARGIN``,
        ``decoration`` must be a subclass of ``Decoration``.

        The decoration must specify its *placement* slot and the slot must be
        valid for the selected *area*.
        '''
        try:
            if decoration.placement not in self._SLOTS[area]:
                raise ValueError('invalid area/placement %r' % area)
        except (KeyError, AttributeError):
            raise ValueError('invalid area/placement %r' % area)

        # TODO validate decoration.placement w/ placements for area
        self._decorations[area].append(decoration)

    def add_title(self, text, area='MARGIN', placement='N',
        color=(0, 0, 0, 255),
        font_size=16,
        background=None,
        border_width=0,
        border_color=None):
        '''Add a title to the map.

        The title can be surrounded by a box with border and background.
        '''
        self.add_decoration(area, Cartouche(text,
            placement=placement,
            color=color,
            background=background,
            border_width=border_width,
            border_color=border_color,
            font_size=font_size,
        ))

    def add_comment(self, text, area='MARGIN', placement='SSE',
        color=(0, 0, 0, 255),
        background=None,
        font_size=12,
        border_width=0,
        border_color=None):
        '''Add a comment to the map.'''
        self.add_decoration(area, Cartouche(text,
            placement=placement,
            color=color,
            background=background,
            border_width=border_width,
            border_color=border_color,
            font_size=font_size,
        ))

    def add_scale(self):
        deco = Scale()

    def add_compass_rose(self, area='MAP', placement='SE',
        color=(0, 0, 0, 255),
        outline=None,
        marker=False):
        '''Add a compass rose to the map.'''
        self.add_decoration(area, CompassRose(
            placement=placement,
            color=color,
            outline=outline,
            marker=marker,
        ))

    def set_margin(self, *args):
        '''Set the size of the margin, that is the white space around the
        mapped content.
        Note that the margin will be extended automatically if a decoration is
        placed on the MARGIN area.
        '''
        if len(args) == 1 and args[0] is None:
            self._margins = None
            return

        # unpack tuple
        if len(args) == 1:
            if isinstance(args[0], tuple) or isinstance(args[0], list):
                return self.set_margin(*args[0])

        # single value, vertical/horizontal or clockwise
        if len(args) == 1:
            val = args[0]
            m = (val, val, val, val)
        elif len(args) == 2:
            v, h = args
            m = (v, h, v, h)
        elif len(args) == 4:
            m = args
        else:
            raise ValueError('invalid number of arguments, expected 1, 2 or 4 args')

        # force type error and rounding
        m = tuple(int(x) for x in m)

        for x in m:
            if x < 0:
                raise ValueError('margin must not be negative')

        self._margins = m

    def set_background(self, *args):
        '''Set the background color for the map (margin area).
        The color is an RGBA tuple.'''
        if len(args) == 1:
            self.background = args[0]
        elif len(args) == 3:
            self.background = (args[0], args[1], args[2], 255)
        elif len(args) == 4:
            self.background = args
        else:
            raise ValueError('invalid number of arguments, expected 1, 3 or 4 args')

    def set_frame(self, width=5, color=(0, 0, 0, 255), alt_color=(255, 255, 255, 255), style='solid'):
        '''Draw a border around the mapped content
        (between MAP area and MARGIN).

        Set the width to ``0`` to remove the frame.
        '''
        # coordinate markers
        # coordinate labels
        if width < 0:
            raise ValueError('frame width must not be negative')
        elif width == 0:
            self._frame = None
        else:
            self._frame = Frame(
                width=width,
                color=color,
                alt_color=alt_color,
                style=style
            )


class Decoration:
    '''Base class for decorations.

    Subclasses must implement the ``calc_size`` and ``draw`` methods.
    '''

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
        self.border_width = border_width or 0
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

    def __repr__(self):
        return '<Cartouche placement=%r, title=%r>' % (self.placement, self.title)


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

    def __repr__(self):
        return '<CompassRose placement=%r>' % self.placement


class Frame:

    STYLES = ('coordinates', 'solid')

    def __init__(self, width=8, color=(0, 0, 0, 255), alt_color=(255, 255, 255, 255), style='solid'):
        self.width = width
        self.color = color
        self.alt_color = alt_color
        self.style = style

    def draw(self, rc, draw, size):
        if self.style == 'coordinates':
            self._draw_coords(rc, draw, size)
        else:
            self._draw_solid(rc, draw, size)

    def _draw_solid(self, rc, draw, size):
        # bottom right pixel for rectangle is *just outside* xy
        w, h = size
        xy = (0, 0, w - 1, h - 1)
        draw.rectangle(xy, outline=self.color, width=self.width)


    def _draw_coords(self, rc, draw, size):
        crop_left, crop_top, _, _ = rc.crop_box
        top, right, bottom, left = self._tick_coordinates(rc.bbox)
        for which, coords in enumerate((top, bottom)):
            prev_x = self.width
            for i, tick_pos in enumerate(coords):
                # x, y are pixels on the MAP
                # the draw context refers to the size incl. border around the map
                x, y = rc.to_pixels(*tick_pos)
                x -= crop_left
                x += self.width

                y -= crop_top
                if which == 1: # bottom
                    y += self.width

                # "-1" accounts for 1px border
                draw.rectangle([
                    prev_x, y,
                    x - 1, y + self.width - 1],
                    fill=self.color if i % 2 else self.alt_color,
                    outline=self.color,
                    width=1
                )
                prev_x = x

        for which, coords in enumerate((left, right)):
            prev_y = self.width
            for i, tick_pos in enumerate(coords):
                x, y = rc.to_pixels(*tick_pos)

                x -= crop_left
                if which == 1:  # right
                    x += self.width

                y -= crop_top
                y += self.width

                draw.rectangle([
                    x, y - 1,
                    x + self.width - 1, prev_y,],
                    fill=self.color if i % 2 else self.alt_color,
                    outline=self.color,
                    width=1
                )
                prev_y = y

        # draw corners
        w, h = size
        draw.rectangle([0, 0, self.width - 1, self.width - 1], fill=self.color)
        draw.rectangle([w - self.width, 0, w - 1, self.width - 1], fill=self.color)
        draw.rectangle([0, h - self.width, self.width - 1, h - 1], fill=self.color)
        draw.rectangle([w - self.width, h - self.width, w - 1, h - 1], fill=self.color)


    def _tick_coordinates(self, bbox, n=8):
        lon_ticks = self._ticks(bbox.minlon, bbox.maxlon, n=n)
        lon_ticks.append(bbox.maxlon)

        lat_ticks = self._ticks(bbox.minlat, bbox.maxlat, n=n)
        lat_ticks.insert(0, bbox.minlat)

        top = [(bbox.maxlat, lon) for lon in lon_ticks]
        bottom = [(bbox.minlat, lon) for lon in lon_ticks]
        left = [(lat, bbox.minlon) for lat in lat_ticks]
        right = [(lat, bbox.maxlon) for lat in lat_ticks]

        return top, right, bottom, left

    def _ticks(self, start, end, n=8):
        '''Create a list of ticks from start to end so that we have ``n`` ticks
        in total (plus a fraction)
        and the tick values are on full degrees, minutes or seconds if possible.
        '''
        span = end - start
        d, m, s = dms(span)

        steps = []
        if d >= n:
            per_tick = d // n
            n_ticks = floor(span / decimal(d=per_tick))
            steps = [decimal(d=i * per_tick) for i in range(1, n_ticks + 1)]
        elif m >= n:
            per_tick = m // n
            n_ticks = floor(span / decimal(m=per_tick))
            steps = [decimal(m=i * per_tick) for i in range(1, n_ticks + 1)]
        else:
            per_tick = s // n
            n_ticks = floor(span / decimal(s=per_tick))
            steps = [decimal(s=i * per_tick) for i in range(1, n_ticks + 1)]

        ticks = [start + v for v in steps]
        return ticks

    def __repr__(self):
        return '<Frame width=%r, style=%r>' % (self.width, self.style)


def _load_font(font_name, font_size):
    '''Load the given true type font, return fallback on failure.'''
    try:
        return ImageFont.truetype(font=font_name, size=font_size)
    except OSError:
        return ImageFont.load_default()
