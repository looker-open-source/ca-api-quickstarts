import streamlit as st

with st.expander("Click to see the Python code"):
    
    st.code("""
from google.cloud import geminidataanalytics

# --- Reference for the first BigQuery table ---
table_ref_1 = geminidataanalytics.BigQueryTableReference()
table_ref_1.project_id = "bigquery-public-data"
table_ref_1.dataset_id = "san_francisco"
table_ref_1.table_id = "street_trees"

# --- Reference for the second BigQuery table ---
table_ref_2 = geminidataanalytics.BigQueryTableReference()
table_ref_2.project_id = "bigquery-public-data"
table_ref_2.dataset_id = "faa"
table_ref_2.table_id = "us_airports"

# --- Create the main datasource reference object ---
datasource_references = geminidataanalytics.DatasourceReferences()

# --- ✨ Assign the list of table references ---
# The key is to provide a list of all your table reference objects.
datasource_references.bq.table_references = [table_ref_1, table_ref_2]

published_context = geminidataanalytics.Context()
published_context.system_instruction = system_instruction
published_context.datasource_references = datasource_references
published_context.options.analysis.python.enabled = True # if wanting to use advanced analysis with python


inline_context = geminidataanalytics.Context()
inline_context.system_instruction = system_instruction
inline_context.datasource_references = datasource_references
inline_context.options.analysis.python.enabled = True # if wanting to use advanced analysis with python


print("Successfully configured multiple BigQuery tables.") """, language="python")