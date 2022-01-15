import io
from math import ceil
import queue
import threading

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


# Most (all?) services will return tiles this size
DEFAULT_TILESIZE = (256, 256)


class RenderContext:
    '''Renders a map, downloading required tiles on the fly.'''

    def __init__(self, service, map, overlays=None, parallel_downloads=None, reporter=None):
        self._service = service
        self._map = map
        self._overlays = overlays or []
        self._parallel_downloads = parallel_downloads or 1
        self._report = reporter or _no_reporter
        self._queue = queue.Queue()
        self._lock = threading.Lock()
        # will be set to the actual size once the first tile is downloaded
        self._tile_size = DEFAULT_TILESIZE
        self._img = None
        self._total_tiles = 0
        self._downloaded_tiles = 0

    def _tile_complete(self):
        self._downloaded_tiles += 1
        percentage = int(self._downloaded_tiles / self._total_tiles * 100.0)
        self._report('%3d%%  %4d / %4d',
            percentage,
            self._downloaded_tiles,
            self._total_tiles)

    @property
    def crop_box(self):
        '''Get the crop box that will be applied to the stitched map.'''
        bbox = self._map.bbox
        left, bottom = self.to_pixels(bbox.minlat, bbox.minlon)
        right, top = self.to_pixels(bbox.maxlat, bbox.maxlon)

        return (left, top, right, bottom)

    @property
    def bbox(self):
        '''The maps bounding box coordinates.'''
        return self._map.bbox

    def build(self):
        '''Download tiles on the fly and render them into an image.'''
        # fill the task queue
        for tile in self._map.tiles.values():
            self._queue.put(tile)

        self._total_tiles = self._queue.qsize()
        self._report('Download %d tiles (parallel downloads: %d)', self._total_tiles, self._parallel_downloads)

        # start parallel downloads
        for w in range(self._parallel_downloads):
            threading.Thread(daemon=True, target=self._work).run()

        self._queue.join()

        self._report('Download complete, create map image')

        if self._overlays:
            self._report('Draw %d overlays', len(self._overlays))
            self._draw_overlays()

        self._crop()
        return self._img

    def to_pixels(self, lat, lon):
        '''Convert the given lat,lon coordinates to pixels on the map image.

        This method can only be used after the first tiles have been downloaded
        and the tile size is known.
        '''
        frac_x, frac_y = self._map.to_pixel_fractions(lat, lon)
        w, h = self._tile_size

        def px(v):
            return int(ceil(v))

        return px(frac_x * w), px(frac_y * h)

    def _draw_overlays(self):
        '''Draw overlay layers on the map image.'''
        # For transparent overlays, we cannot paint directly on the image.
        # Instead, paint on a separate overlay image and compose the results.
        for layer in self._overlays:
            overlay = Image.new('RGBA', self._img.size, color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay, mode='RGBA')
            layer._draw(self, draw)
            self._img.alpha_composite(overlay)

    def _crop(self):
        '''Crop the map image to the bounding box.'''
        self._img = self._img.crop(self.crop_box)

    def _work(self):
        '''Download map tiles and paste them onto the result image.'''
        while True:
            try:
                tile = self._queue.get(block=False)
                try:
                    _, data = self._service.fetch(tile)
                    tile_img = Image.open(io.BytesIO(data))
                    with self._lock:
                        self._paste_tile(tile_img, tile.x, tile.y)
                        self._tile_complete()
                finally:
                    self._queue.task_done()
            except queue.Empty:
                return

    def _paste_tile(self, tile_img, x, y):
        '''Paste a tile image on the main map image.'''
        w, h = tile_img.size
        self._tile_size = w, h  # assume that all tiles have the same size
        if self._img is None:
            xtiles = self._map.bx - self._map.ax + 1
            width = w * xtiles
            ytiles = self._map.by - self._map.ay + 1
            height = h * ytiles
            self._img = Image.new('RGBA', (width, height))

        top = (x - self._map.ax) * w
        left = (y - self._map.ay) * h
        box = (top, left)
        self._img.paste(tile_img, box)


def _no_reporter(*args):
    pass


def load_font(font_name, font_size):
    '''Load the given true type font, return fallback on failure.'''
    try:
        return ImageFont.truetype(font=font_name, size=font_size)
    except OSError:
        return ImageFont.load_default()
