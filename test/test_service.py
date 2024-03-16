import base64
from pathlib import Path
import shutil
from tempfile import mkdtemp
from unittest import TestCase

from mapmaker.service import Cache
from mapmaker.service import MemoryCache


class _CacheTest:
    '''Common Test cases for all implementations of a cache.'''

    def create_cache(self, service, **kwargs):
        raise NotImplementedError

    def test_name_of_wrapped_service_visible(self):
        mock = MockService()
        mock.name = 'foo-service'
        c = self.create_cache(mock)
        self.assertEqual(c.name, mock.name)

    # params are passed properly to the service
    def test_cache_passes_params_properly(self):
        '''Make sure the backing service receives the same params that were
        passed to the cache.'''
        mock = MockService()
        c = self.create_cache(mock)
        c.fetch(1, 2, 3)
        self.assertEqual(mock.last_fetch_params[0], 1)
        self.assertEqual(mock.last_fetch_params[1], 2)
        self.assertEqual(mock.last_fetch_params[2], 3)

    def test_value_is_cached(self):
        x, y, z, = 5, 5, 5
        mock = MockService()
        c = self.create_cache(mock)

        # first request should be passed on to service
        etag_0, value_0 = c.fetch(x, y, z)
        self.assertEqual(mock.fetch_count, 1)

        # request the same entry again...
        etag_1, value_1 = c.fetch(x, y, z)

        # ...should NOT have made an additional call against the service
        self.assertEqual(mock.fetch_count, 1)

        # ... and should return the same results
        self.assertEqual(etag_0, etag_1)
        self.assertEqual(value_0, value_1)


class TestCache(_CacheTest, TestCase):

    cache_dir = None

    def create_cache(self, service, basedir=None):
        if not basedir:
            basedir = self.cache_dir
        return Cache(service, basedir=basedir)

    def setUp(self):
        self.cache_dir = mkdtemp()

    def tearDown(self):
        if self.cache_dir:
            try:
                shutil.rmtree(self.cache_dir)
            except FileNotFoundError:
                pass

    def test_missing_cache_dir_as_not_cached_on_read(self):
        '''If the cache dir does not exist, it should be treated as if
        any requested entry is not in the cache (and not raise an arror).'''
        non_existing_dir = Path(self.cache_dir).joinpath('foo/bar/')
        # precondition for the test
        self.assertFalse(non_existing_dir.is_dir())

        mock = MockService()
        c = self.create_cache(mock, basedir=non_existing_dir)

        c.fetch(1, 1, 1)
        self.assertEqual(mock.fetch_count, 1)

    # creates cache dir on first write if missing

    def test_error_on_invalid_tile_names(self):
        mock = MockService()
        c = Cache(mock, basedir=self.cache_dir)

        # tile indices should be integers
        self.assertRaises(TypeError, c.fetch, 'a', 'b', 'c')
        # etag must be str (or None)
        mock.etag = 123
        self.assertRaises(Exception, c.fetch, 1, 1, 1)
        mock.etag = None

        # this works - not sure if it should
        c.fetch(1.1, 2.2, 3.3)

    def test_etag_forces_fetch(self):
        mock = MockService()
        c = Cache(mock, basedir=self.cache_dir)

        etag, _ = c.fetch(3, 4, 5)
        self.assertEqual(mock.fetch_count, 1)
        c.fetch(3, 4, 5)  # from cache
        self.assertEqual(mock.fetch_count, 1)

        # service returns different etag
        c.fetch(3, 4, 5, etag=etag)
        self.assertEqual(mock.fetch_count, 2)

    def test_handle_unusual_etag(self):
        mock = MockService()
        c = Cache(mock, basedir=self.cache_dir)

        mock.etag = ''
        etag, _ = c.fetch(3, 4, 5)
        self.assertEqual(mock.fetch_count, 1)
        etag, _ = c.fetch(3, 4, 5, etag=etag)
        self.assertEqual(mock.fetch_count, 2)

        mock.etag = None
        etag, _ = c.fetch(3, 4, 5)
        self.assertEqual(mock.fetch_count, 3)
        etag, _ = c.fetch(3, 4, 5, etag=etag)
        self.assertEqual(mock.fetch_count, 4)

    def test_etag_base64_path_separator(self):
        etag = 'subjects?_d=1'

        # precondition for the test - regular base64 encoding contains
        # a path separator (c3ViamVjdHM/X2Q9MQ==)
        naive = base64.b64encode(etag.encode()).decode('ascii')
        self.assertTrue('/' in naive)

        mock = MockService(etag=etag)
        c = Cache(mock, basedir=self.cache_dir)
        etag, value = c.fetch(2, 2, 2)

        self.assertEqual(mock.fetch_count, 1)
        c.fetch(2, 2, 2)  # from cache
        self.assertEqual(mock.fetch_count, 1)


class TestMemoryCache(_CacheTest, TestCase):

    def create_cache(self, service, size=100):
        return MemoryCache(service, size=size)

    def test_max_cache_size(self):
        mock = MockService()
        c = self.create_cache(mock, size=2)

        c.fetch(1, 1, 1)
        c.fetch(2, 2, 2)
        c.fetch(3, 3, 3)
        self.assertEqual(mock.fetch_count, 3)

        # The cache should contain 2 (max size) items now
        # The oldest one should have been removed

        c.fetch(2, 2, 2)
        c.fetch(3, 3, 3)
        self.assertEqual(mock.fetch_count, 3)  # unchanged

        c.fetch(1, 1, 1)
        self.assertEqual(mock.fetch_count, 4)  # from service

        # The most recent 2 items should be in the cahe now:
        # 1.  (1, 1, 1)
        # 2.  (3, 3, 3)
        # Let's make (3, 3, 3) most rcent again
        c.fetch(3, 3, 3)
        self.assertEqual(mock.fetch_count, 4)  # from cache

        # and have (1, 1, 1) removed
        c.fetch(5, 5, 5)
        self.assertEqual(mock.fetch_count, 5)
        c.fetch(1, 1, 1)
        self.assertEqual(mock.fetch_count, 6)


class MockService:

    name = '_mock'

    last_fetch_params = None
    fetch_count = 0

    def __init__(self, etag='xyz'):
        self.etag = etag

    def fetch(self, x, y, z, etag=None, cached_only=False):
        self.last_fetch_params = (x, y, z, etag, cached_only)
        self.fetch_count += 1

        fake_data = '%s.%s.%s' % (x, y, z)
        return self.etag, fake_data.encode('ascii')
