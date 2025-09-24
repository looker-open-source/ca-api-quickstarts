import streamlit as st
from google.api_core import exceptions as google_exceptions
from google.cloud import geminidataanalytics
from state import fetch_agents_state
from utils.agents import get_time_delta_string
import uuid

BIG_QUERY = "BigQuery"
LOOKER = "Looker"

def agents_main():
    state = st.session_state

    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.subheader("Data agents available")
        if st.button("Refresh agents"):
            with st.spinner("Refreshing..."):
                fetch_agents_state()

    # Agent list
    with st.container(border=True, height=450):
        if len(state.agents) == 0:
            st.write("There are no agents available.")
        for ag in state.agents:
            name = ag.display_name or ag.name.split("/")[-1]
            with st.expander(f"**{name}**"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.write(f"**Resource ID:** {ag.name}")
                    display_name = st.text_input(
                        "**Display name:**",
                        value=ag.display_name,
                        key=f"updatedisp-{ag.name}"
                    )
                    description = st.text_input(
                        "**Description:**",
                        value=ag.description,
                        key=f"updatedesc-{ag.name}"
                    )
                    st.write(f"**Created:** {get_time_delta_string(ag.create_time, 'Just created')}")
                    st.write(f"**Updated:** {get_time_delta_string(ag.update_time, 'Just updated')}")
                with col2:
                    system_instruction = st.text_area(
                        "**System instructions:** *(drag the bottom right corner to enlarge text input)*",
                        value=ag.data_analytics_agent.published_context.system_instruction,
                        key=f"updatesys-{ag.name}"
                    )
                    st.text_area(
                        "**Data source:**",
                        value=ag.data_analytics_agent.published_context.datasource_references,
                        disabled=True,
                        key=f"datasrc-{ag.name}"
                    )
                    with st.container(horizontal=True,horizontal_alignment="distribute"):
                        if st.button("**Update agent**", key=f"update-{ag.name}"):
                            agent = geminidataanalytics.DataAgent()
                            agent.name=ag.name
                            agent.display_name=display_name
                            agent.description=description

                            published_context = geminidataanalytics.Context()
                            published_context.datasource_references = ag.data_analytics_agent.published_context.datasource_references
                            published_context.system_instruction=system_instruction
                            agent.data_analytics_agent.published_context = published_context

                            request = geminidataanalytics.UpdateDataAgentRequest(data_agent=agent, update_mask="*")

                            try:
                                state.agent_client.update_data_agent(request=request).result()
                                fetch_agents_state()
                                st.success("Succesfully updated data agent")
                            except Exception as e:
                                st.error(f"Error updating data agent: {e}")

                        if st.button("**:red[DELETE AGENT]**", key=f"delete-{ag.name}"):
                            request = geminidataanalytics.DeleteDataAgentRequest(
                                name=ag.name
                            )
                            try:
                                operation = state.agent_client.delete_data_agent(request=request).result()
                                fetch_agents_state()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting Data Agent: {e}")

    # Create agent form
    # Does not make use of st.form() because it cannot handle dynamic swapping of inputs which we need for Looker vs BQ data source.
    st.subheader("Create a data agent")
    with st.container(border=True, key="create_agent_form"):
        col1, col2 = st.columns(2)
        with col1:
            display_name = st.text_input("Agent display name:")
            description = st.text_area("Agent description:", height=70)
            system_instruction = st.text_area("Agent system instruction:", height=140)
        with col2:
            data_source = st.radio(
                "Data source:",
                [BIG_QUERY, LOOKER],
                horizontal=True
            )
            if data_source == BIG_QUERY:
                bq_project_id = st.text_input("BigQuery project ID:", placeholder="bigquery-public-data")
                bq_dataset_id = st.text_input("BigQuery dataset ID:", placeholder="san_francisco_trees")
                bq_table_id = st.text_input("BigQuery table ID:",placeholder="street_trees")
            else:
                looker_instance_url=st.text_input("Looker instance URL:",
                placeholder="myinstance.looker.com")
                looker_model=st.text_input("Looker model:")
                looker_explore=st.text_input("Looker explore:")


        if st.button("Create agent"):
            agent = geminidataanalytics.DataAgent()
            # TODO: Remove id/name setting after bug fixed where id starting with number fails the create convo endpoint
            id = f"a{uuid.uuid4()}"
            agent.name=f"projects/{st.secrets.cloud.project_id}/locations/global/dataAgents/{id}"
            agent.display_name=display_name
            agent.description=description

            published_context = geminidataanalytics.Context()
            datasource_references = geminidataanalytics.DatasourceReferences()
            if data_source == BIG_QUERY:
                bigquery_table_reference = geminidataanalytics.BigQueryTableReference()
                bigquery_table_reference.project_id = bq_project_id
                bigquery_table_reference.dataset_id = bq_dataset_id
                bigquery_table_reference.table_id = bq_table_id
                datasource_references.bq.table_references = [bigquery_table_reference]
            else:
                looker_explore_reference = geminidataanalytics.LookerExploreReference()
                looker_explore_reference.looker_instance_uri = looker_instance_url
                looker_explore_reference.lookml_model = looker_model
                looker_explore_reference.explore = looker_explore
                datasource_references.looker.explore_references = [looker_explore_reference]

            published_context.datasource_references = datasource_references
            published_context.system_instruction = system_instruction

            agent.data_analytics_agent.published_context = published_context
            # TODO: Remove id/name setting after bug fixed where id starting with number fails the create convo endpoint
            request = geminidataanalytics.CreateDataAgentRequest(
                parent=f"projects/{st.secrets.cloud.project_id}/locations/global",
                data_agent_id=id,
                data_agent=agent
            )

            try:
                state.agent_client.create_data_agent(request=request)
                st.success(f"Agent '{display_name}' successfully created")
                fetch_agents_state()
            except google_exceptions.GoogleAPICallError as e:
                st.error(f"API error creating agent: {e}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

agents_main()
