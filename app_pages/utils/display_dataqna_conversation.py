"""The utility funcitons in this file allow the display of a cortado response
in a streamlit applicaiton"""
from typing import Iterable
import pandas as pd
import streamlit as st

import proto
from google.cloud import dataqna_v1alpha1
from google.protobuf.json_format import MessageToDict


def handle_text_response(resp: dataqna_v1alpha1.TextMessage):
    """Displays a text response"""
    st.text(''.join(resp.parts))


def display_schema(data: dataqna_v1alpha1.Schema):
    """Displays the schema for a response table"""
    fields = data.fields
    df = pd.DataFrame({
      "Column": map(lambda field: getattr(field, 'name'), fields),
      "Type": map(lambda field: getattr(field, 'type'), fields),
      "Description": map(lambda field: getattr(field, 'description', '-'), fields),
      "Mode": map(lambda field: getattr(field, 'mode'), fields)
    })
    st.dataframe(df)


def display_section_title(text: str):
    """Display the title at the head of a section"""
    st.header(text)


def format_bq_table_ref(table_ref: dataqna_v1alpha1.BigQueryTableReference) -> str:
    """Creates a name to display for a big query table reference"""
    return f'{table_ref.project_id}.{table_ref.dataset_id}.{table_ref.table_id}'


def display_datasource(datasource: dataqna_v1alpha1.Datasource):
    """Display a collapsed table of the data used to answer the question"""
    if 'bigquery_table_reference' in datasource:
        st.subheader(format_bq_table_ref(datasource.bigquery_table_reference))
    display_schema(datasource.schema)


def handle_schema_response(resp: dataqna_v1alpha1.SchemaMessage):
    """Displays a collapsed schema of tables used in answering the question"""
    if 'query' in resp:
        st.text(resp.query.question)
    elif 'result' in resp:
        display_section_title('Schema resolved')
        with st.expander('Data sources:'):
            for datasource in resp.result.datasources:
                display_datasource(datasource)


def handle_data_response(resp: dataqna_v1alpha1.DataMessage):
    """Displays data retrieved for a cortado response"""
    if 'query' in resp:
        query = resp.query
        display_section_title('Retrieval query')
        st.text(f'Query name: {query.name}')
        st.text(f'Question: {query.question}')
        with st.expander('Data sources:'):
            for datasource in query.datasources:
                display_datasource(datasource)
    elif 'generated_sql' in resp:
        display_section_title('SQL generated')
        st.code(resp.generated_sql)
    elif 'result' in resp:
        display_section_title('Data retrieved')
        fields = [field.name for field in resp.result.schema.fields]
        d = {}
        for el in resp.result.data:
            for field in fields:
                if field in d:
                    d[field].append(el[field])
                else:
                    d[field] = [el[field]]
        st.dataframe(pd.DataFrame(d))


def handle_chart_response(resp: dataqna_v1alpha1.ChartMessage):
    """Displays a chart response from cortado"""
    def _value_to_dict(v):
        if isinstance(v, proto.marshal.collections.maps.MapComposite):
            return _map_to_dict(v)
        if isinstance(v, proto.marshal.collections.RepeatedComposite):
            return [_value_to_dict(el) for el in v]
        if isinstance(v, (int, float, str, bool)):
            return v
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
        st.text(resp.query.instructions)
    elif 'result' in resp:
        vega_config = resp.result.vega_config
        vega_config_dict = _map_to_dict(vega_config)
        st.vega_lite_chart(vega_config_dict)


def display_dataqna_message(message: dataqna_v1alpha1.Message):
    """Renders a single message from cortado within streamlit"""
    if "system_message" in message:
        m = message.system_message
        with st.chat_message("assistant"):
            if 'text' in m:
                handle_text_response(m.text)
            elif 'schema' in m:
                handle_schema_response(m.schema)
            elif 'data' in m:
                handle_data_response(m.data)
            elif 'chart' in m:
                handle_chart_response(m.chart)
    else:
        with st.chat_message("user"):
            st.markdown(message.user_message.text)


def display_dataqna_messages(conversation: Iterable[dataqna_v1alpha1.Message]):
    """Renders a conversation from cortado within streamlit"""
    for msg in conversation:
        display_dataqna_message(msg)
