'''
Manage *Icons* to b drawn on a map.

Icon sources:

- https://github.com/mapbox/maki
- https://github.com/ideditor/temaki

SVG Icons
Both, *maki* and *temaki* provide icons in SVG format.
``cairosvg`` (https://github.com/Kozea/CairoSVG/)
is used to convert them to PNG which is then rendered onto the map.

The SVG can be scaled to ``width`` and ``height``.

You need to install them by placing them the SVG files under::

    DATA_DIR/icons/maki/
    DATA_DIR/icons/temaki/


TODO
----
support other formats than SVG
'''
import io
from pathlib import Path

import appdirs
import cairosvg
from PIL import Image

from . import __name__ as APP_NAME


class IconProvider:
    '''The IconProvider is responsible for loading icon images by name.

    The provider takes a base directory and expects a list of subdirectories,
    one for each icon set.

    When an icon is requested, the provider looks in each icon set and returns
    the first icon it can find.
    '''

    def __init__(self, base):
        self._base = Path(base)
        self._providers = []
        self._cache = _NoCache()

    def cached(self):
        '''Wrap this *IconProvider* in a memory cache.'''
        self._cache = _MemoryCache()
        return self

    def _discover(self):
        subdirs = [x for x in self._base.iterdir() if x.is_dir()]
        subdirs.sort()
        for base in subdirs:
            self._providers.append(_Provider(base))

    def index(self):
        '''List all available icon names for this provider.'''
        if not self._providers:
            self._discover()

        result = []
        for p in self._providers:
            result += p.index()

        return sorted(set(result))

    def get(self, name, width=None, height=None, color=None):
        '''Loads the image data for the given icon and size.

        The icon is tinted in the given color or black, if no color is given.
        Color must be an RGB(A) tuple or a hex string (e.g. ``#5000ac``).

        Raises LookupError if no icon is found.'''
        color = _rgba(color)
        try:
            return self._cache.get(name, width, height, color)
        except LookupError:
            pass

        if not self._providers:
            self._discover()

        for provider in self._providers:
            try:
                data = provider.get(name, width=width, height=height)
                if color:
                    data = _colorize(data, color)
                self._cache.put(name, width, height, color, data)
                return data
            except LookupError:
                pass

        raise LookupError('No icon found with name %r' % name)

    def __repr__(self):
        return '<IconProvider %s>' % self._base

    @classmethod
    def default(cls):
        '''Set up an *IconProvider* with the default ``DATA_DIR`` as the
        base directory.
        '''
        data_dir = Path(appdirs.user_data_dir(appname=APP_NAME))
        base = data_dir.joinpath('icons')
        return cls(base)


class _Provider:

    def __init__(self, path):
        self._base = Path(path)
        self._prefix = None
        self._suffix = None
        self._ext = '.svg'

    def _icon_path(self, name):
        #filename = self._pattern.format(name=name)
        filename = '{prefix}{name}{suffix}{ext}'.format(
            prefix = self._prefix or '',
            name=name,
            suffix=self._suffix or '',
            ext=self._ext or '')
        return self._base.joinpath(filename)

    def _icon_name(self, path):
        name = path.name
        if self._prefix:
            name = name[len(self._prefix):]
        if self._ext:
            name = name[:-len(self._ext)]
        if self._suffix:
            name = name[:-len(self._suffix)]

        return name

    def index(self):
        result = []
        for entry in self._base.iterdir():
            if entry.is_file():
                result.append(self._icon_name(entry))

        return result

    def get(self, name, width=None, height=None):
        surface = cairosvg.SURFACES['PNG']
        path = self._icon_path(name)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise LookupError('No icon with name %r' % name)

        # returns a bytestr with the encoded image.
        png_data = surface.convert(data,
                                   output_width=width,
                                   output_heiht=height)

        return png_data


class _NoCache:

    def put(self, *args):
        pass

    def get(self, *args):
        raise LookupError


class _MemoryCache:

    def __init__(self):
        self._entries = {}

    def put(self, name, width, height, color, data):
        key = (name, width, height, color)
        self._entries[key] = data

    def get(self, name, width, height, color):
        key = (name, width, height, color)
        return self._entries[key]


def _colorize(icon_data, color):
    '''Paint the given icon in the given color.
    Expects the base color of the icon to be black, so that it can be used as
    a mask.

    ``color`` must be an RGB(A) tuple, e.g. ``(50, 160, 255)``.
    '''
    # Paint new color on otherwise empty/transparent canves, using the icon
    # as mask.
    mask = Image.open(io.BytesIO(icon_data))
    fill = Image.new('RGBA', mask.size, color=color)
    canvas = Image.new('RGBA', mask.size, color=(0, 0, 0, 0))
    canvas.paste(fill, mask=mask)

    # Return PNG encoded images as bytes.
    buf = io.BytesIO()
    canvas.save(buf, format='png')
    return buf.getvalue()


def _rgba(raw):
    '''Make sure color is an RGBA tuple.

    ``raw`` is either already a tuple with RGB or RGBA values
    or it is a hexstring which will then be converted to a tuple.

    If the alpha channel is missing, it will be set to 255.
    '''
    if not raw:
        return None

    # Hex str, e.g. #aabbcc
    if isinstance(raw, str):
        if raw.startswith('#'):
            raw = raw[1:]
        if len(raw) < 6 or len(raw) > 10:
            raise ValueError('invalid color %r' % raw)

        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
        if raw[6:8]:
            a = int(raw[6:8], 1)
        else:
            a = 255

        return r, g, b, a

    # assume already a tuple
    if len(raw) == 3:
        return raw[0], raw[1], raw[2], 255

    return raw
