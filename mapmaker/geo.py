from dataclasses import dataclass
from math import asin
from math import atan
from math import atan2
from math import cos
from math import degrees
from math import floor
from math import radians
from math import sin
from math import sinh
from math import sqrt


BRG_NORTH = 0
BRG_EAST = 90
BRG_SOUTH = 180
BRG_WEST = 270
EARTH_RADIUS = 6371.0 * 1000.0


@dataclass(frozen=True)
class BBox:
    '''An axis-aligned Bounding box defined by two coordinates.'''

    minlat: float = -90.0
    minlon: float = -180.0
    maxlat: float = 90.0
    maxlon: float = 180.0

    def __post_init(self):
        if self.minlat < -90.0:
            raise ValueError('minlat must not be < -90')
        if self.maxlat > 90.0:
            raise ValueError('maxlat must not be >90')
        if self.minlon < -180.0:
            raise ValueError('minlon must not be < -180')
        if self.maxlon > 180.0:
            raise ValueError('maxlon must not be > 180.0')

    def with_aspect(self, aspect):
        '''Extend the given bounding box so that it adheres to the given aspect
        ratio (given as a floating point number).
        Returns a new bounding box with the desired aspect ratio that contains
        the initial box in its center.'''
        # aspect = width : height
        #  4:3  =>  1.32  width > height, aspect is > 1.0
        #  2:3  =>  0.66  width < height, aspect is < 1.0
        if aspect == 1.0:
            return self

        lat = self.minlat
        lon = self.minlon
        height = distance(self.minlat, lon, self.maxlat, lon)
        width = distance(lat, self.minlon, lat, self.maxlon)

        current_aspect = width / height

        if current_aspect > 1.0:  # extend height (latitude)
            target_height = width / aspect
            ext = (target_height - height) / 2
            new_minlat, _ = destination_point(self.minlat, lon, BRG_SOUTH, ext)
            new_maxlat, _ = destination_point(self.maxlat, lon, BRG_NORTH, ext)
            return BBox(
                minlat=new_minlat,
                minlon=self.minlon,
                maxlat=new_maxlat,
                maxlon=self.maxlon
            )
        else:  # < 1.0, extend width (longitude)
            target_width = height * aspect
            ext = (target_width - width) / 2
            _, new_minlon = destination_point(lat, self.minlon, BRG_WEST, ext)
            _, new_maxlon = destination_point(lat, self.maxlon, BRG_EAST, ext)
            return BBox(
                minlat=self.minlat,
                minlon=new_minlon,
                maxlat=self.maxlat,
                maxlon=new_maxlon
            )

    def padded(self, pad):
        '''Create a BBox that is extended towards all sides
        by the given amount in meters.'''
        if not pad:
            return self

        if pad < 0:
            raise ValueError('Pad must be a positive value, got %s' % pad)

        north = self.maxlat
        west = self.minlon
        south = self.minlat
        east = self.maxlon

        maxlat, minlon = destination_point(north, west, 315.0, pad)
        minlat, maxlon = destination_point(south, east, 135.0, pad)

        return BBox(
            minlat=minlat,
            minlon=minlon,
            maxlat=maxlat,
            maxlon=maxlon
        )

    def constrained(self,
                    minlat=-90.0,
                    maxlat=90.0,
                    minlon=-180.0,
                    maxlon=180.0):
        '''Constrain a bounding box to min/max values for latitude or
        longitude.

        Returns a new BBox with the coordinates adjusted to fit within
        given bounds.
        '''
        return BBox(minlat=max(self.minlat, minlat),
                    maxlat=min(self.maxlat, maxlat),
                    minlon=max(self.minlon, minlon),
                    maxlon=min(self.maxlon, maxlon))

    def __repr__(self):
        return '<BBox minlat=%s, minlon=%s, maxlat=%s, maxlon=%s>' % (
            self.minlat, self.minlon, self.maxlat, self.maxlon)

    @classmethod
    def from_radius(cls, lat, lon, radius):
        '''Create a bounding box from a center point an a radius.'''
        lat_n, lon_n = destination_point(lat, lon, BRG_NORTH, radius)
        lat_e, lon_e = destination_point(lat, lon, BRG_EAST, radius)
        lat_s, lon_s = destination_point(lat, lon, BRG_SOUTH, radius)
        lat_w, lon_w = destination_point(lat, lon, BRG_WEST, radius)

        return cls(minlat=min(lat_n, lat_e, lat_s, lat_w),
                   minlon=min(lon_n, lon_e, lon_s, lon_w),
                   maxlat=max(lat_n, lat_e, lat_s, lat_w),
                   maxlon=max(lon_n, lon_e, lon_s, lon_w))


def mercator_to_lat(mercator_y):
    return degrees(atan(sinh(mercator_y)))


def distance(lat0, lon0, lat1, lon1):
    '''Calculate the distance as-the-crow-flies between two points in meters.

        P0 ------------> P1

    '''
    lat0 = radians(lat0)
    lon0 = radians(lon0)
    lat1 = radians(lat1)
    lon1 = radians(lon1)

    d_lat = lat1 - lat0
    d_lon = lon1 - lon0

    a = sin(d_lat / 2) * sin(d_lat / 2)
    b = cos(lat0) * cos(lat1) * sin(d_lon / 2) * sin(d_lon / 2)
    c = a + b

    d = 2 * atan2(sqrt(c), sqrt(1 - c))

    return d * EARTH_RADIUS


def destination_point(lat, lon, bearing, distance):
    '''Determine a destination point from a start location, a bearing
    and a distance.

    Distance is given in METERS.
    Bearing is given in DEGREES
    '''
    # http://www.movable-type.co.uk/scripts/latlong.html
    # search for destinationPoint
    d = distance / EARTH_RADIUS  # angular distance
    brng = radians(bearing)

    lat = radians(lat)
    lon = radians(lon)

    a = sin(lat) * cos(d) + cos(lat) * sin(d) * cos(brng)
    lat_p = asin(a)

    x = cos(d) - sin(lat) * a
    y = sin(brng) * sin(d) * cos(lat)
    lon_p = lon + atan2(y, x)

    return degrees(lat_p), degrees(lon_p)


def dms(decimal):
    '''Convert decimal coordinate into a DMS-tuple
    (degrees, munites, seconds).
    '''
    d = floor(decimal)
    m = floor((decimal - d) * 60)
    s = (decimal - d - m / 60) * 3600.0

    return int(d), int(m), s


def decimal(d=0, m=0, s=0):
    '''Convert a coordinate in DMS to decimal.'''
    m += s / 60.0  # seconds to minutes
    d += m / 60.0  # minutes to degrees
    return d
