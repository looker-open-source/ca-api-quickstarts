# Conversational Analytics API Quickstart

**Note 1:** This repository is not officially maintained like a 1st-party GCP product.

**Note 2:** This app version the DataQnA API, we are working to support the [new geminidataanalytics API](https://cloud.google.com/gemini/docs/conversational-analytics-api/overview)

## Overview

The Conversational Analytics API provides a natural language interface to query BigQuery and Looker data programmatically. This API enables data access through multiple integration points including embedded Looker dashboards, chat applications, and custom web applications. The solution helps organizations streamline ad-hoc data requests and provides self-service analytics capabilities.

This repository serves as a **reference architecture** for integrating with the Conversational Analytics API. The [documentation](https://cloud.google.com/looker/docs/dataqna-home) is also helpful for enablement, setup, and use. It demonstrates a complete implementation pattern that you can either deploy as-is for testing purposes or adapt to your specific production requirements. The application can be deployed in two ways: locally for development and testing, or on Google Cloud Run for a more production-like environment.

The API facilitates the implementation of Conversational Analytics Agents that allow for natural language inputs against:
- Generative AI models with agentic functionality
- Looker's semantic modeling layer for query accuracy improvements
- An extensible API architecture for custom application development

**Note:** This is a pre-GA product intended for test environments only. It should not be used in production environments or to process personal data or other data subject to legal or regulatory compliance requirements. This requires access to our preview allowlist. You can fill out a form to [express interest here](https://docs.google.com/forms/d/e/1FAIpQLSfb-vFXVDrQDij-nsnh2MsykBEAQtrSinunQQGaqqkcyBbYtA/viewform).

## Demo Usage Videos
- Quick 90s Create and Query an Agent [Video Link](https://www.youtube.com/watch?v=VbAdWmhKmOE)
- 5 min Deploy app full featured [Video Link](#)
## Getting Started

### 1. Environment Setup

First, ensure you have the following prerequisites installed:
- Python 3.8 or higher
- Git
- Docker (for Cloud Run deployment)
- Terraform (for Cloud Run deployment)
- Google Cloud SDK (gcloud CLI)

### 2. API Enablement

Enable the required APIs in your Google Cloud project:

```bash
gcloud services enable dataqna.googleapis.com people.googleapis.com aiplatform.googleapis.com run.googleapis.com cloudbuild.googleapis.com --project=YOUR_PROJECT_ID
```

### 3. OAuth Configuration

1. Navigate to the Google Cloud Console and select your project
2. Go to "APIs & Services" > "Credentials"
3. Click "Create credentials" > "OAuth client ID"
4. Select "Web application" as the application type
5. Configure the application name
6. Set the "Application type" to "Web Application"
7. For local deployment, add http://localhost:8501 to both "Authorized JavaScript origins" and "Authorized redirect URIs"
8. For Cloud Run deployment, leave these fields for now (they'll be updated later)
9. Ensure the Audience is set to "External"
10. Click "Create" and note down the GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET

### 4. Repository Setup

Clone the repository and navigate to the project directory:

```bash
git clone https://github.com/looker-open-source/ca-api-quickstarts.git
cd ca-api-quickstarts
```

### 5. Configuration

Create a `.env` file in the project root with the following variables:

```
PROJECT_ID=your-project-id
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
LOOKER_CLIENT_ID=your-looker-client-id
LOOKER_CLIENT_SECRET=your-looker-client-secret
REDIRECT_URI=http://localhost:8501
```

### 6. Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### 7. Application Launch

Start the application locally:

```bash
streamlit run app.py
```

Access the application at http://localhost:8501 in your web browser.

## Using the Application

### Creating and Configuring Data Agents for BigQuery

1. **Login**: Click "Login with Google" and authorize the application
2. **Navigate to Agent Factory**: You'll be directed to the "Data Agent Configuration" page
3. **Select Data Source**:
   - Slect BigQuery as the DataSource
   - Choose your BigQuery Project from the dropdown
   - Select the relevant BigQuery Dataset
5. **Select Tables**: Check the boxes next to specific tables you want to query
6. **Define Instructions**: In the "System Instructions" text box, describe the agent's role and purpose (e.g., "You are an expert sales analyst. Help answer questions about our sales data and product performance.")
7. **Generate Configuration**: Click "Generate / Update Agent Config" and wait for the process to complete
8. **Review and Finalize**: Examine the automatically generated YAML configuration and edit if needed
9. **Update Agent**: Click "Update Agent with this Configuration"

   ### Creating and Configuring Data Agents for Looker

1. **Login**: Click "Login with Google" and authorize the application
2. **Navigate to Agent Factory**: You'll be directed to the "Data Agent Configuration" page
3. **Select Data Source**:
   - Select Looker as the DataSource
4. Enter in your Looker Host, Client ID, and Client Secret.
5. Click Validate Credentials.
6. **Select The Looker Model**: Check the boxes next to specific tables you want to query
7. **Define Instructions**: In the "System Instructions" text box, describe the agent's role and purpose (e.g., "You are an expert sales analyst. Help answer questions about our sales data and product performance.")
8. **Select the Looker Explore**
9. **Review and Finalize**: Make sure all your selection is accurate.
10. **Update Agent**: Navigate to the chat page and start chatting with your Looker Data Agent.

### Querying Your Data

Once your agent is configured:
1. Navigate to the "Chat" page
2. Type natural language questions about your data
3. View responses in text, table, and chart formats
4. Ask follow-up questions that build on previous context

Example queries:
- "How many products are in each category?"
- "What were our top 5 customers by revenue last quarter?"
- "Show me a bar chart of monthly sales trends"
- "Compare performance across regions in a table"

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

## Deployment Options

This reference architecture offers two deployment paths to accommodate different usage scenarios:

### Local Deployment

The local deployment option is ideal for:
- Development and testing
- Customizing the application
- Individual developer use
- Demonstrating capabilities in a controlled environment

The steps for local deployment are covered in the Getting Started section above.

### Google Cloud Run Deployment

The Cloud Run deployment option provides:
- A production-like environment
- Scalable infrastructure
- Secure OAuth implementation
- Shared access for team members

To deploy to Cloud Run:

1. Configure variables in the `deploy.sh` script:
   - PROJECT_ID: GCP project ID for deployment
   - REGION: GCP deployment region
   - DATASTORE_PROJECT_ID: GCP project ID where datasets are located
   - GOOGLE_CLIENT_ID: OAuth 2.0 Client ID
   - GOOGLE_CLIENT_SECRET: OAuth 2.0 Client secret
   - GEMINI_REGION: Location for Gemini calls
   - BQ_LOCATION: BigQuery dataset location
   - MODEL: Gemini model version
   - TEMPERATURE: Temperature parameter for Gemini
   - TOP_P: Top_p parameter for Gemini

2. Run the deployment script:
```bash
./deploy.sh
```
If needed: `chmod +x deploy.sh`

3. Configure OAuth 2.0 Redirect URI:
   - After deployment, add the outputted redirect URI to your OAuth 2.0 Client ID configuration
   - Add it to both "Authorized JavaScript origins" and "Authorized redirect URIs"
   - Save changes and allow a few minutes for permissions to propagate

## Technical Requirements

### API Access

- Data QnA API (allowlist required)
- Google People API
- Vertex AI API

### Required IAM Permissions

- BigQuery: Data Viewer, User
- Vertex AI: Vertex AI User

## Resource Cleanup

### Cloud Run Resource Deprovisioning

```bash
terraform destroy --auto-approve
```

### Artifact Registry Cleanup

```bash
gcloud artifacts repositories delete cortado-docker-repo --location="${REGION}" --project="${PROJECT_ID}"
```

### OAuth Configuration Cleanup

1. Navigate to "APIs & Services" > "Credentials"
2. Edit the OAuth 2.0 Client ID used for the application
3. Remove the redirect URIs associated with the deployed application
4. Save changes

## Product Roadmap and Caveats

### Development Roadmap

- Agent YAML generation built directly into the API
- Migration to a new API surface with enhanced capabilities
- Public Preview in Q2 2025

### Important Caveats

- This is a pre-GA product intended for test environments only
- Subject to the Pre-GA Offerings Terms of the Service Specific Terms and the Consent Addendum for Gemini for Google Cloud Trusted Tester Program
- The current API (dataqna.googleapis.com) is being migrated; documentation for migration will be provided
- Some capabilities in the quickstart will be integrated into the core API in future releases

## Support

If you need access to this repo for a colleague, please email data-qna-api-feedback@google.com

For more information, fill out the [interest form](https://docs.google.com/forms/d/e/1FAIpQLSfb-vFXVDrQDij-nsnh2MsykBEAQtrSinunQQGaqqkcyBbYtA/viewform) to stay updated on new API developments and transition documentation.
