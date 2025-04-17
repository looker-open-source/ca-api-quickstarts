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

from app_pages.utils.looker_utils import (
    check_credentials,
    get_looker_explores,
    get_looker_models
)


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


# --- Configuration Update Functions (BigQuery) ---
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


# --- Callback for Radio Button (BigQuery Table Selection) ---
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
                st.rerun() # Rerun to update the "Added Tables" list immediately


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
            # Clear the multi-select after removal
            st.session_state.config_tables_to_remove = []
            display_success_message(f"{removed_count} table(s) removed!")
            st.rerun() # Rerun to reflect changes
    else:
        st.warning("Please select tables using the checkbox to remove.")


# --- UI Rendering Functions --- #
def render_configuration_inputs():
    """Renders input fields for project, dataset, table selection, and instructions (BigQuery)."""

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
    current_datasets = st.session_state.get('config_datasets', [])
    if current_datasets and st.session_state.get('dataset_id') in current_datasets:
        try:
            dataset_index = current_datasets.index(st.session_state.dataset_id)
        except ValueError: dataset_index = 0
    # Add placeholder if needed or handle empty list
    dataset_options = ["--- Select a Dataset ---"] + current_datasets
    if st.session_state.get('dataset_id'):
        try:
            dataset_index = dataset_options.index(st.session_state.dataset_id)
        except ValueError:
             dataset_index = 0 # Default to placeholder if current value is somehow invalid
    else:
        dataset_index = 0 # Default to placeholder


    st.selectbox(
        "Dataset",
        dataset_options, # Use .get for safety
        key='config_dataset',
        index=dataset_index,
        on_change=on_dataset_change,
        help="Select the BigQuery dataset.",
        # placeholder="Select a dataset..." # Placeholder is less useful with explicit "--- Select ---"
    )

    # --- Table Selection (Radio Buttons) & Management ---
    if "config_table_options" not in st.session_state:
        if st.session_state.get('dataset_id') and st.session_state.dataset_id != "--- Select a Dataset ---":
            update_config_tables() # Load tables if a dataset is selected
        else:
            st.session_state.config_table_options = [] # Ensure it's an empty list

    if "selected_tables" not in st.session_state:
        st.session_state.selected_tables = []

    # Only show table selection if a valid dataset is chosen
    if st.session_state.get('dataset_id') and st.session_state.dataset_id != "--- Select a Dataset ---":
        st.subheader("Select Tables to Add")

        available_tables = st.session_state.get('config_table_options', [])
        if available_tables:
            # Determine current selection index for radio
            current_radio_selection = st.session_state.get('config_radio_selected_table')
            radio_options = ["--- Select Table to Add ---"] + available_tables
            try:
                radio_index = radio_options.index(current_radio_selection) if current_radio_selection else 0
            except ValueError:
                radio_index = 0 # Default to placeholder

            st.radio(
                "Available Tables",
                options=radio_options,
                key='config_radio_selected_table',
                on_change=handle_radio_table_selection,
                index=radio_index,
                help="Select a table's radio button to add it below."
            )
        elif st.session_state.get('dataqna_project_id') and st.session_state.get('dataset_id'):
             st.info("No tables found in the selected dataset.")
        else:
             st.info("Select a project and dataset to see available tables.") # Should not happen if dataset_id check works

        # --- Manage Added Tables Section ---
        st.subheader("Manage Added Tables")
        if st.session_state.selected_tables:
            # Prepare list for display and removal
            selected_table_names_for_removal = [f"{t['project']}.{t['dataset']}.{t['table']}" for t in st.session_state.selected_tables]

            # Display added tables clearly
            st.markdown("**Currently Added:**")
            for table_name in selected_table_names_for_removal:
                 st.markdown(f"- `{table_name}`")
            st.markdown("---") # Separator

            st.multiselect("Select tables to remove",
                           selected_table_names_for_removal,
                           key='config_tables_to_remove',
                           help="Select tables using the checkbox to remove them.")

            remove_yaml_col1, remove_yaml_col2 = st.columns([1, 1])
            with remove_yaml_col1:
                st.button("Remove Selected",
                             key="remove_tables_button", # Add key for clarity
                             on_click=remove_selected_tables,
                             help="Remove the tables selected in the multiselect box above.")
            with remove_yaml_col2:
                st.button("Generate YAML",
                             key="generate_yaml_button", # Add key for clarity
                             on_click=trigger_yaml_generation, # Use a separate function to set the flag
                             help="Fetch schemas (generate missing descriptions) and generate YAML for the added tables.")
        elif st.session_state.get('dataset_id') and st.session_state.dataset_id != "--- Select a Dataset ---":
            st.info("No tables added yet. Use the radio buttons above.")
        else:
             st.info("Select a dataset first, then choose tables to add.") # Guidance if no dataset selected

def trigger_yaml_generation():
    """Sets the flag to start YAML generation on the next rerun."""
    if not st.session_state.get("selected_tables"):
         st.warning("Please add at least one table before generating YAML.")
    else:
        st.session_state.generate_yaml_flag = True
        # No rerun needed here, the main script loop will catch the flag


def render_yaml_section(schemas_with_descriptions):
    """Renders the YAML output section based on fetched/generated schemas."""

    # Start with the basic structure and system description from the input text area
    system_instructions_value = st.session_state.get("config_instructions", "No system instructions provided.")
    final_schema_yaml = {
        "system_description": system_instructions_value,
        "tables": {}
    }

    generation_errors = False
    st.write("Processing selected tables for YAML...")
    # Feedback
    total_tables = len(schemas_with_descriptions)
    if total_tables == 0:
        st.warning("No schemas provided to render YAML.")
        return

    progress_bar = st.progress(0.0)
    gemini_config_present = gemini_project_id and gemini_region

    for i, (table_name, table_data) in enumerate(schemas_with_descriptions.items()):
        # Basic validation of the fetched/generated schema data
        if not isinstance(table_data, dict) or "schema" not in table_data:
            st.error(f"Invalid or incomplete schema data provided for table: `{table_name}`. Skipping in YAML.")
            generation_errors = True
            progress_bar.progress((i + 1) / total_tables) # Update progress even on skip
            continue # Skip this table

        # --- Fetch Golden Queries ---
        most_common_queries_data = ["[Golden query generation skipped or failed]"] # Default
        try:
            # Check if necessary BQ/Gemini config is present for this specific call
            # Ensure dataset_id is valid before proceeding
            bq_project = st.session_state.get('dataqna_project_id')
            bq_dataset = st.session_state.get('dataset_id')

            if bq_location and bq_project and bq_dataset and bq_dataset != "--- Select a Dataset ---" and gemini_config_present:
                 logging.info(f"Fetching golden queries for {table_name}...")
                 # Find the correct project/dataset for *this specific table* if multiple sources were allowed
                 # For now, assuming all tables are from the currently selected project/dataset
                 current_table_project = bq_project # Assuming single source for simplicity now
                 current_table_dataset = bq_dataset

                 most_common_queries_data = get_most_common_queries(
                     current_table_project,
                     current_table_dataset,
                     table_name,
                     gemini_region, # Pass region for Gemini call within get_most_common_queries
                     bq_location
                 )
                 logging.info(f"Finished fetching golden queries for {table_name}.")
                 if not most_common_queries_data: # If function returns empty list/None
                      most_common_queries_data = ["No golden queries generated."]
            else:
                 missing_configs = []
                 if not bq_location: missing_configs.append("BQ Location")
                 if not bq_project: missing_configs.append("Project ID")
                 if not bq_dataset or bq_dataset == "--- Select a Dataset ---": missing_configs.append("Valid Dataset ID")
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
            "golden_queries": most_common_queries_data # Ensure it's not None
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
                    display_success_message("Gemini refinement complete.") # Use timed message
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
              key="update_yaml_instructions_button", # Add key
              on_click=update_system_instructions,
              # This callback uses the text area key
              help="Update the agent's system instructions with the content of the text area above.")


# --- Looker Configuration Callbacks ---

def handle_looker_credentials_change():
    """Update session state when Looker credential inputs change."""
    logging.info("Looker credentials input changed.")
    st.session_state.looker_host = st.session_state.get("looker_host_input", "")
    st.session_state.looker_client_id = st.session_state.get("looker_client_id_input", "")
    # Only update secret if the input field actually exists and has a value
    # This prevents accidental overwriting on reruns if the field isn't rendered
    if "looker_secret_input" in st.session_state:
         st.session_state.looker_secret = st.session_state.get("looker_secret_input", "")

    # When credentials change, validation status is reset
    st.session_state.looker_credentials_valid = False
    st.session_state.looker_api_client = None
    st.session_state.looker_models_list = []
    st.session_state.looker_selected_model = None
    st.session_state.looker_model = None # Also reset the main model variable
    st.session_state.looker_explores_list = []
    st.session_state.looker_selected_explore = None
    st.session_state.looker_explore = None # Also reset the main explore variable


def handle_looker_instruction_change():
    """Update main system instructions when Looker instructions change."""
    st.session_state.system_instruction = st.session_state.get("looker_system_instructions_input", "")

def handle_validate_credentials():
    """Validate Looker credentials and fetch models if successful."""
    logging.info("Validating Looker credentials...")
    host = st.session_state.get("looker_host")
    client_id = st.session_state.get("looker_client_id")
    # Make sure secret is read correctly, even if input isn't always visible
    secret = st.session_state.get("looker_secret")

    if not all([host, client_id, secret]):
        st.warning("Please enter Looker Host, Client ID, and Secret.")
        st.session_state.looker_credentials_valid = False
        # Ensure downstream resets happen even if inputs are missing
        st.session_state.looker_api_client = None
        st.session_state.looker_models_list = []
        st.session_state.looker_selected_model = None
        st.session_state.looker_model = None
        st.session_state.looker_explores_list = []
        st.session_state.looker_selected_explore = None
        st.session_state.looker_explore = None
        return

    try:
        # Ensure secret input value is used if button is clicked before on_change fires fully
        secret_from_input = st.session_state.get("looker_secret_input")
        effective_secret = secret_from_input if secret_from_input else secret # Prioritize fresh input

        if not effective_secret:
            st.warning("Please enter Looker Secret.")
            st.session_state.looker_credentials_valid = False
            return # Don't proceed without secret

        response_code, sdk = check_credentials(host, client_id, effective_secret)
        if response_code == 200 and sdk:
            st.session_state.looker_credentials_valid = True
            st.session_state.looker_api_client = sdk
            # Fetch models immediately after validation
            models = get_looker_models(sdk)
            st.session_state.looker_models_list = models or []
            # Reset downstream selections
            st.session_state.looker_selected_model = None
            st.session_state.looker_model = None
            st.session_state.looker_explores_list = []
            st.session_state.looker_selected_explore = None
            st.session_state.looker_explore = None
            # Reset widget state explicitly if needed (though index logic should handle it)
            st.session_state.looker_model_selector = "--- Select a Model ---"
            st.session_state.looker_explore_selector = "--- Select an Explore ---"
            display_success_message("Looker Credentials Validated!")
            logging.info("Looker credentials validated successfully.")
        else:
            st.error(f"Invalid Looker Credentials (Error {response_code}). Please check and try again.")
            st.session_state.looker_credentials_valid = False
            st.session_state.looker_api_client = None
            st.session_state.looker_models_list = []
            st.session_state.looker_selected_model = None
            st.session_state.looker_model = None
            st.session_state.looker_explores_list = []
            st.session_state.looker_selected_explore = None
            st.session_state.looker_explore = None
            logging.warning(f"Looker credential validation failed with code: {response_code}")
    except Exception as e:
        st.error(f"An error occurred during validation: {e}")
        st.session_state.looker_credentials_valid = False
        st.session_state.looker_api_client = None
        st.session_state.looker_models_list = []
        st.session_state.looker_selected_model = None
        st.session_state.looker_model = None
        st.session_state.looker_explores_list = []
        st.session_state.looker_selected_explore = None
        st.session_state.looker_explore = None
        logging.error(f"Exception during Looker credential validation: {e}", exc_info=True)


def handle_model_change():
    """Fetch explores when the selected Looker model changes."""
    logging.info("Looker model selection changed.")
    selected_model_from_widget = st.session_state.get("looker_model_selector") # Get value from the selector widget

    # Update internal state for config page rendering
    st.session_state.looker_selected_model = selected_model_from_widget if selected_model_from_widget != "--- Select a Model ---" else None

    # Update the main state variable used by other parts of the app
    st.session_state.looker_model = st.session_state.looker_selected_model

    logging.info(f"Selected model (internal config): {st.session_state.looker_selected_model}")
    logging.info(f"Selected model (main app state): {st.session_state.looker_model}")

    # Reset explore selection whenever model changes
    st.session_state.looker_explores_list = []
    st.session_state.looker_selected_explore = None
    st.session_state.looker_explore = None # Also reset the main explore state
    if "looker_explore_selector" in st.session_state:
        st.session_state.looker_explore_selector = "--- Select an Explore ---" # Reset the selector widget state too


    if st.session_state.looker_selected_model and st.session_state.get("looker_api_client"):
        try:
            logging.info(f"Fetching explores for model: {st.session_state.looker_selected_model}")
            explores = get_looker_explores(st.session_state.looker_api_client, st.session_state.looker_selected_model)
            st.session_state.looker_explores_list = explores or []
            logging.info(f"Found explores: {st.session_state.looker_explores_list}")
        except Exception as e:
            st.error(f"Failed to fetch explores for model '{st.session_state.looker_selected_model}': {e}")
            logging.error(f"Exception fetching explores: {e}", exc_info=True)
            st.session_state.looker_explores_list = [] # Ensure it's empty on error
    else:
         logging.info("No model selected or API client not available, skipping explore fetch.")


def handle_explore_change():
    """Update session state when the selected Looker explore changes."""
    logging.info("Looker explore selection changed.")
    selected_explore_from_widget = st.session_state.get("looker_explore_selector") # Get value from the selector widget

    # Update the internal state variable used for rendering the config page correctly
    st.session_state.looker_selected_explore = selected_explore_from_widget if selected_explore_from_widget != "--- Select an Explore ---" else None

    # --- THIS IS THE KEY CHANGE ---
    # Update the main state variable expected by other parts of the app
    st.session_state.looker_explore = st.session_state.looker_selected_explore
    # --- End of Key Change ---

    logging.info(f"Selected explore (internal config): {st.session_state.looker_selected_explore}")
    logging.info(f"Selected explore (main app state): {st.session_state.looker_explore}")


# --- Looker Form Page ---
def looker_form_page():
    """Renders the Looker configuration form elements based on session state."""
    st.subheader("Looker Configuration")

    # 1. System Instructions
    st.text_area("Agent Instructions",
                 value=st.session_state.get("system_instruction", # Reflects main state now
                                             "You are a helpful Looker data analyst."),
                 key="looker_system_instructions_input", # Widget key
                 on_change=handle_looker_instruction_change,
                 height=100,
                 help="Enter general instructions for the agent when using Looker.")

    # 2. Credentials Inputs
    st.text_input("Looker Host (e.g., https://yourcompany.looker.com)",
                  value=st.session_state.get("looker_host", ""),
                  key="looker_host_input",
                  on_change=handle_looker_credentials_change, # Resets validation status
                  help="Enter the full Looker instance URL.")

    st.text_input("Looker Client ID",
                  value=st.session_state.get("looker_client_id", ""),
                  key="looker_client_id_input",
                  type="password",
                  on_change=handle_looker_credentials_change) # Resets validation status

    # Use session state for secret value, allows pre-filling if desired (though usually not)
    # The on_change callback handles updating the state variable.
    st.text_input("Looker Secret",
                  value=st.session_state.get("looker_secret", ""), # Show stored value if exists
                  key="looker_secret_input",
                  type="password",
                  on_change=handle_looker_credentials_change) # Resets validation status

    # 3. Validation Button
    st.button("Validate Credentials",
              type="primary",
              key="looker_validate_button",
              on_click=handle_validate_credentials,
              help="Click to verify credentials and fetch available models.")

    # 4. Model Selection (Conditional)
    if st.session_state.get("looker_credentials_valid", False):
        st.markdown("---") # Separator
        st.markdown("**Select Model & Explore**")
        model_options = ["--- Select a Model ---"] + st.session_state.get("looker_models_list", [])
        # Use looker_selected_model for the index to ensure consistency within the config page
        current_model_for_selector = st.session_state.get("looker_selected_model")
        try:
            model_index = model_options.index(current_model_for_selector) if current_model_for_selector else 0
        except ValueError:
            model_index = 0 # Default to placeholder if value is somehow invalid

        st.selectbox("Looker Model",
                     options=model_options,
                     key="looker_model_selector", # Key for this specific widget
                     index=model_index,
                     on_change=handle_model_change, # Fetches explores and updates state
                     help="Select the Looker model to use.")

        # 5. Explore Selection (Conditional)
        # Only show if a model is selected AND explores have been loaded
        if st.session_state.get("looker_selected_model") and st.session_state.get("looker_explores_list"):
            explore_options = ["--- Select an Explore ---"] + st.session_state.get("looker_explores_list", [])
            # Use looker_selected_explore for the index
            current_explore_for_selector = st.session_state.get("looker_selected_explore")
            try:
                 explore_index = explore_options.index(current_explore_for_selector) if current_explore_for_selector else 0
            except ValueError:
                 explore_index = 0 # Default to placeholder

            # Using selectbox for consistency, change back to radio if preferred
            st.selectbox("Looker Explore",
                        options=explore_options,
                        key="looker_explore_selector", # Key for this specific widget
                        index=explore_index,
                        on_change=handle_explore_change, # Updates selected explore state (both variables now)
                        help="Select the Looker explore to query.")
        elif st.session_state.get("looker_selected_model"):
            # This case handles if explores are still loading or failed to load
             if not st.session_state.get("looker_explores_list"):
                  # Only show message if explores list is actually empty after trying to load
                  st.info("No explores found for the selected model or failed to load explores.")
        # Do not show anything if no model is selected yet


# ... (rest of the code: data_source_on_change, form_page, Main Execution Guard, etc.) ...

# --- Data Source Switching ---
def data_source_on_change():
    """Callback function when the data source radio button changes."""
    if "data_source_radio" in st.session_state:
        previous_source = st.session_state.get("data_source")
        new_source = st.session_state.data_source_radio
        st.session_state.data_source = new_source
        logging.info(f"Data source changed from '{previous_source}' to '{new_source}'")

        # Explicitly set the default instructions for the NEW source
        if new_source == "BigQuery":
            # Retrieve BQ instructions if stored, else use default
            bq_instructions = st.session_state.get("bq_system_instruction", "You are a helpful BigQuery data analysis assistant.")
            st.session_state.system_instruction = bq_instructions
            # Store current BQ instructions in case user switches back later
            if "config_instructions" in st.session_state:
                st.session_state.bq_system_instruction = st.session_state.config_instructions

        elif new_source == "Looker":
            # Retrieve Looker instructions if stored, else use default
            looker_instructions = st.session_state.get("looker_system_instructions_input", "You are a helpful Looker data analyst.")
            st.session_state.system_instruction = looker_instructions
            # Store current Looker instructions if they exist
            if "looker_system_instructions_input" in st.session_state:
                 st.session_state.looker_system_instructions_input = st.session_state.looker_system_instructions_input

            # Ensure looker specific states are initialized if they don't exist
            # (or potentially reset them if desired when switching TO Looker)
            if "looker_credentials_valid" not in st.session_state: st.session_state.looker_credentials_valid = False
            if "looker_models_list" not in st.session_state: st.session_state.looker_models_list = []
            if "looker_selected_model" not in st.session_state: st.session_state.looker_selected_model = None
            if "looker_model" not in st.session_state: st.session_state.looker_model = None
            if "looker_explores_list" not in st.session_state: st.session_state.looker_explores_list = []
            if "looker_selected_explore" not in st.session_state: st.session_state.looker_selected_explore = None
            if "looker_explore" not in st.session_state: st.session_state.looker_explore = None
            if "looker_host" not in st.session_state: st.session_state.looker_host = ""
            if "looker_client_id" not in st.session_state: st.session_state.looker_client_id = ""
            # Secret usually not pre-filled on switch unless specifically needed
            # if "looker_secret" not in st.session_state: st.session_state.looker_secret = ""


# --- Main Form Page ---
def form_page():
    """Main function to render the configuration form page based on selected data source."""

    # Initialize common session state variables if they don't exist
    if "system_instruction" not in st.session_state:
            # Default based on initial data_source selection
            default_source = st.session_state.get("data_source", "BigQuery")
            st.session_state.system_instruction = "You are a helpful Looker data analyst." if default_source == "Looker" else "You are a helpful BigQuery data analysis assistant."
    if "project_id" not in st.session_state:
            st.session_state.project_id = os.getenv("PROJECT_ID", "your-gcp-project-id")
    if "dataqna_project_id" not in st.session_state:
            st.session_state.dataqna_project_id = st.session_state.project_id if st.session_state.project_id != "your-gcp-project-id" else "bigquery-public-data"
    if "selected_tables" not in st.session_state:
            st.session_state.selected_tables = []

    st.header("Configure Data Agent")

    # Render UI based on the selected data source
    selected_data_source = st.session_state.get("data_source", "BigQuery") # Default to BQ if not set

    if selected_data_source == "BigQuery":
        st.subheader("BigQuery Configuration")
        # Display BQ Instructions/Guidance
        if "final_system_instruction_for_display" not in st.session_state:
            st.markdown("""
            Use the fields below to configure the agent for BigQuery:
            1.  **Agent Instructions:** Provide general instructions.
            2.  **Project & Dataset:** Choose the GCP project and BigQuery dataset.
            3.  **Add Tables:** Use the **radio buttons** under "Available Tables" to select tables.
            4.  **Manage Tables:** Review added tables and remove if needed.
            5.  **Generate Configuration:** Click **Generate YAML**. This fetches schemas and uses Gemini for missing descriptions/queries.
            6.  **Review & Edit YAML:** Review the generated YAML configuration.
            7.  **Update Agent:** Click **Update System Instructions** to apply the YAML.
            """)
            st.divider()
        # Render BQ specific inputs
        render_configuration_inputs() # This now includes BQ instructions text area

        # Handle BQ YAML Generation Logic (remains largely the same)
        if st.session_state.get("generate_yaml_flag", False):
            selected_tables_list = st.session_state.get("selected_tables", [])
            if selected_tables_list:
                st.divider()
                st.header("⚙️ Generating Agent Configuration (YAML)...")
                with st.expander("Generation Progress & Details", expanded=True):
                    st.info("Fetching schemas and generating missing descriptions/queries...")
                    all_schemas_with_descriptions = {}
                    generation_successful = True
                    with st.spinner("Processing tables..."):
                        for table_info in selected_tables_list:
                            project = table_info['project']
                            dataset = table_info['dataset']
                            table_name = table_info['table']
                            schema = cached_get_table_schema_and_description_with_generation(
                                project, dataset, table_name)
                            if schema:
                                all_schemas_with_descriptions[table_name] = schema
                                logging.info(f"Schema processed for {table_name}")
                            else:
                                generation_successful = False
                                logging.error(f"Failed to get/generate schema for {table_name}")

                    if not generation_successful:
                            st.warning("YAML generation may be incomplete due to errors processing some tables.")
                    elif not all_schemas_with_descriptions:
                            st.error("Failed to process schemas for all selected tables.")
                    else:
                            st.success("Schema processing complete.")

                if all_schemas_with_descriptions:
                    # Pass the correct BQ instructions to render_yaml_section if needed
                    # Or ensure render_yaml_section reads from the correct state variable
                    render_yaml_section(all_schemas_with_descriptions)
                else:
                    st.error("Cannot generate YAML as no valid table schemas could be processed.")

            else: # generate_yaml_flag is True, but selected_tables is empty
                st.warning("No tables selected. Please add tables before generating YAML.")

            # Reset the flag AFTER processing is complete
            st.session_state.generate_yaml_flag = False

        # Re-display the final YAML if it exists in state
        elif "final_system_instruction_for_display" in st.session_state:
            st.divider()
            st.header("⚙️ Agent Configuration (YAML)")
            st.text_area(label='Final System Instructions (YAML)',
                            value=st.session_state.final_system_instruction_for_display,
                            key="final_system_instruction_textarea",
                            height=600,
                            help="This is the final YAML configuration. Review and edit directly here before updating the agent.")
            st.button("Update System Instructions",
                      key="update_yaml_instructions_button_redisplay", # Different key if needed
                      on_click=update_system_instructions,
                      help="Update the agent's system instructions with the content of the text area above.")

    elif selected_data_source == "Looker":
        # Display Looker Instructions/Guidance
        st.markdown("""
        Use the fields below to configure the agent for Looker:
        1.  **Agent Instructions:** Provide general instructions.
        2.  **Credentials:** Enter your Looker Host URL, API Client ID, and Client Secret.
        3.  **Validate:** Click "Validate Credentials" to verify access and load models.
        4.  **Select Model:** Choose the Looker model you want the agent to use.
        5.  **Select Explore:** Choose the specific Looker explore within the selected model.
        6.  Navigate to the Chat page to interact with the agent using the selected Looker model and explore.
        """)
        st.divider()
        # Render Looker specific form page
        looker_form_page() # This now includes Looker instructions text area

    else:
        st.error("Invalid data source selected.")


# --- Main Execution Guard ---
if "token" not in st.session_state:
    # Redirect to login if no token - assuming app.py handles login
    # Check if 'pages/app.py' exists or adjust the path as needed
    try:
        st.switch_page("app.py") # Adjust if your main/login page is named differently
    except Exception as e:
        logging.error(f"Failed to switch page to app.py: {e}")
        st.error("User not authenticated. Please login.") # Fallback message
else:
    # Set page config only once
    try:
        st.set_page_config(layout="wide", page_title="Data Agent Configuration")
    except st.errors.StreamlitAPIException as e:
        if "can only be called once per app" not in str(e):
            logging.error(f"Error setting page config: {e}")
            # raise e # Optional: re-raise if it's an unexpected error

    st.title("📊 Data Agent Configuration")

    # Initialize data_source if it doesn't exist
    if "data_source" not in st.session_state:
        st.session_state.data_source = "BigQuery" # Default to BigQuery

    # Data Source Selection Radio Button
    data_source_options = ["BigQuery", "Looker"]
    try:
        # Index should reflect the actual 'data_source' state, not the radio button's potentially lagging state
        data_source_index = data_source_options.index(st.session_state.data_source)
    except ValueError:
        st.session_state.data_source = "BigQuery" # Reset to default if invalid value
        data_source_index = 0 # Default to BigQuery

    # Use a key for the widget itself, distinct from the primary state variable if necessary
    st.radio(
        "Select Data Source",
        options=data_source_options,
        key="data_source_radio", # Key for the radio widget
        horizontal=True,
        on_change=data_source_on_change, # Callback updates st.session_state.data_source
        index=data_source_index # Set index based on the actual session state
    )
    logging.info(f"Render - data_source_radio value: {st.session_state.get('data_source_radio')}, data_source session: {st.session_state.get('data_source')}")

    # Render the rest of the form based on the selection
    form_page()