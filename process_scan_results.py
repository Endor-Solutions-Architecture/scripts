import json
import sys
import logging
from types import SimpleNamespace
import requests
import typer


logger = logging.getLogger(__name__)
FORMAT = "[%(filename)s:%(lineno)4s - %(funcName)s ] %(message)s"
logging.basicConfig(format=FORMAT)
logger.setLevel(logging.WARN)

cli = typer.Typer(add_completion=False)

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
        typer.echo("*** DEBUG MODE ENABLED ***", file=sys.stderr)
        logger.setLevel(logging.DEBUG)

    # load query file as json
    #query_json = load_json_from_file(query_file)
    query_json = load_query(query_file, start_date, end_date, namespace)

    logger.debug(f"{query_json=}")

    ctx.obj = SimpleNamespace(
        api_key = api_key,
        api_secret = api_secret,
        namespace = namespace,
        start_date = start_date,
        end_date = end_date,
        query_json = query_json
    )

    # get an auth token and make it accessible globally
    global auth_token
    auth_token = endor_api_get_auth_token(api_key, api_secret)

@cli.command()
def make_csv(ctx: typer.Context):
    """
    Generate CSV output
    """
    # get the data from API
    query_response = endor_api_query(
        query_json = ctx.obj.query_json,
        namespace = ctx.obj.namespace
    )

    #logger.debug(f"{query_response=}")


def endor_api_query(query_json, namespace: str, params = {}):

    ENDOR_API_URL=f"https://api.endorlabs.com/v1/namespaces/{namespace}/queries"

    logger.debug(f"{ENDOR_API_URL=}")

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Request-Timeout": "60"
    }
   
    logger.debug(f"{headers=}")
   
    payload = query_json

    next_page_id = None

    response_data={}
    
    while True:
        if next_page_id:
            params['list_parameters.page_id'] = next_page_id
        
        response = requests.post(ENDOR_API_URL, json=payload, headers=headers, params=params, timeout=600)
        
        if response.status_code != 200:
            print(f"Failed to get projects, Status Code: {response.status_code}, Response: {response.text}")
            raise Exception(f"Failed to execute query: {response.status_code}, {response.text}")
        
        response_data.update(response.json())
       
        next_page_id = response_data.get('list', {}).get('response', {}).get('next_page_id')
        if not next_page_id:
            return response_data



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
    filter = f"meta.create_time >= date({start_date})"
    
    if end_date:
        filter = f"{filter} and meta.create_time <= date({end_date})"
    
    raw_query['spec']['query_spec']['list_parameters']['filter'] = filter

    #handle namespace substitution
    raw_query['tenant_meta']['namespace'] = namespace

    return raw_query

if __name__ == "__main__":
    logger.debug("version: ", sys.version)
    cli()


    