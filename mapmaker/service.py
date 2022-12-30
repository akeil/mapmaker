import base64
from collections import OrderedDict
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import io
import logging
import os
from pathlib import Path
import random
from urllib.parse import urlparse
import threading

import appdirs
from PIL import Image
import requests

from mapmaker import __version__
from mapmaker import __author__
from mapmaker import __name__ as APP_NAME
from mapmaker.tilemap import Tile


_LOG = logging.getLogger(APP_NAME)


class TileService:
    '''A web service that fetches slippy map tiles in OSM format.

    ``name`` is the unique name for this service. It is for example used as
    the directory name for the cache (if a cache is used).

    ``url_pattern`` if a format string with the URL for a specific tile,
    e.g. "https://tile.openstreetmap.org/{z}/{x}/{y}.png".
    It must contain the ``{x}, {y}, {z}`` placeholders.

    The URL pattern may contain an ``{s}`` parameter, which allows to use
    different servers (subdomains, usually).
    By default, it will be set to the value ``a``.

    If the ``abc`` parameter is given, it should be a list of values suitable
    for the ``{s}`` placeholder. A random value will be chosen with each
    request.

    ``max_retries`` controls how often failed requests should be repeated
    before raising an error. Retries are only made for failed connections
    (including timeouts).
    If the server responds with an error code (e.g. 403 or 404), the request
    is *not* attempted again.
    '''

    def __init__(self,
                 name,
                 url_pattern,
                 abc=None,
                 api_keys=None,
                 max_retries=3):
        self.name = name
        self.url_pattern = url_pattern
        self._abc = abc
        self._api_keys = api_keys or {}
        self._max_retries = max_retries

        s = requests.Session()
        ua = '%s/%s +https://github.com/akeil/mapmaker' % (APP_NAME, __version__)
        s.headers['User-Agent'] = ua
        self._session = s

    def cached(self, basedir=None, limit=None, min_hours=24):
        '''Wrap this tile service in a file system cache with default
        parameters.

        If ``basedir`` is set, this will be used as the base directory for
        the cache. If *None*, the default directory will be used.

        If ``limit`` is set, the cache sized is limited to that size.
        '''
        return Cache(self, basedir=basedir, limit=limit, min_hours=min_hours)

    def memory_cache(self, size=100):
        '''Wrap this cache into a *MemoryCache*.

        Note that if you also want a file system cahce (recommended), then
        wrap the service in an FS-cache first, then with a memory cache.
        '''
        return MemoryCache(self, size=size)

    @property
    def top_level_domain(self):
        parts = self.domain.split('.')
        # TODO: not quite correct, will fail e.g. for 'foo.co.uk'
        return '.'.join(parts[-2:])

    @property
    def domain(self):
        parts = urlparse(self.url_pattern)
        return parts.netloc

    def fetch(self, x, y, z, etag=None, cached_only=False):
        '''Fetch the given tile from the Map Tile Service.

        ``x, y, z`` are the tile coordinates and zoom level.

        If an ``etag`` is specified, it will be sent to the server.
        If the server replies with a status "Not Modified", this method
        returns *None* instead of the tile data.

        If ``cached_only`` is *True*, a ``LookupError`` is raised if the
        requested tile needs to be fetched from the service.
        The ``cached_only`` flag only makes sense if the service is wrapped
        into a cache. For a TileService without a cache, this will raise an
        error for every request.

        Returns the response ``etag`` and the raw image data.
        '''
        if cached_only:
            raise LookupError('No cached tile for %s,%s,%s', x, y, z)

        s = self._server()
        api = self._api_key()
        url = self.url_pattern.format(
            x=x,
            y=y,
            z=z,
            s=s,
            api=api,
        )

        headers = {}
        if etag:
            headers['If-None-Match'] = etag

        try:
            #res = self._session.get(url, headers=headers)
            #res.raise_for_status()
            res = self._request(url, headers)
        except Exception as err:
            log_api = '<API_KEY>' if api else '<NO_API_KEY>'
            log_url = self.url_pattern.format(x=x, y=y, z=z, s=s, api=log_api)
            _LOG.warning('Request for %r failed with %s', log_url, err)
            _LOG.debug(err, exc_info=True)
            raise err

        if res.status_code == 304:
            return etag, None

        recv_etag = res.headers.get('etag')
        return recv_etag, res.content

    def _request(self, url, headers, retry_count=1):
        try:
            res = self._session.get(url, headers=headers)
            res.raise_for_status()
            return res
        except (requests.Timeout, requests.ConnectionError) as err:
            # Any error type we would like to retry goes here.
            # Raise only if retries are exhausted.
            if retry_count > self._max_retries:
                _LOG.warning('Request failed after %d retries', retry_count)
                raise err

            _LOG.info('Retry (%d) request after %s', retry_count, err)

        retry_count += 1
        return self._request(url, headers, retry_count=retry_count)

    def _server(self):
        if not self._abc:
            return 'a'

        i = random.randint(0, len(self._abc) - 1)
        return self._abc[i]

    def _api_key(self):
        return self._api_keys.get(self.domain, '')

    def __repr__(self):
        return '<TileService name=%r>' % self.name


# TODO: use _lock() properly

class Cache:
    '''File system cache that can be used as a wrapper around a *TileService*.

    The *Cache* can be used instead of the service and will attempt to load
    requested tiles from the file system before falling back on the backing
    service.

    Downloaded tiles are automatically added to the cache.

    No attempt is made to obtain the lifetime of a cache entry from the
    service response. Instead the files ``mtime`` attribute is used to
    delete older files until a given size ``limit`` is reached.
    If the cache is set up with no ``limit``, entries are kept indefinetly.

    If available, the cache keeps the ``ETAG`` from the server response
    and uses the ``If-None-Match`` header when requesting tiles.
    So even with cache, a HTTP request is made for each requested tile.

    The cache layout (below ``basedir``) includes the *name* of the serbice.
    The same basedir can be used for different services as long as they
    have unique names.

    ``min_hours`` controls how long we use the cached tile *without* checking
    the ETAG. Since it is unlikely that tiles change frequently *and* it is
    (assumed) likely that the same tiles are requested multiple times within
    a short timespan, this saves the additional request.
    '''

    def __init__(self, service, basedir=None, limit=None, min_hours=24):
        self._service = service
        self._limit = limit
        self._min_age = timedelta(hours=min_hours)
        self._lock = threading.Lock()

        if not basedir:
            basedir = appdirs.user_cache_dir(appname=APP_NAME,
                                             appauthor=__author__)
        self._base = Path(basedir)

    def memory_cache(self, size=100):
        '''Wrap this cache into a *MemoryCache*.'''
        return MemoryCache(self, size=size)

    @property
    def name(self):
        return self._service.name

    @property
    def url_pattern(self):
        return self._service.url_pattern

    @property
    def top_level_domain(self):
        return self._service.top_level_domain

    @property
    def domain(self):
        return self._service.domain

    def fetch(self, x, y, z, etag=None, cached_only=False):
        '''Attempt to serve the tile from the cache, if that fails, fetch it
        from the backing service.
        On a successful service call, put the result into the cache.

        When ``cached_only`` is *True*, the cache entry is only returned
        if it can be done so without checking the ETAG against the server.
        That is, if the cache entry is younger than ``min_hours``.
        '''
        # etag is likely to be None
        if etag is None:
            etag, mtime = self._find(x, y, z)

        # If the cached entry is not "too old", return it without checking
        # the ETAG.
        if mtime:
            modified = datetime.fromtimestamp(mtime, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            age = now - modified
            if age < self._min_age:
                cached = self._get(x, y, z, etag)
                return etag, cached

        recv_etag, data = self._service.fetch(x, y, z,
                                              etag=etag,
                                              cached_only=cached_only)
        if data is None:
            try:
                cached = self._get(x, y, z, etag)
                return etag, cached
            except LookupError:
                pass

        if data is None:
            # cache lookup failed
            recv_etag, data = self._service.fetch(x, y, z)

        self._put(x, y, z, recv_etag, data)
        return recv_etag, data

    def _get(self, x, y, z, etag):
        if not etag:
            raise LookupError

        try:
            return self._path(x, y, z, etag).read_bytes()
        except Exception:
            raise LookupError

    def _find(self, x, y, z):
        '''Finds the cache entry for tile x, y, z.

        If found, returns the ``etag`` value and the ``mtime`` of the cached
        tile.

        If no cached tile is found, returns None, None.
        '''
        # expects filename pattern:  Y.BASE64(ETAG).png
        p = self._path(x, y, z, '')
        d = p.parent
        match = '%06d.' % y

        try:
            for entry in d.iterdir():
                if entry.name.startswith(match):
                    if entry.is_file():
                        try:
                            safe_etag = entry.name.split('.')[1]
                            etag_bytes = base64.b64decode(safe_etag)
                            etag = etag_bytes.decode('ascii')

                            stat = entry.stat()
                            mtime = stat.st_mtime

                            return etag, mtime
                        except Exception:
                            # Errors if we encounter unexpected filenames
                            pass

        except FileNotFoundError:
            pass

        return None, None

    def _put(self, x, y, z, etag, data):
        if not etag:
            return

        p = self._path(x, y, z, etag)
        if p.is_file():
            return

        self._clean(x, y, z, etag)

        d = p.parent
        d.mkdir(parents=True, exist_ok=True)

        with p.open('wb') as f:
            f.write(data)

        self._vacuum()

    def _clean(self, x, y, z, current):
        '''Remove outdated cache entries for a given tile.'''
        existing, _ = self._find(x, y, z)
        if existing and existing != current:
            p = self._path(x, y, z, existing)
            p.unlink(missing_ok=True)

    def _path(self, x, y, z, etag):
        safe_etag = base64.b64encode(etag.encode()).decode('ascii')
        filename = '%06d.%s.png' % (y, safe_etag)

        return self._base.joinpath(
            self._service.name,
            '%02d' % z,
            '%06d' % x,
            filename,
        )

    def _vacuum(self):
        '''Trim the cache up to or below the limit.
        Deletes older tiles before newer ones.'''
        if not self._limit:
            return

        with self._lock:
            used = 0
            entries = []
            for base, dirname, filenames in os.walk(self._base):
                for filename in filenames:
                    path = Path(base).joinpath(filename)
                    stat = path.stat()
                    used += stat.st_size
                    entries.append((stat.st_ctime, stat.st_size, path))

            excess = used - self._limit
            if excess <= 0:
                return

            # delete some additional entries to avoid frequent deletes
            excess *= 1.1

            entries.sort()  # oldest first
            for _, size, path in entries:
                path.unlink()
                excess -= size
                if excess <= 0:
                    break

    def __repr__(self):
        return '<Cache %r>' % str(self._base)


class MemoryCache:
    '''Wraps a tile service in a memory cache.

    Up to ``size`` recently requested tiles are kept in memory.

    This cache does not make an effort to check the ``ETAG`` for a tile.
    If a tile cached tile is found for the given x, y, z coordinates, it is
    returned without checking for a more recent version.
    '''

    def __init__(self, service, size=100):
        self._service = service
        self._size = size
        self._lock = threading.Lock()
        self._values = OrderedDict()

    @property
    def name(self):
        return self._service.name

    @property
    def url_pattern(self):
        return self._service.url_pattern

    @property
    def top_level_domain(self):
        return self._service.top_level_domain

    @property
    def domain(self):
        return self._service.domain

    def fetch(self, x, y, z, etag=None, cached_only=False):
        result = None
        k = (x, y, z)
        try:
            with self._lock:
                result = self._values[k]
                # Move recently requested to the top
                self._values.move_to_end(k, last=False)

            return result
        except KeyError:
            pass

        # Cache miss, request from service
        result = self._service.fetch(x, y, z,
                                     etag=etag,
                                     cached_only=cached_only)

        # If the cache is full, remove one item (the last)
        with self._lock:
            if len(self._values) >= self._size:
                self._values.popitem(last=True)

            # Cache the result as the first (most recent) entry
            self._values[k] = result
            self._values.move_to_end(k, last=False)

        return result


class Fallback:
    '''Wraps a TileService (or cache) to fall back on a lower zoom level if the
    requested zoom level is not available.

    When the fallback tile is used, it is scaled up to match the expected pixel
    dimensions.

    This is done recursively, i.e. if zoom level 10 is requested, but only 8 is
    available, the fallback tile will be taken from zoom level 8 and scaled x2.

    The appropriate subimage is taken from the fallback tile so that the
    returned image fits in place of the originally requested tile.
    '''

    def __init__(self, service):
        self._service = service

    @property
    def name(self):
        return self._service.name

    @property
    def url_pattern(self):
        return self._service.url_pattern

    @property
    def top_level_domain(self):
        return self._service.top_level_domain

    @property
    def domain(self):
        return self._service.domain

    def fetch(self, x, y, z, etag=None, cached_only=False):
        try:
            return self._service.fetch(x, y, z,
                                       etag=etag,
                                       cached_only=cached_only)
        except Exception:
            return self._fallback(x, y, z, cached_only=cached_only)

    def _fallback(self, x, y, z, cached_only=False):
        tile = Tile(x, y, z)
        parent, offset = tile.parent()
        _LOG.info('Use fallback %s => %s', tile, parent)
        _, data = self.fetch(parent.x,
                             parent.y,
                             parent.z,
                             cached_only=cached_only)

        return None, self._subimage(data, offset)

    def _subimage(self, data, offset):
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        dx, dy = offset
        box = (w // 2 * dx,
               h // 2 * dy,
               w // 2 * (dx + 1),
               h // 2 * (dy + 1))
        # Take a quarter of the source image and resoize it to required size
        sub = img.resize(img.size, box=box)

        buf = io.BytesIO()
        sub.save(buf, format='png')
        return buf.getvalue()
