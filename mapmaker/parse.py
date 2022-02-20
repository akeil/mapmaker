import argparse
from argparse import ArgumentError
from collections import namedtuple

from .geo import BBox
from .geo import decimal
from .tilemap import MIN_LAT, MAX_LAT
from .decorations import PLACEMENTS
from .decorations import Frame


class BBoxAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        # expect one of;
        #
        # A: two lat/lon pairs
        #    e.g. 47.437,10.953 47.374,11.133
        #
        # B: lat/lon and radius
        #    e.g. 47.437,10.953 2km
        try:
            box = bbox(values)
            setattr(namespace, self.dest, box)
        except ValueError as err:
            raise ArgumentError(self, ('failed to parse bounding box from'
                                       ' %r: %s') % (' '.join(values), err))


def bbox(values):
    '''Parse a bounding box from a pair of coordinates or from a single
    coordinate and a redius.

    1. two lat lon pairs::

        ["47.437,10.953", "47.374,11.133"]

    2. single coordinate and radius::

        ["47.437,10.953", "2km"]

    If successful, returns a ``BBox`` object.
    Raises *ValueError* on failure.
    '''
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

        bbox = BBox.from_radius(lat0, lon0, value)

    # constrain to min/max values of slippy tile map
    bbox = bbox.constrained(minlat=MIN_LAT, maxlat=MAX_LAT)

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


class MarginAction(argparse.Action):

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
    if isinstance(raw, str):
        if ',' in raw:
            values = raw.split(',')
        else:
            values = raw.split()  # whitespace
    else:  # assume list of ints
        values = raw

    # handle different variatnes vor "values"
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


class TextAction(argparse.Action):
    '''Parse title or comment arguments.
    Expect three "formal" arguments:

    - placement (e.g. NW or S)
    - border (integer value)
    - color (RGBA tuple, comma separated)

    Followed by at least one "free form" argument which constitutes the actual
    title string.
    '''

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs must None")

        super().__init__(option_strings, dest, nargs='+', **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):

        placement, border, foreground, background = None, None, None, None

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

            if foreground is None:
                try:
                    foreground = color(value)
                    consumed += 1
                    continue
                except ValueError:
                    pass

            if background is None:
                try:
                    background = color(value)
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

        params = (placement, border, foreground, background, text)
        setattr(namespace, self.dest, params)


FrameParams = namedtuple('FrameParams', 'width color alt_color style')


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
            raise ValueError("nargs must None")

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

        # apply defaults
        if self.default:
            d_width, d_color, d_alt_color, d_style = self.default
            width = d_width if width is None else width
            primary = d_color if primary is None else primary
            alternate = d_alt_color if alternate is None else alternate
            style = d_style if style is None else style

        setattr(namespace, self.dest, FrameParams(
            width=width,
            color=primary,
            alt_color=alternate,
            style=style))


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


def color(raw):
    '''Parse an RGBA tuple from a string in format:

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


def _parse_placement(raw):
    '''Parse a placement (e.g. "N", "SE" or "WSW") from a string.'''
    if not raw:
        raise ValueError('invalid value for placement %r' % raw)

    v = raw.strip().upper()
    if v in PLACEMENTS:
        return v

    raise ValueError('invalid value for placement %r' % raw)


def aspect(raw):
    '''Parse an aspect ratio given in the form of "19:9" into a float.'''
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
