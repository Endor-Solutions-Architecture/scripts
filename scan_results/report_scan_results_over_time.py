import json
import re
import sys
import logging
import csv
import uuid
from types import SimpleNamespace
import colorlog
import requests
import typer
import pandas as pd
import openpyxl

# format for color coded logging
FORMAT = "%(log_color)s%(levelname)s%(reset)s | %(asctime)s | %(message)s"

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(FORMAT))

logger = colorlog.getLogger(__name__)
logger.addHandler(handler)

logger.setLevel(logging.INFO)

cli = typer.Typer(add_completion=False, pretty_exceptions_enable=False)

@cli.callback(no_args_is_help=True)
def main(
    ctx: typer.Context,
    start_date: str = typer.Option(
        ...,
        envvar="START_DATE",
        help="include scan result data after or equal to this date",
    ),
    end_date: str = typer.Option(
        None,
        envvar="END_DATE",
        help="include scan result data before or equal to this date",
    ),
    query_file: str = typer.Option(
        ...,
        envvar="QUERY_FILE",
        help="file containing the query to execute",
    ),
    api_key: str = typer.Option(
        ...,
        envvar="ENDOR_API_CREDENTIALS_KEY",
        help="API key for Endor Labs",
    ),
    api_secret: str = typer.Option(
        ...,
        envvar="ENDOR_API_CREDENTIALS_SECRET",
        help="API secret for Endor Labs",
    ),
    namespace: str = typer.Option(
        ...,
        envvar="ENDOR_NAMESPACE",
        help="Namespace within ENDOR_LABS",
    ),
    debug: bool = typer.Option(False, help="Set log level to debug"),
):
    """
    Post process scan results data
    """
    if debug:
        logger.info("*** DEBUG MODE ENABLED ***")
        logger.setLevel(logging.DEBUG)

    logger.info(f"Namespace: {namespace}")
    logger.info(f"Start Date: {start_date}")

    if end_date:
      logger.info(f"end_date: {end_date}")

    # get an auth token and make it accessible globally
    global auth_token
    auth_token = endor_api_get_auth_token(api_key, api_secret)

    logger.info("Obtained Auth token")

    # load and run query from query_file
    query_json = load_query(query_file, start_date, end_date, namespace)

    logger.info(f"Pulling historical scans, please wait...")
    
    # get the data from API
    scan_results = endor_api_query(
        query_json = query_json,
        namespace = namespace
    )

    logger.info(f"{len(scan_results)} scan results found")

    # for convenience store data for typer commands to share
    ctx.obj = SimpleNamespace(
        api_key = api_key,
        api_secret = api_secret,
        namespace = namespace,
        start_date = start_date,
        end_date = end_date,
        query_json = query_json,
        query_file = query_file,
        scan_results = scan_results,
    )


@cli.command()
def make_csv(ctx: typer.Context):
    """
    Generate CSV output
    """
    csv_filename = f"{ctx.obj.query_file}.{uuid.uuid4()}.csv"

    _make_csv_file(scan_results=ctx.obj.scan_results, csv_filename=f"{csv_filename}")

    logger.info(f"CSV report generated @ {csv_filename}\n")
    
@cli.command()
def make_excel(ctx: typer.Context):
    """
    Generate Excel (.xlsx) output (in addition to CSV)
    """
    csv_filename = f"{ctx.obj.query_file}.{uuid.uuid4()}.csv"
    excel_filename = f"{ctx.obj.query_file}.{uuid.uuid4()}.xlsx"

    _make_csv_file(scan_results=ctx.obj.scan_results, csv_filename=f"{csv_filename}")
    logger.info(f"CSV report generated @ {csv_filename}\n")

    _make_excel_file(csv_filename, excel_filename)
    logger.info(f"Excel report generated @ {excel_filename}")

def _make_excel_file(csv_filename, excel_filename):
    # Step 1: Load CSV data into a DataFrame
    df = pd.read_csv(csv_filename)

    df = df.sort_values(by=['project_short_name', 'scan_start_time'], ascending=[True, False])

    # Step 2: Write the DataFrame to an Excel file (without formatting yet)
    df.to_excel(excel_filename, index=False)

    # Step 3: Load the workbook and select the active worksheet
    workbook = openpyxl.load_workbook(excel_filename)
    worksheet = workbook.active

    # Step 4: Freeze the top row
    worksheet.freeze_panes = worksheet['A2']

    # Step 5: Color the top row gray
    gray_fill = openpyxl.styles.PatternFill(start_color='CCCCCC', end_color='CCCCCC', fill_type='solid')
    for cell in worksheet[1]:
        cell.fill = gray_fill

    # Step 6: Set automatic column width
    for col in worksheet.columns:
        max_length = 0
        column = col[0].column_letter  # Get the column name
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)
        worksheet.column_dimensions[column].width = adjusted_width

    # Hide some columns
    # scan_end_time
    worksheet.column_dimensions['C'].hidden = True
    # scan_duration_ms
    worksheet.column_dimensions['E'].hidden = True

    # Step 7: Save the workbook
    workbook.save(excel_filename)

def _make_csv_file(scan_results, csv_filename):
     # Define the CSV header
    header = [
    'project_short_name', 'scan_start_time', 'scan_end_time', 'scan_status', 
    'scan_duration_ms', 'scan_duration_h_m_s', 'scan_duration_h', 'scan_duration_m', 'scan_duration_s', 
    'num_packages_approximate', 'num_packages_full', 'quick_scan', 'as_default_branch', 'detached_ref_name', 
    'refs', 'build', 'host_arch', 'host_os', 'host_memory', 'host_num_cpus', 'endorctl_version', 
    'exit_code_status', 'project_uuid', 'scan_uuid', 'project_name',
    ]

    # Open the output file for writing
    with open(csv_filename, 'w', newline='') as csvfile:
        # Initialize the CSV writer
        writer = csv.DictWriter(csvfile, fieldnames=header)
        
        # Write the header row
        writer.writeheader()

        for scan_result in scan_results:
            project_name = scan_result['meta']['references']['Project']['list']['objects'][0]['meta']['name']
            project_short_name = extract_path(project_name)
            project_uuid = scan_result['meta']['parent_uuid']
            scan_uuid = scan_result['uuid']
            spec = scan_result['spec']
            
            # Extract environment and stats
            environment = spec.get('environment', {})
            stats = spec.get('stats', {})
            runtimes = spec.get('runtimes', {})
            scan_config = environment.get('config').get('ScanConfig')
            quick_scan = scan_config.get('QuickScan')
            as_default_branch = scan_config['AsDefaultBranch']
            build = scan_config['Build']
            detached_ref_name = scan_config['DetachedRefName']
            refs = scan_config['Refs']

            #format duration string
            h, m, s = milliseconds_to_hms(runtimes.get('TYPE_ALL_SCANS'))
            scan_duration_h_m_s = f"{h} h {m} m {s} s"

            # Prepare the row dictionary
            row = {
                'project_short_name': project_short_name,
                'scan_start_time': spec.get('start_time'),
                'scan_end_time': spec.get('end_time'),
                'scan_status': spec.get('status'),
                'scan_duration_ms': runtimes.get('TYPE_ALL_SCANS'),
                'scan_duration_h_m_s': scan_duration_h_m_s,
                'scan_duration_h': h,
                'scan_duration_m': m,
                'scan_duration_s': s,
                'num_packages_approximate': stats.get('dependency_analysis_num_approximate'),
                'num_packages_full': stats.get('dependency_analysis_num_full'),
                'quick_scan': quick_scan,
                'as_default_branch': as_default_branch,
                'detached_ref_name': detached_ref_name,
                'refs': refs,
                'build': build,
                'host_arch': environment.get('arch'),
                'host_os': environment.get('os'),
                'host_memory': environment.get('memory'),
                'host_num_cpus': environment.get('num_cpus'),
                'endorctl_version': environment.get('endorctl_version'),
                'exit_code_status': spec.get('exit_code'),
                'project_uuid': project_uuid,
                'scan_uuid': scan_uuid,
                'project_name': project_name
            }

            # Write the row to the CSV
            writer.writerow(row)


def endor_api_query(query_json, namespace: str, params = {}):

    ENDOR_API_URL=f"https://api.endorlabs.com/v1/namespaces/{namespace}/queries"
    logger.debug(f"{ENDOR_API_URL=}")

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Request-Timeout": "600"
    }

    # handle iterating pages with api query
    payload = query_json.copy()
    combined_results = []
    next_page_token = None
    
    while True:
        if next_page_token:
            # modify the query JSON to include additional parameter for the next_page_token
            payload['spec']['query_spec']['list_parameters']['page_token'] = next_page_token

        logger.debug(f"Calling API list_parameters: {payload.get('spec').get('query_spec').get('list_parameters')}")
        response = requests.post(ENDOR_API_URL, json=payload, headers=headers, timeout=600)
        logger.debug(f"{response.status_code=}")
        
        if response.status_code != 200:
            logger.error(f"Failed to get results, Status Code: {response.status_code}, Response: {response.text}")
            raise Exception(f"Failed to execute query: {response.status_code}, {response.text}")
        
        response_json = response.json()
        
        combined_results.extend(response_json.get('spec').get('query_response').get('list').get('objects'))
       
        current_page_token = next_page_token
        next_page_token = response_json.get('spec').get('query_response').get('list').get('response').get('next_page_token', None)
        logger.debug(f"{len(combined_results)=}, {next_page_token=}")

        if not next_page_token or next_page_token == '' or next_page_token == current_page_token:
            break
            
    return combined_results


def endor_api_get_auth_token(api_key: str, api_secret: str):
    url = "https://api.endorlabs.com/v1/auth/api-key"
    payload = {
        "key": api_key,
        "secret": api_secret
    }
    headers = {
        "Content-Type": "application/json",
        "Request-Timeout": "60"
    }
    response = requests.post(url, json=payload, headers=headers, timeout=60)
    if response.status_code == 200:
        token = response.json().get('token')
        return token
    else:
        raise Exception(f"Failed to get token: {response.status_code}, {response.text}")

def load_json_from_file(path: str):
  f = open(path)
  json_data = json.load(f)
  f.close()
  
  return json_data


def load_query(path: str, start_date: str, end_date: str, namespace: str):
    raw_query = load_json_from_file(path)
    
    # handle filter substituion
    # assume start_date is required
    filter = f"context.type==CONTEXT_TYPE_MAIN and meta.create_time >= date({start_date})"
    
    if end_date:
        filter = f"{filter} and meta.create_time <= date({end_date})"
    
    raw_query['spec']['query_spec']['list_parameters']['filter'] = filter

    #handle namespace substitution
    raw_query['tenant_meta']['namespace'] = namespace

    return raw_query


def milliseconds_to_hms(milliseconds: int) -> tuple[int, int, int]:
    # Convert milliseconds to seconds
    total_seconds = milliseconds / 1000
    
    # Calculate hours, minutes, and seconds
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    
    return hours, minutes, seconds

def extract_path(url: str) -> str:
    # Define the regex pattern
    pattern = r'https://gitlab\.com/fivn(/[^.]+)'
    
    # Search for the pattern
    match = re.search(pattern, url)
    
    if match:
        # Extract the matched group and return it
        return match.group(1)
    return url


if __name__ == "__main__":
    logger.debug("version: ", sys.version)
    cli()


    