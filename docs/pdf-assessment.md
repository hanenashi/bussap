# Supplied network PDF: assessment before a phone viewer

The root ` sapporobus.pdf` is a 1.8 MB, one-page, 2381 × 2310 pt vector PDF. `pdfimages -list` found no embedded raster images. Fonts are mostly embedded Japanese subsets; `pdftotext -bbox-layout` produced about 5,041 positioned words. A 1600 px overview render is useful for recognizing the overall colored network, but individual stop labels are too small to read there. The original PDF can be zoomed cleanly; its text and route strokes are not a ready-made route database.

The page itself says **2016-12-01** and **禁無断転載**, with a creator credit to 愉会三丁目. It is nine years older than the current timetable feeds. Do not publish the PDF or a traced copy as a BUSSAP web asset without permission. Leave the original file untouched for now.

For a current network overview, construct a new diagram from present-day stop sequences and verified coordinates, then compare its broad coverage against the PDF as a private historical reference. Chuo/Jotetsu GTFS has stop sequences but no `shapes.txt`; JR Ekibus exposes route courses and stop markers. This can establish route order and approximate connections, but not exact street paths. Label any straight-line geometry approximate. A plain zoomable PDF viewer remains an option if redistribution permission is obtained.

[bus-routes.net](https://bus-routes.net/) is a useful live visual cross-check and permits normal links. Its own [data explanation](https://yuru-to.net/data/detail/) says the legacy bus layer comes from 2022 national route data and the GTFS layer is refreshed from open feeds. Its [terms](https://yuru-to.net/policy/) prohibit unauthorized republication of site content, so BUSSAP links to it instead of copying its map, routes, or images.

Local inspection commands:

```sh
pdfinfo ' sapporobus.pdf'
pdfimages -list ' sapporobus.pdf'
pdffonts ' sapporobus.pdf'
pdftotext -bbox-layout ' sapporobus.pdf' /tmp/bussap-pdf-bbox.html
pdftocairo -f 1 -l 1 -scale-to 1600 -png -singlefile ' sapporobus.pdf' /tmp/bussap-pdf-overview
```
