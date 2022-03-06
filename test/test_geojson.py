from pathlib import Path
import unittest
from unittest import TestCase


from mapmaker import geoj


_HOME = Path(__file__).parent


class LoadTest(TestCase):
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

    def assertIsGeoJSON(self, obj):
        self.assertIsNotNone(obj)
        self.assertTrue(hasattr(obj, 'draw'))

    def test_invalid_arg(self):
        self.assertRaises(Exception, geoj.load, None)
        self.assertRaises(Exception, geoj.load, 'invalid')
        self.assertRaises(Exception, geoj.load, 1)
        self.assertRaises(Exception, geoj.load, '{}')
        self.assertRaises(Exception, geoj.load, '/does/not/exists.json')

        # valid JSON, but invalid GeoJSON type
        self.assertRaises(Exception, geoj.load, '{"type": "INVALID"}')
