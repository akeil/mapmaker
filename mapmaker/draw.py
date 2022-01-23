'''Draw elements on the map content.

Map Elements are additional content such as *Placemarks* or *Tracks* that are
painted over the map content.
They are typically placed using lat/lon coordinates.
'''


from math import radians
from math import sin

from PIL import Image

from .render import load_font
from .render import contrast_color


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

    :label:         Text the will be shown on the map.
    :symbol:        The icon that will be drawn on the map. Must be one of
                    *dot*, *square* or *triangle*.
                    Default is "dot", use *None* to omit the icon.
    :border:        If >0, draws a border around the icon.
    :color:         The main color for the icon.
    :fill:          An optional fill color for the icon.
    :size:          Controls the size (in pixels) of the marker.
    :font_name:     Font family to use for the label.
    :font_size:     Font size for the label.
    :label_color:   Text color to use for the label.
    :label_bg:      Background color for the label.
    '''

    DOT = 'dot'
    SQUARE = 'square'
    TRIANGLE = 'triangle'

    def __init__(self, lat, lon, symbol='dot', label=None,
        color=(0, 0, 0, 255), fill=None, border=0, size=4,
        font_name=None, font_size=10, label_color=(0, 0, 0, 255), label_bg=None,
        ):
        self.lat = lat
        self.lon = lon
        # Marker
        self.symbol = symbol
        self.color = color
        self.fill = fill
        self.border = border
        self.size = size
        # Label
        self.label = label
        self.font_name = font_name or 'DejaVuSans.ttf'
        self.font_size = font_size or 10
        self.label_color = label_color
        self.label_bg = label_bg

    def draw(self, rc, draw):
        x, y = rc.to_pixels(self.lat, self.lon)

        # draw the marker
        if self.size and self.symbol:
            brush = {
                Placemark.DOT: self._draw_dot,
                Placemark.SQUARE: self._draw_square,
                Placemark.TRIANGLE: self._draw_triangle,
            }[self.symbol]
            brush(draw, x, y)

        # draw the label
        if self.label:
            self._draw_label(draw, x, y)

    def _draw_dot(self, draw, x, y):
        '''Draw a circular symbol.'''
        d = self.size / 2
        xy = [x-d, y-d, x+d, y+d]
        draw.ellipse(xy,
            fill=self.fill or self.color,
            outline=self.color,
            width=self.border)

    def _draw_square(self, draw, x, y):
        '''Draw a square symbol.'''
        d = self.size / 2
        xy = [x-d, y-d, x+d, y+d]
        draw.rectangle(xy,
            fill=self.fill or self.color,
            outline=self.color,
            width=self.border)

    def _draw_triangle(self, draw, x, y):
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

    def _draw_label(self, draw, x, y):
        '''Draw the label.'''
        font = load_font(self.font_name, self.font_size)
        # place label below marker
        loc = (x, y + self.size / 2 + 2)
        text = self.label.strip()
        anchor = 'ma'  # middle ascender
        text_color = self.label_color or (0, 0, 0, 255)
        stroke_width = 0  # do not use stroke_width w/o stroke_fill (looks bad)
        stroke_fill = None

        # background box or outline around the text
        if self.label_bg:
            self._draw_label_bg(draw, loc, text, font, anchor, stroke_width)
        else:
            stroke_width = 1
            stroke_fill = contrast_color(text_color)

        draw.text(loc, text,
            font=font,
            anchor=anchor,
            fill=text_color,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )

    def _draw_label_bg(self, draw, loc, text, font, anchor, stroke_width):
        '''Draw a rectangle as the background for the label.'''
        px, py = loc
        box = None

        try:
            box = font.getbbox(text, anchor=anchor, stroke_width=stroke_width)
            box = (
                px + box[0] - 1,
                py + box[1] - 1,
                px + box[2] - 1,
                py + box[3] - 1,
            )
        except AttributeError:
            # the fallback font cannot calculate a bbox
            # fallback will not be rendered at "anchor"
            tw, th = font.getsize(text, stroke_width=stroke_width)
            box = (
                px,
                py,
                px + tw,
                py + th,
            )

        # pad the box
        pad = 2
        box = (
            box[0] - pad,
            box[1] - pad,
            box[2] + pad,
            box[3] + pad,
        )

        draw.rectangle(box,
            fill=self.label_bg,
            outline=contrast_color(self.label_bg),
            width=1,
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
