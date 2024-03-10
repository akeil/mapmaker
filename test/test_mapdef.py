import io
import unittest
from unittest import TestCase

from mapmaker.mapdef import MapParams


class TestMapParams(TestCase):

    def test_minimal_args(self):
        '''Make sure we can set up a map with minimal arguments.'''
        p = MapParams((50.0, 7.0), radius=100)
        m = p.create_map()
        self.assertIsNot(None, m.bbox)

        p = MapParams((50.0, 7.0), pos1=(51.0, 8.0))
        m = p.create_map()
        self.assertIsNot(None, m.bbox)

    def test_validate_minimal(self):
        '''Make sure we raise an error if are missing minimal params.'''
        p = MapParams(None)
        self.assertRaises(ValueError, p.create_map)

        p = MapParams((50.0, 7.0))
        self.assertRaises(ValueError, p.create_map)

        p = MapParams(None, pos1=(50.0, 7.0))
        self.assertRaises(ValueError, p.create_map)

        p = MapParams(None, radius=100)
        self.assertRaises(ValueError, p.create_map)

    def test_validate_ambigious_bbox(self):
        p = MapParams((50.0, 7.0), pos1=(51.0, 8.0), radius=100)
        self.assertRaises(ValueError, p.create_map)

    def test_parse_empty(self):
        '''Make sure we can parse an empty config'''
        ini = ''
        p = MapParams.from_file(io.StringIO(ini))
        self.assertIsNot(None, p)

    def test_parse_any_section(self):
        '''Make sure we accept any section name.'''

        names = ['XYZ', 'map', 'Map', 'DEFAULT']

        for name in names:
            ini = '''[%s]
            pos0 = 12.0, 34.0
            ''' % name

            p = MapParams.from_file(io.StringIO(ini))
            self.assertEqual(p.pos0, (12.0, 34.0),
                              msg='Section name %s not recognized' % name)

    def test_parse(self):
        ini = '''[map]
        pos0 = 12.0, 34.0
        pos1 = 56.0, 78.0
        radius = 123
        style = osm
        zoom = 10
        aspect = 16:9
        margin = 50, 25, 25, 25
        background = #ffffff
        geojson = /path/to/file1.json
            /path/to/file2.json

        [frame]
        width       = 5
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
        font_name       = Some Font

        [compass]
        placement = SE
        color = 0, 0, 0
        outline  = 255, 255, 255
        marker = No

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
        border_width    = 1
        border_color    = #00ff00
        background      = #0000ff
        font_name       = Some Font
        font_size       = 10
        '''
        p = MapParams.from_file(io.StringIO(ini))

        self.assertEqual(p.radius, 123)
        self.assertEqual(p.pos0, (12.0, 34.0))
        self.assertEqual(p.pos1, (56.0, 78.0))
        self.assertEqual(p.style, 'osm')
        self.assertEqual(p.zoom, 10)
        self.assertEqual(p.aspect, 16/9)
        self.assertEqual(p.margin, (50, 25, 25, 25))
        self.assertEqual(p.background, (255, 255, 255, 255))
        self.assertEqual(p.geojson, ['/path/to/file1.json',
                                     '/path/to/file2.json'])

        self.assertIsNot(None, p.frame)
        self.assertEqual(p.frame.width, 5)
        self.assertEqual(p.frame.color, (0, 0, 0, 255))
        self.assertEqual(p.frame.alt_color, (255, 255, 255, 255))
        self.assertEqual(p.frame.style, 'coordinates')

        self.assertIsNot(None, p.scale)
        self.assertEqual(p.scale.placement, 'SW')
        self.assertEqual(p.scale.color, (0, 0, 0, 255))
        self.assertEqual(p.scale.border_width, 2)
        self.assertEqual(p.scale.underlay, 'compact')
        self.assertEqual(p.scale.label_style, 'default')
        self.assertEqual(p.scale.font_size, 10)
        self.assertEqual(p.scale.font_name, 'Some Font')

        self.assertIsNot(None, p.compass)
        self.assertEqual(p.compass.placement, 'SE')
        self.assertEqual(p.compass.color, (0, 0, 0, 255))
        self.assertEqual(p.compass.outline, (255, 255, 255, 255))
        self.assertEqual(p.compass.marker, False)

        self.assertIsNot(None, p.title)
        self.assertEqual(p.title.text, 'My Map')
        self.assertEqual(p.title.area, 'MARGIN')
        self.assertEqual(p.title.placement, 'N')
        self.assertEqual(p.title.color, (255, 0, 0, 255))
        self.assertEqual(p.title.border_width, 1)
        self.assertEqual(p.title.border_color, (144, 144, 144, 255))
        self.assertEqual(p.title.background, (144, 144, 144, 255))
        self.assertEqual(p.title.font_name, 'DejaVuSans')
        self.assertEqual(p.title.font_size, 16)

        self.assertIsNot(None, p.comment)
        self.assertEqual(p.comment.text, 'This is an example map')
        self.assertEqual(p.comment.area, 'MARGIN')
        self.assertEqual(p.comment.placement, 'S')
        self.assertEqual(p.comment.color, (0, 0, 0, 255))
        self.assertEqual(p.comment.border_width, 1)
        self.assertEqual(p.comment.border_color, (0, 255, 0, 255))
        self.assertEqual(p.comment.background, (0, 0, 255, 255))
        self.assertEqual(p.comment.font_name, 'Some Font')
        self.assertEqual(p.comment.font_size, 10)
