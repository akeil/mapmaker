'''Decorations are graphic elements that are painted over and around the map
content, for example a title or a legend.

Decorations are placed using pixel coordinates.
'''


from math import floor

from .geo import decimal
from .geo import dms
from .render import load_font


# Placment locations on the MAP and MARGIN area.
PLACEMENTS = (
    'NW', 'NNW', 'N', 'NNE', 'NE',
    'WNW', 'W', 'WSW',
    'ENE', 'E', 'ESE',
    'SW', 'SSW', 'S', 'SSE', 'SE',
    'C',
)


class Decoration:
    '''Base class for decorations.

    Subclasses must implement the ``calc_size`` and ``draw`` methods.
    '''

    def __init__(self, placement):
        self.placement = placement
        self.margin = (4, 4, 4, 4)

    def calc_size(self, map_size):
        raise ValueError('Not implemented')

    def draw(self, draw, size):
        raise ValueError('Not implemented')


class Cartouche(Decoration):
    '''Draws a text area either on the map or on the margin.

    The text can have a box with an optional border or background color.
    '''

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
                 font_name=None,
                 font_size=12):
        '''Initialize a Text area.'''
        super().__init__(placement)
        self.title = title
        self.color = color
        self.background = background
        self.border_width = border_width or 0
        self.border_color = border_color
        self.font_name = font_name or 'DejaVuSans'
        self.font_size = font_size
        self.padding = (4, 8, 4, 8)  # padding between text and border

        # TODO: when placed at the edge, add 1px padding towards edge

    def calc_size(self, map_size):
        if not self.title or not self.title.strip():
            return 0, 0

        font = load_font(self.font_name, self.font_size)

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
        font = load_font(self.font_name, self.font_size)

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
                       width=self.border_width)
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
                  fill=self.color)

    def __repr__(self):
        return '<Cartouche placement=%r, title=%r>' % (self.placement,
                                                       self.title)


class Scale:

    def __init__(self):
        self.placement = 'SW'
        self.anchor = 'bottom left'

    def draw(self):
        pass


class CompassRose(Decoration):
    '''Draws a compass rose at the given placement location on the map.

    The "compass" consists of an error pointing north
    and an optional "N" marker at the top of the arrow.
    '''

    def __init__(self,
                 placement='SE',
                 color=(0, 0, 0, 255),
                 outline=None,
                 marker=False):
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
            font = load_font(self.font, self.font_size)
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
                     outline=self.outline)

        if self.marker:
            w, h = size
            x = w // 2
            y = m_top
            draw.text((x, y), 'N',
                      font=font,
                      anchor='mt',
                      fill=self.color,
                      stroke_width=1,
                      stroke_fill=self.outline)

    def __repr__(self):
        return '<CompassRose placement=%r>' % self.placement


class Frame:
    '''Draws a frame around the map content.

    Either a "solid" border or a two-colored border sized according to lat/lon
    coordinates.

    The frame width adds to the total size of the map image.
    '''

    STYLES = ('coordinates', 'solid')

    def __init__(self,
                 width=8,
                 color=(0, 0, 0, 255),
                 alt_color=(255, 255, 255, 255),
                 style='solid'):
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
        _, h = size

        top, right, bottom, left = self._tick_coordinates(rc.bbox)
        for which, coords in enumerate((top, bottom)):
            prev_x = self.width
            for i, tick_pos in enumerate(coords):
                # x, y are pixels on the MAP
                # draw context refers to the size incl. border around the map
                x, y = rc.to_pixels(*tick_pos)
                x -= crop_left
                x += self.width

                y -= crop_top
                if which == 1:  # bottom
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
            prev_y = h - self.width - 1
            for i, tick_pos in enumerate(coords):
                x, y = rc.to_pixels(*tick_pos)

                x -= crop_left
                if which == 1:  # right
                    x += self.width

                y -= crop_top
                y += self.width

                xy = [x,
                      y - 1,
                      x + self.width - 1,
                      prev_y]
                fill = self.color if i % 2 else self.alt_color
                draw.rectangle(xy,
                               fill=fill,
                               outline=self.color,
                               width=1)
                prev_y = y

        self._draw_corners(draw, size)

    def _tick_coordinates(self, bbox, n=5):
        # regular ticks
        lon_ticks = self._ticks(bbox.minlon, bbox.maxlon, n)
        # partial tick for the last segment
        lon_ticks.append(bbox.maxlon)

        lat_ticks = self._ticks(bbox.minlat, bbox.maxlat, n)
        lat_ticks.append(bbox.maxlat)

        top = [(bbox.maxlat, lon) for lon in lon_ticks]
        bottom = [(bbox.minlat, lon) for lon in lon_ticks]
        left = [(lat, bbox.minlon) for lat in lat_ticks]
        right = [(lat, bbox.maxlon) for lat in lat_ticks]

        return top, right, bottom, left

    def _ticks(self, start, end, n):
        '''Create a list of ticks from start to end so that we have ``n`` ticks
        in total (plus a fraction) and the tick values are on full degrees,
        minutes or seconds if possible.
        '''
        span = end - start
        d, m, s = dms(span)
        m_half = m * 2

        print('DMS for ticks', d, m, m_half, s)
        print('N-Ticks:', n)
        print('Span', span)

        steps = []
        if d >= n:
            per_tick = d // n
            n_ticks = floor(span / decimal(d=per_tick))
            steps = [decimal(d=i * per_tick) for i in range(1, n_ticks + 1)]
        elif m >= n:
            per_tick = m // n
            n_ticks = floor(span / decimal(m=per_tick))
            steps = [decimal(m=i * per_tick) for i in range(1, n_ticks + 1)]
        elif m_half >= n:
            per_tick = (m_half // n) / 2
            print('Per Tick', per_tick)
            n_ticks = floor(span / decimal(m=per_tick))
            print('N Ticks', n_ticks)
            steps = [decimal(m=i * per_tick) for i in range(1, n_ticks + 1)]
        else:
            per_tick = s // n
            n_ticks = floor(span / decimal(s=per_tick))
            steps = [decimal(s=i * per_tick) for i in range(1, n_ticks + 1)]

        ticks = [start + v for v in steps]
        return ticks

    def _draw_corners(self, draw, size):
        w, h = size
        width = self.width
        draw.rectangle([0, 0, width - 1, width - 1], fill=self.color)
        draw.rectangle([w - width, 0, w - 1, width - 1], fill=self.color)
        draw.rectangle([0, h - width, width - 1, h - 1], fill=self.color)
        draw.rectangle([w - width, h - width, w - 1, h - 1], fill=self.color)

    def __repr__(self):
        return '<Frame width=%r, style=%r>' % (self.width, self.style)
