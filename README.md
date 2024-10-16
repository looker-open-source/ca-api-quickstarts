# Readme

This repository contains notebooks, code samples, sample apps and other resource that demonstrate how to use, develop and manage the Cortado DataQnA API on Google Cloud.

# Overview

Cortado is an automated analyst as a service that can answer data analytics questions by using GenAI building blocks. It enables custom experiences to be built on top, such as a multi-turn conversational assistant for business users, in 1P, 2P, or 3P surfaces.

Cortado utilizes context about the user and datasets as well as several GenAI tools to plan and orchestrate a response to the user’s question. Data source selection and context (columns to not use, fields to join, business jargon) used to improve answer accuracy are bundled as “Data Gems”, created in BigQuery or Looker Studio, and consumed by Cortado.

Cortado provides a stream of updates from itself and the underlying tools as it progresses through solving the question. The Cortado API gives developers freedom to expose as much information as they’d like to end users.

Currently, Cortado only supports BigQuery datasources - Looker Datasource will follow.

### Contribute

See the [Contributing Guide](./CONTRIBUTING.md).

## Repository structure

```bash
├── apps - Apps sample demonstrating the use of Cortado
│   ├── ...
├── notebooks - Notebooks demonstrating use of each Vertex AI service
│   ├── ...
├── code - Sample code and tutorials
│   ├── ...
```

## Examples

| Category |          Product          |                            Description                            |
| :------: | :-----------------------: | :---------------------------------------------------------------: |
|   Apps   | [Gradio/](./apps/gradio/) | Lightweight locally deployable chat interface to try out Cortado. |

## Disclaimer

This is not an officially supported Google product. The code in this repository is for demonstrative purposes only.
