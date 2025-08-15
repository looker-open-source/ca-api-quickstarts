import pandas as pd
import json as json_lib
import altair as alt

import proto
from google.protobuf.json_format import MessageToDict

import streamlit as st

# Based off documentation: https://cloud.google.com/gemini/docs/conversational-analytics-api/build-agent-sdk#define_helper_functions

def handle_text_response(resp):
  parts = getattr(resp, 'parts')
  st.markdown(''.join(parts))

def display_schema(data):
  fields = getattr(data, 'fields')
  df = pd.DataFrame({
    "Column": map(lambda field: getattr(field, 'name'), fields),
    "Type": map(lambda field: getattr(field, 'type'), fields),
    "Description": map(lambda field: getattr(field, 'description', '-'), fields),
    "Mode": map(lambda field: getattr(field, 'mode'), fields)
  })
  with st.expander("**Schema**:"):
    st.dataframe(df)

def format_looker_table_ref(table_ref):
 return 'lookmlModel: {}, explore: {}, lookerInstanceUri: {}'.format(table_ref.lookml_model, table_ref.explore, table_ref.looker_instance_uri)

def format_bq_table_ref(table_ref):
  return '{}.{}.{}'.format(table_ref.project_id, table_ref.dataset_id, table_ref.table_id)

def display_datasource(datasource):
  source_name = ''
  if 'studio_datasource_id' in datasource:
   source_name = getattr(datasource, 'studio_datasource_id')
  elif 'looker_explore_reference' in datasource:
   source_name = format_looker_table_ref(getattr(datasource, 'looker_explore_reference'))
  else:
    source_name = format_bq_table_ref(getattr(datasource, 'bigquery_table_reference'))

  st.markdown("**Data source**: " + source_name)
  display_schema(datasource.schema)

def handle_schema_response(resp):
  if 'query' in resp:
    st.markdown("**Query:** " + resp.query.question)
  elif 'result' in resp:
    st.markdown("**Schema resolved.**")
    for datasource in resp.result.datasources:
      display_datasource(datasource)

def handle_data_response(resp):
  if 'query' in resp:
    query = resp.query
    st.markdown("**Retrieval query**")
    st.markdown('**Query name:** {}'.format(query.name))
    st.markdown('**Question:** {}'.format(query.question))
    for datasource in query.datasources:
      display_datasource(datasource)
  elif 'generated_sql' in resp:
    with st.expander("**SQL generated:**"):
        st.code(resp.generated_sql, language="sql")
  elif 'result' in resp:
    st.markdown('**Data retrieved:**')

    fields = [field.name for field in resp.result.schema.fields]
    d = {}
    for el in resp.result.data:
      for field in fields:
        if field in d:
          d[field].append(el[field])
        else:
          d[field] = [el[field]]

    st.dataframe(pd.DataFrame(d))

def handle_chart_response(resp):
  def _value_to_dict(v):
    if isinstance(v, proto.marshal.collections.maps.MapComposite):
      return _map_to_dict(v)
    elif isinstance(v, proto.marshal.collections.RepeatedComposite):
      return [_value_to_dict(el) for el in v]
    elif isinstance(v, (int, float, str, bool)):
      return v
    else:
      return MessageToDict(v)

  def _map_to_dict(d):
    out = {}
    for k in d:
      if isinstance(d[k], proto.marshal.collections.maps.MapComposite):
        out[k] = _map_to_dict(d[k])
      else:
        out[k] = _value_to_dict(d[k])
    return out

  if 'query' in resp:
    st.markdown(resp.query.instructions)
  elif 'result' in resp:
    vegaConfig = resp.result.vega_config
    vegaConfig_dict = _map_to_dict(vegaConfig)
    chart = alt.Chart.from_json(json_lib.dumps(vegaConfig_dict))
    st.altair_chart(chart, use_container_width=True)

def show_message(msg):
  m = msg.system_message
  if 'text' in m:
    handle_text_response(getattr(m, 'text'))
  elif 'schema' in m:
    handle_schema_response(getattr(m, 'schema'))
  elif 'data' in m:
    handle_data_response(getattr(m, 'data'))
  elif 'chart' in m:
    handle_chart_response(getattr(m, 'chart'))