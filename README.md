# Car Data Scraper

A Python web scraper for collecting comprehensive car model data from Chinese automotive websites (Autohome).

## Features

- Scrapes complete vehicle data (20+ fields) from Autohome
- Saves data to SQLite database
- Exports to CSV and Excel formats
- Supports resume from interruption
- Anti-detection measures: random User-Agent, request delays, session management
- Batch processing with automatic pauses

## Data Fields

- Brand / Sub-brand
- Series ID / Name
- Model ID / Name
- Year
- Official Price / Dealer Price
- Body Structure
- Energy Type
- Seats
- Dimensions (L*W*H)
- Wheelbase
- Engine / Motor
- Transmission
- Drive Mode
- Fuel Consumption
- EV Range
- Charging Time
- Vehicle Level
- Launch Date
- Status

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Full Crawl
```bash
python main.py
```

### Dry Run (brand list only)
```bash
python main.py --dry-run
```

### Test Mode (1 series only)
```bash
python main.py --test
```

### Retry Failed Tasks
```bash
python main.py --retry-failed
```

### Export Only
```bash
python main.py --export-only
```

### Specify Letter Range
```bash
python main.py --start-letter A --end-letter C
```

## Output

- Database: `result/car_data.db`
- CSV: `result/car_data.csv`
- Excel: `result/car_data.xlsx`

## License

MIT License - See [LICENSE](LICENSE) for details.

## Author

WangYang (forza_wy@outlook.com)
