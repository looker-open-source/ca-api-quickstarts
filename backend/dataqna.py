"""Provides functionality to call the ask question funcitonality from
the cortado SDK"""
from typing import Iterable, Sequence
from google.cloud import dataqna_v1alpha1
from google.oauth2.credentials import Credentials
from httpx_oauth.clients.google import GoogleOAuth2


def generate_response(messages: list[dataqna_v1alpha1.Message],
                      billing_project: str, bq_project_id: str,
                      bq_dataset_id: str, bq_table_ids: Sequence[str], token: GoogleOAuth2,
                      system_instruction: str = "answer questions"
                      ) -> Iterable[dataqna_v1alpha1.Message]:
    """Generates a response to a conversation using the cortado api"""
    # while the api allows multiple table references it will often error out
    # when attempting to use them, for now only call this with one reference
    datasource_references = dataqna_v1alpha1.DatasourceReferences(
        bq=dataqna_v1alpha1.BigQueryTableReferences(
            table_references=[
                dataqna_v1alpha1.BigQueryTableReference(
                    project_id=bq_project_id,
                    dataset_id=bq_dataset_id,
                    table_id=bq_table_id)
                for bq_table_id in bq_table_ids
                ]
        )
    )

    # Form the request
    request = dataqna_v1alpha1.AskQuestionRequest(
        # Specify a GCP project for which the DataQnA API has been enabled.
        project=f"projects/{billing_project}",
        messages=messages,
        context=dataqna_v1alpha1.InlineContext(
            system_instruction=system_instruction,
            datasource_references=datasource_references
            )
        )

    # create a client
    client = dataqna_v1alpha1.DataQuestionServiceClient(
        credentials=Credentials(token=token['access_token']))
    # Make the request
    return client.ask_question(request=request)
