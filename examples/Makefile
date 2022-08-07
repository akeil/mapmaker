OUTDIR := ./out


# GeoJSON ---------------------------------------------------------------------

geojson: feature feature-collection geometry-collection


geometry-collection: outdir
	mapmaker 56.796893,-5.003376 1km\
	 $(OUTDIR)/geometry-collection.png\
	 --style atlas\
	 --zoom 15\
	 --title Ben Nevis\
	 --comment GeoJSON GeometryCollection\
	 --margin 15\
	 --frame 3 160,160,160\
	 --geojson ./geometry-collection.json


feature: outdir
	mapmaker 55.689763,12.583541 1km\
	 $(OUTDIR)/feature.png\
	 --style positron\
	 --zoom 14\
	 --title Copenhagen\
	 --comment GeoJSON Feature\
	 --margin 15\
	 --frame 3 160,160,160\
	 --geojson ./feature.json


feature-collection: outdir
	mapmaker 47.681484,8.621135 1km\
	 $(OUTDIR)/feature-collection.png\
	 --style positron\
	 --zoom 15\
	 --title Schaffhausen\
	 --comment GeoJSON FeatureCollection\
	 --margin 15\
	 --frame 3 160,160,160\
	 --geojson ./feature-collection.json


outdir:
	mkdir -p $(OUTDIR)


clean:
	rm $(OUTDIR)/* || true
