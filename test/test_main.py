from unittest import TestCase

from mapmaker.main import parse_args
from mapmaker.service import ServiceRegistry


class TestParseArgs(TestCase):

    def parse(self, *argv):
        # TODO: maybe use a mock service as we only need registry.list()
        registry = ServiceRegistry.default()
        return parse_args(registry, argv)

    def test_point_radius(self):
        args, params = self.parse('10.10,20.20', '123')
        self.assertEqual(params.pos0, (10.10, 20.20))
        self.assertIs(params.pos1, None)
        self.assertEqual(params.radius, 123)

    def test_point_radius_km(self):
        args, params = self.parse('10.10,20.20', '5km')
        self.assertEqual(params.radius, 5_000)

    def test_point_radius_invalid(self):
        args, params = self.parse('10.10,20.20', '-123')
        self.assertRaises(ValueError, params.validate)

    def test_two_points(self):
        args, params = self.parse('10.10,20.20', '30.30,40.40')
        self.assertEqual(params.pos0, (10.10, 20.20))
        self.assertEqual(params.pos1, (30.30, 40.40))
        self.assertIs(params.radius, None)

    def test_zoom(self):
        for z in range(0, 19):
            _, params = self.parse('10.10,20.20', '123', '-z', str(z))
            self.assertEqual(params.zoom, z)
            _, params = self.parse('10.10,20.20', '123', '--zoom', str(z))
            self.assertEqual(params.zoom, z)

    def test_style(self):
        # NOTE: must be one of the items from ServiceRegistry.list()
        style = 'topo'
        _, params = self.parse('10.10,20.20', '123', '-s', style)
        self.assertEqual(params.style, style)
        _, params = self.parse('10.10,20.20', '123', '--style', style)
        self.assertEqual(params.style, style)

    def test_aspect(self):
        aspect = '1:2'
        expect = 1 / 2
        _, params = self.parse('10.10,20.20', '123', '-a', aspect)
        self.assertEqual(params.aspect, expect)
        _, params = self.parse('10.10,20.20', '123', '--aspect', aspect)
        self.assertEqual(params.aspect, expect)

    def test_title(self):
        # TODO: can also parse less info and have defaults
        # TODO: sequence of arguments before Text does not matter
        # => partially covered by test_parse
        title = ['S', '#ff0000', '1', 'My Title']
        _, params = self.parse('10.10,20.20', '123', '--title', *title)
        self.assertEqual(params.title.text, 'My Title')
        self.assertEqual(params.title.color, (255, 0, 0, 255))
        self.assertEqual(params.title.placement, 'S')
        self.assertEqual(params.title.border_width, 1)
        # defaults applied
        self.assertIsNot(params.title.area, None)
        self.assertIsNot(params.title.border_color, None)
        self.assertIsNot(params.title.font_name, None)
        self.assertGreater(params.title.font_size, 0)

    def test_comment(self):
        # TODO: can also parse less info and have defaults
        # TODO: sequence of arguments before Text does not matter
        # => partially covered by test_parse
        comment = ['S', '#ff0000', '1', 'My Comment']
        _, params = self.parse('10.10,20.20', '123', '--comment', *comment)
        self.assertEqual(params.comment.text, 'My Comment')
        self.assertEqual(params.comment.color, (255, 0, 0, 255))
        self.assertEqual(params.comment.placement, 'S')
        self.assertEqual(params.comment.border_width, 1)
        # defaults applied
        self.assertIsNot(params.comment.area, None)
        self.assertIsNot(params.comment.border_color, None)
        self.assertIsNot(params.comment.font_name, None)
        self.assertGreater(params.comment.font_size, 0)

    def test_margin(self):
        '''Margins is specified clockwise'''
        # => more detailed in test_parse
        margin = ['1', '2', '3', '4']
        _, params = self.parse('10.10,20.20', '123', '--margin', *margin)
        self.assertEqual(params.margin[0], 1)
        self.assertEqual(params.margin[1], 2)
        self.assertEqual(params.margin[2], 3)
        self.assertEqual(params.margin[3], 4)

    def test_background(self):
        _, params = self.parse('10.10,20.20', '123', '--background', '#00FF00')
        self.assertEqual(params.background, (0, 255, 0, 255))

    def test_frame(self):
        frame = ['6', '#ffffff', '#000000', 'coordinates']
        _, params = self.parse('10.10,20.20', '123', '--frame', *frame)
        self.assertEqual(params.frame.color, (255, 255, 255, 255))
        self.assertEqual(params.frame.alt_color, (0, 0, 0, 255))
        self.assertEqual(params.frame.width, 6)
        self.assertEqual(params.frame.style, 'coordinates')

    def test_scale(self):
        scale = ['SW', '3', '#0000ff', 'nolabel']
        _, params = self.parse('10.10,20.20', '123', '--scale', *scale)

        self.assertEqual(params.scale.placement, 'SW')
        self.assertEqual(params.scale.border_width, 3)
        self.assertEqual(params.scale.color, (0, 0, 255, 255))
        self.assertEqual(params.scale.label_style, 'nolabel')

        # defaults
        self.assertIsNot(params.scale.underlay, None)
        self.assertIsNot(params.scale.font_name, None)
        self.assertGreater(params.scale.font_size, 0)

    def test_flags(self):
        args, _ = self.parse('10.10,20.20', '123',
                             '--dry-run', '--no-cache', '--silent')
        self.assertTrue(args.dry_run)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.silent)

    def test_defaults(self):
        '''Make sure we can use minimal command line and still have default
        values for all required params.'''
        args, params = self.parse('10.10,20.20', '123')
        self.assertGreaterEqual(params.zoom, 0)
        self.assertLessEqual(params.zoom, 19)
        self.assertIsNot(params.style, None)
        self.assertGreater(params.aspect, 0)
        self.assertIsNot(params.background, None)
