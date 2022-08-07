from collections import defaultdict

from .tilemap import TileMap
from .render import MapBuilder
from .render import Composer
from .decorations import Cartouche, CompassRose, Frame


class Map:
    '''Holds the map definition and allows to render the map into an image.

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

    There are 9 slots within the ``MAP`` and 12 slots on the ``MARGIN``.
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

    def __init__(self, bbox):
        # Map content
        self.bbox = bbox
        self.elements = []
        # Decorations
        self._margin = None
        self._frame = None
        self._decorations = defaultdict(list)
        self._background = (255, 255, 255, 255)

    @property
    def _has_decorations(self):
        if self._margin and sum(self._margin):
            return True

        return self._decorations or self._frame

    def render(self, service, zoom, icons=None, parallel_downloads=None, reporter=None):
        '''Render this map into a PIL image.

        Uses the given *TileService* and zoom level to obtain map tiles.
        '''
        tiles = TileMap.from_bbox(self.bbox, zoom)

        builder = MapBuilder(service, tiles,
                             overlays=self.elements,
                             icons=icons,
                             parallel_downloads=parallel_downloads,
                             reporter=reporter)

        if self._has_decorations:
            builder = Composer(builder,
                               margin=self._margin,
                               frame=self._frame,
                               background=self._background,
                               decorations=self._decorations)

        return builder.build()

    def add_element(self, element):
        self.elements.append(element)

    def add_decoration(self, area, decoration):
        '''Add a decoration to the given map area.

        ``area is one of ``MAP`` or ``MARGIN``,
        ``decoration`` must be a subclass of ``Decoration``.

        The decoration must specify its *placement* slot and the slot must be
        valid for the selected *area*.
        '''
        try:
            if decoration.placement not in Map._SLOTS[area]:
                raise ValueError('invalid area/placement %r' % area)
        except (KeyError, AttributeError):
            raise ValueError('invalid area/placement %r' % area)

        self._decorations[area].append(decoration)

    def add_title(self, text,
                  area='MARGIN',
                  placement='N',
                  color=(0, 0, 0, 255),
                  font_size=16,
                  font_name=None,
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
                                            font_name=font_name))

    def add_comment(self, text,
                    area='MARGIN',
                    placement='SSE',
                    color=(0, 0, 0, 255),
                    background=None,
                    font_size=12,
                    font_name=None,
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
                            font_name=font_name))

    def add_scale(self):
        pass
        # TODO: implement
        # deco = Scale()

    def add_compass_rose(self,
                         area='MAP',
                         placement='SE',
                         color=(0, 0, 0, 255),
                         outline=None,
                         marker=False):
        '''Add a compass rose to the map.'''
        self.add_decoration(area, CompassRose(placement=placement,
                                              color=color,
                                              outline=outline,
                                              marker=marker))

    def set_margin(self, *args):
        '''Set the size of the margin, that is the white space around the
        mapped content.
        Note that the margin will be extended automatically if a decoration is
        placed on the MARGIN area.
        '''
        if len(args) == 1 and args[0] is None:
            self._margin = None
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
            raise ValueError(('invalid number of arguments,'
                              ' expected 1, 2 or 4 args'))

        # force type error and rounding
        m = tuple(int(x) for x in m)

        for x in m:
            if x < 0:
                raise ValueError('margin must not be negative')

        self._margin = m

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
            raise ValueError(('invalid number of arguments,'
                              ' expected 1, 3 or 4 args'))

    def set_frame(self,
                  width=5,
                  color=(0, 0, 0, 255),
                  alt_color=(255, 255, 255, 255),
                  style='solid'):
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

    def __repr__(self):
        return '<Map bbox=%s>' % self.bbox
