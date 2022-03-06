'''
Methods for drawing *GeoJSON* objects on a map.

What can be drawn:

GeoJSON allows the use of
foreign members https://datatracker.ietf.org/doc/html/rfc7946#section-6.1
which are additional attributes of an object.

These can be used to control how an element is drawn (color, line width, etc.).


Point, MultiPoint
-----------------
Draws a *Placemark* at the given location.

Special attributes:

:symbol: Controls how the placemark looks like (dot, square, ...)
:label: Text displayed below the point(s)


LineString, MultiLineString
---------------------------
Draws a line on the map

Special attributes:

:color: RGB value to control the color of the line
:width: Controls the width of the line


Polygon, MultiPolygon
---------------------

Special attributes:

:color: RGB value to control the color of the line
:width: Controls the width of the line
:fill: Controls the fill color


GeometryCollection
------------------
Draws whatever is contained in the collection.


Feature, FeatureCollection
--------------------------
Draws the ``geometry`` member.


Ideas
-----
- Use separate *opacity* attribute?
- Use a 'layer' attribute to order elements on z-axis?

'''
from .draw import Placemark
from .draw import Shape
from .draw import Track

import geojson


# GeoJSON types
_POINT = 'Point'
_MULTI_POINT = 'MultiPoint'
_LINE = 'LineString'
_MULTI_LINE = 'MultiLineString'
_POLYGON = 'Polygon'
_MULTI_POLYGON = 'MultiPolygon'
_COLLECTION = 'GeometryCollection'
_FEATURE = 'Feature'
_FEATURE_COLLECTION = 'FeatureCollection'


def load(arg):
    '''Load GeoJSON object from the given ``arg`` which is either
    a file-like object, a path or a JSON string.

    Returns a GeoJSON object that can be added as a *drawable* element
    to a map.

    .. code:: python

        my_map = Map(bbox)
        elem = load(data)
        my_map.add_element(elem)
        my_map.render(...)  # draws GeoJSON elements on the map

    If the GeoJSON contains multiple elements (e.g. GeometryCollection),
    all of these will be drawn on the map.

    Raises an error if no JSON can be parsed or if the JSON is not a valid
    GeoJSON object.
    '''
    # arg is a file-like object?
    try:
        obj = geojson.load(arg)
        return wrap(obj)
    except Exception as err:
        pass

    # arg is a JSON string?
    try:
        obj = geojson.loads(arg)
        return wrap(obj)
    except Exception as err:
        pass

    # arg is a path?
    # Note: open(<int>) would also attempt to read a file pointer.
    if not isinstance (arg, int):
        with open(arg) as f:
            obj = geojson.load(f)
            return wrap(obj)

    raise ValueError('invalid GeoJSON %r' % arg)


def wrap(obj):
    '''Wrap a GeoJSON object into a *drawable* element for the map.'''
    try:
        t = obj['type']
    except KeyError:
        raise ValueError('Missing type attribute. Not a GeoJSON object?')

    try:
        # TODO: validate() each object?
        return {
            _POINT: _Point,
            _MULTI_POINT: _MultiPoint,
            _LINE: _LineString,
            _MULTI_LINE: _MultiLineString,
            _POLYGON: _Polygon,
            _MULTI_POLYGON: _MultiPolygon,
            _COLLECTION: _GeometryCollection,
            _FEATURE: _Feature,
            _FEATURE_COLLECTION: _FeatureCollection,
        }[t](obj)
    except KeyError:
        raise ValueError('Unsupported type %r' % t)


class _Wrapper:
    '''Base class for making a GeoJSON Geometry *drawable*.'''

    def __init__(self, obj):
        self._obj = obj

    def draw(self, rc, draw):
        raise ValueError('not implemented')


class _Point(_Wrapper):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        return coords[0], coords[1]

    def draw(self, rc, draw):
        lat, lon = self.coordinates
        # TODO: more properties
        Placemark(lat, lon).draw(rc, draw)


class _MultiPoint(_Point):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        return [(x[0], x[1]) for x in coords]

    def draw(self, rc, draw):
        # TODO: additional properties, same as _Point
        for lat, lon in self.positions:
            Placemark(lat, lon).draw(rc, draw)


class _LineString(_Wrapper):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        return [(x[0], x[1]) for x in coords]

    def draw(self, rc, draw):
        # TODO: additional properties
        waypoints = self.coordinates
        Track(waypoints).draw(rc, draw)


class _MultiLineString(_LineString):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        collection = []
        for points in coordinates:
            collection.append([(x[0], x[1]) for x in points])
        return collection

    def draw(self, rc, draw):
        # TODO: additional properties, same as _LineString
        tracks = self.coordinates
        for track in tracks:
            Track(waypoints).draw(rc, draw)


class _Polygon(_Wrapper):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        return [(x[0], x[1]) for x in coords]

    def draw(self, rc, draw):
        # TODO: additional properties, same as _LineString
        points = self.coordinates
        Shape(points).draw(rc, draw)


class _MultiPolygon(_Wrapper):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        collection = []
        for points in coordinates:
            collection.append([(x[0], x[1]) for x in points])
        return collection

    def draw(self, rc, draw):
        # TODO: additional properties, same as _LineString
        shapes = self.coordinates
        for points in shapes:
            Shape(points).draw(rc, draw)


class _GeometryCollection(_Wrapper):

    @property
    def geometries(self):
        return [x for x in self._obj.get('geometries', [])]

    def draw(self, rc, draw):
        for geometry in self.geometries:
            # raises error for unknown `type`
            wrap(geometry).draw(rc, draw)


class _Feature(_Wrapper):

    @property
    def geometry(self):
        return self._obj.get('geometry')

    def draw(self, rc, draw):
        # geometry can be `null`
        if self.geometry:
            # raises error for unknown `type`
            wrap(self.geometry).draw(rc, draw)


class _FeatureCollection(_Wrapper):

    @property
    def coordinates(self):
        return [_Feature(x) for x in self._obj.get('features', [])]

    def draw(self, rc, draw):
        for feature in self.features:
            feature.draw(rc, draw)
