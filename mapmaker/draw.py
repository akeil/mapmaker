'''Draw elements on the map content.

Map Elements are additional content such as *Placemarks* or *Tracks* that are
painted over the map content.
They are typically placed using lat/lon coordinates.
'''


from math import radians
from math import sin

from PIL import Image

from .render import load_font


class DrawLayer:
    '''A DrawLayer is used to draw elements on the map
    using lat/lon coordinates.
    '''

    def draw(self, rc, draw):
        ''''Internal draw method, used by the rendering context.'''
        raise ValueError('Not implemented')


class Track(DrawLayer):
    '''Draw a path along the given list of coordinates (``waypoints``).

    ``color`` and ``width`` control the line that is used to draw the track.
    '''

    def __init__(self, waypoints, color=(0, 0, 0, 255), width=1):
        self.waypoints = waypoints
        self.color = color
        self.width = width

    def draw(self, rc, draw):
        xy = [rc.to_pixels(lat, lon) for lat, lon in self.waypoints]
        draw.line(xy,
            fill=self.color,
            width=self.width,
            joint='curve'
        )


class Placemark(DrawLayer):
    '''Draw a placemark with a ``symbol`` and a ``label`` at the given location.

    ``color`` is the main color used for the outline and the text,
    ``fill`` is the optional fill color.

    Use ``border`` to draw a border around the symbol.

    ``size`` controls the size (in pixels) of the waypoint marker.

    ``symbol`` is the icon that will be drawn on the map. Must be one of
    *dot*,
    *square*
    or +triangle*.
    '''

    DOT = 'dot'
    SQUARE = 'square'
    TRIANGLE = 'triangle'

    def __init__(self, lat, lon, symbol='dot', label=None, color=(0, 0, 0, 255), fill=None, border=0, size=4):
        self.lat = lat
        self.lon = lon
        self.symbol = symbol
        self.label = label
        self.color = color
        self.fill = fill
        self.border = border
        self.size = size

    def draw(self, rc, draw):
        x, y = rc.to_pixels(self.lat, self.lon)

        # draw the marker
        if self.size and self.symbol:
            brush = {
                Placemark.DOT: self._dot,
                Placemark.SQUARE: self._square,
                Placemark.TRIANGLE: self._triangle,
            }[self.symbol]
            brush(draw, x, y)

        # draw the label
        if self.label:
            self._label(draw, x, y)

    def _dot(self, draw, x, y):
        d = self.size / 2
        xy = [x-d, y-d, x+d, y+d]
        draw.ellipse(xy,
            fill=self.fill or self.color,
            outline=self.color,
            width=self.border)

    def _square(self, draw, x, y):
        d = self.size / 2
        xy = [x-d, y-d, x+d, y+d]
        draw.rectangle(xy,
            fill=self.fill or self.color,
            outline=self.color,
            width=self.border)

    def _triangle(self, draw, x, y):
        '''Draw a triangle with equally sized sides and the center point
        on the XY location.
        '''
        h = self.size
        angle = radians(60.0)  # all angles are the same

        # Formula for the Side
        # b = h / sin(alpha)
        side = h / sin(angle)

        top = (x, y - h / 2)
        left = (x - side / 2, y + h / 2)
        right = (x + side / 2, y + h / 2)

        draw.polygon([top, right, left],
            fill=self.fill or self.color,
            outline=self.color)

    def _label(self, draw, x, y):
        font = load_font('DejaVuSans.ttf', 10)
        # place label below marker
        loc = (x, y + self.size / 2 + 2)

        draw.text(loc, self.label,
            font=font,
            anchor='ma',  # middle ascender
            fill=(0, 0, 0, 255),
            stroke_width=1,
            stroke_fill=(255, 255, 255, 255))


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

    def draw(self, rc, draw):
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

    def draw(self, rc, draw):
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


class Shape(DrawLayer):
    '''Draw a polygon defines by a list oif lat/lon pairs.'''

    def __init__(self, points, color=(0, 0, 0, 255), fill=None):
        if len(points) < 3:
            raise ValueError('points must be a list with at least three entries')

        self.points = points
        self.color = color
        self.fill = fill

    def draw(self, rc, draw):
        xy = [rc.to_pixels(lat, lon) for lat, lon in self.points]
        draw.polygon(xy,
            fill=self.fill,
            outline=self.color)
