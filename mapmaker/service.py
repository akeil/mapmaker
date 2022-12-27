import base64
import os
from pathlib import Path
from urllib.parse import urlparse
import threading

import appdirs
import requests

from mapmaker import __version__
from mapmaker import __author__
from mapmaker import __name__ as APP_NAME


class TileService:
    '''A web service that fetches slippy map tiles in OSM format.'''

    def __init__(self, name, url_pattern, api_keys):
        self.name = name
        self.url_pattern = url_pattern
        self._api_keys = api_keys or {}

    def cached(self, basedir=None, limit=None):
        '''Wrap this tile service in a file system cache with default
        parameters.

        If ``basedir`` is set, this will be used as the base directory for
        the cache. If *None*, the default directory will be used.

        If ``limit`` is set, the cache sized is limited to that size.
        '''
        return Cache(self, basedir=basedir, limit=limit)

    @property
    def top_level_domain(self):
        parts = self.domain.split('.')
        # TODO: not quite correct, will fail e.g. for 'foo.co.uk'
        return '.'.join(parts[-2:])

    @property
    def domain(self):
        parts = urlparse(self.url_pattern)
        return parts.netloc

    def fetch(self, x, y, z, etag=None):
        '''Fetch the given tile from the Map Tile Service.

        ``x, y, z`` are the tile coordinates and zoom level.

        If an ``etag`` is specified, it will be sent to the server.
        If the server replies with a status "Not Modified", this method
        returns *None* instead of the tile data.

        Returns the response ``etag`` and the raw image data.
        '''
        url = self.url_pattern.format(
            x=x,
            y=y,
            z=z,
            s='a',  # TODO: abc
            api=self._api_key(),
        )

        headers = {
            'User-Agent': '%s/%s +https://github.com/akeil/mapmaker' % (APP_NAME, __version__)
        }
        if etag:
            headers['If-None-Match'] = etag

        res = requests.get(url, headers=headers)
        res.raise_for_status()

        if res.status_code == 304:
            return etag, None

        recv_etag = res.headers.get('etag')
        return recv_etag, res.content

    def _api_key(self):
        return self._api_keys.get(self.domain, '')

    def __repr__(self):
        return '<TileService name=%r>' % self.name


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
    '''

    def __init__(self, service, basedir=None, limit=None):
        self._service = service
        self._limit = limit
        self._lock = threading.Lock()

        if not basedir:
            basedir = appdirs.user_cache_dir(appname=APP_NAME,
                                             appauthor=__author__)
        self._base = Path(basedir)

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

    def fetch(self, x, y, z, etag=None):
        '''Attempt to serve the tile from the cache, if that fails, fetch it
        from the backing service.
        On a successful service call, put the result into the cache.'''
        # etag is likely to be None
        if etag is None:
            etag = self._find(x, y, z)

        recv_etag, data = self._service.fetch(x, y, z, etag=etag)
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
                            return etag_bytes.decode('ascii')
                        except Exception:
                            # Errors if we encounter unexpected filenames
                            pass

        except FileNotFoundError:
            pass

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
        existing = self._find(x, y, z)
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
