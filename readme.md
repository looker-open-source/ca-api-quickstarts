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

First, ensure you have the following prerequisites installed:
- Python 3.11 or higher
- Git
- Google Cloud SDK (gcloud CLI)

### 2. Configure permissions

1. Enable the required APIs in your Google Cloud project (charges may apply):

```bash
gcloud services enable geminidataanalytics.googleapis.com bigquery.googleapis.com cloudaicompanion.googleapis.com people.googleapis.com aiplatform.googleapis.com --project=YOUR_PROJECT_ID
```

2. Any user that will use the app must have these IAM roles depending on the data 
source they will query in the app:

BigQuery: Data Viewer, User 
or
Looker: Instance User

### 3. Configure OAuth

#### Create consent screen
1. Navigate to the Google Cloud console and create an Oauth consent screen through the [consent screen wizard](https://console.cloud.google.com/auth/overview/create). If a consent screen already exists, adjust the following values accordingly through both the [branding](https://console.cloud.google.com/auth/branding) page and [audience](https://console.cloud.google.com/auth/audience) page.
2. Set “App name” to your choice.
3. Set “User support email” to your choice. 
4. Set "Audience" to your choice.
5. Set "Contact Information" to your choice.
6. Select "Create" to create your consent screen.

#### Create OAuth client

1. Go to "APIs & Services" > "Credentials"
2. Click "Create credentials" > "OAuth client ID"
3. Select "Web application" as the “Application type”
4. Configure the application name to your choice
5. Add “http://localhost:8501” to "Authorized JavaScript origins"
6. Add "http://localhost:8501  to "Authorized redirect URIs"
7. Click "Create" and note down the Client ID and Client Secret for the next step.

### 4. Setup local repository

Clone the repository and navigate to the project directory:

```bash
git clone https://github.com/looker-open-source/ca-api-quickstarts.git
cd ca-api-quickstarts
```

### 5. Configure environment

Create a `.env` file in the project root with the following variables:

```
PROJECT_ID=YOUR_PROJECT_ID
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID_FROM_PREVIOUS
GOOGLE_CLIENT_SECRET=YOUR_CLIENT_SECRET_FROM_PREVIOUS
REDIRECT_URI=http://localhost:8501

# Uncomment next 2 lines, if using Looker as data source
#LOOKER_CLIENT_ID=YOUR_LOOKER_CLIENT_ID
#LOOKER_CLIENT_SECRET=YOUR_LOOKER_CLIENT_SECRET
```

If Looker will be a data source, retrieve the Looker client id and Looker client secret that will be used to access Looker. Read this [Looker authentication documentation](https://cloud.google.com/looker/docs/api-auth) if you need guidance.


### 6. Install dependencies

Install the app's dependencies:

```bash
pip install -r requirements.txt
```

### 7. Launch app

Start the app locally:

```bash
streamlit run app.py
```

Access the app at http://localhost:8501 in your web browser.


### 8. Clean up

If needed, you can clean up your OAuth configuration.

1. In google cloud console, navigate to "APIs & Services" > "Credentials"
2. Edit the OAuth 2.0 Client ID used for the application
3. Remove the redirect URIs associated with the deployed application
4. Save changes

or 

Delete the OAuth client. 

## App usage guide

### Create, update, view, and delete a data agent

1. Select "Login with Google" and authorize the application
2. You will land on the "Agents" page
3. Scroll down to "Create Agent" form.
4. Enter the "display name", "description", and "system instructions". [Tips for writing system instructions](https://cloud.google.com/gemini/docs/conversational-analytics-api/data-agent-system-instructions)
5. If you want the agent to query Looker as a data source:
   - Select "Looker" as the data source
   - Enter the Looker instance url. e.g. "myinstance.looker.com"
   - Enter the Looker model name
   - Enter the Looker explore name
6. Or, if you want the agent to query BigQuery as a data source:
   - Select "BigQuery" as the DataSource
   - Enter the id of the project containing the BigQuery dataset. e.g. "bigquery-public-data"
   - Enter the name of the dataset. e.g. "san_francisco_trees"
   - Enter the name of the table. e.g. "street_trees"
7. Select "Create"
8. View the data agents you've created in the agents page. 
9. Select a data agent to expand it. 
10. You can change all fields except "Data Source". Select "Update agent" after you've made your changes to save your changes to the agent.
11. You can select "Delete agent" to delete the agent.

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
