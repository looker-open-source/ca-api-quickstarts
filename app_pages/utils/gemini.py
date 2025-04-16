import vertexai
from vertexai.generative_models import (GenerativeModel,
                                        GenerationConfig)
import os
import time
import logging

selected_model = os.getenv("MODEL")
temperature = os.getenv("TEMPERATURE")
top_p = os.getenv("TOP_P")


logging.basicConfig(level=logging.INFO)


def gemini_request(project: str, location: str, prompt: str, max_retries: int = 3, delay: int = 2) -> str:
    """
    Makes a request to the Gemini API with manual retry logic and exponential backoff using the time library.

    Args:
        project: The Google Cloud project ID.
        location: The location (e.g., "us-central1").
        prompt: The text prompt to send to the Gemini model.
        max_retries: Maximum number of retries.
        delay: Initial delay in seconds for exponential backoff.
        temperature: The temperature of the model.
        top_p: The top_p of the model.

    Returns:
        The generated text from Gemini, or an error message string if an error occurred.
    """

    vertexai.init(project=project, location=location)
    config = GenerationConfig(temperature=0.2,
                              top_p=0.8)
    model = GenerativeModel(selected_model)

    retry_delay = delay
    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(prompt, generation_config=config)

            if response.candidates:
                return response.candidates[0].content.parts[0].text
            else:
                error_message = "Error: No candidates returned."
                logging.error(error_message)
                return "Error: The model did not generate any content. Please check your prompt and try again."

        except Exception as e:
            error_message = f"Gemini API Error (Attempt {attempt+1}/{max_retries+1}): {type(e).__name__} - {str(e)}"
            logging.exception(error_message)
            if attempt < max_retries:
                logging.info(f"Retrying in {retry_delay:.2f} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
                # Exponential backoff (multiply delay by 2 for each retry)
            else:
                return f"Error: Failed to get response after {max_retries + 1} attempts. Details: {error_message}"

    return "Error: Should not reach here, retry loop should handle errors."
    # Fallback error in case logic error.


def generate_description_prompt_for_column(key: str, sample_data: list, schema: str) -> str:
    text = """You are an expert database analyst.
    You are skilled at understanding database schemas and data to provide
    concise and accurate descriptions of individual columns.

    Your task is to generate a 1-2 sentence description of a database
    column given the following information:

    1.  **Database Schema:** A detailed representation of the db structure,
    including table names, column names, data types, primary keys, foreign
    keys, and relationships between tables.  This will be provided in a clear,
    readable format (e.g., textual description, SQL DDL, or a similar representation).
    2.  **Column Name:** The exact name of the column you are describing.
    3.  **Sample Data:** A list of distinct values found in the column.
    The list may contain a mix of data types (strings, numbers, dates, etc.).
    If the list of data is very long,
    focus on identifying the most common patterns and data types.

    Your response should be a concise, informative description of the column,
    focusing on its purpose and the type of data it contains. Consider:

    *   What kind of information does this column likely hold?
    *   What is the likely meaning or purpose of the values in this column within the context of the database schema?
    *   Are there any obvious patterns or constraints in the sample data (e.g., dates, codes, categories)?

    **Output Requirements:**
    Please only use the active voice. Do not use the word appears.

    **Example One**
    **Column Name:** `RegistrationDate`

    **Sample Data:** `['2023-01-15', '2023-03-20', '2023-05-01', '2023-01-15', '2023-04-10']`

    **Response:**
    `The RegistrationDate column stores the date they registered their account.
    The values represent dates in the format YYYY-MM-DD.`

    **Example Two**
    **Column Name:** `sex`

    **Sample Data:** `[FEMALE,FEMALE,MALE,FEMALE,FEMALE,MALE, FEMALE]`

    **Response:**
    `Stores the biological sex of a penguin, recorded as either "MALE" or "FEMALE".`

    **Example Three**
    **Column Name:** `address`

    **Sample Data:** `[1000 Brazos,1308 W. 6th St.,800 Guadalupe St.,2322 Red River Street,64 Rainey St,1789 Brazos St.425 W 4th Street]`

    **Response:**
    ` Contains the full street address as a single string.`


    **Instructions:**

    Now, analyze the following Database Schema, Column Name, and Sample Data
    and generate a description according to the guidelines above.
    Only provide the description.
    Do not include any introductory or conversational phrases."""

    final_prompt = text + "\nColumn Name:" + str(key) + "\nSample Data:" + str(sample_data)

    return final_prompt


def generate_description_prompt_for_table(key: str, sample_data: list, schema: str) -> str:

    text = """You are an AI assistant designed to provide concise, qualitative descriptions of database tables.  Your input consists of two parts: a database schema and a JSON representation of the top 10 rows from that table.

    Your task is to analyze the schema and the example data to generate a one or two-sentence description of the table's **purpose and general contents**, focusing on the *type* of information it is designed to hold.  **Do not describe the *specific data* contained within the example rows.** Instead, describe the table's intended function or the kind of entities or relationships it is meant to represent.

    **Focus on the qualitative aspects:**

    *   What kind of entities does this table describe (e.g., customers, products, orders, events)?
    *   What kind of relationships or transactions are likely stored (e.g., order placements, product reviews, user logins)?
    *   What is the general purpose of the table in a database (e.g., storing user profiles, tracking inventory, logging activity)?

    **Output Requirements:**

    *   Your output should be a single paragraph containing one to two sentences.
    *   The description should be clear, concise, and avoid jargon.
    *   Do not mention specific values from the example rows.
    *   Focus on the *qualitative* nature of the data the table *intends* to hold, not the *specific* data in the example rows.

    **Input Format:**

    The input will be provided in the following format:
    Use code with caution.
    Text
    SCHEMA:
    <Database Schema Definition (e.g., CREATE TABLE statement)>

    DATA:
    <JSON representation of the top 10 rows>

    **Example:**
    Use code with caution.
    SCHEMA:
    CREATE TABLE products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(255),
    description TEXT,
    price DECIMAL(10, 2),
    category_id INT,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
    );

    DATA:
    [
    {"product_id": 1, "product_name": "Laptop", "description": "High-performance laptop", "price": 1200.00, "category_id": 1},
    {"product_id": 2, "product_name": "Mouse", "description": "Wireless mouse", "price": 25.00, "category_id": 2},
    {"product_id": 3, "product_name": "Keyboard", "description": "Mechanical keyboard", "price": 75.00, "category_id": 2},
    {"product_id": 4, "product_name": "Monitor", "description": "27-inch monitor", "price": 300.00, "category_id": 1},
    {"product_id": 5, "product_name": "Printer", "description": "Laser printer", "price": 200.00, "category_id": 3},
    {"product_id": 6, "product_name": "Tablet", "description": "10-inch tablet", "price": 350.00, "category_id": 1},
    {"product_id": 7, "product_name": "Webcam", "description": "HD webcam", "price": 50.00, "category_id": 2},
    {"product_id": 8, "product_name": "Speakers", "description": "Bluetooth speakers", "price": 100.00, "category_id": 2},
    {"product_id": 9, "product_name": "Projector", "description": "Portable projector", "price": 400.00, "category_id": 1},
    {"product_id": 10, "product_name": "Scanner", "description": "Document scanner", "price": 150.00, "category_id": 3}
    ]

    **Expected Output:**
    Use code with caution.
    This table stores information about products, including their names, descriptions, prices, and category assignments. It serves as a catalog of available items.

    Now go, and provide the best answer you can to the user.\n"""

    final_prompt = text + "\nTABLE: [" + str(key) + "]\nSCHEMA: [" + str(schema) + "]\nDATA: [" + str(sample_data) + "]\n"

    return final_prompt


def yaml_prompt(yaml_string: str) -> str:
    prompt = """You are an expert data model transformer and prompt engineer. Your task is to take a YAML file describing database tables as input and transform it into a more comprehensive and structured YAML format suitable for use by an intelligent agent interacting with data. You will also extract natural language queries and SQL queries and place them appropriately in the output YAML.

        Crucially, you must use the examples provided below as a structural guide for the output YAML format, but you MUST NOT copy any specific values (synonyms, tags, sample values, aggregations, descriptions etc.) from the example outputs. Generate new values based on the input YAML and your own understanding of data modeling best practices. For every field you generate (synonyms, tags, sample_values, aggregations, glossaries, natural_language_query, sql_query), you must ensure it is directly relevant and logically connected to the field's description and the table's overall purpose. You should perform a step-by-step reasoning process for each field to ensure relevance, although this reasoning should not be included in the final output YAML file.

        Input: You will receive a YAML file as input called input_data. This YAML will contain a system_description field (which you MUST preserve in the output), and a tables field. Under tables, there will be table names as keys, each containing a description and a schema. The schema is a list of fields with name and description.  The input YAML may also contain `natural_language_query` and `sql_query` fields *outside* the schema, associated with the entire table.

        Output: You must output a new YAML file with the following structure. You should populate this structure by extracting information from the input YAML and intelligently filling in missing fields as described below.  **Crucially, you must not alter any of the original values from the input YAML when copying them to the new format, especially the `system_description`, table names, field names, and descriptions.** Focus on enriching the data with synonyms, tags, sample values, etc., and now also glossaries and golden queries.

        Output YAML Structure and Instructions for each field:

        system_description:

        Instruction: **CRITICAL: Directly copy the `system_description` value from the input YAML to the output YAML without any modification.**  Do not attempt to infer or change it, even if it seems generic. Your primary task is to preserve this value exactly as it is provided in the input.

        tables: This will be a list of table objects. For each table in the input YAML's tables section, create a corresponding table object in the output tables list.

        table (within tables list):

        name:

        Instruction: Use the table name from the input YAML directly. For example, if the input table is named users, the output name should also be users.

        description:

        Instruction: Use the description from the input YAML for the table. If the input description is brief, expand upon it to be more informative about the table's purpose and contents. If no description exists in the input, generate one based on the table name and field names. Please be sure to trim any white or blank space from these strings before adding them to the output file.

        synonyms:

        Instruction: Generate and provide a list of alternative names or terms that users might use to refer to this table. Include common abbreviations, informal names, or conceptually related terms. Aim for at least 2-3 relevant synonyms. Examples: customers for users, products for items. Do not take example synonyms from the provided examples. Generate new synonyms based on the input table description and your understanding.

        tags:

        Instruction: Categorize the table with relevant keywords or tags. These should be short, descriptive, and aid in organizing tables. Think about the domain, type of data, or purpose. Examples: user data, sales, product catalog, financial. Do not take example tags from the provided examples. Generate new tags based on the input table description and your understanding.

        fields: This will be a list of field objects. For each field in the input YAML's schema for a table, create a corresponding field object in the output fields list.

        field (within fields list):

        name:

        Instruction: Use the name of the field directly from the input YAML.

        description:

        Instruction: Use the description from the input YAML for the field. Enhance the description to be more detailed and informative about the column's meaning, data type (if inferable), and role within the table. Elaborate if the input description is too short or vague.

        synonyms:

        Instruction: Generate and provide alternative names or phrases users might use to refer to this column in natural language queries. Consider different wording or common abbreviations. Aim for at least 2-3 synonyms. Examples: user ID for id, customer name for first_name, email address for email. Do not take example synonyms from the provided examples. Generate new synonyms based on the input field description and your understanding.

        tags:

        Instruction: Categorize the field with keywords relevant to its data type, content, or purpose. Examples: identifier, personal information, location, date, numeric value, categorical. Do not take example tags from the provided examples. Generate new tags based on the input field description and your understanding.

        sample_values:

        Instruction: Generate a list of realistic example values that could be found in this column. These should illustrate the data type and format. Provide at least 2-3 diverse sample values, or more if the data type is varied. If you can infer the data type (e.g., from description keywords like "integer", "string", "email"), use that to guide sample value generation. Do not take example sample values from the provided examples. Generate new sample values based on the input field description and your understanding of typical data for this field type.

        aggregations:

        Instruction: List common aggregation functions (e.g., sum, avg, count, min, max, distinct count) that are applicable to this column. Base your choices on the data type and purpose of the column. For numerical columns, sum, avg, min, max are often relevant. For categorical or identifier columns, count, distinct count are frequently useful. If no aggregations are obviously applicable, output an empty list [], but consider if count or distinct count could still be useful. Do not take example aggregations from the provided examples. Determine appropriate aggregations based on the input field description and your understanding of common aggregation functions.

        measures:

        Instruction: For this input transformation task, always output an empty list [] for measures. Measures are not present in the input and are not to be generated in this step.

        golden_queries:

        Instruction: Extract `natural_language_query` and `sql_query` from the input YAML, if present, and create a `golden_query` object for each.  If these fields are not present in the input, output an empty list [].  Associate each `golden_query` with the correct table.

        golden_action_plans:

        Instruction: For this input transformation task, always output an empty list [] for golden_action_plans. Golden action plans are not present in the input and are not to be generated in this step.

        relationships:

        Instruction: For this input transformation task, always output an empty list [] for relationships. Relationships are not present in the input and are not to be generated in this step.

        glossaries:

        Instruction: Generate a list of glossary terms relevant to the input data. Identify key terms from the table and field names and descriptions. For each term, provide a concise definition based on the context of the data.  Focus on terms that are important for understanding the data model and its purpose. Aim for at least 2-3 glossary terms.

        additional_instructions:

        Instruction: For this input transformation task, always output an empty list [] for additional_instructions. Additional instructions are not present in the input and are not to be generated in this step.

        Reasoning Requirement (Internal Process - Do Not Output in YAML):

        For each field (synonyms, tags, sample_values, aggregations, glossaries) in the output YAML, you must internally perform a step-by-step reasoning process to ensure the generated values are relevant and consistent with the descriptions. This reasoning process should NOT be included in the output YAML itself. It is for your internal validation before outputting the YAML.

        For example, when generating synonyms for a field named first_name with the description "The users column stores a user's name...", your internal reasoning might look like this:

        Analyze the field name and description: The field is first_name and it's part of user data, storing a user's name. "First name" is the core concept.

        Consider alternative phrasing: People might refer to "first name" as "given name", "name first", or simply "name" in a context where first name is implied.

        Think of abbreviations or common variations: "fname" is a common abbreviation for "first name" in technical contexts.

        Filter for relevance: All of these ("given name", "name first", "fname") are indeed relevant synonyms for "first name" in the context of user data.

        Generate synonyms: Output synonyms: ['given name', 'name first', 'fname'] (or similar).

        Similarly, for tags, sample_values, aggregations, and glossaries, you need to go through a similar reasoning process to ensure that the generated values are meaningful, relevant, and aligned with the input descriptions. After generating the complete output YAML, you must perform a final check to ensure every generated field relates to the input description before finalizing the output.  Also, ensure the extracted `natural_language_query` and `sql_query` are correctly placed.


    **Example 1 Output YAML (Illustrative - Do not copy values directly, generate your own):**

    system_instructions: This is a dope demo
    tables:
        users:
        description: 'This table stores information about users, including their personal
            details such as name, age, location, and contact information. It likely serves
            as a directory of user profiles within the application.

            '
        schema:
        - name: id
            description: 'The users column likely serves as a unique identifier for users
            in the database. It stores integer values.

            '
        - name: first_name
            description: 'The users column stores a user''s name. The values represent names
            as strings.

            '
        - name: last_name
            description: 'This column stores the last name of a user.

            '
        - name: gender
            description: 'The users column stores the gender of a user. The values are strings
            representing the user''s gender.
        - name: email
            description: 'The users column stores the email address of a user. It uniquely
            identifies each user in the system.
            '
            natural_language_query: '```sql

            SELECT * FROM `zinc-forge-302418.ecomm_copy.users` LIMIT 10

            ```


            This SQL query selects all columns (`*`) from the table named `users` within
            the dataset `ecomm_copy` in the Google Cloud project `zinc-forge-302418`. The
            `LIMIT 10` clause restricts the result set to the first 10 rows.


            In simpler terms, it retrieves the first 10 rows of user data from your
            specified BigQuery table.

            natural_language_query: '```sql


            Example Output YAML:
            system_instructions: This is a dope demo
        tables:
        - table:
            - name: users
            - description: This table stores information about users, including their personal
            details such as name, age, location, and contact information. It likely serves
            as a directory of user profiles within the application.
            - synonyms: customers
            - tags: 'user, customer, buyer'
            - fields:
                - field:
                    - name: id
                    - description: The users column likely serves as a unique identifier for users
                in the database. It stores integer values
                - field:
                    - name: first_name
                    - description: The users column stores a user''s name. The values represent names
                as strings
                    - tag: person
                    - sample_values: 'graham, sara, brian'
                - field:
                    - name: last_name
                    - description: This column stores the last name of a user
                    - tag: person
                    - sample_values: 'warmer, stilles, smith'
                - field:
                    - name: gender
                    - description: gender of the user
                    - sample_values:
                        - male
                        - female
                - field:
                    - name: email
                    - description: The users column stores the email address of a user. It uniquely
                identifies each user in the system
                    - tag: contact
                    - sample_values: 'brian@gmail.com, graham@gmail.com'
            - golden_queries:
                - golden_query:
                    natural_language_query: This SQL query selects the `zip` column from the `zinc-forge-302418.ecomm_copy.users` table and limits the result set to the first 10 rows. It will return a list of 10 zip codes (or fewer if the table has less than 10 rows).
                    sql_query: "SELECT zip FROM `zinc-forge-302418.ecomm_copy.users` LIMIT 10"
                - golden_query:
                    natural_language_query: This SQL query selects all columns (`*`) from the table named `users` within the dataset `ecomm_copy` in the Google Cloud project `zinc-forge-302418`. The `LIMIT 10` clause restricts the result set to the first 10 rows.
                    In simpler terms, it retrieves the first 10 user records from your e-commerce database.
                    sql_query: "SELECT * FROM `zinc-forge-302418.ecomm_copy.users` LIMIT 10"
            - golden_action_plans: []
        - relationships: []
        - glossaries:
            - glossary:
                - term: users
                - definition: Individuals who use the system or application, often with personal details stored.
            - glossary:
                - term: email
                - definition: A unique electronic address used for communication and user identification within the system.
        - additionl_instructions: []

        **Example 2 Input YAML:**
        system_instructions: answer questions
        tables:
        penguins:
        description: 'This table contains data about penguins, including their species,
        the island they inhabit, and various physical measurements such as culmen length
        and depth, flipper length, and body mass. It also records the sex of each penguin.

        '
        schema:
        - name: species
        description: 'The penguins column stores the species and scientific name of
        a penguin. It records the penguin type as a string.

        '
        - name: island
        description: 'The Island the penguins are from. '
        - name: culmen_length_mm
        description: 'The penguins column records bill depth measurements in millimeters.
        It contains numeric data, with some missing values represented as NaN.

        '
        - name: culmen_depth_mm
        description: 'The penguins column records flipper lengths in millimeters.

        '
        - name: flipper_length_mm
        description: 'The length of the flipper for each penguin in millimeters. '
        - name: body_mass_g
        description: 'The body mass index of the penguin. '
        - name: sex
        description: 'either m or f '

        natural_language_query: '```sql

        SELECT * FROM `zinc-forge-302418.birds.penguins` LIMIT 10

        ```


        This SQL query selects all columns (`*`) from the table `penguins` within
        the dataset `birds` in the Google Cloud project `zinc-forge-302418`, and
        limits the result set to the first 10 rows. This is a common way to preview
        the data in a table.

        '
        sql_query: SELECT * FROM `zinc-forge-302418.birds.penguins` LIMIT 10

        ** Example 2 Output YAML (Illustrative - Do not copy values directly, generate your own):**
        system_description: answer questions
        tables:
    - table:
        name: penguins
        description: 'This table contains data about penguins, including their species,
            the island they inhabit, and various physical measurements such as culmen length
            and depth, flipper length, and body mass. It also records the sex of each penguin.
            '
        synonyms:
            - penguin_data
            - penguin_info
            - birds
        tags:
            - biology
            - animals
            - wildlife
            - penguins
            - species
        fields:
            - field:
                name: species
                description: 'The penguins column stores the species and scientific name of
                a penguin. It records the penguin type as a string.

                '
                synonyms:
                - penguin species
                - species name
                - type of penguin
                tags:
                - categorical
                - species identification
                - penguin type
                sample_values:
                - Adelie Penguin (Pygoscelis adeliae)
                - Gentoo penguin (Pygoscelis papua)
                - Chinstrap penguin (Pygoscelis antarctica)
                aggregations:
                - count
                - distinct count
            - field:
                name: island
                description: 'The Island the penguins are from. '
                synonyms:
                - penguin island
                - island name
                - location
                tags:
                - categorical
                - location
                - island name
                sample_values:
                - Torgersen
                - Biscoe
                - Dream
                aggregations:
                - count
                - distinct count
            - field:
                name: culmen_length_mm
                description: 'The penguins column records bill depth measurements in millimeters.
                It contains numeric data, with some missing values represented as NaN.

                '
                synonyms:
                - culmen length
                - bill length
                - penguin culmen length
                - culmen in mm
                tags:
                - numeric
                - measurement
                - length
                sample_values:
                - '40'
                - '45.5'
                - '38.2'
                aggregations:
                - sum
                - avg
                - min
                - max
                - count
            - field:
                name: culmen_depth_mm
                description: 'The penguins column records flipper lengths in millimeters.
                '
                synonyms:
                - culmen depth
                - bill depth
                - penguin culmen depth
                - culmen depth in mm
                tags:
                - numeric
                - measurement
                - depth
                sample_values:
                - '17'
                - '18.3'
                - '19.5'
                aggregations:
                - sum
                - avg
                - min
                - max
                - count
            - field:
                name: flipper_length_mm
                description: 'The length of the flipper for each penguin in millimeters. '
                synonyms:
                - flipper length
                - penguin flipper length
                - flipper size
                - flipper length in mm
                tags:
                - numeric
                - measurement
                - length
                sample_values:
                - '190'
                - '205'
                - '215'
                aggregations:
                - sum
                - avg
                - min
                - max
                - count
            - field:
                name: body_mass_g
                description: 'The body mass index of the penguin. '
                synonyms:
                - body mass
                - penguin weight
                - mass
                - body mass in grams
                tags:
                - numeric
                - measurement
                - weight
                sample_values:
                - '3500'
                - '4200'
                - '5000'
                aggregations:
                - sum
                - avg
                - min
                - max
                - count
            - field:
                name: sex
                description: 'either m or f '
                synonyms:
                - penguin sex
                - gender
                tags:
                - categorical
                - gender
                sample_values:
                - M
                - F
                - male
                - female
                aggregations:
                - count
                - distinct count
        measures: []
        golden_queries:
        - golden_query:
            natural_language_query: This SQL query selects the species column from the zinc-forge-302418.birds.penguins table and returns the first 10 rows. It's a good way to get a quick preview of the different species present in the dataset.
            sql_query: "SELECT species FROM `zinc-forge-302418.birds.penguins` LIMIT 10"]
        - golden_query:
            natural_language_query: This SQL query selects all columns (*) from the table penguins within the dataset birds in the Google Cloud project zinc-forge-302418, and limits the result set to the first 10 rows. This is a common way to preview the data in a table.
            sql_query: "SELECT * FROM `zinc-forge-302418.birds.penguins` LIMIT 10"
                golden_action_plans: []
        relationships: []
        glossaries:
          - glossary:
              - term: penguins
              - definition: A group of aquatic, flightless birds living primarily in the Southern Hemisphere.
          - glossary:
              - term: culmen_length_mm
              - definition:  The length of a penguin's bill, measured in millimeters.
          - glossary:
              - term: body_mass_g
              - definition: The weight of a penguin, measured in grams.
        additional_instructions: []

        *** Key Reminders:
        *Do not change any original names, descriptions, sql_query, or natural_language_query from the input YAML when transferring them to the output.
        *Focus on filling in the missing fields (synonyms, tags, sample_values, aggregations, glossaries etc.) with relevant and helpful information based on your understanding of the data and the descriptions provided.
        *Extract and correctly place natural_language_query and sql_query into golden_query objects under the correct table.
        *Output valid YAML.
        """

    result = prompt + "\n input_data:\n " + yaml_string
    return result
