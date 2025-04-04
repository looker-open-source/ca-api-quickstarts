import streamlit as st
import os
import yaml
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from streamlit.runtime.scriptrunner import add_script_run_ctx

# Rest of your imports and utility functions
from app_pages.utils.display_bq_data import (
    list_datasets as util_list_datasets,
    list_tables as util_list_tables,
    get_all_tables_schemas_and_descriptions as util_get_all_schemas,
    select_10_from_table,
    select_column_from_table,
    get_most_common_queries,
)
from app_pages.utils.gemini import (
    gemini_request,
    generate_description_prompt_for_column,
    generate_description_prompt_for_table,
    yaml_prompt,
)

# --- Constants ---
# Using constants for session state keys helps prevent typos
CONFIG_PROJECT_ID = "config_project_id"
CONFIG_DATASET_ID = "config_dataset_id"
CONFIG_AVAILABLE_DATASETS = "config_available_datasets"
CONFIG_AVAILABLE_TABLES = "config_available_tables"
CONFIG_SELECTED_TABLES_INFO = "config_selected_tables_info" # List[Dict[str, str]]
CONFIG_TABLE_SCHEMAS = "config_table_schemas" # Dict[str, Dict] -> table_name: schema_data
CONFIG_SYSTEM_INSTRUCTIONS = "config_system_instructions"
CONFIG_FINAL_YAML = "config_final_yaml"
CONFIG_CURRENT_EDIT_TABLE_IDX = "config_current_edit_table_idx"
CONFIG_TABLES_TO_REMOVE = "config_tables_to_remove"
CONFIG_CURRENTLY_SELECTED_TABLE = "config_currently_selected_table" # For the single selectbox
CONFIG_CHECKED_TABLES = "config_checked_tables" # Set of checked tables


# --- Environment Variables ---
# It's good practice to load these once
GEMINI_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
GEMINI_REGION = os.getenv("GEMINI_REGION")
BQ_LOCATION = os.getenv("BQ_LOCATION")
DEFAULT_PROJECT = "bigquery-public-data"
CURRENT_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT) # Get current GCP project or default

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Utility Functions ---
def display_timed_message(message: str, type: str = "success", icon="✅", duration: int = 2):
    """Displays a Streamlit message (success, warning, error, info) for a duration."""
    func = getattr(st, type, st.info) # Default to info if type is invalid
    message_placeholder = st.empty()
    message_placeholder.success(message, icon=icon) if type == "success" else func(message)
    time.sleep(duration)
    message_placeholder.empty()

def remove_yaml_prefix_and_suffix(text: str) -> str:
    """Removes standard YAML code block fences."""
    prefix = "```yaml"
    suffix = "```"
    if isinstance(text, str): # Ensure it's a string
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip()
        if text.endswith(suffix):
            text = text[:-len(suffix)].rstrip()
    return text

# --- Data Fetching and Caching ---

@st.cache_data(ttl=3600) # Cache dataset list for 1 hour
def list_datasets_cached(project_name: str) -> List[str]:
    """Cached wrapper for listing datasets."""
    logger.info(f"Fetching datasets for project: {project_name}")
    try:
        return util_list_datasets(project_name)
    except Exception as e:
        st.error(f"Error listing datasets for {project_name}: {e}")
        return []

@st.cache_data(ttl=3600) # Cache table list for 1 hour
def list_tables_cached(project_name: str, dataset_name: str) -> List[str]:
    """Cached wrapper for listing tables."""
    logger.info(f"Fetching tables for {project_name}.{dataset_name}")
    try:
        return util_list_tables(project_name, dataset_name)
    except Exception as e:
        st.error(f"Error listing tables for {project_name}.{dataset_name}: {e}")
        return []

@st.cache_data(ttl=3600) # Cache schemas for 1 hour
def get_schemas_cached(project_name: str, dataset_name: str, table_names: Tuple[str]) -> Dict[str, Any]:
    """
    Fetches schemas for a specific list of tables within a dataset.
    Caches the result based on project, dataset, and the tuple of table names.
    """
    logger.info(f"Fetching schemas for tables {table_names} in {project_name}.{dataset_name}")
    if not table_names:
        return {}
    try:
        selected_schemas = {}  # Initialize before the if block
        # Fetch all schemas for the dataset - consider optimizing if the util allows fetching specific tables
        all_schemas = util_get_all_schemas(project_name, dataset_name)
        # Filter for the requested tables
        selected_schemas = {name: schema for name, schema in all_schemas.items() if name in table_names}
        # Check if any requested tables were missing
        missing_tables = set(table_names) - set(selected_schemas.keys())
        if missing_tables:
            st.warning(f"Could not find schemas for tables: {', '.join(missing_tables)}")
        return selected_schemas
    except Exception as e:
        st.error(f"Error fetching schemas for {project_name}.{dataset_name}: {e}")
        return {}

# --- State Initialization ---
def initialize_session_state():
    """Initializes required session state variables if they don't exist."""
    state_defaults = {
        CONFIG_PROJECT_ID: CURRENT_PROJECT,
        CONFIG_DATASET_ID: None,
        CONFIG_AVAILABLE_DATASETS: [],
        CONFIG_AVAILABLE_TABLES: [],
        CONFIG_SELECTED_TABLES_INFO: [], # List of dicts {project, dataset, table}
        CONFIG_TABLE_SCHEMAS: {}, # Populated after tables are selected and Generate clicked
        CONFIG_SYSTEM_INSTRUCTIONS: "You are a helpful data analysis assistant.", # Default instruction
        CONFIG_FINAL_YAML: None, # Store the generated YAML string here
        CONFIG_CURRENT_EDIT_TABLE_IDX: 0,
        CONFIG_TABLES_TO_REMOVE: [],
        CONFIG_CURRENTLY_SELECTED_TABLE: None,
        CONFIG_CHECKED_TABLES: set(), # Add this new state for checkbox selections
        "project_id": CURRENT_PROJECT # Assuming this is used elsewhere for auth/defaults
        # Removed flags like hide_schema_descriptions, generate_yaml_flag
    }
    for key, default_value in state_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    # Ensure initial dataset list is populated for the default/current project
    if not st.session_state[CONFIG_AVAILABLE_DATASETS]:
         st.session_state[CONFIG_AVAILABLE_DATASETS] = list_datasets_cached(st.session_state[CONFIG_PROJECT_ID])


# --- Callback Functions (State Updates) ---
def update_selected_project():
    """Callback when project selection changes."""
    st.session_state[CONFIG_PROJECT_ID] = st.session_state["project_selector"] # Get value from widget
    st.session_state[CONFIG_DATASET_ID] = None
    st.session_state[CONFIG_AVAILABLE_TABLES] = []
    st.session_state[CONFIG_SELECTED_TABLES_INFO] = []
    st.session_state[CONFIG_TABLE_SCHEMAS] = {}
    st.session_state[CONFIG_FINAL_YAML] = None # Clear generated YAML
    st.session_state[CONFIG_CURRENT_EDIT_TABLE_IDX] = 0
    st.session_state[CONFIG_CURRENTLY_SELECTED_TABLE] = None
    # Fetch new datasets
    st.session_state[CONFIG_AVAILABLE_DATASETS] = list_datasets_cached(st.session_state[CONFIG_PROJECT_ID])
    logger.info(f"Project changed to: {st.session_state[CONFIG_PROJECT_ID]}. Resetting dependent state.")

def update_selected_dataset():
    """Callback when dataset selection changes."""
    st.session_state[CONFIG_DATASET_ID] = st.session_state["dataset_selector"] # Get value from widget
    st.session_state[CONFIG_AVAILABLE_TABLES] = [] # Clear old tables
    st.session_state[CONFIG_SELECTED_TABLES_INFO] = [] # Clear selected tables
    st.session_state[CONFIG_TABLE_SCHEMAS] = {}
    st.session_state[CONFIG_FINAL_YAML] = None # Clear generated YAML
    st.session_state[CONFIG_CURRENT_EDIT_TABLE_IDX] = 0
    st.session_state[CONFIG_CURRENTLY_SELECTED_TABLE] = None
    # Fetch new tables
    if st.session_state[CONFIG_PROJECT_ID] and st.session_state[CONFIG_DATASET_ID]:
        st.session_state[CONFIG_AVAILABLE_TABLES] = list_tables_cached(
            st.session_state[CONFIG_PROJECT_ID],
            st.session_state[CONFIG_DATASET_ID]
        )
    logger.info(f"Dataset changed to: {st.session_state[CONFIG_DATASET_ID]}. Resetting tables.")

def add_selected_table():
    """Adds the currently selected table to the list."""
    project = st.session_state[CONFIG_PROJECT_ID]
    dataset = st.session_state[CONFIG_DATASET_ID]
    table = st.session_state[CONFIG_CURRENTLY_SELECTED_TABLE] # From the single selectbox

    if project and dataset and table:
        table_info = {"project": project, "dataset": dataset, "table": table}
        # Avoid duplicates
        if table_info not in st.session_state[CONFIG_SELECTED_TABLES_INFO]:
            st.session_state[CONFIG_SELECTED_TABLES_INFO].append(table_info)
            st.session_state[CONFIG_CURRENT_EDIT_TABLE_IDX] = len(st.session_state[CONFIG_SELECTED_TABLES_INFO]) - 1
            st.session_state[CONFIG_FINAL_YAML] = None # Adding tables requires regeneration
            display_timed_message(f"Table '{table}' added! Click 'Generate/Update Agent Config' to process.")
            logger.info(f"Added table: {table_info}")
        else:
            st.warning(f"Table '{table}' is already selected.")
    else:
        st.warning("Please ensure a project, dataset, and table are selected.")

def remove_selected_tables_action():
    """Removes tables selected in the multiselect."""
    tables_to_remove_fqn = st.session_state[CONFIG_TABLES_TO_REMOVE] # Fully qualified names

    if not tables_to_remove_fqn:
        st.warning("No tables selected for removal.")
        return

    removed_count = 0
    current_tables = st.session_state[CONFIG_SELECTED_TABLES_INFO]
    new_selected_tables = []

    for table_info in current_tables:
        fqn = f"{table_info['project']}.{table_info['dataset']}.{table_info['table']}"
        if fqn not in tables_to_remove_fqn:
            new_selected_tables.append(table_info)
        else:
            removed_count += 1

    if removed_count > 0:
        st.session_state[CONFIG_SELECTED_TABLES_INFO] = new_selected_tables
        st.session_state[CONFIG_CURRENT_EDIT_TABLE_IDX] = max(0, len(new_selected_tables) - 1)
        st.session_state[CONFIG_TABLE_SCHEMAS] = { # Remove schemas of removed tables
            k: v for k, v in st.session_state[CONFIG_TABLE_SCHEMAS].items()
            if any(t['table'] == k for t in new_selected_tables)
        }
        st.session_state[CONFIG_FINAL_YAML] = None # Removing tables requires regeneration
        display_timed_message(f"Removed {removed_count} table(s). Click 'Generate/Update Agent Config' to process.")
        logger.info(f"Removed tables: {tables_to_remove_fqn}")
        # Clear the multiselect selection
        st.session_state[CONFIG_TABLES_TO_REMOVE] = []
    else:
         st.warning("Selected tables for removal not found in the current list.")


def generate_agent_config():
    """Fetches schemas, generates descriptions (if needed), builds YAML."""
    logger.info("Starting agent configuration generation...")
    selected_tables = st.session_state[CONFIG_SELECTED_TABLES_INFO]
    if not selected_tables:
        st.warning("Please add tables before generating the configuration.")
        return

    # --- 1. Fetch Schemas for all selected tables ---
    # Group tables by project/dataset to minimize API calls if needed (though get_schemas_cached handles one dataset)
    # For simplicity here, assuming all selected tables are from the *currently selected* project/dataset in the UI
    # A more robust solution would handle tables from multiple datasets if the UI allowed that.
    project = st.session_state[CONFIG_PROJECT_ID]
    dataset = st.session_state[CONFIG_DATASET_ID]
    table_names = tuple(t['table'] for t in selected_tables) # Use tuple for caching

    if not project or not dataset:
        st.error("Project or Dataset not selected correctly.")
        return

    with st.spinner("Fetching table schemas..."):
        schemas = get_schemas_cached(project, dataset, table_names)
        st.session_state[CONFIG_TABLE_SCHEMAS] = schemas # Store fetched schemas

    if not schemas:
        st.error("Failed to fetch schemas for selected tables. Cannot generate configuration.")
        return

    # --- 2. Generate Missing Descriptions (Optional - triggered here explicitly) ---
    # Consider adding a button to trigger this separately if it's slow
    # For now, included in the main generation flow.
    with st.spinner("Checking and generating missing descriptions (this may take a moment)..."):
        for table_name, table_data in st.session_state[CONFIG_TABLE_SCHEMAS].items():
            # Generate table description if missing
            if not table_data.get("description"):
                logger.info(f"Generating description for table: {table_name}")
                try:
                    # Add error handling and retry logic for sample data
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            sample_data = select_10_from_table(project, dataset, table_name, BQ_LOCATION)
                            if sample_data is not None and not sample_data.empty:
                                prompt = generate_description_prompt_for_table(
                                    table_name, 
                                    sample_data, 
                                    schema=table_data
                                )
                                desc = gemini_request(GEMINI_PROJECT_ID, GEMINI_REGION, prompt)
                                if desc:
                                    table_data["description"] = desc
                                    break
                            else:
                                logger.warning(f"Attempt {attempt + 1}: Empty sample data for {table_name}")
                        except Exception as e:
                            logger.error(f"Attempt {attempt + 1} failed for {table_name}: {e}")
                            if attempt == max_retries - 1:
                                raise
                            time.sleep(1)  # Wait before retry
                    
                    if not table_data.get("description"):
                        # Fallback: Generate description from schema only
                        schema_only_prompt = (
                            f"Generate a clear description for the BigQuery table '{table_name}' "
                            f"based on its schema: {table_data.get('schema', [])}. "
                            "Focus on the table's purpose and content based on column names and types."
                        )
                        desc = gemini_request(GEMINI_PROJECT_ID, GEMINI_REGION, schema_only_prompt)
                        table_data["description"] = desc or f"Table {table_name} - schema-based description"
                        
                except Exception as e:
                    logger.error(f"Failed to generate description for {table_name}: {e}")
                    table_data["description"] = f"Table {table_name} - contains {len(table_data.get('schema', []))} columns"

            # Improve column description generation
            for col_schema in table_data.get("schema", []):
                col_name = col_schema.get("name")
                if col_name and not col_schema.get("description"):
                    try:
                        # Try to get column sample data
                        col_vals = select_column_from_table(project, dataset, table_name, col_name)
                        
                        if col_vals and not col_vals.empty:
                            prompt = generate_description_prompt_for_column(
                                table_name, 
                                col_vals, 
                                col_name=col_name,
                                col_type=col_schema.get("type", "UNKNOWN")
                            )
                        else:
                            # Fallback: Generate from name and type only
                            prompt = (
                                f"Generate a clear description for the column '{col_name}' "
                                f"of type {col_schema.get('type', 'UNKNOWN')} in table '{table_name}'. "
                                "Infer its likely purpose and content from the name."
                            )
                        
                        desc = gemini_request(GEMINI_PROJECT_ID, GEMINI_REGION, prompt)
                        col_schema["description"] = desc or f"Column storing {col_name} data"
                        
                    except Exception as e:
                        logger.error(f"Error generating description for column {table_name}.{col_name}: {e}")
                        col_schema["description"] = f"Column storing {col_name} data"

    # --- 3. Build the YAML structure ---
    final_yaml_data = {
        "system_description": st.session_state[CONFIG_SYSTEM_INSTRUCTIONS],
        "tables": {}
    }

    for table_name, table_data in st.session_state[CONFIG_TABLE_SCHEMAS].items():
        if not isinstance(table_data, dict) or "schema" not in table_data:
            st.error(f"Invalid schema data for table: {table_name}. Skipping.")
            continue

        # Fetch golden queries (consider making this optional or async)
        with st.spinner(f"Fetching common queries for {table_name}..."):
             try:
                 golden_queries = get_most_common_queries(project, dataset, table_name, GEMINI_REGION, BQ_LOCATION)
             except Exception as e:
                 logger.warning(f"Could not fetch golden queries for {table_name}: {e}")
                 golden_queries = ["Error fetching golden queries."] # Provide fallback

        table_yaml_entry = {
            "description": table_data.get("description", f"Missing description for {table_name}"),
            "schema": [],
            "golden_queries": golden_queries,  # No trailing comma needed
            "measures": [],
            "golden_action_plans": [],
            "relationships": [],
            "glossaries": [],
            "additional_instructions": []
        }

        for col_schema in table_data.get("schema", []):
             if isinstance(col_schema, dict) and "name" in col_schema:
                 table_yaml_entry["schema"].append({
                     "name": col_schema["name"],
                     "description": col_schema.get("description", "").strip() # Ensure description exists
                 })
             else:
                 logger.warning(f"Skipping invalid column schema item in table {table_name}: {col_schema}")

        final_yaml_data["tables"][table_name] = table_yaml_entry

    # --- 4. Convert intermediate structure to YAML string ---
    intermediate_yaml_string = yaml.dump(final_yaml_data, sort_keys=False, allow_unicode=True)

    # --- 5. Refine YAML with Gemini (Optional but kept from original) ---
    with st.spinner("Refining configuration with AI..."):
        try:
            refine_prompt = yaml_prompt(intermediate_yaml_string)
            final_yaml_string = gemini_request(GEMINI_PROJECT_ID, GEMINI_REGION, refine_prompt)
            final_yaml_string = remove_yaml_prefix_and_suffix(final_yaml_string)
        except Exception as e:
            st.error(f"Error refining YAML with Gemini: {e}. Using unrefined version.")
            logger.error(f"Gemini YAML refinement error: {e}")
            final_yaml_string = intermediate_yaml_string # Fallback

    st.session_state[CONFIG_FINAL_YAML] = final_yaml_string
    logger.info("Agent configuration generation complete.")
    display_timed_message("Agent configuration generated successfully!", type="success")


def update_final_agent_instructions():
    """Updates the main system instructions with the generated/edited YAML."""
    if st.session_state[CONFIG_FINAL_YAML]:
        # Update the system instructions with the YAML configuration
        st.session_state[CONFIG_SYSTEM_INSTRUCTIONS] = st.session_state[CONFIG_FINAL_YAML]
        # Also update any other state variables that might need the configuration
        if "chat_system_instructions" in st.session_state:
            st.session_state.chat_system_instructions = st.session_state[CONFIG_FINAL_YAML]
        if "agent_configuration" in st.session_state:
            st.session_state.agent_configuration = st.session_state[CONFIG_FINAL_YAML]
            
        display_timed_message("Agent instructions updated with generated configuration!", type="success")
        logger.info("Main agent instructions updated from generated YAML.")
        
        # Force a rerun to update UI components
        st.rerun()
    else:
        st.warning("No generated configuration found to update agent instructions.")


# --- UI Rendering Functions ---

def render_project_dataset_selectors():
    """Renders project and dataset selection widgets."""
    st.header("1. Select Data Source")
    project_options = list(set([DEFAULT_PROJECT, CURRENT_PROJECT])) # Ensure unique options
    try:
        current_project_index = project_options.index(st.session_state[CONFIG_PROJECT_ID])
    except ValueError:
        current_project_index = 0 # Default if current project not in options (e.g., manual edit)

    st.selectbox(
        "BigQuery Project",
        project_options,
        index=current_project_index,
        key="project_selector", # Key for the widget itself
        on_change=update_selected_project, # Callback updates main state key
        help="Select the Google Cloud project containing your BigQuery data.",
    )

    # Dataset Selector (only if project is selected)
    if st.session_state[CONFIG_PROJECT_ID]:
        available_datasets = st.session_state[CONFIG_AVAILABLE_DATASETS]
        # Prepend a placeholder if no dataset is selected yet
        dataset_options = ["-- Select Dataset --"] + available_datasets
        current_dataset = st.session_state[CONFIG_DATASET_ID]

        try:
            # Find index, accounting for the placeholder
            current_dataset_index = dataset_options.index(current_dataset) if current_dataset else 0
        except ValueError:
             current_dataset_index = 0 # Should not happen if state is consistent


        st.selectbox(
            "BigQuery Dataset",
            dataset_options,
            index=current_dataset_index,
            key="dataset_selector", # Key for the widget itself
            on_change=update_selected_dataset, # Callback updates main state key
            help="Select the BigQuery dataset.",
        )

def render_table_selection_management():
    """Renders table selection using checkboxes."""
    st.header("2. Select Tables")
    project = st.session_state[CONFIG_PROJECT_ID]
    dataset = st.session_state[CONFIG_DATASET_ID]

    if not project or not dataset:
        st.info("Please select a project and dataset first.")
        return

    available_tables = st.session_state[CONFIG_AVAILABLE_TABLES]
    if not available_tables:
        st.info(f"No tables found in {project}.{dataset} or fetching...")
        return

    st.subheader("Available Tables")
    st.info("Select tables to include in your configuration:")

    # Create columns for better layout
    cols = st.columns([3, 1])
    
    with cols[0]:
        # Convert currently selected tables to a set of table names for easy lookup
        currently_selected = {t['table'] for t in st.session_state[CONFIG_SELECTED_TABLES_INFO]}
        
        # Create checkboxes for each available table
        for table in available_tables:
            is_checked = st.checkbox(
                table,
                value=table in currently_selected,
                key=f"checkbox_{table}",
                help=f"Include {table} in the agent configuration"
            )
            
            # Handle checkbox state changes
            if is_checked and table not in currently_selected:
                # Add newly checked table
                table_info = {"project": project, "dataset": dataset, "table": table}
                st.session_state[CONFIG_SELECTED_TABLES_INFO].append(table_info)
                st.session_state[CONFIG_FINAL_YAML] = None  # Require regeneration
            elif not is_checked and table in currently_selected:
                # Remove unchecked table
                st.session_state[CONFIG_SELECTED_TABLES_INFO] = [
                    t for t in st.session_state[CONFIG_SELECTED_TABLES_INFO]
                    if t['table'] != table
                ]
                st.session_state[CONFIG_FINAL_YAML] = None  # Require regeneration

    with cols[1]:
        if st.session_state[CONFIG_SELECTED_TABLES_INFO]:
            st.info("Selected Tables:")
            for table_info in st.session_state[CONFIG_SELECTED_TABLES_INFO]:
                st.markdown(f"- `{table_info['table']}`")
        else:
            st.warning("No tables selected")

    # Add a clear selection button
    if st.session_state[CONFIG_SELECTED_TABLES_INFO]:
        if st.button("Clear All Selections", type="secondary"):
            st.session_state[CONFIG_SELECTED_TABLES_INFO] = []
            st.session_state[CONFIG_FINAL_YAML] = None
            st.rerun()  # Refresh to update checkbox states

def render_agent_instructions_input():
    """Renders the text area for base system instructions."""
    st.header("3. Define Data Agent Instructions")
    st.text_area(
        label="System Instructions",
        key=CONFIG_SYSTEM_INSTRUCTIONS, # Directly bind to session state
        height=150,
        help="Provide general instructions for how the AI agent should behave and interact."
    )

def render_generation_button():
    """Renders the button to trigger the schema fetching and YAML generation."""
    st.header("4. Generate Agent Configuration")
    st.button(
        "Generate / Update Agent Config (Fetches Schemas & Descriptions)",
        on_click=generate_agent_config,
        type="primary",
        use_container_width=True,
        help="Click here after selecting tables and defining instructions. This will fetch schemas, auto-generate missing descriptions, and create the detailed YAML configuration below."
    )

def render_final_yaml_display_and_update():
    """Displays the generated YAML and allows updating the agent."""
    if not st.session_state.get(CONFIG_FINAL_YAML):
        st.info("Click the 'Generate / Update Agent Config' button above to create the configuration.")
        return

    st.header("5. Review and Finalize Configuration")

    st.markdown("""
    **Review the generated YAML configuration below.**

    *   Descriptions for tables and columns may have been auto-generated. **Please verify their accuracy.**
    *   Gemini attempts to refine the structure and add common queries. Review these additions.
    *   **Recommended:** Manually enhance the YAML by adding relevant `measures`, `golden_action_plans`, `relationships`, `glossaries`, or `additional_instructions` for optimal agent performance.
    *   You can edit the YAML directly in the text area below.
    """)

    # Display the YAML in a text area for editing
    st.text_area(
        label="Agent Configuration (YAML)",
        key=CONFIG_FINAL_YAML, # Bind directly for editing
        height=600,
        help="Review and edit the generated YAML. Click 'Update Agent with this Configuration' when satisfied."
    )

    st.button(
        "Update Agent with this Configuration",
        on_click=update_final_agent_instructions,
        use_container_width=True,
        help="Saves the YAML above as the active instructions for the chat agent."
    )


# --- Main Page Function ---
def configuration_page():
    """Renders the main configuration page."""
    st.title("🤖 Data Agent Configuration")

    st.markdown("""
    Configure your Data Agent by connecting it to your BigQuery data and defining its behavior.
    Follow the steps below:
    1.  **Select Data Source:** Choose the BigQuery project and dataset.
    2.  **Select Tables:** Add the specific tables the agent should query.
    3.  **Define Base Instructions:** Provide general guidelines for the agent.
    4.  **Generate Configuration:** Fetch table details and create the technical YAML config.
    5.  **Review and Finalize:** Inspect the generated YAML, edit if needed, and update the agent.
    """)
    st.sidebar.divider()

    # Initialize state on first run
    initialize_session_state()

    render_project_dataset_selectors()
    st.divider()
    render_table_selection_management()
    st.divider()
    render_agent_instructions_input()
    st.divider()
    render_generation_button()
    st.divider()
    render_final_yaml_display_and_update()

    # --- Sidebar Actions ---
    st.sidebar.title("Agent Actions")
    # Optional: Button to clear everything and start over
    if st.sidebar.button("Reset Configuration"):
        # Clear relevant config state keys
        keys_to_clear = [
            CONFIG_PROJECT_ID, CONFIG_DATASET_ID, CONFIG_AVAILABLE_DATASETS,
            CONFIG_AVAILABLE_TABLES, CONFIG_SELECTED_TABLES_INFO, CONFIG_TABLE_SCHEMAS,
            CONFIG_SYSTEM_INSTRUCTIONS, CONFIG_FINAL_YAML, CONFIG_CURRENT_EDIT_TABLE_IDX,
            CONFIG_TABLES_TO_REMOVE, CONFIG_CURRENTLY_SELECTED_TABLE, CONFIG_CHECKED_TABLES
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        # Re-initialize to defaults
        initialize_session_state()
        st.rerun()

    # Logout Button (as in original)
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

# --- Entry Point Check ---
if "token" not in st.session_state: # Basic auth check example
    st.switch_page("app.py") # Redirect to login/main app page
else:
    configuration_page()