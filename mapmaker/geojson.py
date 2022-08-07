'''
Methods for drawing *GeoJSON* objects on a map.

What can be drawn:

GeoJSON allows the use of
foreign members https://datatracker.ietf.org/doc/html/rfc7946#section-6.1
which are additional attributes of an object.

These can be used to control how an element is drawn (color, line width, etc.).


Geometries
==========


Point, MultiPoint
-----------------
Draws a *Placemark* at the given location.

Special attributes:

:symbol:        Controls how the placemark looks (dot, square, ...)
:label:         Text displayed below the point(s)
:color:         Main color for the symbol
:fill:          Fill color for the symbol
:border:        Border width for symbol
:size:          Symbol size
:font_name:     Font family to use for the label.
:font_size:     Font size to use for the label.
:label_color:   Text and border color for the label.
:label_bg:      Background color for the label

For *MultiPoint* objects, the additional attributes are shared among all
points.


LineString, MultiLineString
---------------------------
Draws a line on the map.

Special attributes:

:color: RGB value to control the color of the line.
:width: Controls the width of the line.


Polygon, MultiPolygon
---------------------
Special attributes:

:color: RGB value to control the color of the line
:fill: Controls the fill color


GeometryCollection
------------------
Draws whatever is contained in the collection.


Feature, FeatureCollection
--------------------------
Draws the ``geometry`` member.

The ``properties`` attribute of a *Feature* can hold the special attributes
for the geometries. In this case, these attrbiutes are applied to the contained
geometries.


Attribute Types
===============
The additional attributes have the following special types:

:color: An array with 3(4) RGB(A) values, e.g. ``[220, 220, 220, 100]``.


Ideas
=====
- Use separate *opacity* attribute?
- Use a 'layer' attribute to order elements on z-axis?

'''
from itertools import chain

from .draw import Placemark
from .draw import Shape
from .draw import Track
from . import parse

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


def read(arg):
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
    except Exception:
        pass

    # arg is a JSON string?
    try:
        obj = geojson.loads(arg)
        return wrap(obj)
    except Exception:
        pass

    # arg is a path?
    # Note: open(<int>) would also attempt to read a file pointer.
    if not isinstance(arg, int):
        with open(arg) as f:
            obj = geojson.load(f)
            return wrap(obj)

    raise ValueError('invalid GeoJSON %r' % arg)


def wrap(obj, feature=None):
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
        }[t](obj, feature=feature)
    except KeyError:
        raise ValueError('Unsupported type %r' % t)


class _Wrapper:
    '''Base class for making a GeoJSON Geometry *drawable*.'''

    def __init__(self, obj, feature=None):
        self._obj = obj
        self._feature = feature

    def _get(self, key):
        '''Get a value from the wrapped GeoJSON objects "foreign members".

        If the value is not set *and* if we have a parent feature, look up
        the value in the Feature's ``properties`` dict.
        '''
        try:
            return self._obj[key]
        except KeyError:
            if self._feature:
                return self._feature.get('properties', {})[key]
            else:
                raise

    def _int(self, key):
        try:
            return int(self._get(key))
        except (KeyError, ValueError, TypeError):
            pass

    def _str(self, key):
        try:
            return str(self._get(key))
        except KeyError:
            pass

    def _color(self, key):
        try:
            val = self._get(key)
        except KeyError:
            return

        if not val:
            return

        if isinstance(val, str):
            return parse.color(val)

        # assume array w/ RGB values
        try:
            r, g, b = int(val[0]), int(val[1]), int(val[2])
            a = val[3] if len(val) == 4 else 255
            # TODO: okay to silently accept array with len > 4?
            return (r, g, b, a)
        except (ValueError, TypeError, IndexError):
            pass

    def drawables(self):
        '''Get the *Drawable* elements defined by a geojson object.'''
        raise ValueError('not implemented')


class _Point(_Wrapper):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        # lon,lat => lat,lon
        return coords[1], coords[0]

    @property
    def symbol(self):
        return self._str('symbol') or Placemark.DOT

    def _placemark(self, lat, lon):
        # also used by _PointList
        return Placemark(lat,
                         lon,
                         symbol=self.symbol,
                         label=self._str('label'),
                         color=self._color('color'),
                         fill=self._color('fill'),
                         border=self._int('border'),
                         size=self._int('size'),
                         font_name=self._str('font_name'),
                         font_size=self._int('font_size'),
                         label_color=self._color('label_color'),
                         label_bg=self._color('label_bg'))

    def drawables(self):
        lat, lon = self.coordinates
        return self._placemark(lat, lon).drawables()


class _MultiPoint(_Point):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        # lon,lat => lat,lon
        return [(x[1], x[0]) for x in coords]

    def drawables(self):
        d = [self._placemark(lat, lon).drawables()
             for lat, lon in self.coordinates]
        return chain(*d)


class _LineString(_Wrapper):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        # lon,lat => lat,lon
        return [(x[1], x[0]) for x in coords]

    def _track(self, points):
        return Track(points,
                     color=self._color('color'),
                     width=self._int('width'))

    def drawables(self):
        waypoints = self.coordinates
        return self._track(waypoints).drawables()


class _MultiLineString(_LineString):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        collection = []
        for points in coords:
            # lon,lat => lat,lon
            collection.append([(x[1], x[0]) for x in points])
        return collection

    def drawables(self):
        d = [self._track(waypoints).drawables()
             for waypoints in self.coordinates]
        return chain(*d)


class _Polygon(_Wrapper):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        # TODO
        # GeoJSON polygon MUST define an exterior ring (the "outer" shape)
        # and CAN define 0..n interior rings ("holes" within the shape)
        # We cannot do holes, so we just select the exterior ring.
        try:
            # lon,lat => lat,lon
            return [(x[1], x[0]) for x in coords[0]]
        except IndexError:
            return []

    def _shape(self, points):
        return Shape(points,
                     color=self._color('color'),
                     fill=self._color('fill'))


    def drawables(self):
        points = self.coordinates
        return self._shape(points).drawables()


class _MultiPolygon(_Polygon):

    @property
    def coordinates(self):
        coords = self._obj['coordinates']
        collection = []
        for points in coords:
            # TODO
            # GeoJSON polygon MUST define an exterior ring (the "outer" shape)
            # and CAN define 0..n interior rings ("hols" within the shape)
            # We cannot do holes, so we just select the exterior ring.
            try:
                # lon,lat => lat,lon
                collection.append([(x[1], x[0]) for x in points[0]])
            except IndexError:
                pass

        return collection

    def drawables(self):
        d = [self._shape(points).drawables() for points in self.coordinates]
        return chain(*d)


class _GeometryCollection(_Wrapper):

    @property
    def geometries(self):
        return [x for x in self._obj.get('geometries', [])]

    def drawables(self):
        all = []
        for geometry in self.geometries:
            all += wrap(geometry).drawables()
        return all


class _Feature(_Wrapper):

    @property
    def geometry(self):
        return self._obj.get('geometry')

    def drawables(self):
        if not self.geometry:
            return []
        return wrap(self.geometry, feature=self._obj).drawables()


class _FeatureCollection(_Wrapper):

    @property
    def features(self):
        return [_Feature(x) for x in self._obj.get('features', [])]

    def drawables(self):
        all = []
        for feature in self.features:
            all += feature.drawables()
        return all
