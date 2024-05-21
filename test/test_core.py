from unittest import TestCase

from mapmaker.core import Map
from mapmaker.geo import BBox


class TestMap(TestCase):

    def test_add_decoration_valid(self):
        for area in (Map.MAP, Map.MARGIN):
            for slot in Map._SLOTS[area]:
                deco = Decoration(placement=slot)
                m = Map(BBox())
                m.add_decoration(area, deco)

    def test_add_decoration_multiple(self):
        '''We can add multiple decorations in the same area/placement)'''
        m = Map(BBox())
        for area in (Map.MAP, Map.MARGIN):
            m.add_decoration(area, Decoration(placement='N'))
            m.add_decoration(area, Decoration(placement='N'))

    def test_add_decoration_invalid_area(self):
        m = Map(BBox())
        deco = Decoration()
        self.assertRaises(ValueError, m.add_decoration, None, deco)
        self.assertRaises(ValueError, m.add_decoration, 'foo', deco)
        self.assertRaises(ValueError, m.add_decoration, 1, deco)

    def test_add_decoration_invalid_placement(self):
        m = Map(BBox())

        area = Map.MAP
        invalid = ('NNW', None, 1)
        for placement in invalid:
            deco = Decoration(placement=placement)
            self.assertRaises(ValueError, m.add_decoration, area, deco)

        # Margin
        area = Map.MARGIN
        invalid = ('C', None, 1)
        for placement in invalid:
            deco = Decoration(placement=placement)
            self.assertRaises(ValueError, m.add_decoration, area, deco)


class Decoration:

    def __init__(self, placement='N'):
        self.placement = placement
