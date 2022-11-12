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
from pathlib import Path

import appdirs
import cairosvg

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

    def get(self, name, width=None, height=None):
        '''Loads the image data for the given icon and size.

        Raises LookupError if no icon is found.'''
        try:
            return self._cache.get(name, width, height)
        except LookupError:
            pass

        if not self._providers:
            self._discover()

        for provider in self._providers:
            try:
                data = provider.get(name, width=width, height=height)
                self._cache.put(name, width, height, data)
                return data
            except LookupError:
                pass

        raise LookupError('No icon found with name %r' % name)

    def __repr__(self):
        return '<IconProvider %s>' % self._base

    @classmethod
    def default(cls):
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

    def put(self, name, width, height, data):
        key = (name, width, height)
        self._entries[key] = data

    def get(self, name, width, height):
        key = (name, width, height)
        return self._entries[key]
