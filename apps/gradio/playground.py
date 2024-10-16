# Copyright 2024 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import gradio as gr
import proto
from google.protobuf.json_format import MessageToDict
import json as json_lib
import altair as alt
from google.cloud import dataqna_v1alpha1


client = dataqna_v1alpha1.DataQuestionServiceClient()
NEWLINE = "<br />"
system_instruction = "Visualize results in a chart."  # @param {type:"string"}


def display_schema(data):
    fields = getattr(data, "fields")

    headers = ["Column", "Type", "Description", "Mode"]
    rows = [
        [
            getattr(field, "name"),
            getattr(field, "type"),
            getattr(field, "description", "-"),
            getattr(field, "mode"),
        ]
        for field in fields
    ]

    markdown_table = "| " + " | ".join(headers) + " |\n"
    markdown_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"

    for row in rows:
        markdown_table += "| " + " | ".join(row) + " |\n"

    return "\n" + markdown_table + "\n"


def format_bq_table_ref(table_ref):
    return "{}.{}.{}".format(
        table_ref.project_id, table_ref.dataset_id, table_ref.table_id
    )


def display_datasource(datasource):
    source_name = ""
    if "bigquery_table_reference" in datasource:
        source_name = format_bq_table_ref(
            getattr(datasource, "bigquery_table_reference")
        )

    source_name += display_schema(datasource.schema)
    return source_name


def handle_text_response(resp):
    parts = getattr(resp, "parts")
    response = "".join(parts)
    return response


def handle_schema_response(resp):
    response = ""
    if "query" in resp:
        query = getattr(resp.query, "question")
        response += "__Your question was:__ " + "_" + query + "_" + NEWLINE
    if "result" in resp:
        for datasource in resp.result.datasources:
            response += "__Data source:__ " + "_" + display_datasource(datasource) + "_"
    return response


def handle_data_response(resp):
    response = ""
    if "generated_sql" in resp:
        sql = resp.generated_sql
        response += "Generated query: \n```sql\n" + sql + "\n```"
    elif "result" in resp:
        fields = [field.name for field in resp.result.schema.fields]
        data = []
        for el in resp.result.data:
            row = [str(el[field]) for field in fields]  # Convert values to strings
            data.append(row)

        markdown_table = "| " + " | ".join(fields) + " |\n"
        markdown_table += "| " + " | ".join(["---"] * len(fields)) + " |\n"
        for row in data:
            markdown_table += "| " + " | ".join(row) + " |\n"

        response += "\n" + markdown_table + "\n"
    return response


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

    if "result" in resp:
        vegaConfig = resp.result.vega_config
        vegaConfig_dict = _map_to_dict(vegaConfig)
        response = alt.Chart.from_json(json_lib.dumps(vegaConfig_dict))
        return response


def show_message_new(msg):
    message = ""
    m = msg.system_message
    if "text" in m:
        message += handle_text_response(getattr(m, "text"))
    elif "schema" in m:
        message += handle_schema_response(getattr(m, "schema"))
    elif "data" in m:
        message += handle_data_response(getattr(m, "data"))
    return message


def ask_question(
    project_id: str,
    billing_project: str,
    dataset_id: str,
    table_id: str,
    question,
    history=None,
):
    messages = [dataqna_v1alpha1.Message()]
    messages[0].user_message.text = question

    request = dataqna_v1alpha1.AskQuestionRequest(
        project=f"projects/{billing_project}",
        messages=messages,
        context=dataqna_v1alpha1.InlineContext(
            system_instruction=system_instruction,
            datasource_references=dataqna_v1alpha1.DatasourceReferences(
                bq=dataqna_v1alpha1.BigQueryTableReferences(
                    table_references=[
                        dataqna_v1alpha1.BigQueryTableReference(
                            project_id=project_id,
                            dataset_id=dataset_id,
                            table_id=table_id,
                        )
                    ]
                )
            ),
        ),
    )
    message = ""
    i = 1
    chart = None
    stream = client.ask_question(request=request)
    for response in stream:
        if "chart" in response.system_message:
            chart = handle_chart_response(getattr(response.system_message, "chart"))
        else:
            message += show_message_new(response)
    return message, chart


INTRODUCTION = """
# Cortado ☕️ on Gradio


Welcome to Cortado on Gradio. Specify your project, dataset and table and fire away! 🔥
"""

chat = gr.Interface(
    allow_flagging="never",
    fn=ask_question,
    inputs=[
        gr.Text(placeholder="Your GCP Project ID"),
        gr.Text(placeholder="Your billing project ID"),
        gr.Text(placeholder="Your Dataset ID"),
        gr.Text(placeholder="Your Table ID"),
        gr.Text(placeholder="Your question"),
    ],
    outputs=[gr.Markdown(), gr.Plot()],
)

with gr.Blocks() as demo:
    gr.Markdown(INTRODUCTION)
    chat.render()

demo.launch()
