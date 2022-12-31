__version__ = '1.5.2'
__author__ = 'akeil'

from .core import Map
from .geo import BBox

from .icons import IconProvider

from .tilemap import Tile, tile_bounds, tile_location, tile_number

from .service import TileService
