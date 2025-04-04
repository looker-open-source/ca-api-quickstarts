# -*- coding: utf-8 -*-
# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import annotations

from typing import MutableMapping, MutableSequence

import proto  # type: ignore

from google.cloud.dataqna_v1alpha1.types import context as gcd_context
from google.cloud.dataqna_v1alpha1.types import datasource
from google.protobuf import struct_pb2  # type: ignore
from google.protobuf import timestamp_pb2  # type: ignore


__protobuf__ = proto.module(
    package='google.cloud.dataqna.v1alpha1',
    manifest={
        'AskQuestionRequest',
        'Message',
        'UserMessage',
        'SystemMessage',
        'TextMessage',
        'SchemaMessage',
        'SchemaQuery',
        'SchemaResult',
        'DataMessage',
        'LookerQuery',
        'DataQuery',
        'DataResult',
        'BigQueryJob',
        'AnalysisMessage',
        'AnalysisQuery',
        'AnalysisEvent',
        'ChartMessage',
        'ChartQuery',
        'ChartResult',
        'ErrorMessage',
        'Blob',
    },
)


class AskQuestionRequest(proto.Message):
    r"""Request for AskQuestion.

    Attributes:
        project (str):
            Required. The GCP project to be used for
            quota and billing.
        messages (MutableSequence[google.cloud.dataqna_v1alpha1.types.Message]):
            Required. Content of current conversation
        context (google.cloud.dataqna_v1alpha1.types.InlineContext):
            Optional. Context for the question
    """

    project: str = proto.Field(
        proto.STRING,
        number=1,
    )
    messages: MutableSequence['Message'] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message='Message',
    )
    context: gcd_context.InlineContext = proto.Field(
        proto.MESSAGE,
        number=3,
        message=gcd_context.InlineContext,
    )


class Message(proto.Message):
    r"""A message from an internaction between the user and the
    system.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        user_message (google.cloud.dataqna_v1alpha1.types.UserMessage):
            A message from the user that is interacting
            with the system.

            This field is a member of `oneof`_ ``kind``.
        system_message (google.cloud.dataqna_v1alpha1.types.SystemMessage):
            A message from the system in response to the
            user.

            This field is a member of `oneof`_ ``kind``.
        timestamp (google.protobuf.timestamp_pb2.Timestamp):
            Output only. For user messages, this is the
            time at which the system received the message.
            For system messages, this is the time at which
            the system generated the message.
    """

    user_message: 'UserMessage' = proto.Field(
        proto.MESSAGE,
        number=2,
        oneof='kind',
        message='UserMessage',
    )
    system_message: 'SystemMessage' = proto.Field(
        proto.MESSAGE,
        number=3,
        oneof='kind',
        message='SystemMessage',
    )
    timestamp: timestamp_pb2.Timestamp = proto.Field(
        proto.MESSAGE,
        number=1,
        message=timestamp_pb2.Timestamp,
    )


class UserMessage(proto.Message):
    r"""A message from the user that is interacting with the system.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        text (str):
            Text should use this field instead of blob.

            This field is a member of `oneof`_ ``kind``.
    """

    text: str = proto.Field(
        proto.STRING,
        number=1,
        oneof='kind',
    )


class SystemMessage(proto.Message):
    r"""A message from the system in response to the user. This
    message can also be a message from the user as historical
    context for multiturn conversations with the system.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        text (google.cloud.dataqna_v1alpha1.types.TextMessage):
            A direct natural language response to the
            user message.

            This field is a member of `oneof`_ ``kind``.
        schema (google.cloud.dataqna_v1alpha1.types.SchemaMessage):
            A message produced during schema resolution.

            This field is a member of `oneof`_ ``kind``.
        data (google.cloud.dataqna_v1alpha1.types.DataMessage):
            A message produced during data retrieval.

            This field is a member of `oneof`_ ``kind``.
        analysis (google.cloud.dataqna_v1alpha1.types.AnalysisMessage):
            A message produced during analysis.

            This field is a member of `oneof`_ ``kind``.
        chart (google.cloud.dataqna_v1alpha1.types.ChartMessage):
            A message produced during chart generation.

            This field is a member of `oneof`_ ``kind``.
        error (google.cloud.dataqna_v1alpha1.types.ErrorMessage):
            An error message.

            This field is a member of `oneof`_ ``kind``.
    """

    text: 'TextMessage' = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof='kind',
        message='TextMessage',
    )
    schema: 'SchemaMessage' = proto.Field(
        proto.MESSAGE,
        number=2,
        oneof='kind',
        message='SchemaMessage',
    )
    data: 'DataMessage' = proto.Field(
        proto.MESSAGE,
        number=3,
        oneof='kind',
        message='DataMessage',
    )
    analysis: 'AnalysisMessage' = proto.Field(
        proto.MESSAGE,
        number=4,
        oneof='kind',
        message='AnalysisMessage',
    )
    chart: 'ChartMessage' = proto.Field(
        proto.MESSAGE,
        number=5,
        oneof='kind',
        message='ChartMessage',
    )
    error: 'ErrorMessage' = proto.Field(
        proto.MESSAGE,
        number=6,
        oneof='kind',
        message='ErrorMessage',
    )


class TextMessage(proto.Message):
    r"""A multi-part text message.

    Attributes:
        parts (MutableSequence[str]):
            Output only. The parts of the message.
    """

    parts: MutableSequence[str] = proto.RepeatedField(
        proto.STRING,
        number=1,
    )


class SchemaMessage(proto.Message):
    r"""A message produced during schema resolution.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        query (google.cloud.dataqna_v1alpha1.types.SchemaQuery):
            A schema resolution query.

            This field is a member of `oneof`_ ``kind``.
        result (google.cloud.dataqna_v1alpha1.types.SchemaResult):
            The result of a schema resolution query.

            This field is a member of `oneof`_ ``kind``.
    """

    query: 'SchemaQuery' = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof='kind',
        message='SchemaQuery',
    )
    result: 'SchemaResult' = proto.Field(
        proto.MESSAGE,
        number=2,
        oneof='kind',
        message='SchemaResult',
    )


class SchemaQuery(proto.Message):
    r"""A query for resolving the schema relevant to the posed
    question.

    Attributes:
        question (str):
            Output only. The question to send to the
            system for schema resolution.
    """

    question: str = proto.Field(
        proto.STRING,
        number=1,
    )


class SchemaResult(proto.Message):
    r"""The result of schema resolution.

    Attributes:
        datasources (MutableSequence[google.cloud.dataqna_v1alpha1.types.Datasource]):
            Output only. The datasources used to resolve
            the schema query.
    """

    datasources: MutableSequence[datasource.Datasource] = proto.RepeatedField(
        proto.MESSAGE,
        number=1,
        message=datasource.Datasource,
    )


class DataMessage(proto.Message):
    r"""A message produced during data retrieval.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        query (google.cloud.dataqna_v1alpha1.types.DataQuery):
            A data retrieval query.

            This field is a member of `oneof`_ ``kind``.
        generated_sql (str):
            SQL generated by the system to retrieve data.

            This field is a member of `oneof`_ ``kind``.
        result (google.cloud.dataqna_v1alpha1.types.DataResult):
            Retrieved data.

            This field is a member of `oneof`_ ``kind``.
        generated_looker_query (google.cloud.dataqna_v1alpha1.types.LookerQuery):
            Looker Query generated by the system to
            retrieve data.

            This field is a member of `oneof`_ ``kind``.
        big_query_job (google.cloud.dataqna_v1alpha1.types.BigQueryJob):
            A BigQuery job executed by the system to
            retrieve data.

            This field is a member of `oneof`_ ``kind``.
    """

    query: 'DataQuery' = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof='kind',
        message='DataQuery',
    )
    generated_sql: str = proto.Field(
        proto.STRING,
        number=2,
        oneof='kind',
    )
    result: 'DataResult' = proto.Field(
        proto.MESSAGE,
        number=3,
        oneof='kind',
        message='DataResult',
    )
    generated_looker_query: 'LookerQuery' = proto.Field(
        proto.MESSAGE,
        number=4,
        oneof='kind',
        message='LookerQuery',
    )
    big_query_job: 'BigQueryJob' = proto.Field(
        proto.MESSAGE,
        number=5,
        oneof='kind',
        message='BigQueryJob',
    )


class LookerQuery(proto.Message):
    r"""A query for retrieving data from a Looker explore. See
    https://cloud.google.com/looker/docs/reference/looker-api/latest/methods/Query/run_inline_query

    Attributes:
        model (str):
            Required. The LookML model used to generate
            the query.
        explore (str):
            Required. The LookML explore used to generate
            the query.
        fields (MutableSequence[str]):
            Optional. The fields to retrieve from the
            explore.
        filters (MutableSequence[google.cloud.dataqna_v1alpha1.types.LookerQuery.Filter]):
            Optional. The filters to apply to the
            explore.
        sorts (MutableSequence[str]):
            Optional. The sorts to apply to the explore.
    """

    class Filter(proto.Message):
        r"""A Looker query filter.

        Attributes:
            field (str):
                Required. The field to filter on.
            value (str):
                Required. The value f field to filter on.
        """

        field: str = proto.Field(
            proto.STRING,
            number=1,
        )
        value: str = proto.Field(
            proto.STRING,
            number=2,
        )

    model: str = proto.Field(
        proto.STRING,
        number=1,
    )
    explore: str = proto.Field(
        proto.STRING,
        number=2,
    )
    fields: MutableSequence[str] = proto.RepeatedField(
        proto.STRING,
        number=3,
    )
    filters: MutableSequence[Filter] = proto.RepeatedField(
        proto.MESSAGE,
        number=4,
        message=Filter,
    )
    sorts: MutableSequence[str] = proto.RepeatedField(
        proto.STRING,
        number=5,
    )


class DataQuery(proto.Message):
    r"""A query for retrieving data.

    Attributes:
        name (str):
            Output only. A snake-case name for the query that reflects
            its intent. It is used to name the corresponding data
            result, so that it can be referenced in later steps.

            Example: "total_sales_by_product" Example:
            "sales_for_product_12345".
        question (str):
            Output only. The question to answer.
        datasources (MutableSequence[google.cloud.dataqna_v1alpha1.types.Datasource]):
            Output only. The datasources available to
            answer the question.
    """

    name: str = proto.Field(
        proto.STRING,
        number=3,
    )
    question: str = proto.Field(
        proto.STRING,
        number=1,
    )
    datasources: MutableSequence[datasource.Datasource] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message=datasource.Datasource,
    )


class DataResult(proto.Message):
    r"""Retrieved data.

    Attributes:
        name (str):
            Output only. A snake-case name for the data result that
            reflects its contents. The name is used to pass the result
            around by reference, and serves as a signal about its
            meaning.

            Example: "total_sales_by_product" Example:
            "sales_for_product_12345".
        schema (google.cloud.dataqna_v1alpha1.types.Schema):
            Output only. The schema of the data.
        data (MutableSequence[google.protobuf.struct_pb2.Struct]):
            Output only. The content of the data. Each
            row is a struct that matches the schema. Simple
            values are represented as strings, while nested
            structures are represented as lists or structs.
    """

    name: str = proto.Field(
        proto.STRING,
        number=3,
    )
    schema: datasource.Schema = proto.Field(
        proto.MESSAGE,
        number=1,
        message=datasource.Schema,
    )
    data: MutableSequence[struct_pb2.Struct] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message=struct_pb2.Struct,
    )


class BigQueryJob(proto.Message):
    r"""A BigQuery job executed by the system.

    Attributes:
        project_id (str):
            Required. The project the job belongs to.
        job_id (str):
            Required. The ID of the job.
        destination_table (google.cloud.dataqna_v1alpha1.types.BigQueryTableReference):
            Output only. A reference to the destination
            table of the job's query results.
        schema (google.cloud.dataqna_v1alpha1.types.Schema):
            Output only. The schema of the job's query
            results.
    """

    project_id: str = proto.Field(
        proto.STRING,
        number=1,
    )
    job_id: str = proto.Field(
        proto.STRING,
        number=2,
    )
    destination_table: datasource.BigQueryTableReference = proto.Field(
        proto.MESSAGE,
        number=3,
        message=datasource.BigQueryTableReference,
    )
    schema: datasource.Schema = proto.Field(
        proto.MESSAGE,
        number=4,
        message=datasource.Schema,
    )


class AnalysisMessage(proto.Message):
    r"""A message produced during analysis.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        query (google.cloud.dataqna_v1alpha1.types.AnalysisQuery):
            An analysis query.

            This field is a member of `oneof`_ ``kind``.
        progress_event (google.cloud.dataqna_v1alpha1.types.AnalysisEvent):
            An event indicating the progress of the
            analysis.

            This field is a member of `oneof`_ ``kind``.
    """

    query: 'AnalysisQuery' = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof='kind',
        message='AnalysisQuery',
    )
    progress_event: 'AnalysisEvent' = proto.Field(
        proto.MESSAGE,
        number=2,
        oneof='kind',
        message='AnalysisEvent',
    )


class AnalysisQuery(proto.Message):
    r"""A query for performing an analysis.

    Attributes:
        question (str):
            Output only. An analysis question to help
            answer the user's original question.
        data_result_names (MutableSequence[str]):
            Output only. The names of previously
            retrieved data results to analyze.
    """

    question: str = proto.Field(
        proto.STRING,
        number=1,
    )
    data_result_names: MutableSequence[str] = proto.RepeatedField(
        proto.STRING,
        number=2,
    )


class AnalysisEvent(proto.Message):
    r"""An event indicating the progress of an analysis.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        planner_reasoning (str):
            Python codegen planner's reasoning.

            This field is a member of `oneof`_ ``kind``.
        coder_instruction (str):
            Instructions issued for code generation.

            This field is a member of `oneof`_ ``kind``.
        code (str):
            Generated code

            This field is a member of `oneof`_ ``kind``.
        execution_output (str):
            Output from code execution

            This field is a member of `oneof`_ ``kind``.
        execution_error (str):
            An error from code execution

            This field is a member of `oneof`_ ``kind``.
        result_vega_chart_json (str):
            Result as Vega chart JSON string

            This field is a member of `oneof`_ ``kind``.
        result_natural_language (str):
            Result as NL string

            This field is a member of `oneof`_ ``kind``.
        result_csv_data (str):
            Result as CSV string

            This field is a member of `oneof`_ ``kind``.
        result_reference_data (str):
            Result as a reference to a data source

            This field is a member of `oneof`_ ``kind``.
        error (str):
            A generic error message

            This field is a member of `oneof`_ ``kind``.
    """

    planner_reasoning: str = proto.Field(
        proto.STRING,
        number=2,
        oneof='kind',
    )
    coder_instruction: str = proto.Field(
        proto.STRING,
        number=3,
        oneof='kind',
    )
    code: str = proto.Field(
        proto.STRING,
        number=4,
        oneof='kind',
    )
    execution_output: str = proto.Field(
        proto.STRING,
        number=5,
        oneof='kind',
    )
    execution_error: str = proto.Field(
        proto.STRING,
        number=6,
        oneof='kind',
    )
    result_vega_chart_json: str = proto.Field(
        proto.STRING,
        number=7,
        oneof='kind',
    )
    result_natural_language: str = proto.Field(
        proto.STRING,
        number=8,
        oneof='kind',
    )
    result_csv_data: str = proto.Field(
        proto.STRING,
        number=9,
        oneof='kind',
    )
    result_reference_data: str = proto.Field(
        proto.STRING,
        number=10,
        oneof='kind',
    )
    error: str = proto.Field(
        proto.STRING,
        number=11,
        oneof='kind',
    )


class ChartMessage(proto.Message):
    r"""A message produced during chart generation.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        query (google.cloud.dataqna_v1alpha1.types.ChartQuery):
            A query for generating a chart.

            This field is a member of `oneof`_ ``kind``.
        result (google.cloud.dataqna_v1alpha1.types.ChartResult):
            The result of a chart generation query.

            This field is a member of `oneof`_ ``kind``.
    """

    query: 'ChartQuery' = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof='kind',
        message='ChartQuery',
    )
    result: 'ChartResult' = proto.Field(
        proto.MESSAGE,
        number=2,
        oneof='kind',
        message='ChartResult',
    )


class ChartQuery(proto.Message):
    r"""A query for generating a chart.

    Attributes:
        instructions (str):
            Output only. Natural language instructions
            for generating the chart.
        data_result_name (str):
            Output only. The name of a previously
            retrieved data result to use in the chart.
    """

    instructions: str = proto.Field(
        proto.STRING,
        number=1,
    )
    data_result_name: str = proto.Field(
        proto.STRING,
        number=2,
    )


class ChartResult(proto.Message):
    r"""The result of a chart generation query.

    Attributes:
        vega_config (google.protobuf.struct_pb2.Struct):
            Output only. A generated Vega chart config.
            See https://vega.github.io/vega/docs/config/
        image (google.cloud.dataqna_v1alpha1.types.Blob):
            Optional. A rendering of the chart if this
            was requested in the context.
    """

    vega_config: struct_pb2.Struct = proto.Field(
        proto.MESSAGE,
        number=2,
        message=struct_pb2.Struct,
    )
    image: 'Blob' = proto.Field(
        proto.MESSAGE,
        number=3,
        message='Blob',
    )


class ErrorMessage(proto.Message):
    r"""An error message.

    Attributes:
        text (str):
            Output only. The text of the error.
    """

    text: str = proto.Field(
        proto.STRING,
        number=1,
    )


class Blob(proto.Message):
    r"""A blob of data with a MIME type.

    Attributes:
        mime_type (str):
            Required. The IANA standard MIME type of the
            message data.
        data (bytes):
            Required. The data represented as bytes.
    """

    mime_type: str = proto.Field(
        proto.STRING,
        number=1,
    )
    data: bytes = proto.Field(
        proto.BYTES,
        number=2,
    )


__all__ = tuple(sorted(__protobuf__.manifest))
