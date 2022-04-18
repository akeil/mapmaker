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

import cairosvg


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

    def _discover(self):
        subdirs = [x for x in self._base.iterdir() if x.is_dir()]
        subdirs.sort()
        for dir in subdirs:
            self._providers.append(_Provider(dir, '{name}.svg'))

    def get(self, name, width=None, height=None):
        '''Loads the image data for the given icon and size.

        Raises LookupError if no icon is found.'''
        if not self._providers:
            self._discover()

        for provider in self._providers:
            try:
                return provider.get(name, width=width, height=height)
            except LookupError:
                pass

        raise LookupError('No icon found with name %r' % name)


class _Provider:

    def __init__(self, path, pattern):
        self._base = Path(path)
        self._pattern = pattern

    def _icon_path(self, name):
        filename = self._pattern.format(name=name)
        return self._base.joinpath(filename)

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
