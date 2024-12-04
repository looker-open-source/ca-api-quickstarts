import streamlit as st


import requests
import json as json_lib
import pandas as pd
from dataclasses import dataclass


import google.auth
import google.auth.transport.requests


datasets = {
    "Iowa Liquor Sales": {
        "description": "This dataset contains every wholesale purchase of liquor in the State of Iowa by retailers for sale to individuals since January 1, 2012. The State of Iowa controls the wholesale distribution of liquor intended for retail sale (off-premises consumption), which means this dataset offers a complete view of retail liquor consumption in the entire state. The dataset contains every wholesale order of liquor by all grocery stores, liquor stores, convenience stores, etc., with details about the store and location, the exact liquor brand and size, and the number of bottles ordered. You can find more details, as well as sample queries, in the GCP Marketplace here: https://console.cloud.google.com/marketplace/details/iowa-department-of-commerce/iowa-liquor-sales",
        "project": "bigquery-public-data",
        "dataset": "iowa_liquor_sales",
        "tables": ["sales"],
        "questions": [
            "Which store has sold the most bottles?",
            "Which top 5 stores have the highest sales in 2024?",
            "What are the top 5 most sold liquor categories by volume?",
            "Show the monthly total sales of all stores on a timeline",
        ],
    },
    "FAA Airport Data": {
        "description": "Airport defines area on land or water intended to be used either wholly or in part for the arrival; departure and surface movement of aircraft/helicopters. This airport data is provided as a vector geospatial-enabled file format. Airport information is published every eight weeks by the U.S. Department of Transportation, Federal Aviation Administration-Aeronautical Information Services. The data is provided by the Federal Aviation Administration for public use with no restrictions for use. A limited number of Non-US Landing Facilities are included in this file. Some of these, in particular the Canadian facilities, are included to facilitate cartographic requirements in border regions. These records are not guaranteed to be complete and are not inclusive of all Canadian facilities. This airport data should not be considered official source for non-US facilities. Please contact the appropriate authority for more accurate and updated non-US airports data.",
        "project": "bigquery-public-data",
        "dataset": "faa",
        "tables": ["us_airports"],
        "questions": [
            "How many airports are there per state?",
            "What are the top 5 airports by elevation",
            "Which types of airports do we have and how many of each?",
        ],
    },
    "New York Citibike": {
        "description": "This dataset contains data about New York City Citibike stations and trips",
        "project": "bigquery-public-data",
        "dataset": "new_york_citibike",
        "tables": ["stations", "trips"],
        "questions": [
            "What is the average trip duration for Citibike users?",
            "Which Citibike station has the highest number of checkouts?",
            "What are the most popular routes during weekdays?",
        ],
    },
    "NCAA Basketball": {
        "description": "This dataset contains data about NCAA Basketball games, teams, and players. Game data covers play-by-play and box scores back to 2009, as well as final scores back to 1996. Additional data about wins and losses goes back to the 1894-5 season in some teams' cases. Sportradar: Copyright Sportradar LLC. Access to data is intended solely for internal research and testing purposes, and is not to be used for any business or commercial purpose. Data are not to be exploited in any manner without express approval from Sportradar. NCAA®: Copyright National Collegiate Athletic Association. Access to data is provided solely for internal research and testing purposes, and may not be used for any business or commercial purpose. Data are not to be exploited in any manner without express approval from the National Collegiate Athletic Association.",
        "project": "bigquery-public-data",
        "dataset": "ncaa_basketball",
        "tables": [],
    },
}


def get_bearer_token():
    """Retrieves a bearer token for the application default credentials."""

    creds, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    return creds.token


ACCESS_TOKEN = get_bearer_token()
billing_project = ""  # ADD YOUR BILLING PROJECT

url = f"https://dataqna.googleapis.com/v1alpha1/projects/{billing_project}:askQuestion"
headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

st.set_page_config(layout="wide")


def create_datasource(datasource: dict):
    response = []
    for table in datasource["tables"]:
        response.append(
            {
                "projectId": datasource["project"],
                "datasetId": datasource["dataset"],
                "tableId": table,
            }
        )
    return response


def display_section_title(text):
    st.write(text)


def get_property(data, field_name, default=""):
    return data[field_name] if field_name in data else default


def format_bq_table_ref(table_ref):
    return "{}.{}.{}".format(
        table_ref["projectId"], table_ref["datasetId"], table_ref["tableId"]
    )


def display_datasource(datasource):
    source_name = ""

    if "studioDatasourceId" in datasource:
        source_name = datasource["studioDatasourceId"]
    else:
        source_name = format_bq_table_ref(datasource["bigqueryTableReference"])


def is_json(str):
    try:
        json_object = json_lib.loads(str)
    except ValueError as e:
        return False
    return True


def handle_error(resp):
    display_section_title("Error")
    print("Code: {}".format(resp["code"]))
    print("Message: {}".format(resp["message"]))


def handle_text_response(resp):
    parts = resp["parts"]
    print("".join(parts))

    st.write("".join(parts))


def handle_schema_response(resp):
    if "query" in resp:
        print(resp["query"]["question"])
    elif "result" in resp:
        display_section_title("Schema resolved")
        print("Data sources:")
        for datasource in resp["result"]["datasources"]:
            display_datasource(datasource)


def handle_data_response(resp):
    if "query" in resp:
        query = resp["query"]

        for datasource in query["datasources"]:
            display_datasource(datasource)
    elif "generatedSql" in resp:
        display_section_title("SQL generated")

        st.code(resp["generatedSql"])
    elif "result" in resp:
        display_section_title("You can see the result here:")
        if "schema" in resp["result"] and "fields" in resp["result"]["schema"]:
            fields = map(
                lambda field: get_property(field, "name"),
                resp["result"]["schema"]["fields"],
            )
            dict = {}

            for field in fields:
                if "data" in resp["result"]:
                    dict[field] = list(
                        map(lambda el: get_property(el, field), resp["result"]["data"])
                    )
                else:

                    print("Error: 'data' key not found in response.")

            st.chat_message(ASSISTANT).dataframe(pd.DataFrame(dict))


def handle_chart_response(resp):
    if "query" in resp:
        print(resp["query"]["instructions"])
    elif "result" in resp:
        vegaConfig = resp["result"]["vegaConfig"]
        print(vegaConfig)
        st.vega_lite_chart(vegaConfig, use_container_width=True)


def get_stream(url, json) -> str:
    s = requests.Session()
    print("\n\n**********************")
    print(json)

    acc = ""

    with s.post(url, json=json, headers=headers, stream=True) as resp:
        for line in resp.iter_lines():
            # print(line)
            if not line:
                continue

            decoded_line = str(line, encoding="utf-8")

            if decoded_line == "[{":
                acc = "{"
            elif decoded_line == "}]":
                acc += "}"
            elif decoded_line == ",":
                continue
            else:
                acc += decoded_line
            if not is_json(acc):
                continue

            data_json = json_lib.loads(acc)
            # print("Response ", data_json)

            if not "systemMessage" in data_json:
                if "error" in data_json:
                    handle_error(data_json["error"])
                continue

            if "text" in data_json["systemMessage"]:
                handle_text_response(data_json["systemMessage"]["text"])
            elif "schema" in data_json["systemMessage"]:
                handle_schema_response(data_json["systemMessage"]["schema"])
            elif "data" in data_json["systemMessage"]:
                handle_data_response(data_json["systemMessage"]["data"])
            elif "chart" in data_json["systemMessage"]:
                handle_chart_response(data_json["systemMessage"]["chart"])

            acc = ""
    return data_json


data_select = st.selectbox(
    "Which public dataset would you like to talk 🤳🏽 to?",
    ("Iowa Liquor Sales", "FAA Airport Data"),
    placeholder="Select a dataset...",
    index=None,
)


@dataclass
class Message:
    actor: str
    payload: str


USER = "user"
ASSISTANT = "ai"
MESSAGES = "messages"
PROMPTS_HISTORY = "prompts_history"

prompt: str = st.chat_input("Enter your question here")

if data_select in datasets:
    select = datasets[data_select]
    data_sources = create_datasource(select)
    st.info(f"You have selected: **{data_select}**")
    st.info(f'Tables used: {select["tables"]}')
    with st.expander("See dataset description"):
        st.write(select["description"])
    st.write("## Example questions (clickable)")
    for question in select["questions"]:
        if st.button(question):
            resp = get_stream(
                url,
                json={
                    "messages": [{"userMessage": {"text": f"{question}"}}],
                    "context": {
                        "systemInstruction": "You are a data analyst helping business users answer questions and visualize if appropriate!",
                        "datasourceReferences": {
                            "bq": {"tableReferences": data_sources}
                        },
                    },
                },
            )


if prompt:

    st.chat_message(USER).write(prompt)

    resp = get_stream(
        url,
        json={
            "messages": [{"userMessage": {"text": f"{prompt}"}}],
            "context": {
                "systemInstruction": "You are a data analyst helping business users answer questions and visualize if appropriate!",
                "datasourceReferences": {"bq": {"tableReferences": data_sources}},
            },
        },
    )
