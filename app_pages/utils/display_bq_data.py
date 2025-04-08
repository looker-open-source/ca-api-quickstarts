from google.cloud import bigquery
from google.cloud.bigquery import Dataset, Table, SchemaField, Client
import pandas as pd
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union, Tuple
from app_pages.utils.gemini import gemini_request
import logging

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

TableSchema = Dict[str, Dict[str, Union[List[Dict[str, str]], str]]]
CommonQueries = List[Dict[str, Dict[str, str]]]

def list_datasets(project_id: str) -> List[str]:
    """Lists all datasets in the specified BigQuery project."""
    try:
        client: Client = bigquery.Client(project=project_id)
        datasets: List[Dataset] = list(client.list_datasets())

        if datasets:
            logging.info(f"Datasets in project {project_id}:")
            dataset_ids: List[str] = []
            for dataset in datasets:
                dataset_id: str = dataset.dataset_id
                dataset_ids.append(dataset_id)
                logging.info(f"\t- {dataset_id}")
            return dataset_ids
        logging.info(f"Project {project_id} does not contain datasets.")
        return []
    except Exception as e:
        logging.error(f"Error listing datasets for project {project_id}: {e}")
        return []

def list_tables(project_id: str, dataset_id: str) -> Optional[List[str]]:
    """Lists all tables in a BigQuery dataset."""
    table_list: List[str] = []
    client: Client = bigquery.Client(project=project_id)
    dataset_ref: bigquery.DatasetReference = bigquery.DatasetReference(
        project_id, 
        dataset_id
    )
    try:
        tables: List[Table] = list(client.list_tables(dataset_ref))
        logging.info(f"Tables in dataset {project_id}.{dataset_id}:")
        table_list = [table.table_id for table in tables]
        return table_list
    except Exception as e:
        logging.error(f"An error occurred listing tables in {dataset_id}: {e}")
        return None

def get_table_schema_and_description_dict(
    project_id: str,
    dataset_id: str,
    table_id: str
) -> Optional[TableSchema]:
    """Retrieves the schema and description of a BigQuery table as a dictionary."""
    try:
        client: Client = bigquery.Client(project=project_id)
        table_ref: bigquery.TableReference = client.dataset(dataset_id).table(table_id)
        table: Table = client.get_table(table_ref)

        schema: List[Dict[str, str]] = [
            {
                "name": field.name,
                "type": field.field_type,
                "description": field.description or "",
            }
            for field in table.schema
        ]

        return {
            table_id: {
                "schema": schema,
                "description": table.description or "",
            }
        }

    except Exception as e:
        logging.error(f"An error occurred getting schema for {table_id}: {e}")
        return None

def get_all_tables_schemas_and_descriptions(
    project_id: str,
    dataset_id: str
) -> Dict[str, Any]:
    """Retrieves schemas and descriptions for all tables in a dataset."""
    client: Client = bigquery.Client(project=project_id)
    dataset_ref: bigquery.DatasetReference = client.dataset(dataset_id)
    all_tables_data: Dict[str, Any] = {}

    try:
        tables: List[Table] = list(client.list_tables(dataset_ref))
    except Exception as e:
        logging.error(f"Error listing tables in dataset {dataset_id}: {e}")
        return {}

    for table in tables:
        table_data = get_table_schema_and_description_dict(
            project_id,
            dataset_id,
            table.table_id
        )
        if table_data:
            all_tables_data.update(table_data)
    return all_tables_data

def select_10_from_table(
    project_id: str,
    dataset_id: str,
    table_id: str,
    location: str = "US"
) -> pd.DataFrame:
    """Selects the first 10 rows from a BigQuery table."""
    client: Client = bigquery.Client()
    query: str = f"SELECT * FROM `{project_id}.{dataset_id}.{table_id}` LIMIT 10"
    try:
        results: pd.DataFrame = client.query(query, location=location).to_dataframe()
        return results
    except Exception as e:
        logging.error(f"Error selecting data from table {table_id}: {e}")
        return pd.DataFrame()

def select_column_from_table(
    project_id: str,
    dataset_id: str,
    table_id: str,
    col: str,
    row_limit: int = 10
) -> Optional[List[Any]]:
    """Selects a specific column from a BigQuery table."""
    try:
        client: Client = bigquery.Client(project=project_id)
        query: str = f"""
            SELECT {col}
            FROM `{project_id}.{dataset_id}.{table_id}`
            LIMIT {row_limit}
        """
        query_job = client.query(query)
        results = query_job.result()

        df: pd.DataFrame = results.to_dataframe()
        if not df.empty and col in df.columns:
            series = df[col]
            if isinstance(series, dict):
                logging.warning("Unexpected type: Pandas Series is a dict.")
                return None
            results_list: List[Any] = series.tolist()
            return results_list
        return None
    except Exception as e:
        logging.error(f"An error occurred in select_column_from_table: {e}")
        return None

def find_first_ten_matching(data_list: List[Tuple[Any, int]], search_string: str) -> List[Any]:
    """Finds the first ten items in a list that contain a specific string."""
    matching_items: List[Any] = []
    for item in data_list:
        if isinstance(item, str) and search_string.lower() in item.lower():
            matching_items.append(item)
            if len(matching_items) == 10:
                break
    return matching_items

def get_most_common_queries(
    project_id: str,
    dataset_id: str,
    table_id: str,
    gemini_location: str,
    location: str = "US"
) -> CommonQueries:
    """Retrieves the 20 most common SELECT queries from BigQuery job history."""
    client: Client = bigquery.Client(project=project_id)
    try:
        jobs = list(client.list_jobs(
            min_creation_time=datetime.now() - timedelta(days=30),
            state_filter='DONE',
            max_results=1000
        ))
    except Exception as e:
        logging.error(f"Error listing BigQuery jobs: {e}")
        return []

    query_counter: Counter = Counter()
    queries: List[str] = []
    questions: List[str] = []

    for job in jobs:
        if job.job_type == 'query' and not job.error_result:
            query: str = ' '.join(job.query.split())
            query_counter[query] += 1

    logging.info("Top 20 most frequently run queries:")
    for query in query_counter.most_common(20):
        queries.append(query[0])

    refined_queries: List[str] = find_first_ten_matching(queries, table_id)
    for q in refined_queries:
        prompt: str = f"""You are a SQL expert your job is to analyze this SQL query in the query section
         and provide a single sentence question that the SQL query can answer. The questions should be
         based on the perspective of a business user. What analyst or business question could be answered
         with this SQL query. Do not put any SQL into the response. The answers should not describe the structure of the
         data, but should describe a business question the data can solve.
         query: {q}:"""
        try:
            question: str = gemini_request(project_id, gemini_location, prompt)
            questions.append(question)
        except Exception as e:
            logging.error(f"Error calling Gemini API for query '{q}': {e}")
            questions.append(f"Error generating question for query: {q}")
    common_queries: CommonQueries = []
    for question, sql in zip(questions, refined_queries):
        common_queries.append(
            {"golden_query": {"natural_language_query": question, "sql": sql}}
        )

    return common_queries
