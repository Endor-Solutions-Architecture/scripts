# scan_results
Generate a report of scan results over a given time period in either csv of excel format.

## set up script
```
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## set up environment
```
export ENDOR_API_CREDENTIALS_KEY=<your API Key>
export ENDOR_API_CREDENTIALS_SECRET=<your API Secret>
export ENDOR_NAMESPACE=<namespace>
```

## generate csv report
```
python3 report_scan_results_over_time.py --start-date="2024-07-15" --query-file=query.scan_results_over_time_context_main.json  make-csv
```

## generate excel report
```
python3 report_scan_results_over_time.py --start-date="2024-07-15" --query-file=query.scan_results_over_time_context_main.json  make-excel
```
