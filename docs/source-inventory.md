# Source inventory — initial audit

Checked 2026-11-03. A listing or accessible website is not proof of usable, current schedules.

| Source | Observed | Still to verify |
| --- | --- | --- |
| [HODA Chuo GTFS](https://ckan.hoda.jp/dataset/gtfs-data/resource/dbadfccc-670e-49b9-be77-c3f346ee3160) | ZIP updated 2026-10-29; CC Attribution. 185 routes, 3,863 stop records, 8,639 trips, 200,801 stop-time rows. Declared coverage 2026-10-01 to 2027-03-31. 2,483 stop records fall in a rough Sapporo bounding box. | Representative official-time comparisons, route labels, shapes, update cadence |
| [HODA Jotetsu GTFS](https://ckan.hoda.jp/dataset/gtfs-data/resource/fef98fef-6fe2-472f-bde3-9d4f0a509a4a) | ZIP updated 2026-10-22; CC Attribution. 33 routes, 348 stop records, 1,468 trips, 33,435 stop-time rows. Same declared coverage. All 348 stops fall in the rough Sapporo box. | Representative official-time comparisons, route labels, shapes, update cadence |
| [Sapporo Ekibus](https://ekibus.city.sapporo.jp/) | JR local departures retrieved for three routes using the site's POST timetable endpoint; API revision 2026-04-01. Site publishes seasonal and special-service caveats. | Visible UI/operator comparison, full coverage, calendar exceptions, rate limits, stable IDs |
| [JR Hokkaido Bus local routes](https://www.jrhokkaidobus.com/timetable/routebus_sapporo/) | Operator links to Busdia; its [PDF timetable index](https://www.jrhokkaidobus.com/timetable/time/) offers 2026-04 local schedules | Match three API samples to operator PDFs. Busdia homepage timed out from Beechan on 2026-11-03. |
| Root ` sapporobus.pdf` | One-page, 2016-12-01 network map; text is extractable; `禁無断転載` printed on page | Current relevance and permission to redistribute in any deployed app |

The owner confirmed completing the [HODA use-purpose form](https://ckan.hoda.jp/dataset/gtfs-data) before the ZIP downloads. The ZIPs are kept outside the repository at `/tmp/bussap-audit/`.

## GTFS checks

The Chuo ZIP SHA-256 was `3366bb558e1598065c0593795b0025937b4d9dab22e7f6c148d61383a320ead2`; Jotetsu was `8f7fa6e1e8d934669396a44652bac604d3fa6679b46cdcf37b9580be33e2aec5`. Both identify `Asia/Tokyo` and Jorudan as feed publisher. Both have `calendar_dates.txt`, but no `shapes.txt`; every `route_short_name` inspected was empty. Coordinates are populated and inside broad Hokkaido bounds. Duplicate stop names occur across distinct IDs and boarding positions.

Applying calendar and exception rows yielded active trip counts on 2026-11-03 (Culture Day) of 3,621 Chuo and 641 Jotetsu; 2026-11-04 had 5,494 and 851; 2027-04-01 had zero because it is outside declared coverage. These are structural checks, not yet verified departure-time matches.

## JR local timetable probe

The site's [APIService.js](https://ekibus.city.sapporo.jp/js/ngServices/APIService.js) sends POST requests to `https://ekibus-api.city.sapporo.jp`. Stop search uses `/get_route_prediction`, routes at a stop use `/Get_station_linelist`, and the visible timetable panel uses `/Get_station_linelist_timetable`. `get_station_data` returned coordinates for JR stop 340238. The API sent `Access-Control-Allow-Origin: *` in one observed response; browser behavior remains to be tested.

The route pattern is assembled by the site's [timeResultController.js](https://ekibus.city.sapporo.jp/js/ngControllers/timeResultController.js) as `line_id:course_id-pos`. Example reproducible request:

```sh
curl -fsS -X POST https://ekibus-api.city.sapporo.jp/Get_station_linelist_timetable \
  -d 'kind=0&pattern=340044:340100-0&departure_station_id=340238'
```

Compact observations. The first three departures in both day columns were visually checked against JR's 2026-04 operator PDFs: [No.12](https://www.jrhokkaidobus.com/pdf/timetable/2026_04/12.pdf) for 新１２ and [No.3](https://www.jrhokkaidobus.com/pdf/timetable/2026_04/03.pdf) for 琴２９ and 宮４９.

| JR local stop / route | Pattern | Weekday `dia_flg=1` | Weekend example `dia_flg=2` | Revision |
| --- | --- | --- | --- | --- |
| 新札幌駅, 中央通線[新１２] toward 厚別営業所前, boarding point 1 | `340044:340100-0` | 07:50, 08:30, 09:08; 20 total | 07:50, 08:20, 09:00; 16 total | 2026-04-01 |
| ＪＲ琴似駅, 琴似西野線[琴２９] toward 地下鉄宮の沢駅前, boarding point 6 | `340096:340373-0` | 06:58, 07:36, 08:27; 16 total | 07:00, 08:00, 09:00; 12 total | 2026-04-01 |
| 地下鉄宮の沢駅前, 新発寒線[宮４９] toward 手稲駅北口, boarding point 6 | `340006:340011-0` | 06:32, 07:14, 07:43; 10 total | 06:32, 07:10, 07:50; 9 total | 2026-04-01 |

The timetable endpoint returns four day categories: weekday; first/third/fifth Saturdays; second/fourth Saturdays; Sunday/holidays. The three samples had identical times in categories 2–4, but that must not be generalized to other routes. This endpoint has no requested date, so special closures and future season changes cannot be inferred from its response alone. A second endpoint, `/get_time_table`, returned weekday and Saturday lists for these routes but HTTP 500 for categories 3 and 4; the panel endpoint is the better candidate.

**Current confidence:** JR regular local data is reachable, and three routes' first three weekday and weekend departures match independent 2026-04 operator PDFs. This proves a useful current-revision schedule path. A production-ready JR adapter still needs broad route coverage checks, full-table comparisons, handling of first/third/fifth vs second/fourth Saturdays, and a separate plan for seasonal changes and exceptional dates.

The operator's [Shin-Sapporo terminal guide](https://www.jrhokkaidobus.com/timetable/terminal/shinsapporo/) independently lists 新１２ from boarding point 1, and its [Miyanosawa terminal guide](https://www.jrhokkaidobus.com/timetable/terminal/miyanosawa/) independently lists 宮４９ from boarding point 6. JR's 2026-04 PDFs are image-based; the six three-time comparisons above were made visually after rendering pages 1 and 2 locally. The PDF route diagrams offer a fallback for route shape context, subject to reuse rights.

The bounded live probe is `python3 scripts/probe_jr.py`. Its [fixture](../fixtures/jr_local_samples.json) contains only three sample identities, the observed revision, first three times per day category, and operator PDF links. It makes three POST requests with a short pause; it fails when the revision, route identity or sample times change. A pass is a source-health check, not proof of all routes or of a particular future date.

## GTFS versus operator timetable samples

GTFS `calendar.txt` and `calendar_dates.txt` were applied for Wednesday 2026-11-04 and Saturday 2026-11-07 before selecting trips. Times below are from one direction and one exact boarding stop ID. They match the indicated operator PDFs' first three times for the corresponding weekday and Saturday/Sunday/holiday columns.

| Operator | GTFS boarding stop / direction | 2026-11-04 first three | 2026-11-07 first three | Operator timetable |
| --- | --- | --- | --- | --- |
| Chuo | `S010200009900800`, 地下鉄麻生駅, 麻０５ to 屯田６条１２丁目 | 07:40, 08:45, 09:47 | 08:06, 09:06, 10:06 | [2026 summer Sapporo L PDF](https://www.chuo-bus.co.jp/feature/dia-summer2026/pdf/sapporo_L.pdf), 麻０５ table |
| Jotetsu | `S010800000100100`, 札幌駅, 南５４ to 南町四丁目 | 06:58, 07:25, 08:00 | 06:55, 07:40, 08:10 | [2026-04 Sapporo stop 25 PDF](https://www.jotetsu.co.jp/bus/times/260401/sapporoeki-25.pdf), 南５４ table |

Jotetsu's GTFS stop has `platform_code=２５`, consistent with its Sapporo stop 25 timetable. The Chuo sample has no platform code; its coordinates distinguish it from other stops named 地下鉄麻生駅. These comparisons confirm two sample patterns in the current operator timetables, not full feed accuracy. Recheck when Chuo's winter timetable takes effect.

## JR date and season follow-up, 2026-11-03

The operator's [current timetable index](https://www.jrhokkaidobus.com/timetable/time/) links April 2026 PDFs, and the seven additional ordinary local patterns sampled at 札幌駅前 all reported Ekibus revision `20260401`. Their first/third/fifth Saturday (`dia_flg=2`) and second/fourth Saturday (`dia_flg=3`) lists were identical. This is a seven-pattern observation, **not** a rule for every JR route. One sampled 快速６４ pattern had weekday trips but zero departures in all three weekend categories. The earlier three PDF-checked patterns also retained the same April revision.

The Ekibus site's `get_holiday` endpoint was probed with a date string. It returned `holiday: "true"` for 2026-11-03 and 2026-11-07, and `"false"` for 2026-11-04. It also returned `"false"` for **2027-01-01** and **2027-03-22**, both listed as holidays by the [Cabinet Office](https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html). Its holiday data therefore cannot be trusted for future years without checking its coverage. BUSSAP's CLI uses the Cabinet Office's published 2026–2027 dates instead; that determines a day category, not whether the operator will actually run that category on an exceptional date.

The JR endpoint still gives no validity end date and no date-specific exception list. The operator's April PDFs establish the timetable revision and allow manual comparisons, but not the exact end of validity or future year-end operation. **Do not promote JR category times to verified date-specific departures yet.** A changed Ekibus revision now causes the CLI to return `source_revision_changed_review_required` with no departures. The next practical source check is an accessible Busdia timetable or a new operator notice/PDF when the next revision is published; compare route changes and special dates before expanding validity.
