'''Helpers for parsing various information from strings.
Intended to be used in conjunction with the Python ``argparse`` module.
'''
import argparse
from argparse import ArgumentError

from .decorations import Frame
from .decorations import PLACEMENTS
from .decorations import Scale
from .geo import decimal
from .mapdef import MapParams
from .mapdef import FrameParams
from .mapdef import TitleParams
from .mapdef import CommentParams
from .mapdef import ScaleParams


class MapParamsAction(argparse.Action):
    '''Create a MapParams object either from an ini-file
    or from a BBox definition'''

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) > 2:
            raise ArgumentError('Maximum number of arguments exceeded')

        p = None
        if len(values) == 1:
            # assume path to ini
            try:
                with open(values[0]) as f:
                    p = MapParams.from_file(f)
            except Exception as err:
                msg = ('could not read map definition from'
                       ' %r: %s') % (values[0], err)
                raise ArgumentError(self, msg)
        else:
            # assume bbox coordinates
            try:
                p = self._with_bbox(values)
            except Exception as err:
                msg = ('failed to parse bounding box from'
                       ' %r: %s') % (' '.join(values), err)
                raise ArgumentError(self, msg)

        setattr(namespace, self.dest, p)

    def _with_bbox(self, values):
        pos0 = coordinates(values[0])
        p = MapParams(pos0)

        # simple case, BBox from lat,lon pairs
        if ',' in values[1]:
            pos1 = coordinates(values[1])
            p.pos1 = pos1
        # bbox from point and radius
        else:
            radius = distance(values[1])
            p.radius = radius

        return p


class MarginAction(argparse.Action):
    '''Parse the settings for the map margin.
    See ``margin()``.'''

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs must None")

        super().__init__(option_strings, dest, nargs='+', **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        try:
            margins = margin(values)
            setattr(namespace, self.dest, margins)
        except ValueError as err:
            raise ArgumentError(self, str(err))


def margin(raw):
    '''Parse the settings for the margin (the whitespace around the map
    content).

    Expect either a list of integers or a comma-separated string (of integers).
    The list can contain

    - a single value with the margin for all four sides
    - two values with the margins for top/bottom and left/right
    - four values with margins for top, left, bottom, right (clockwise)

    Returns a tuple with margins ``(top, left bottom, right)``.

    Raises *ValueError* for invalid input.
    '''
    if isinstance(raw, str):
        if ',' in raw:
            values = raw.split(',')
        else:
            values = raw.split()  # whitespace
    else:  # assume list of ints
        values = raw

    # handle different variants vor "values"
    if len(values) == 1:
        v = int(values[0])
        margins = v, v, v, v
    elif len(values) == 2:
        vert, hori = values
        margins = int(vert), int(hori), int(vert), int(hori)
    elif len(values) == 4:
        top, right, bottom, left = values
        margins = int(top), int(right), int(bottom), int(left)
    else:
        raise ValueError(('invalid number of arguments (%s) for margin,'
                          ' expected 1, 2, or 4 values') % len(values))

    for v in margins:
        if v < 0:
            raise ValueError(('invalid margin %r, must not be negative') % v)

    return margins


class _TextAction(argparse.Action):
    '''Parse title or comment arguments.
    Expect three "formal" arguments:

    - placement (e.g. NW or S)
    - border (integer value)
    - color (RGBA tuple, comma separated)

    Followed by at least one "free form" argument which constitutes the actual
    title string.
    '''

    _factory = None

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs must be None")

        super().__init__(option_strings, dest, nargs='+', **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        placement, border, fg, bg = None, None, None, None

        consumed = 0
        for value in values:
            if placement is None:
                try:
                    placement = _parse_placement(value)
                    consumed += 1
                    continue
                except ValueError:
                    pass

            if border is None:
                try:
                    border = int(value)
                    if border < 0:
                        msg = ('invalid border width %r,'
                               ' must not be negative' % value)
                        raise ArgumentError(self, msg)

                    consumed += 1
                    continue
                except ValueError:
                    pass

            if fg is None:
                try:
                    fg = color(value)
                    consumed += 1
                    continue
                except ValueError:
                    pass

            if bg is None:
                try:
                    bg = color(value)
                    consumed += 1
                    continue
                except ValueError:
                    pass

            # stop parsing formal parameters
            # as soon as the first "free form" is encountered
            break

        text = ' '.join(values[consumed:])
        if not text:
            msg = 'missing title string in %r' % ' '.join(values)
            raise ArgumentError(self, msg)

        p = self._factory.default()
        p.placement = placement if placement is not None else p.placement
        p.border_width = border if border is not None else p.border_width
        p.color = fg if fg is not None else p.color
        p.border_color = fg if fg is not None else p.border_color
        p.background = bg if bg is not None else p.background
        p.text = text if text is not None else p.text
        setattr(namespace, self.dest, p)


class TitleAction(_TextAction):
    _factory = TitleParams


class CommentAction(_TextAction):
    _factory = CommentParams


class FrameAction(argparse.Action):
    '''Handle parameters for Frame:

    - border width as single integer
    - color as RGB(A) tuple from comma separated string
    - alternate color as RGB(A) tuple
    - style as enumeration

    Arguments can be provided in any order.
    The second argument that specifies a color is the "alt color".

    Can also be invoked with no arguments to set a frame with default values.
    '''

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs must be None")

        super().__init__(option_strings, dest, nargs='*', **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) > 4:
            msg = ('invalid number of arguments (%s) for frame, expected up to'
                   ' four: BORDER, COLOR, ALT_COLOR and STYLE') % len(values)
            raise ArgumentError(self, msg)

        width, primary, alternate, style = None, None, None, None

        # accept values for BORDER, COLOR and STYLE in any order
        # accept each param only once
        # make sure all values are consumed
        unrecognized = []
        for value in values:
            if width is None:
                try:
                    width = int(value)
                    if width < 0:
                        msg = ('invalid width %r,'
                               ' must not be negative') % value
                        raise ArgumentError(self, msg)
                    continue
                except ValueError:
                    pass

            if primary is None:
                try:
                    primary = color(value)
                    continue
                except ValueError:
                    pass

            if alternate is None:
                try:
                    alternate = color(value)
                    continue
                except ValueError:
                    pass

            if style is None:
                if value in Frame.STYLES:
                    style = value
                    continue

            # did not understand "value"
            unrecognized.append(value)

        if unrecognized:
            msg = 'unrecognized frame parameters: %r' % ', '.join(unrecognized)
            raise ArgumentError(self, msg)

        p = FrameParams.default()
        p.width = width if width is not None else p.width
        p.color = primary if primary is not None else p.color
        p.alt_color = alternate if alternate is not None else p.alt_color
        p.style = style if style is not None else p.style
        setattr(namespace, self.dest, p)


class ScaleAction(argparse.Action):
    '''Parse various parameters for the map's scale bar

    - placement (SW, SE, ...)
    - border width (single integer)
    - color (rgba)
    - label ('label' or 'nolabel')
    '''

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs must be None")

        super().__init__(option_strings, dest, nargs='*', **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) > 5:
            msg = ('invalid number of arguments (%s) for frame, expected up to'
                   ' five: PLACEMENT, BORDER, COLOR, LABEL,'
                   ' UNDERLINE') % len(values)
            raise ArgumentError(self, msg)

        place, width, fg_color, label, underlay = None, None, None, None, None

        # accept values for BORDER, COLOR and STYLE in any order
        # accept each param only once
        # make sure all values are consumed
        unrecognized = []
        for value in values:
            if place is None:
                try:
                    place = _parse_placement(value)
                    continue
                except ValueError:
                    pass

            if width is None:
                try:
                    width = int(value)
                    if width < 0:
                        msg = ('invalid width %r,'
                               ' must not be negative') % value
                        raise ArgumentError(self, msg)
                    continue
                except ValueError:
                    # assume this was not the value for width
                    pass

            if fg_color is None:
                try:
                    fg_color = color(value)
                    continue
                except ValueError:
                    # assume it was not the value for color
                    pass

            if label is None:
                if value.lower() in Scale.LABEL_STYLES:
                    label = value.lower()
                    continue

            if underlay is None:
                if value.lower() in Scale.UNDERLAY_STYLES:
                    underlay = value.lower()
                    continue

            # did not understand "value"
            unrecognized.append(value)

        if unrecognized:
            msg = 'unrecognized scale parameters: %r' % ', '.join(unrecognized)
            raise ArgumentError(self, msg)

        p = ScaleParams.default()
        p.placement = place if place is not None else p.placement
        p.border_width = width if width is not None else p.border_width
        p.color = fg_color if fg_color is not None else p.color
        p.label_style = label if label is not None else p.label_style
        p.underlay = underlay if underlay is not None else p.underlay

        setattr(namespace, self.dest, p)


def coordinates(raw):
    '''Parse a pair of lat/lon coordinates.

    Supports the following format:

    - DMS, e.g. 47°25'16'',10°59'07''
    - Decimal, e.g. 47.42111,10.985278

    Lat and Lon must be separated by a comma ",".
    Whitespace is ignored.

    Raises *ValueError* for invalid input.
    '''

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
            msg = 'extra content for DMS coordinates: %r' % remainder
            raise ValueError(msg)

        # combine + return
        return decimal(d=d, m=m, s=s)

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


def distance(raw):
    '''Parse a distance in meters from various formats:

    - 123.45, integer or float
    - 400 m, value and unit
    - 1.5 km, value and unit in km

    Always returns the distance in METERS.
    '''
    if not raw:
        raise ValueError('missing distance value')

    s = raw.lower()
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

    return value


def color(raw):
    '''Parse an RGBA tuple from a string in format:

    - R,G,B     / 255,255,255
    - R,G,B,A   / 255,255,255,255
    - RRGGBB    / #aa20ff
    - #RRGGBBAA / #0120ab90

    Returns a tuple of integers with ``(r, g, b, a)``.

    Raises *ValueError* for invalid input.
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


def _parse_placement(raw):
    '''Parse a placement (e.g. "N", "SE" or "WSW") from a string.'''
    if not raw:
        raise ValueError('invalid value for placement %r' % raw)

    v = raw.strip().upper()
    if v in PLACEMENTS:
        return v

    raise ValueError('invalid value for placement %r' % raw)


def aspect(raw):
    '''Parse an aspect ratio given in the form of "16:9" into a float.

    Raises *ValueError* for invalid input.
    '''
    if not raw:
        raise ValueError('Invalid argument (empty)')

    parts = raw.split(':')
    if len(parts) != 2:
        raise ValueError('invalid aspect %r, expected format "W:H"' % raw)

    w, h = parts
    w, h = float(w), float(h)
    if w <= 0 or h <= 0:
        raise ValueError

    return w / h
