from pathlib import Path
import unittest
from unittest import TestCase


from mapmaker import geoj


_HOME = Path(__file__).parent


class _GeoJSONTest(TestCase):

    def assertIsGeoJSON(self, obj):
        self.assertIsNotNone(obj)
        self.assertTrue(hasattr(obj, 'draw'))


class LoadTest(_GeoJSONTest):
    '''Test the various options to open and parse geojson.'''

    def test_load_str(self):
        jsonstr = '''{
            "coordinates": [123.45, 12.45],
            "type": "Point"
        }'''
        obj = geoj.load(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_load_path(self):
        path = _HOME.joinpath('./geojson_point.json')
        # Path object
        obj = geoj.load(path)
        self.assertIsGeoJSON(obj)

        # str path
        obj = geoj.load(str(path))
        self.assertIsGeoJSON(obj)

    def test_load_fp(self):
        path = _HOME.joinpath('./geojson_point.json')
        with path.open() as fp:
            obj = geoj.load(fp)
        self.assertIsGeoJSON(obj)

    def test_invalid_arg(self):
        self.assertRaises(Exception, geoj.load, None)
        self.assertRaises(Exception, geoj.load, 'invalid')
        self.assertRaises(Exception, geoj.load, 1)
        self.assertRaises(Exception, geoj.load, '{}')
        self.assertRaises(Exception, geoj.load, '/does/not/exists.json')

        # valid JSON, but invalid GeoJSON
        self.assertRaises(Exception, geoj.load, '{"type": "INVALID", "coordinates": [12, 34]}')
        # after loading with geojson, Point will have an empty coordinates array []
        # self.assertRaises(Exception, geoj.load, '{"type": "Point"}')  # no coordinates


class GeometriesTest(_GeoJSONTest):
    '''Test if we understand all of the GeoJSON gemoetries.'''

    def test_point(self):
        jsonstr = '''{
            "coordinates": [123.45, 12.45],
            "type": "Point"
        }'''
        obj = geoj.load(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_multi_point(self):
        jsonstr = '''{
            "coordinates": [[123.45, 12.45], [101.45, 11.45], [102.45, 13.45]],
            "type": "MultiPoint"
        }'''
        obj = geoj.load(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_line_string(self):
        jsonstr = '''{
            "coordinates": [[123.45, 12.45], [101.45, 11.45], [102.45, 13.45]],
            "type": "LineString"
        }'''
        obj = geoj.load(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_multi_line_string(self):
        jsonstr = '''{
            "coordinates": [
                [[123.45, 12.45], [101.45, 11.45], [102.45, 13.45]],
                [[50.12, 20.12], [51.12, 21.12], [52.12, 22.12]]
            ],
            "type": "MultiLineString"
        }'''
        obj = geoj.load(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_polygon(self):
        jsonstr = '''{
            "coordinates": [[123.45, 12.45], [101.45, 11.45], [102.45, 13.45]],
            "type": "Polygon"
        }'''
        obj = geoj.load(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_multi_polygon(self):
        jsonstr = '''{
            "coordinates": [
                [[123.45, 12.45], [101.45, 11.45], [102.45, 13.45]],
                [[50.12, 20.12], [51.12, 21.12], [52.12, 22.12]]
            ],
            "type": "MultiPolygon"
        }'''
        obj = geoj.load(jsonstr)
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
        obj = geoj.load(jsonstr)
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
        obj = geoj.load(jsonstr)
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
        obj = geoj.load(jsonstr)
        self.assertIsGeoJSON(obj)

    def test_elevation(self):
        '''Test if we can handle an additional ``elevation`` value in
        coordinates.'''
        jsonstr = '''{
            "coordinates": [123.45, 12.45, 220.2],
            "type": "Point"
        }'''
        obj = geoj.load(jsonstr)
        self.assertIsGeoJSON(obj)
