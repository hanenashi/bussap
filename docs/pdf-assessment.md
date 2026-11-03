# Supplied network PDF: historical reference

The root ` sapporobus.pdf` is a 1.8 MB, one-page, 2381 × 2310 pt vector PDF. `pdfimages -list` found no embedded raster images. Fonts are mostly embedded Japanese subsets; `pdftotext -bbox-layout` produced about 5,041 positioned words. A 1600 px overview render is useful for recognizing the overall colored network, but individual stop labels are too small to read there. The original PDF can be zoomed cleanly; its text and route strokes are not a ready-made route database.

The page itself says **2016-12-01** and **禁無断転載**, with a creator credit to 愉会三丁目. It is older than the current timetable feeds. The owner requested a reference-only viewer on the private, tailnet-only BUSSAP service. The original file remains untouched and is served inline only from that service. Do not expose this viewer on a public deployment without resolving redistribution permission.

The map has a **参考路線図 (2016年・PDF)** link that opens `/network-map` in a new tab. That page has one visible back button and uses vendored PDF.js 5.4.624 to render the original PDF into a canvas. It starts at 2.3× fit width, supports one-finger panning, two-finger pinch zoom from 1× to 32×, and double-tap zoom. A 1.5× source-resolution overview stays responsive during movement; at close zoom, PDF.js redraws only the visible phone-sized area directly from the vector PDF at up to 2× display pixel density. The viewer does not parse or copy route data. For a current network overview, construct a new diagram from present-day stop sequences and verified coordinates, then compare its broad coverage against the PDF as a private historical reference. Chuo/Jotetsu GTFS has stop sequences but no `shapes.txt`; JR Ekibus exposes route courses and stop markers. This can establish route order and approximate connections, but not exact street paths. Label any straight-line geometry approximate.

[bus-routes.net](https://bus-routes.net/) is a useful live visual cross-check and permits normal links. Its own [data explanation](https://yuru-to.net/data/detail/) says the legacy bus layer comes from 2022 national route data and the GTFS layer is refreshed from open feeds. Its [terms](https://yuru-to.net/policy/) prohibit unauthorized republication of site content, so BUSSAP links to it instead of copying its map, routes, or images.

Local inspection commands:

```sh
pdfinfo ' sapporobus.pdf'
pdfimages -list ' sapporobus.pdf'
pdffonts ' sapporobus.pdf'
pdftotext -bbox-layout ' sapporobus.pdf' /tmp/bussap-pdf-bbox.html
pdftocairo -f 1 -l 1 -scale-to 1600 -png -singlefile ' sapporobus.pdf' /tmp/bussap-pdf-overview
```
