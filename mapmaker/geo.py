from collections import namedtuple


BRG_NORTH = 0
BRG_EAST = 90
BRG_SOUTH = 180
BRG_WEST = 270
EARTH_RADIUS = 6371.0 * 1000.0

# supported lat bounds for slippy map
MAX_LAT = 85.0511
MIN_LAT = -85.0511


BBox = namedtuple('BBox', 'minlat minlon maxlat maxlon')


def with_aspect(bbox, aspect):
    '''Extend the given bounding box so that it adheres to the given aspect
    ratio (given as a floating point number).
    Returns a new bounding box with the desired aspect ratio that contains
    the initial box in its center'''
    #  4:3  =>  1.32  width > height, aspect is > 1.0
    #  2:3  =>  0.66  width < height, aspect is < 1.0
    if aspect == 1.0:
        return bbox

    lat = bbox.minlat
    lon = bbox.minlon
    width = distance(bbox.minlat, lon, bbox.maxlat, lon)
    height = distance(lat, bbox.minlon, lat, bbox.maxlon)

    if aspect < 1.0:
        # extend "height" (latitude)
        target_height = width / aspect
        extend_height = (target_height - height) / 2
        new_minlat, _ = destination_point(bbox.minlat, lon, BRG_SOUTH, extend_height)
        new_maxlat, _ = destination_point(bbox.maxlat, lon, BRG_NORTH, extend_height)
        return BBox(
            minlat=new_minlat,
            minlon=bbox.minlon,
            maxlat=new_maxlat,
            maxlon=bbox.maxlon
        )
    else:  # aspect > 1.0
        # extend "width" (longitude)
        target_width = height * aspect
        extend_width = (target_width - width) / 2
        _, new_minlon = destination_point(lat, bbox.minlon, BRG_WEST, extend_width)
        _, new_maxlon = destination_point(lat, bbox.maxlon, BRG_EAST, extend_width)
        return BBox(
            minlat=bbox.minlat,
            minlon=new_minlon,
            maxlat=bbox.maxlat,
            maxlon=new_maxlon
        )


def bbox_from_radius(lat, lon, radius):
    '''Create a bounding box from a center point an a radius.'''
    lat_n, lon_n = destination_point(lat, lon, BRG_NORTH, radius)
    lat_e, lon_e = destination_point(lat, lon, BRG_EAST, radius)
    lat_s, lon_s = destination_point(lat, lon, BRG_SOUTH, radius)
    lat_w, lon_w = destination_point(lat, lon, BRG_WEST, radius)

    return BBox(
        minlat=min(lat_n, lat_e, lat_s, lat_w),
        minlon=min(lon_n, lon_e, lon_s, lon_w),
        maxlat=max(lat_n, lat_e, lat_s, lat_w),
        maxlon=max(lon_n, lon_e, lon_s, lon_w),
    )


def mercator_to_lat(mercator_y):
    return math.degrees(math.atan(math.sinh(mercator_y)))


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
    '''Determine a destination point from a start location, a bearing and a distance.

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
    '''Convert decimal coordinate into a DMS-tuple (degrees, munites, seconds).'''
    d = floor(decimal)
    m = floor((decimal - d) * 60)
    s = (decimal - d - m / 60) * 3600.0

    return int(d), int(m), s


def decimal(d=0, m=0, s=0):
    '''Convert a coordinate in DMS to decimal.'''
    m += s / 60.0  # seconds to minutes
    d += m / 60.0  # minutes to degrees
    return d
