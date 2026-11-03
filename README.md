# BUSSAP

Personal Sapporo bus map and timetable project. The current code is a small source-validation CLI for Hokkaido Chuo Bus, Jotetsu, and JR Hokkaido Bus local routes. There is no phone UI yet. See [battleplan.md](battleplan.md) and [docs/source-inventory.md](docs/source-inventory.md).

## Source query on Beechan

Python 3 with the standard library is sufficient. The owner has completed HODA's use-purpose form. Run from the repository root:

```sh
python3 scripts/departures.py refresh all
python3 scripts/departures.py find-stops jotetsu --name 札幌駅
python3 scripts/departures.py query jotetsu --stop S010800000100100 --date 2026-11-07 --route 南５４ --destination 南町四丁目 --limit 3
python3 scripts/departures.py find-stops jr --name 新札幌駅
python3 scripts/departures.py jr-patterns --stop 340238 --limit 5
python3 scripts/departures.py query jr --stop 340238 --pattern 340044:340100-0 --date 2026-11-03 --limit 3
```

`refresh` validates and atomically replaces the two GTFS ZIPs in ignored `.local-data/`, retaining a `.previous.zip` backup. `BUSSAP_DATA_DIR` can point to another local cache directory. `find-stops` returns source-specific boarding IDs; shared names can refer to several different curbside positions. JR patterns include line, course, direction and boarding number.

GTFS queries apply `calendar.txt` plus `calendar_dates.txt`, reject dates outside feed coverage, and return `scheduled_at` in Asia/Tokyo. The `--date` is the **service date**: a GTFS time such as `25:15:00` belongs to that service day and gets a next-calendar-day timestamp. `--after` uses the same service-day clock and accepts times beyond 24:00.

JR queries infer one of Ekibus's four day categories using the [Cabinet Office 2026–2027 holiday list](https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html), or `--jr-category` can select one explicitly. The result is labeled `day_category_candidate_unverified_for_date` and carries the user-facing warning `cant promise correct times now`. The API does not establish seasonal validity or exceptional operations for a requested date. The bounded `python3 scripts/probe_jr.py` checks three known local patterns against the audit fixture; a changed revision causes the query to withhold departures until reviewed.

Run the small local tests with:

```sh
python3 -m unittest discover -s tests -v
```
