import base64
import os
from pathlib import Path
from urllib.parse import urlparse
import threading

import requests

from mapmaker import __version__


class TileService:
    '''A web service that fetches slippy map tiles in OSM format.'''

    def __init__(self, name, url_pattern, api_keys):
        self.name = name
        self.url_pattern = url_pattern
        self._api_keys = api_keys or {}

    @property
    def top_level_domain(self):
        parts = self.domain.split('.')
        # TODO: not quite correct, will fail e.g. for 'foo.co.uk'
        return '.'.join(parts[-2:])

    @property
    def domain(self):
        parts = urlparse(self.url_pattern)
        return parts.netloc

    def fetch(self, tile, etag=None):
        '''Fetch the given tile from the Map Tile Service.

        If an etag is specified, it will be sent to the server. If the server
        replies with a status "Not Modified", this method returns +None*.'''
        url = self.url_pattern.format(
            x=tile.x,
            y=tile.y,
            z=tile.zoom,
            s='a',  # TODO: abc
            api=self._api_key(),
        )

        headers = {
            'User-Agent': 'mapmaker/%s +https://github.com/akeil/mapmaker' % __version__
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
    '''

    def __init__(self, service, basedir, limit=None):
        self._service = service
        self._base = Path(basedir)
        self._limit = limit
        self._lock = threading.Lock()

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

    def fetch(self, tile, etag=None):
        '''Attempt to serve the tile from the cache, if that fails, fetch it
        from the backing service.
        On a successful service call, put the result into the cache.'''
        # etag is likely to be None
        if etag is None:
            etag = self._find(tile)

        recv_etag, data = self._service.fetch(tile, etag=etag)
        if data is None:
            try:
                cached = self._get(tile, etag)
                return etag, cached
            except LookupError:
                pass

        if data is None:
            # cache lookup failed
            recv_etag, data = self._service.fetch(tile)

        self._put(tile, recv_etag, data)
        return recv_etag, data

    def _get(self, tile, etag):
        if not etag:
            raise LookupError

        try:
            return self._path(tile, etag).read_bytes()
        except Exception:
            raise LookupError

    def _find(self, tile):
        # expects filename pattern:  Y.BASE64(ETAG).png
        p = self._path(tile, '')
        d = p.parent
        match = '%06d.' % tile.y

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

    def _put(self, tile, etag, data):
        if not etag:
            return

        p = self._path(tile, etag)
        if p.is_file():
            return

        self._clean(tile, etag)

        d = p.parent
        d.mkdir(parents=True, exist_ok=True)

        with p.open('wb') as f:
            f.write(data)

        self._vacuum()

    def _clean(self, tile, current):
        '''Remove outdated cache entries for a given tile.'''
        existing = self._find(tile)
        if existing and existing != current:
            p = self._path(tile, existing)
            p.unlink(missing_ok=True)

    def _path(self, tile, etag):
        safe_etag = base64.b64encode(etag.encode()).decode('ascii')
        filename = '%06d.%s.png' % (tile.y, safe_etag)

        return self._base.joinpath(
            self._service.name,
            '%02d' % tile.zoom,
            '%06d' % tile.x,
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
