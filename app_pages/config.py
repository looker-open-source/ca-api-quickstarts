import os
import streamlit as st
import yaml
import time  # Import the time module
import logging
from app_pages.utils.display_bq_data import (
    list_datasets,
    list_tables,
    get_all_tables_schemas_and_descriptions,
    select_10_from_table,
    select_column_from_table,
    get_most_common_queries)

from app_pages.utils.gemini import (
    gemini_request,
    # Added back imports for description generation
    generate_description_prompt_for_column,
    generate_description_prompt_for_table,
    yaml_prompt
    )

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

gemini_project_id = os.getenv("PROJECT_ID")
gemini_region = os.getenv("GEMINI_REGION")
bq_location = os.getenv("BQ_LOCATION")

# --- Utility Functions ---
def display_success_message(message, icon="✅", duration=1):
    """
    Displays a success message in Streamlit for a short duration.
    """
    success = st.success(message, icon=icon)
    time.sleep(duration)
    success.empty()

def remove_yaml_prefix_and_suffix(text):
    """
    Checks if a string starts with '```yaml' and ends with '```',
    and removes them if they do. Handles None input.
    """
    prefix = "```yaml"
    suffix = "```"

    if not isinstance(text, str):
        return text # Return input if not a string (e.g., None)

    if text.startswith(prefix):
        text = text[len(prefix):].lstrip()

    if text.endswith(suffix):
        text = text[:-len(suffix)].rstrip()

    return text


# --- Configuration Update Functions ---
# NO CACHING HERE.  We want fresh dataset lists.
def list_datasets_no_cache(project_name):
    """Uncached version of list_datasets."""
    try:
        return list_datasets(project_name)
    except Exception as e:
        st.error(f"Error listing datasets for project '{project_name}': {e}")
        return [] # Return empty list on error

def update_config_datasets():
    """Update datasets dropdown."""
    if "dataqna_project_id" not in st.session_state:
        st.session_state.dataqna_project_id = "bigquery-public-data" # Default

    project_name = st.session_state.dataqna_project_id
    st.session_state.config_datasets = list_datasets_no_cache(project_name) if project_name else []

    # Reset downstream state when project changes
    if "config_table_options" in st.session_state:
        del st.session_state.config_table_options
    if "dataset_id" in st.session_state:
        st.session_state.dataset_id = None
    # Reset table selection state
    if 'config_radio_selected_table' in st.session_state:
         st.session_state.config_radio_selected_table = None
    if 'selected_tables' in st.session_state:
         st.session_state.selected_tables = []
    if 'table_ids' in st.session_state:
        st.session_state.table_ids = []


# NO CACHING HERE.  We want fresh table lists.
def list_tables_no_cache(project_name, dataset_name):
    """Uncached version of list_tables."""
    try:
        return list_tables(project_name, dataset_name)
    except Exception as e:
        st.error(f"Error listing tables for '{project_name}.{dataset_name}': {e}")
        return [] # Return empty list on error

def update_config_tables():
    """Update tables list based on selected dataset."""
    project_name = st.session_state.dataqna_project_id
    dataset_name = st.session_state.dataset_id
    st.session_state.config_table_options = list_tables_no_cache(project_name, dataset_name) if project_name and dataset_name else []
    # Reset radio button selection when table options change
    if 'config_radio_selected_table' in st.session_state:
         st.session_state.config_radio_selected_table = None


@st.cache_data(ttl=3600)  # Cache schema AND generated descriptions for 1 hour
def cached_get_table_schema_and_description_with_generation(project_name,
                                                            dataset_name,
                                                            table_name):
    """
    Fetches table schema and description from BigQuery.
    If descriptions are missing, attempts to generate them using Gemini.
    Returns the schema dictionary, potentially with generated descriptions.
    """
    logging.info(f"Fetching/generating schema for {project_name}.{dataset_name}.{table_name}")
    # 1. Fetch original schema and descriptions
    try:
        # Use the underlying function that just fetches metadata
        all_schemas = get_all_tables_schemas_and_descriptions(project_name, dataset_name)
        if not all_schemas or table_name not in all_schemas:
            st.warning(f"Schema not found via metadata for table: {project_name}.{dataset_name}.{table_name}")
            return None
        table_data = all_schemas[table_name] # Get the specific table's data
        if not isinstance(table_data, dict):
             st.error(f"Invalid schema format retrieved for {table_name}. Expected dict.")
             return None # Cannot process non-dict data

    except Exception as e:
        st.error(f"Error fetching initial schema for '{project_name}.{dataset_name}.{table_name}': {e}")
        logging.exception(f"Error fetching initial schema for {project_name}.{dataset_name}.{table_name}")
        return None

    # --- Description Generation Logic ---
    gemini_config_present = gemini_project_id and gemini_region

    # 2. Generate Table Description if missing
    if not table_data.get("description"):
        logging.info(f"Attempting to generate missing table description for `{table_name}`...")
        if not gemini_config_present:
             logging.warning(f"Skipping table description generation for {table_name}: Missing Gemini config (Project ID or Region).")
             table_data["description"] = "[Auto-generation skipped: Missing Gemini config]"
        else:
            try:
                sample_data = select_10_from_table(project_name, dataset_name, table_name, bq_location)
                if sample_data is not None and not sample_data.empty:
                    table_prompt = generate_description_prompt_for_table(table_name,
                                                                         sample_data,
                                                                         schema=table_data)
                    generated_desc = gemini_request(gemini_project_id,
                                                    gemini_region,
                                                    table_prompt)
                    if generated_desc and isinstance(generated_desc, str):
                         table_data["description"] = generated_desc.strip()
                         logging.info(f"Successfully generated table description for {project_name}.{dataset_name}.{table_name}")
                    else:
                         logging.warning(f"Gemini returned empty or invalid description for table {table_name}.")
                         table_data["description"] = "[Auto-generation failed: Empty response from Gemini]"
                else:
                    logging.warning(f"Could not retrieve sample data for table {table_name}. Cannot generate description.")
                    table_data["description"] = "[Auto-generation skipped: No sample data available]"
            except Exception as e:
                logging.error(f"Error generating table description for {table_name}: {e}", exc_info=True)
                st.warning(f"An error occurred generating table description for `{table_name}`.") # User feedback
                table_data["description"] = f"[Auto-generation failed: Error - {e}]"

    # 3. Generate Column Descriptions if missing
    if 'schema' in table_data and isinstance(table_data['schema'], list):
        for schema_item in table_data['schema']:
            # Ensure item is valid and description is missing
            if isinstance(schema_item, dict) and not schema_item.get('description'):
                col_name = schema_item.get('name')
                if not col_name: continue # Skip columns without a name

                logging.info(f"Attempting to generate missing column description for `{table_name}.{col_name}`...")
                if not gemini_config_present:
                    logging.warning(f"Skipping column description generation for {table_name}.{col_name}: Missing Gemini config.")
                    schema_item["description"] = "[Auto-generation skipped: Missing Gemini config]"
                    continue # Move to next column

                try:
                    col_data = select_column_from_table(project_name,
                                                        dataset_name,
                                                        table_name,
                                                        col_name)
                    # Check if data was retrieved (can be empty list for empty columns)
                    if col_data is not None:
                         col_prompt = generate_description_prompt_for_column(
                                                                             col_name,
                                                                             col_data,
                                                                             schema=table_data)
                         generated_col_desc = gemini_request(gemini_project_id,
                                                             gemini_region,
                                                             col_prompt)
                         if generated_col_desc and isinstance(generated_col_desc, str):
                             schema_item["description"] = generated_col_desc.strip()
                             logging.info(f"Successfully generated column description for {table_name}.{col_name}")
                         else:
                             logging.warning(f"Gemini returned empty or invalid description for column {table_name}.{col_name}.")
                             schema_item["description"] = f"[Auto-generation failed: Empty response from Gemini]"
                    else: # col_data is None, indicating error during fetch
                        logging.warning(f"Could not retrieve sample data for column {table_name}.{col_name}. Cannot generate description.")
                        schema_item["description"] = "[Auto-generation skipped: No sample data available]"
                except Exception as e:
                    logging.error(f"Error generating column description for {table_name}.{col_name}: {e}", exc_info=True)
                    st.warning(f"An error occurred generating column description for `{table_name}.{col_name}`.") # User feedback
                    schema_item["description"] = f"[Auto-generation failed: Error - {e}]"

    # 4. Return the potentially modified table_data
    logging.info(f"Finished schema processing for {project_name}.{dataset_name}.{table_name}")
    return table_data


def update_system_instructions():
    """Update system instructions state from the text area."""
    if "final_system_instruction_textarea" in st.session_state:
        st.session_state.system_instruction = st.session_state.final_system_instruction_textarea
        display_success_message('Agent Instructions Updated!')
    else:
        st.warning("Could not update instructions. YAML text area not found.")


def on_project_change():
    """Handles changes to the project selection."""
    st.session_state.dataqna_project_id = st.session_state.config_project_name
    update_config_datasets() # This function already handles resetting downstream state


def on_dataset_change():
    """Handles changes to the dataset selection."""
    st.session_state.dataset_id = st.session_state.config_dataset
    update_config_tables()
    # Clear selected tables when dataset changes
    if "selected_tables" in st.session_state:
        st.session_state.selected_tables = []
    if "table_ids" in st.session_state:
        st.session_state.table_ids = []
    # Reset radio button selection explicitly
    st.session_state.config_radio_selected_table = None


# --- Callback for Radio Button ---
def handle_radio_table_selection():
    """Adds the table selected via radio button if not already present."""
    selected_table = st.session_state.get('config_radio_selected_table') # Use .get for safety
    if selected_table and selected_table != "--- Select Table to Add ---":
        project = st.session_state.dataqna_project_id
        dataset = st.session_state.dataset_id

        if project and dataset:
            table_info = {
                "project": project,
                "dataset": dataset,
                "table": selected_table
            }
            if "selected_tables" not in st.session_state:
                st.session_state.selected_tables = []

            if table_info not in st.session_state.selected_tables:
                st.session_state.selected_tables.append(table_info)
                st.session_state.table_ids = [t['table'] for t in st.session_state.selected_tables]
                display_success_message(f"Table '{selected_table}' added!")
                st.rerun()


# --- UI Rendering Functions ---
def render_configuration_inputs():
    """Renders input fields for project, dataset, table selection, and instructions."""

    if "system_instruction" not in st.session_state:
         st.session_state.system_instruction = "You are a helpful BigQuery data analysis assistant."

    st.text_area(label='Agent Instructions',
                 value=st.session_state.system_instruction,
                 key="config_instructions", # This key holds the initial/editable instructions
                 height=150,
                 help="Enter general instructions for the data agent.")

    # --- Project Selection ---
    if "project_id" not in st.session_state:
        st.session_state.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
        # Provide a fallback

    project_options = ["bigquery-public-data", st.session_state.project_id]
    if "dataqna_project_id" not in st.session_state or st.session_state.dataqna_project_id not in project_options:
        st.session_state.dataqna_project_id = "bigquery-public-data" # Default

    st.selectbox(
        "Project Name",
        project_options,
        key="config_project_name",
        index=project_options.index(st.session_state.dataqna_project_id),
        on_change=on_project_change,
        help="Select the BigQuery project.",
    )

    # --- Dataset Selection ---
    if "config_datasets" not in st.session_state:
        update_config_datasets()

    dataset_index = 0
    if st.session_state.get('config_datasets') and st.session_state.get('dataset_id') in st.session_state.config_datasets:
        try:
            dataset_index = st.session_state.config_datasets.index(st.session_state.dataset_id)
        except ValueError: dataset_index = 0

    st.selectbox(
        "Dataset",
        st.session_state.get('config_datasets', []), # Use .get for safety
        key='config_dataset',
        index=dataset_index,
        on_change=on_dataset_change,
        help="Select the BigQuery dataset.",
        placeholder="Select a dataset..."
    )

    # --- Table Selection (Radio Buttons) & Management ---
    if "config_table_options" not in st.session_state:
        update_config_tables()
    if "selected_tables" not in st.session_state:
        st.session_state.selected_tables = []

    if st.session_state.get('dataset_id') is not None:
        st.title("Select Tables")

        available_tables = st.session_state.get('config_table_options', [])
        if available_tables:
            radio_options = ["--- Select Table to Add ---"] + available_tables
            st.radio(
                "Available Tables (Select to Add)",
                options=radio_options,
                key='config_radio_selected_table',
                on_change=handle_radio_table_selection,
                index=0, # Default to the placeholder
                help="Select a table's radio button to add it below."
            )
        elif st.session_state.get('dataqna_project_id') and st.session_state.get('dataset_id'):
             st.info("No tables found in the selected dataset.")

        # --- Manage Added Tables Section ---
        if st.session_state.selected_tables:
            st.markdown("**Added Tables:**")
            selected_table_names_for_removal = [f"{t['project']}.{t['dataset']}.{t['table']}" for t in st.session_state.selected_tables]
            for table_name in selected_table_names_for_removal:
                 st.markdown(f"- `{table_name}`")

            st.multiselect("Select tables to remove",
                           selected_table_names_for_removal,
                           key='config_tables_to_remove',
                           help="Select tables using the checkbox to remove them.")

            remove_yaml_col1, remove_yaml_col2 = st.columns([1, 1])
            with remove_yaml_col1:
                if st.button("Remove Selected",
                             help="Remove the tables selected above."):
                    remove_selected_tables()
                    # This function now handles rerun
            with remove_yaml_col2:
                if st.button("Generate YAML",
                             help="Fetch schemas (generate missing descriptions) and generate YAML."):
                    if not st.session_state.selected_tables:
                         st.warning("Please add at least one table before generating YAML.")
                    else:
                        st.session_state.generate_yaml_flag = True
                        st.rerun()
        elif st.session_state.get('dataset_id'):
            st.info("No tables added yet. Use the radio buttons above.")


def remove_selected_tables():
    """Removes selected tables from the selected_tables list."""
    tables_to_remove = st.session_state.get('config_tables_to_remove', [])
    # Use .get
    removed_count = 0

    if tables_to_remove:
        current_selected_tables = st.session_state.selected_tables.copy()
        # Work on a copy
        for table_str in tables_to_remove:
            try:
                project, dataset, table = table_str.split(".")
                table_info = { "project": project, "dataset": dataset, "table": table }
                if table_info in current_selected_tables:
                    current_selected_tables.remove(table_info)
                    removed_count += 1
            except ValueError:
                st.warning(f"Invalid table format found during removal: {table_str}")
                continue

        if removed_count > 0:
            st.session_state.selected_tables = current_selected_tables
            st.session_state.table_ids = [t['table'] for t in st.session_state.selected_tables]
            display_success_message(f"{removed_count} table(s) removed!")
            # st.session_state.config_tables_to_remove = []
            st.rerun()
    else:
        st.warning("Please select tables using the checkbox to remove.")


def show_instructions() -> None:
    """Displays initial instructions for the user."""
    st.markdown("### Welcome to the Data Agent Configuration!")
    st.markdown("""
    1.  **Enter Agent Instructions:** Provide general instructions for how the agent should behave in the text area.
    2.  **Select Project & Dataset:** Choose the Google Cloud project and BigQuery dataset containing your data.
    3.  **Add Tables:** Use the **radio buttons** under "Available Tables" to select the tables you want the agent to access. Added tables will appear below.
    4.  **Manage Tables:** If you need to remove tables, use the checkboxes under "Added Tables" and click "Remove Selected".
    5.  **Generate Configuration:** Once your tables are selected, click **Generate YAML/Create Agent**. This fetches the table schemas. **If descriptions are missing in BigQuery metadata, Gemini will attempt to generate them.** `golden_queries` are also generated by Gemini.
    6.  **Review & Edit YAML:** The generated YAML configuration will appear below. Review the fetched/generated descriptions and generated queries. You can directly edit the YAML in the text area.
    7.  **Update Agent:** Click **Update System Instructions** to ly the final YAML configuration to the agent.
    8.  **Chat:** Navigate to the Chat tab (if available) to interact with your configured agent.
    """)
    st.divider()


def render_yaml_section(schemas_with_descriptions):
    """Renders the YAML output section based on fetched/generated schemas."""

    # Start with the basic structure and system description from the input text area
    final_schema_yaml = {
        "system_description": st.session_state.get("config_instructions", "No system instructions provided."),
        "tables": {}
    }

    generation_errors = False
    st.write("Processing selected tables for YAML...")
    # Feedback
    progress_bar = st.progress(0)
    total_tables = len(schemas_with_descriptions)
    gemini_config_present = gemini_project_id and gemini_region

    for i, (table_name, table_data) in enumerate(schemas_with_descriptions.items()):
        # Basic validation of the fetched/generated schema data
        if not isinstance(table_data, dict) or "schema" not in table_data:
            st.error(f"Invalid or incomplete schema data provided for table: `{table_name}`. Skipping in YAML.")
            generation_errors = True
            continue # Skip this table

        # --- Fetch Golden Queries ---
        most_common_queries_data = ["No golden queries generated."] # Default
        try:
            # Check if necessary BQ/Gemini config is present for this specific call
            if bq_location and st.session_state.get('dataqna_project_id') and st.session_state.get('dataset_id') and gemini_config_present:
                 logging.info(f"Fetching golden queries for {table_name}...")
                 most_common_queries_data = get_most_common_queries(
                     st.session_state.dataqna_project_id,
                     st.session_state.dataset_id,
                     table_name,
                     gemini_region, # Pass region for Gemini call within get_most_common_queries
                     bq_location
                 )
                 logging.info(f"Finished fetching golden queries for {table_name}.")
            else:
                 missing_configs = []
                 if not bq_location: missing_configs.append("BQ Location")
                 if not st.session_state.get('dataqna_project_id'): missing_configs.append("Project ID")
                 if not st.session_state.get('dataset_id'): missing_configs.append("Dataset ID")
                 if not gemini_config_present: missing_configs.append("Gemini Project/Region")
                 logging.warning(f"Skipping golden query generation for `{table_name}` due to missing configuration: {', '.join(missing_configs)}.")
                 most_common_queries_data = ["[Golden query generation skipped: Missing config]"]

        except Exception as e:
            logging.error(f"Could not fetch golden queries for table `{table_name}`: {e}", exc_info=True)
            st.warning(f"An error occurred fetching golden queries for table `{table_name}`.")
            most_common_queries_data = ["[Error fetching golden queries]"]

        # --- Assemble Table YAML Data ---
        # Use the description directly from the potentially modified table_data
        table_description = table_data.get("description", "") # Use empty string if None/missing

        table_yaml_data = {
            "description": table_description,
            "schema": [],
            "golden_queries": most_common_queries_data if most_common_queries_data else ["No golden queries generated."] # Ensure it's not None
        }

        # Process columns using fetched/generated schema data
        if isinstance(table_data.get("schema"), list):
            for schema_item in table_data["schema"]:
                if isinstance(schema_item, dict) and "name" in schema_item:
                    col_name = schema_item.get("name")
                    # Use column description directly from fetched/generated schema item
                    col_description = schema_item.get("description", "") # Use empty string if None/missing
                    col_type = schema_item.get("type", "UNKNOWN") # Get type

                    table_yaml_data["schema"].append({
                        "name": col_name,
                        "type": col_type, # Include type in YAML
                        "description": col_description.strip() if col_description else ""
                    })
                else:
                    logging.warning(f"Invalid schema item found in table: `{table_name}`. Skipping item.")
        else:
            st.error(f"Invalid schema format for table `{table_name}` (expected list). Skipping columns.")
            generation_errors = True

        final_schema_yaml["tables"][table_name] = table_yaml_data
        progress_bar.progress((i + 1) / total_tables) # Update progress

    # Convert intermediate Python dict to initial YAML string (for Gemini input)
    initial_yaml_string = yaml.dump(
        final_schema_yaml,
        sort_keys=False,
        default_flow_style=False,
        width=1000)

    # --- Refine YAML with Gemini (Optional but kept) ---
    st.info("Refining YAML structure and content with Gemini...", icon="✨")
    final_schema_yaml_string_for_display = initial_yaml_string
    # Default if Gemini fails
    try:
        if gemini_config_present:
            prompt_for_yaml = yaml_prompt(initial_yaml_string)
            gemini_response = gemini_request(gemini_project_id, gemini_region, prompt_for_yaml)
            if isinstance(gemini_response, str):
                cleaned_response = remove_yaml_prefix_and_suffix(gemini_response)
                if cleaned_response and cleaned_response.strip():
                    final_schema_yaml_string_for_display = cleaned_response
                    st.success("Gemini refinement complete.", icon="✅")
                else:
                     st.warning("Gemini returned an empty or invalid refinement. Using the initial YAML structure.")
            else:
                 st.warning(f"Gemini returned unexpected type ({type(gemini_response)}). Using the initial YAML structure.")
        else:
            st.warning("Skipping Gemini YAML refinement due to missing configuration (Project ID or Region).")

    except Exception as e:
        logging.error(f"Error during Gemini YAML refinement API call: {e}", exc_info=True)
        st.error(f"An error occurred during Gemini YAML refinement: {e}")
        # Show error to user
        generation_errors = True
        # Mark error if refinement fails critically

    # Store the final YAML in session state FOR the text area display
    # Use a distinct key to avoid conflict with the main 'system_instruction' state
    st.session_state.final_system_instruction_for_display = final_schema_yaml_string_for_display

    # --- Display Final YAML and Update Button ---
    if generation_errors:
         st.warning("There were errors during YAML generation or refinement. Please review the output carefully.")

    st.markdown("""**Review Generated YAML**
*   Descriptions shown are fetched from BigQuery metadata or **auto-generated by Gemini** if missing.
*   `golden_queries` are generated by Gemini.
*   Edit the YAML below if needed, then click "Update System Instructions".
*   Consider adding `measures`, `relationships`, `glossaries`, etc., for optimal performance.""",
            unsafe_allow_html=True)

    st.text_area(label='Final System Instructions (YAML)',
                 value=st.session_state.final_system_instruction_for_display,
                 key="final_system_instruction_textarea",
                 # Key for the text area widget
                 height=600,
                 help="This is the final YAML configuration. Review and edit directly here before updating the agent.")

    st.button("Update System Instructions",
              on_click=update_system_instructions,
              # This callback uses the text area key
              help="Update the agent's system instructions with the content of the text area above.")


def form_page():
    """Main function to render the configuration form page."""

    # --- Initialization and Sidebar Setup ---
    if "system_instruction" not in st.session_state:
        st.session_state.system_instruction = "You are a helpful BigQuery data analysis assistant."
    if "project_id" not in st.session_state:
        st.session_state.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
    if "dataqna_project_id" not in st.session_state:
         st.session_state.dataqna_project_id = st.session_state.project_id if st.session_state.project_id != "your-gcp-project-id" else "bigquery-public-data"
    if "selected_tables" not in st.session_state:
        st.session_state.selected_tables = []

    # Display initial instructions only if YAML hasn't been generated/displayed yet
    if "final_system_instruction_for_display" not in st.session_state:
        show_instructions()

    # Logout Button
    if st.sidebar.button("Logout", key="logout_button"):
        keys_to_clear = list(st.session_state.keys())
        for key in keys_to_clear:
            if key != 'token': # Keep token if needed
                 del st.session_state[key]
        st.switch_page("app.py")
        st.rerun()

    st.header("Configure Data Agent")
    render_configuration_inputs() # Renders sidebar elements

    # --- Main Page Area: YAML Generation and Display ---
    if st.session_state.get("generate_yaml_flag", False):
        selected_tables_list = st.session_state.get("selected_tables", [])
        if selected_tables_list:
            st.divider()
            st.header("⚙️ Generating Agent Configuration...") # Update header during generation
            # Use an expander for potentially verbose generation logs/status
            with st.expander("Generation Progress & Details", expanded=True):
                st.info("Fetching schemas and generating missing descriptions/queries...")
                all_schemas_with_descriptions = {}
                generation_successful = True
                # Use st.status for better progress indication during fetch/generation
                with st.spinner("Processing tables..."):
                    for table_info in selected_tables_list:
                        project = table_info['project']
                        dataset = table_info['dataset']
                        table_name = table_info['table']
                        # This function now handles fetching AND generation
                        schema = cached_get_table_schema_and_description_with_generation(
                            project,
                            dataset,
                            table_name)
                        if schema:
                            all_schemas_with_descriptions[table_name] = schema
                            logging.info(f"Schema processed for {table_name}")
                        else:
                            # Error/warning already displayed by the function
                            generation_successful = False
                            logging.error(f"Failed to get/generate schema for {table_name}")
                            # Optionally break early if one fails? Or continue? Let's continue.

                if not generation_successful:
                     st.warning("YAML generation may be incomplete due to errors fetching or generating schemas for some tables. See warnings above.")
                elif not all_schemas_with_descriptions:
                     st.error("Failed to process schemas for all selected tables.")
                else:
                     st.success("Schema processing complete.")

            # Proceed to render YAML section only if we got some schemas
            if all_schemas_with_descriptions:
                 render_yaml_section(all_schemas_with_descriptions)
            else:
                 st.error("Cannot generate YAML as no valid table schemas could be processed.")

            # Reset the flag AFTER processing is complete
            st.session_state.generate_yaml_flag = False
            # No rerun needed here, results are displayed by render_yaml_section

        else: # generate_yaml_flag is True, but selected_tables is empty
            st.warning("No tables selected. Please add tables in the sidebar before generating YAML.")
            st.session_state.generate_yaml_flag = False # Reset flag

    # Re-display the final YAML if it exists in state (on subsequent reruns without clicking generate)
    elif "final_system_instruction_for_display" in st.session_state:
         st.divider()
         st.header("⚙️ Agent Configuration (YAML)") # Static header when just displaying
         # Re-render the YAML section using the stored display value
         st.text_area(label='Final System Instructions (YAML)',
                      value=st.session_state.final_system_instruction_for_display,
                      key="final_system_instruction_textarea", # Use same key
                      height=600,
                      help="This is the final YAML configuration. Review and edit directly here before updating the agent.")
         st.button("Update System Instructions",
                   on_click=update_system_instructions, # Use same callback
                   help="Update the agent's system instructions with the content of the text area above.")


# --- Main Execution Guard ---
if "token" not in st.session_state:
    st.switch_page("app.py")
else:
    try:
        st.set_page_config(layout="wide", page_title="Data Agent Configuration")
    except st.errors.StreamlitAPIException as e:
        if "set_page_config()" in str(e) or "can only be called once per app" in str(e):
            pass
        else:
            raise
    st.title("📊 Data Agent Configuration")
    form_page()
