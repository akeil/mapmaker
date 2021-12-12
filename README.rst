Map Maker
#########
``mapmaker`` is a simple script to generate map images for "Slippy Tile" maps.
Map tiles are downloaded from services such as OpenStreetMap and are combined
into a single image.


Installation
============
Use the installation script:

.. code:: shell-session

    $ python setup.py install

Or install using pip:

.. code:: shell-session

    $ pip install mapmaker


Command Line Usage
==================
Use ``mapmaker --help`` to show a detailed list of options.


Basic Usage
-----------
This will create a file ``map.png`` in the current directory. The map will
cover the bounding box specified with two pairs of lat/lon coordinates:

.. code:: shell-session

    $ mapmaker  47.44,10.95 47.37,11.13

One can also specify a center point and a radius:

.. code:: shell-session

    $ mapmaker 63.0695,-151.0074 100km

If the coordinates start with a negative value, use ``--`` to indicate the
end of command line flags:

.. code:: shell-session

    $ mapmaker -- -32.653197,-70.0112 100km

Coordinates can also be specified in DMS format:

.. code:: shell-session

    $ mapmaker "63°4'10.2'' N, 151°0'26.64'' W" 4km

Use a single quote for minutes (``'``)
and two single quotes (``''``) for seconds.
Note the quotes around the command line argument.


You can also specify the **output file** (default is *map.png*):

.. code:: shell-session

    $ mapmaker 63.0695,-151.0074 100km denali.png


Additional Options
------------------
Specify the **zoom level** with the ``--zoom`` flag. The default is 8.
Higher values mean more detail and result in larger map images.

.. code:: shell-session

    $ mapmaker --zoom 12 63.0695,-151.0074 100km

Use ``--style`` to control the **look** of the map:

.. code:: shell-session

    $ mapmaker --style human 63.0695,-151.0074 100km

Use the ``--shading`` flag to overlay a hillshading layer over the map image.
Note that hillshading is not available for all regions.

.. code:: shell-session

    $ mapmaker --shading 45.83,6.88 100km

Note that some map styles already come with hillshading.

To control the resulting image format, use ``--aspect``:

.. code:: shell-session

    $ mapmaker --aspect 16:9 45.83,6.88 100km

The aspect ratio is given in the format ``W:H`` (e.g. 4:3 or 19:9).
The resulting map image will contain the given bounding box (or point w/ radius)
and max be extended to North/South or East/West to match the aspect ratio.
Note that the *resolution* of the image depends on the ``--zoom`` factor.


Create a Gallery
----------------
Use the ``--gallery`` flag to render a set of maps, one for each available style.
In this case, you specify an output directory instead of a file (default is the
current directory).
This flag ignores the ``--style`` parameter.


Configuration
#############
The configuration file is located at ``~/.config/mapmaker/config.ini``


Styles (Tile Servers)
=====================
You can specify additional map styles like this:

.. code:: ini

    # ~/.config/mapmaker/config.ini

    [services]
    osm   = https://tile.openstreetmap.org/{z}/{x}/{y}.png
    topo  = https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png

Where ``osm`` is the name of the style (as used in the ``--style`` flag) and
the URL is the URL pattern for downloading tiles.

The URL pattern contains three variables:

:z: zoom level
:x: X-coordinate of the tile
:y: Y-coordinate of the tile

See for example https://wiki.openstreetmap.org/wiki/Tiles.

The URL may contain an additional placeholder for an API Key (see below)::

    atlas = https://tile.thunderforest.com/atlas/{z}/{x}/{y}.png?apikey={api}
                                                                         ^^^


Authorization
=============
Authorization is needed for the following services:

======================= ======= ======================================
Domain                  Type    Homepage
======================= ======= ======================================
tile.thunderforest.com  API Key https://www.thunderforest.com/
maps.geoapify.com       API Key https://www.geoapify.com/
api.mapbox.com          Token   https://mapbox.com/
======================= ======= ======================================

Most services offer a free plan for limited/non-commercial use. Check out the
URL from the table above.

Once you have registered, place your API Keys in a config file like this:

.. code:: ini

    # ~/.config/mapmaker/config.ini

    [keys]
    tile.thunderforest.com  = YOUR_API_KEY
    maps.geoapify.com       = YOUR_API_KEY
    api.mapbox.com          = YOUR_API_KEY

Where ``tile.thunderforest.com`` is the domain from which the image tiles are
requested.
