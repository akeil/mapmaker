'''Data structure for map definitions.

Can be read from an .ini file:

.. code:: ini

    [map]
    zoom = 10
    style = osm
    # Define the BBox either with pos0/pos1 or with pos0/radius
    pos0 = 47.44, 10.95
    pos1 = 47.37, 11.13
    radius = 10 km
    aspect = 16:9
    margin = 50, 25, 25, 25
    background = #ffffff

    [frame]
    width       = 5
    # colors can be defined with rgba values or as hex strings
    color       = 0, 0, 0, 255
    alt_color   = #ffffff
    style       = coordinates

    [scale]
    placement       = SW
    color           = 0, 0, 0, 255
    border_width    = 2
    underlay        = compact
    label_style     = default
    font_size       = 10
    font_name       =

    [compass]
    placement = SW
    color = 0, 0, 0
    outline  = 255, 255, 255
    marker = False

    [title]
    # Optional, settings for the map title
    text            = My Map
    area            = MARGIN
    placement       = N
    color           = #ff0000
    border_width    = 1
    border_color    = #909090
    background      = #909090FF
    font_name       = DejaVuSans
    font_size       = 16

    [comment]
    # Optional, comment
    text            = This is an example map
    area            = MARGIN
    placement       = S
    color           = #000000
    border_width    = 0
    border_color    =
    background      =
    font_name       =
    font_size       = 10
'''
import configparser
from dataclasses import dataclass

from . import parse
from .core import Map
from .decorations import Cartouche, Scale, CompassRose
from .geo import BBox


_BLACK = (0, 0, 0, 255)
_WHITE = (255, 255, 255, 255)
_DEFAULT_FONT = 'DejaVuSans'


@dataclass
class TextParams:

    text: str
    area: str
    placement: str
    border_width: int = 0
    color: tuple[int, int, int, int] = (0, 0, 0, 255)
    border_color: tuple[int, int, int, int] = (0, 0, 0, 255)
    background: tuple[int, int, int, int] = None
    font_name: str = None
    font_size: int = None

    def as_decoration(self):
        # TODO check all args present
        return Cartouche(self.text,
                         placement=self.placement,
                         color=self.color,
                         background=self.background,
                         border_width=self.border_width,
                         border_color=self.border_color,
                         font_size=self.font_size,
                         font_name=self.font_name)

    @classmethod
    def _from_config(cls, cfg, section):
        return cls(text=cfg.get(section, 'text'),
                   area=cfg.get(section, 'area'),
                   placement=cfg.get(section, 'placement'),
                   border_width=cfg.getint(section, 'border_width'),
                   color=_parsed(cfg, section, 'color', parse.color),
                   border_color=_parsed(cfg, section, 'border_color', parse.color),
                   background=_parsed(cfg, section, 'background', parse.color),
                   font_name=cfg.get(section, 'font_name'),
                   font_size=cfg.getint(section, 'font_size'))


@dataclass
class ScaleParams:
    placement: str = 'SW'
    color: tuple[int, int, int, int] = (0, 0, 0, 255)
    border_width: int = 2
    underlay: str = 'compact'
    label_style: str = 'default'
    font_size: int = 10
    font_name: str = None

    def as_decoration(self):
        return Scale(placement=self.placement,
                     color=self.color,
                     border_width=self.border_width,
                     underlay=self.underlay,
                     label_style=self.label_style,
                     font_size=self.font_size,
                     font_name=self.font_name or _DEFAULT_FONT)

    @classmethod
    def _from_config(cls, cfg, section):
        return cls(placement=cfg.get(section, 'placement'),
                   color=_parsed(cfg, section, 'color', parse.color),
                   border_width=cfg.getint(section, 'border_width'),
                   underlay=cfg.get(section, 'underlay'),
                   label_style=cfg.get(section, 'label_style'),
                   font_size=cfg.getint(section, 'font_size'),
                   font_name=cfg.get(section, 'font_name'))


@dataclass
class FrameParams:
    width: int = 5
    color: tuple[int, int, int, int] = (0, 0, 0, 255)
    alt_color: tuple[int, int, int, int] = None
    style: str = 'solid'

    @classmethod
    def _from_config(cls, cfg, section):
        return cls(width=cfg.getint(section, 'width'),
                   color=_parsed(cfg, section, 'color', parse.color),
                   alt_color=_parsed(cfg, section, 'alt_color', parse.color),
                   style=cfg.get(section, 'style'))


@dataclass
class CompassParams:
    placement: str = 'SW'
    color: tuple[int, int, int, int] = (0, 0, 0, 255)
    outline: tuple[int, int, int, int] = None
    marker: bool = False

    def as_decoration(self):
        return CompassRose(placement=self.placement,
                           color=self.color,
                           outline=self.outline,
                           marker=self.marker)

    @classmethod
    def _from_config(cls, cfg, section):
        return cls(placement=cfg.get(section, 'placement'),
                   color=_parsed(cfg, section, 'color', parse.color),
                   outline=_parsed(cfg, section, 'outline', parse.color),
                   marker=cfg.getboolean(section, 'marker'))


@dataclass
class MapParams:
    # Bounding Box
    # either a single lat/lon + radius
    # or a pair of minlat/minlon or maxlat/maxlon
    pos0: tuple[float, float]
    pos1: tuple[float, float] = None
    radius: float = None

    style: str = None
    zoom: int = None

    aspect: float = None  # calculated from e.g. 16:9
    margin: tuple[int, int, int, int] = None
    background: tuple[int, int, int, int] = (255, 255, 255, 255)
    title: TextParams = None
    comment: TextParams = None
    frame: FrameParams = None
    scale: ScaleParams = None
    compass: CompassParams = None

    def create_map(self):
        self.validate()  # throws
        m = Map(self.bbox)
        m.set_margin(self.margin)
        m.set_background(self.background)
        if self.frame:
            m.set_frame(width=self.frame.width,
                        color=self.frame.color or _BLACK,
                        alt_color=self.frame.alt_color or _WHITE,
                        style=self.frame.style or 'solid')

        if self.scale:
            m.add_decoration('MAP', self.scale.as_decoration())

        if self.compass:
            m.add_decoration('MAP', self.compass.as_decoration())

        # TODO: make sure to apply default values
        if self.title:
            m.add_decoration('MARGIN', self.title.as_decoration())
        if self.comment:
            m.add_decoration('MARGIN', self.comment.as_decoration())

        return m

    def validate(self):
        if self.pos1 is not None and self.radius is not None:
            raise ValueError('Only one of `pos1` and `radius` must be set')

        if self.pos0 is None:
            raise ValueError('Missing `pos0` for BBox')

        if self.pos1 is None and self.radius is None:
            raise ValueError('Missing `pos1` or `radius` for BBox')
        # TODO implement
        # radius >0 or None
        # check bbox in valid range
        # check zoom in valid range
        pass

    @property
    def bbox(self):
        if not self.pos0:
            raise ValueError('missing point 0 for bbox')

        bbox = None
        lat0, lon0 = self.pos0
        if self.pos1:
            # prefer two-coordinate setup
            lat1, lon1 = self.pos1
            bbox = BBox(minlat=lat0, minlon=lon0, maxlat=lat1, maxlon=lon1)
        elif self.radius:
            bbox = BBox.from_radius(lat0, lon0, self.radius)
        else:
            raise ValueError('missing either point 1 or radius for bbox')

        if self.aspect:
            bbox = bbox.with_aspect(self.aspect)

        return bbox

    @classmethod
    def from_config(cls, cfg):
        defined = [s for s in cfg.sections()]
        if defined:
            s = defined[0]
        else:
            s = cfg.default_section

        title = None
        if 'title' in cfg.sections():
            title = TextParams._from_config(cfg, 'title')

        comment = None
        if 'comment' in cfg.sections():
            comment = TextParams._from_config(cfg, 'comment')

        frame = None
        if 'frame' in cfg.sections():
            frame = FrameParams._from_config(cfg, 'frame')

        scale = None
        if 'scale' in cfg.sections():
            scale = ScaleParams._from_config(cfg, 'scale')

        compass = None
        if 'compass' in cfg.sections():
            compass = CompassParams._from_config(cfg, 'compass')

        return cls(style=_parsed(cfg, s, 'style', str),
                   zoom=_parsed(cfg, s, 'zoom', int),
                   pos0=_parsed(cfg, s, 'pos0', parse.coordinates),
                   pos1=_parsed(cfg, s, 'pos1', parse.coordinates),
                   radius=_parsed(cfg, s, 'radius', parse.distance),
                   aspect=_parsed(cfg, s, 'aspect', parse.aspect),
                   margin=_parsed(cfg, s, 'margin', parse.margin),
                   background=_parsed(cfg, s, 'background', parse.color),
                   frame=frame,
                   scale=scale,
                   compass=compass,
                   title=title,
                   comment=comment)

    @classmethod
    def from_path(cls, path):
        cfg = configparser.ConfigParser()
        cfg.read([path, ])
        return cls.from_config(cfg)

    @classmethod
    def from_file(cls, f):
        cfg = configparser.ConfigParser()
        cfg.read_file(f)
        return cls.from_config(cfg)



def _parsed(cfg, s, k, parsefunc):
    try:
        value = cfg.get(s, k, fallback=None)
    except configparser.NoSectionError:
        value = None

    if value is None or value == '':
        return None
    return parsefunc(value)
