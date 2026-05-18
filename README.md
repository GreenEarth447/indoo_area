# Building Indoor Area Demo

Estimates indoor floor area (sqm) per building and per floor from Google Street View + satellite imagery.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
copy config.example.yaml config.yaml
```

Set `GOOGLE_MAPS_API_KEY` in `.env`. Enable Geocoding API, Maps Static API, and Street View Static API on the Google Cloud project (billing required).

## Run

```bash
python check_google_key.py
python run_demo.py --continue-on-error
```

Single building:

```bash
python run_demo.py --address "Empire State Building, 20 W 34th St, New York, NY 10001"
```

Building list: `buildings_demo.yaml` (10 NYC landmarks). Batch summary: `outputs/batch_summary_*.csv`.

## Output

Per building under `outputs/<slug>/`:

- `result.json` — footprint, floors, indoor sqm per floor
- `satellite.jpg`, `streetview/` — source imagery
- `summary.png` — quick report

## Notes

- Indoor sqm is estimated from exterior imagery (footprint × floors × efficiency factor).
- Tall buildings use OSM height/levels when Street View cannot show the full facade.
