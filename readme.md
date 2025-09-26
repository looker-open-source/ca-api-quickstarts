# Conversational Analytics API Quickstart App

## Status and Support

This repo is maintained, but not warrantied by Google. Issues and feature requests can be reported via https://github.com/looker-open-source/ca-api-quickstarts/issues.

## Overview

The Conversational Analytics API provides a natural language interface to query BigQuery and Looker data programmatically. The API enables data access through multiple integration points including embedded Looker dashboards, chat applications, and custom web applications. The API helps organizations streamline ad-hoc data requests and provides self-service analytics capabilities.

This repository serves as a quick start app to integrate with the Conversational Analytics API. You can either deploy this example implementation as-is for testing purposes or adapt it to your specific production requirements. The application currently can only be deployed locally for development and testing.  Check out the [API documentation](https://cloud.google.com/gemini/docs/conversational-analytics-api/overview) for additional enablement, setup, and use.

Try out this app to: 
- Create, update, list, and delete data agents managed/used by the Conversational Analytics API
- Configure BQ as a data source for the data agents
- Configure Looker as a data sourc for the data agents to benefit from Looker's semantic modeling improved context and accuracy in conversations
- Hold multi-turn conversations with the data agents
- View past conversations with the data agents
- Learn more about the extensible API architecture for your own custom application development

**Note:** This is a pre-GA product intended for test environments only. It should not be used in production environments or to process personal data or other data subject to legal or regulatory compliance requirements. 
This repository is subject to the Pre-GA Offerings Terms of the Service Specific Terms and the Consent Addendum for Gemini for Google Cloud Trusted Tester Program

## Getting Started (Local development)

The local deployment option is ideal for:
- Development and testing
- Customizing the application
- Individual developer use
- Demonstrating capabilities in a controlled environment

### 1. Setup environment

You must have the following prerequisites installed in your local environment:
- Python 3.11 or higher
- Git
- Google Cloud SDK (gcloud CLI)

### 2. Configure everything Google Cloud

1. Determine your Google Cloud billing project you will use for the quickstart app. Enable the required APIs on the Google Cloud billing project (charges may apply):

```bash
gcloud services enable geminidataanalytics.googleapis.com bigquery.googleapis.com cloudaicompanion.googleapis.com --project=YOUR_PROJECT_ID
```

2. Determine the user or service account the quickstart app will use to access cloud resources. Setup gcloud CLI application default credentials for the account. Check out these [steps](https://cloud.google.com/docs/authentication/set-up-adc-local-dev-environment#local-user-cred) for more context.
```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

3. Set the correct IAM roles on the user or service account from step 2 depending on the type of the data source the app will query:

    | Data source    | Roles |
    | -------- | ------- |
    | BigQuery  | `roles/bigquery.dataViewer` BigQuery Data Viewer <br >  `roles/bigquery.user` BigQuery User |
    | Looker | `roles/looker.instanceUser` Looker Instance User |

### 3. Setup local repository

Clone the repository and navigate to the project directory:

```bash
git clone https://github.com/looker-open-source/ca-api-quickstarts.git
cd ca-api-quickstarts
```

### 4. Configure secrets/environment

Create a `secrets.toml` file in the `.streamlit` directory:

```
[cloud]
project_id = "YOUR_PROJECT_ID"

# Uncomment next 3 lines if using Looker as data source
#[looker]
#client_id = "YOUR_LOOKER_CLIENT_ID"
#client_secret = "YOUR_LOOKER_CLIENT_SECRET"
```

If you will use Looker as a data source:

1. Determine the Looker account that will access Looker. 
2. Ensure the Looker account has the [access_data](https://cloud.google.com/looker/docs/admin-panel-users-roles#access_data) and [gemini_in_looker](https://cloud.google.com/looker/docs/admin-panel-users-roles#gemini_in_looker) permissions. 
3. Retrieve the [Looker account's client id and client secret](https://cloud.google.com/looker/docs/api-auth#authentication_with_an_sdk) and set it in the secrets.toml file.

*The quickstart app auths with a [Looker API key](https://cloud.google.com/gemini/docs/conversational-analytics-api/authentication#looker-api-keys). The app DOES NOT use a [Looker access token](https://cloud.google.com/gemini/docs/conversational-analytics-api/authentication#looker-access-token).*

### 5. Install dependencies

Install the app's dependencies:

```bash
pip install -r requirements.txt
```

### 6. Launch app

Start the app locally:

```bash
streamlit run app.py
```

Access the app at http://localhost:8501 in your web browser.

## App usage guide

### Create, update, view, and delete a data agent

1. Navigate to the "Agents" page
2. Scroll down to "Create Agent" form.
3. Enter the "display name", "description", and "system instructions". [Tips for writing system instructions](https://cloud.google.com/gemini/docs/conversational-analytics-api/data-agent-system-instructions)
4. If you want the agent to query Looker as a data source:
   - Select "Looker" as the data source
   - Enter the Looker instance url. e.g. "myinstance.looker.com"
   - Enter the Looker model name
   - Enter the Looker explore name
5. Or, if you want the agent to query BigQuery as a data source:
   - Select "BigQuery" as the DataSource
   - Enter the id of the project containing the BigQuery dataset. e.g. "bigquery-public-data"
   - Enter the name of the dataset. e.g. "san_francisco_trees"
   - Enter the name of the table. e.g. "street_trees"
6. Select "Create"
7. View the data agents you've created in the agents page. 
8. Select a data agent to expand it. 
9. You can change all fields except "Data Source". Select "Update agent" after you've made your changes to save your changes to the agent.
10. You can select "Delete agent" to delete the agent.

### Query your data

Once your agent is configured:
1. Navigate to the "Chat" page
2. The last created agent is automatically selected.
3. Ask a question in the chat prompt field. A conversation will automatically be started
3. View responses in text, table, and chart formats.
4. Ask follow-up questions to hold a multi-turn conversation that builds on previous context.

Example queries:
- "How many products are in each category?"
- "What were our top 5 customers by revenue last quarter?"
- "Show me a bar chart of monthly sales trends"
- "Compare performance across regions in a table"

### View and continue past conversations
1. Navigate to the "Chat" page.
2. Select the agent you'd like to see past conversations with in the dropdown in the top bar.
3. Select a past conversation from the dropdown.
4. Check out the past messages from the selected conversation.
5. You can continue the past conversation by asking another question in the chat prompt field.

## Tips

### Understanding Semantic Layers

A critical component of the Conversational Analytics API is its semantic layer implementation, which dramatically improves query accuracy and contextual understanding.

#### The Importance of Semantic Layers

Semantic layers act as a translation layer between raw data and business users, providing:

1. **Business Context**: Mapping technical fields to business terminology
2. **Relationship Modeling**: Pre-defining table joins and relationships
3. **Metric Definitions**: Establishing consistent calculations and aggregations
4. **Enhanced Accuracy**: Providing guardrails for query generation

Internal testing shows that Looker's semantic layer reduces data errors in GenAI natural language queries by two-thirds compared to ungoverned data warehouse tables. As use cases become more complex—involving multiple tables, joins, and complex calculations—semantic layers like Looker's excel by offloading reasoning complexity from the AI model.

#### Types of Semantic Layers

The application supports two types of semantic layers:

1. **YAML-Based Metadata Layer** (BigQuery)
   - Automatically generated with table/field descriptions, synonyms, and relationships
   - Can be manually edited to improve performance for specific use cases
   - Gives some benefits of a formal semantic model

2. **LookML Semantic Layer** (Looker)
   - Leverages existing LookML models with rich metadata
   - Includes pre-defined joins and consistent calculation definitions
   - Provides field-level permissions and governance controls
   - Offers superior accuracy for complex, multi-table queries

#### Choosing the Right Approach

- **For Existing Looker Users**: Leverage your existing LookML investment for highest accuracy
- **For BigQuery-Only Users**: Use the YAML generation capabilities with manual refinement
- **For Complex Use Cases**: Consider developing LookML models for critical data domains
