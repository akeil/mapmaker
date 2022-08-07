'''Draw elements on the map content.

Map Elements are additional content such as *Placemarks* or *Tracks* that are
painted over the map content.
They are typically placed using lat/lon coordinates.
'''
from functools import partial
from math import sqrt
from math import floor
from math import radians
from math import sin

from PIL import Image

from .geo import BBox
from .render import load_font
from .render import contrast_color


_BLACK = (0, 0, 0, 255)

# Default layers (z-index) for drawing
BASE_LAYER = 0
TRACK_LAYER = 1
SHAPE_LAYER = 2
MARKER_LAYER = 3
TEXT_LAYER = 4


class DrawLayer:
    '''A DrawLayer is used to draw elements on the map
    using lat/lon coordinates.
    '''

    layer = BASE_LAYER

    def draw(self, rc, draw):
        ''''Internal draw method, used by the rendering context.'''
        raise ValueError('Not implemented')

    def drawables(self):
        return [self, ]


class Track(DrawLayer):
    '''Draw a path along the given list of coordinates (``waypoints``).

    ``color`` and ``width`` control the line that is used to draw the track.

    :waypoints: A list (or iterable) of lat/lon pairs.
    :color:     An RGBA tuple for the color with which to draw the track.
    :width:     The thickness of the line.
    '''

    layer = TRACK_LAYER

    def __init__(self, waypoints, color=None, width=1):
        self.waypoints = waypoints
        self.color = color or _BLACK
        self.width = 1 if width is None else width

    def draw(self, rc, draw):
        xy = [rc.to_pixels(lat, lon) for lat, lon in self.waypoints]
        draw.line(xy,
                  fill=self.color,
                  width=self.width,
                  joint='curve')

    def __repr__(self):
        return '<Track waypoints=%d color=%s>' % (len(self.waypoints),
                                                  self.color)


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

    You can omit ``symbol`` to draw only the ``label`` and vice-versa.
    If you omit both, nothing will be drawn.
    '''

    DOT = 'dot'
    SQUARE = 'square'
    TRIANGLE = 'triangle'

    SYMBOLS = ('dot', 'square', 'triangle')

    layer = MARKER_LAYER

    def __init__(self, lat, lon,
                 symbol='dot',
                 label=None,
                 color=None,
                 fill=None,
                 border=0,
                 size=4,
                 font_name=None,
                 font_size=10,
                 label_color=None,
                 label_bg=None):
        self.lat = lat
        self.lon = lon
        # Marker
        self.symbol = symbol
        self.color = color or _BLACK
        self.fill = fill
        # TODO: make sure border !=0 if "color" is set?
        self.border = border or 0
        self.size = 4 if size is None else size
        # Label
        self.label = label
        self.font_name = font_name or 'DejaVuSans.ttf'
        self.font_size = font_size or 10
        self.label_color = label_color or _BLACK
        self.label_bg = label_bg
        self.padding = (2, 4, 2, 4)  # padding between text and box

    def drawables(self):
        all = []

        if self.size and self.symbol:
            if self.symbol in Placemark.SYMBOLS:
                marker = Symbol(self.lat, self.lon, self.symbol,
                                color=self.color,
                                fill=self.fill,
                                border=self.border,
                                size=self.size)
            else:
                marker = Icon(self.lat, self.lon, self.symbol,
                              color=self.color,
                              fill=self.fill,
                              border=self.border,
                              size=self.size)
            all.append(marker)

        if self.label:
            offset=(0, (self.size + self.border) // 2 + 2)  # draw label slightly below marker
            label = Label(self.lat, self.lon, self.label,
                          offset=offset,
                          color=self.label_color,
                          fill=self.label_bg,
                          border=self.border,
                          font_name=self.font_name,
                          font_size=self.font_size)
            all.append(label)

        return all

    def __repr__(self):
        return '<Placemark lat=%s, lon=%s, symbol=%r, label=%r>' % (
            self.lat, self.lon, self.symbol, self.label)


class Symbol(DrawLayer):
    '''Draw a symbol on the map.'''

    layer = MARKER_LAYER

    def __init__(self, lat, lon, symbol,
                 color=None,
                 fill=None,
                 border=0,
                 size=None):
        self.lat = lat
        self.lon = lon
        self.symbol = symbol
        self.color = color or _BLACK
        self.fill = fill
        self.border = border or 0
        self.size = 4 if size is None else size

    def draw(self, rc, draw):
        x, y = rc.to_pixels(self.lat, self.lon)

        brushes = {
            Placemark.DOT: self._draw_dot,
            Placemark.SQUARE: self._draw_square,
            Placemark.TRIANGLE: self._draw_triangle,
        }
        brush = brushes[self.symbol]
        brush(draw, x, y)

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

    def __repr__(self):
        return '<Symbol lat=%s, lon=%s, symbol=%r>' % (
            self.lat, self.lon, self.symbol)


class Icon(DrawLayer):
    '''Draw a named icon that can be loaded by an IconProivder.'''

    layer = MARKER_LAYER

    def __init__(self, lat, lon, name,
                 color=None,
                 fill=None,
                 border=0,
                 size=None):
        self.lat = lat
        self.lon = lon
        self.name = name
        self.color = color or _BLACK
        self.fill = fill
        self.border = border or 0
        self.size = 4 if size is None else size

    def draw(self, rc, draw):
        x, y = rc.to_pixels(self.lat, self.lon)
        # flat background "behind" the icon
        if self.fill:
            #self._draw_background(draw, x, y)
            self._draw_glow(draw, x, y)

        # icon is a PILImage
        icon = rc.get_icon(self.name, width=self.size, height=self.size)

        # Place the icon centered over location
        offset = self.size // 2
        pos = (x - offset, y - offset)

        draw.bitmap(pos, icon, fill=self.color)

    def _draw_glow(self, draw, x, y):
        '''draw a radial gradient behind the icon.

        The gradient is painted in the ``fill`` color with opacity from 1.0
        at the center to 0.0 on the edges.
        This creates a "glow" behind the icon.
        '''
        # Image.radial_gradient creates a gradient from black to white at 256x256
        # where only the outermost pixel (at the corners) are completely white
        # https://pillow.readthedocs.io/en/stable/reference/Image.html
        #
        # So this WILL NOT work
        #
        # grad = Image.radial_gradient('L')
        # mask = ImageOps.invert(grad).resize(size)

        # The "glow area" is a fair bit larger than the icon.
        s = int(self.size * 1.8)
        size = (s, s)

        # Create a gradient mask from white (center) to black (edges)
        mask = Image.new('L', size, color=0)
        for px in range(s):
            for py in range(s):
                # get the distance from current pos to center
                a = (s / 2) - px
                b = (s / 2) - py
                # a² + b² = c²
                c = sqrt(a**2 + b**2)

                # relative distance
                distance = c / (s / 2)

                # from 255/white at the center to 0/black at the edges
                value = 255 - int(floor(255 * distance))
                mask.putpixel((px, py), value)

        mask.save('mask.png')
        # place centered over location
        pos = (
            x - (s // 2),
            y - (s // 2)
        )
        print('Draw glow at', pos, 'with color', self.fill)
        draw.bitmap(pos, mask, fill=self.fill)

    def _draw_background(self, draw, x, y):
        '''Draw a solid circular background behind the icon.'''
        s = (self.size // 2)
        s = int(s * 1.4)  # slightly larger than the icon
        box = [
            x - s,  # x0
            y - s,  # y0
            x + s,  # x1
            y + s,  # y1
        ]
        draw.ellipse(box,
                     fill=self.fill,
                     outline=self.color,
                     width=self.border)

    def __repr__(self):
        return '<Icon lat=%s, lon=%s, name=%r>' % (
            self.lat, self.lon, self.name)


class Label(DrawLayer):
    '''Draw a text label on the map.

    The label is drawn with its anchor at the specified location.
    You can specify an ``offset`` in pixels to draw the label some distance
    away from the lat/lon location.
    '''
    _STROKE_WITH = 2

    layer = TEXT_LAYER
    anchor = 'ma'  # middle ascender

    def __init__(self, lat, lon, text,
                 offset=None,
                 color=None,
                 fill=None,
                 border=0,
                 font_name=None,
                 font_size=10):
        self.lat = lat
        self.lon = lon
        self.text = text
        self.offset = offset or (0, 0)
        self.color = color or _BLACK
        self.fill = fill
        self.border = border or 0
        self.font_name = font_name or 'DejaVuSans.ttf'
        self.font_size = font_size or 10
        self.padding = (2, 4, 2, 4)  # padding between text and box

    def draw(self, rc, draw):
        x, y = rc.to_pixels(self.lat, self.lon)
        # apply offset
        offset = self.offset or (0, 0)
        x += offset[0]
        y += offset[1]
        loc = (x, y)

        text = self.text.strip()
        font = load_font(self.font_name, self.font_size)

        stroke_width = 0  # do not use stroke_width w/o stroke_fill (looks bad)
        stroke_fill = None

        if self.fill or self.border:
            self._draw_background(draw, loc, text, font)
        else:
            stroke_width = Label._STROKE_WITH
            stroke_fill = contrast_color(self.color)

        self._draw_text(draw, loc, text, font, stroke_width, stroke_fill)


    def _draw_text(self, draw, loc, text, font, stroke_width, stroke_fill):
        '''Draw the label.'''
        draw.text(loc, text,
                  font=font,
                  anchor=self.anchor,
                  fill=self.color,
                  stroke_width=stroke_width,
                  stroke_fill=stroke_fill)

    def _draw_background(self, draw, loc, text, font):
        '''Draw a rectangle as the background for the label.'''
        px, py = loc
        box = None

        try:
            box = font.getbbox(text,
                               anchor=self.anchor,
                               stroke_width=0)
            box = (px + box[0] - 1,
                   py + box[1] - 1,
                   px + box[2] - 1,
                   py + box[3] - 1)
        except AttributeError:
            # the fallback font cannot calculate a bbox
            # fallback will not be rendered at "anchor"
            tw, th = font.getsize(text, stroke_width=0)
            box = (px,
                   py,
                   px + tw,
                   py + th)

        # pad the box
        padding = self.padding or (0, 0, 0, 0)
        pad_top, pad_right, pad_bottom, pad_left = padding
        box = (box[0] - pad_left,
               box[1] - pad_top,
               box[2] + pad_right,
               box[3] + pad_bottom)

        draw.rectangle(box,
                       fill=self.fill,
                       outline=self.color,
                       width=1)

    def __repr__(self):
        return '<Label lat=%s, lon=%s, label=%r>' % (
            self.lat, self.lon, self.label)


class Box(DrawLayer):
    '''Draw a rectangular box on the map as defined by the given bounding box.

    ``color`` and ``width`` control the border, ``fill`` determines the fill
    color (box will not be filled if *None*).

    Style can be ``Box.REGULAR`` for a normal rectangle
    or ``Box.BRACKET`` for painting only the "edges" of the box.

    :bbox:  a *BoundingBox* with the box that should be drawn.
    :color: Border color for the box, RGBA tuple.
    :fill:  Fill color for the box, RGBA tuple. If *None*, only the outline
            is drawn.
    :width: The thickness of the outline border.
    :style: The type of box to be drawn, see above.
    '''

    REGULAR = 'regular'
    BRACKET = 'bracket'

    layer = SHAPE_LAYER

    def __init__(self, bbox,
                 color=None,
                 fill=None,
                 width=1,
                 style=None):
        self.bbox = bbox
        self.style = style or Box.REGULAR
        self.color = color or _BLACK
        self.fill = fill
        self.width = 1 if width is None else width

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
                       width=self.width)

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
                       width=0)

    def __repr__(self):
        return '<Box bbox=%s, style=%r>' % (self.bbox, self.style)


class Circle(DrawLayer):
    '''Draw a circle around a given center in ``lat, lon``
    with a ``radius`` is defined in meters.

    ``color`` and ``width`` control the border, ``fill`` determines the fill
    color (box will not be filled if *None*).

    If ``marker`` is *True*, a small marker is drawn in the center.

    :lat:    Latitude of the center for the circle.
    :lon:    Longitude of the center for the circle.
    :radius: Radius im meters.
    :color:  Outline color, RGBA tuple.
    :fill:   Optional fill color. If *None*, only the outline is drawn.
    :width:  Line width for the outline.
    :marker: If *True*, a small dot is drawn at the center.
    '''

    layer = SHAPE_LAYER

    def __init__(self, lat, lon, radius,
                 color=None,
                 fill=None,
                 width=1,
                 marker=False):
        self.lat = lat
        self.lon = lon
        self.radius = radius
        self.color = color or _BLACK
        self.fill = fill
        self.width = 1 if width is None else width
        self.marker = marker

    def draw(self, rc, draw):
        bbox = BBox.from_radius(self.lat, self.lon, self.radius)
        xy = [
            rc.to_pixels(bbox.maxlat, bbox.minlon),
            rc.to_pixels(bbox.minlat, bbox.maxlon),
        ]

        draw.ellipse(xy,
                     outline=self.color,
                     fill=self.fill,
                     width=self.width)

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

    def __repr__(self):
        return '<Circle lat=%s, lon=%s, radius=%s>' % (
            self.lat, self.lon, self.radius)


class Shape(DrawLayer):
    '''Draw a polygon defined by a list of lat/lon pairs.'''

    layer = SHAPE_LAYER

    def __init__(self, points, color=None, fill=None):
        if len(points) < 3:
            raise ValueError(('points must be a list '
                              'with at least three entries'))

        self.points = points
        self.color = color or _BLACK
        self.fill = fill

    def draw(self, rc, draw):
        xy = [rc.to_pixels(lat, lon) for lat, lon in self.points]
        # TODO: width
        draw.polygon(xy,
                     fill=self.fill,
                     outline=self.color)

    def __repr__(self):
        return '<Polygon points=%d>' % len(self.points)
