from pathlib import Path
from unittest import TestCase


from mapmaker import geojson


_HOME = Path(__file__).parent


class _GeoJSONTest(TestCase):

    def assertIsGeoJSON(self, obj):
        self.assertIsNotNone(obj)
        self.assertTrue(hasattr(obj, 'drawables'))


class ReadTest(_GeoJSONTest):
    '''Test the various options to open and parse geojson.'''

    def test_read_str(self):
        jsonstr = '''{
            "coordinates": [123.45, 12.45],
            "type": "Point"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_read_path(self):
        path = _HOME.joinpath('./geojson_point.json')
        # Path object
        obj = geojson.read(path)
        self.assertIsGeoJSON(obj)

        # str path
        obj = geojson.read(str(path))
        self.assertIsGeoJSON(obj)

    def test_read_fp(self):
        path = _HOME.joinpath('./geojson_point.json')
        with path.open() as fp:
            obj = geojson.read(fp)
        self.assertIsGeoJSON(obj)

    def test_invalid_arg(self):
        self.assertRaises(Exception, geojson.read, None)
        self.assertRaises(Exception, geojson.read, 'invalid')
        self.assertRaises(Exception, geojson.read, 1)
        self.assertRaises(Exception, geojson.read, '{}')
        self.assertRaises(Exception, geojson.read, '/does/not/exists.json')

        # valid JSON, but invalid GeoJSON
        self.assertRaises(Exception,
                          geojson.read,
                          '{"type": "INVALID", "coordinates": [12, 34]}')

        # TODO: validation currently not possible
        # self.assertRaises(Exception, geojson.read, '{"type": "Point"}')

    def test_wrap_dict(self):
        '''Check if we can load dict data that was not obtained from the
        geojson library.'''
        data = {
            'type': 'Point',
            'coordinates': [12.34, 56.78]
        }
        obj = geojson.wrap(data)
        self.assertIsGeoJSON(obj)


class GeometriesTest(_GeoJSONTest):
    '''Test if we understand all of the GeoJSON geometries.'''

    def test_point(self):
        jsonstr = '''{
            "coordinates": [123.45, 12.45],
            "type": "Point"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_multi_point(self):
        jsonstr = '''{
            "coordinates": [[123.45, 12.45], [101.45, 11.45], [102.45, 13.45]],
            "type": "MultiPoint"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_line_string(self):
        jsonstr = '''{
            "coordinates": [[123.45, 12.45], [101.45, 11.45], [102.45, 13.45]],
            "type": "LineString"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_multi_line_string(self):
        jsonstr = '''{
            "coordinates": [
                [[123.45, 12.45], [101.45, 11.45], [102.45, 13.45]],
                [[50.12, 20.12], [51.12, 21.12], [52.12, 22.12]]
            ],
            "type": "MultiLineString"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_polygon(self):
        jsonstr = '''{
            "coordinates": [[123.45, 12.45], [101.45, 11.45], [102.45, 13.45]],
            "type": "Polygon"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_multi_polygon(self):
        jsonstr = '''{
            "coordinates": [
                [[123.45, 12.45], [101.45, 11.45], [102.45, 13.45]],
                [[50.12, 20.12], [51.12, 21.12], [52.12, 22.12]]
            ],
            "type": "MultiPolygon"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_geometry_collection(self):
        jsonstr = '''{
            "geometries": [
                {
                    "coordinates": [10.10, 20.20],
                    "type": "Point"
                },
                {
                    "coordinates": [15.15, 25.25],
                    "type": "Point"
                }
            ],
            "type": "GeometryCollection"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_feature(self):
        jsonstr = '''{
            "geometry": {
                "coordinates": [15.15, 25.25],
                "type": "Point"
            },
            "properties": null,
            "type": "Feature"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_feature_collection(self):
        jsonstr = '''{
            "features": [
                {
                    "geometry": {
                        "coordinates": [15.15, 25.25],
                        "type": "Point"
                    },
                    "properties": null,
                    "type": "Feature"
                },
                {
                    "geometry": {
                        "coordinates": [15.15, 25.25],
                        "type": "Point"
                    },
                    "properties": null,
                    "type": "Feature"
                }
            ],
            "type": "FeatureCollection"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_elevation(self):
        '''Test if we can handle an additional ``elevation`` value in
        coordinates.'''
        jsonstr = '''{
            "coordinates": [123.45, 12.45, 220.2],
            "type": "Point"
        }'''
        obj = geojson.read(jsonstr)
        self.assertIsGeoJSON(obj)
