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

from google.cloud.dataqna_v1alpha1.types import datasource


__protobuf__ = proto.module(
    package='google.cloud.dataqna.v1alpha1',
    manifest={
        'InlineContext',
    },
)


class InlineContext(proto.Message):
    r"""A collection of context to apply to this conversation

    Attributes:
        system_instruction (str):
            Optional. The basic entry point for data
            owners creating domain knowledge for Agent.

            Why: Business jargon (e.g., YTD revenue is
            calculated as…, Retirement Age is 65 in the USA,
            etc) and system instructions (e.g., answer like
            a Pirate) can help the model understand the
            business context around a user question
        datasource_references (google.cloud.dataqna_v1alpha1.types.DatasourceReferences):
            Required. Datasources available for answering
            the question
    """

    system_instruction: str = proto.Field(
        proto.STRING,
        number=1,
    )
    datasource_references: datasource.DatasourceReferences = proto.Field(
        proto.MESSAGE,
        number=2,
        message=datasource.DatasourceReferences,
    )


__all__ = tuple(sorted(__protobuf__.manifest))
