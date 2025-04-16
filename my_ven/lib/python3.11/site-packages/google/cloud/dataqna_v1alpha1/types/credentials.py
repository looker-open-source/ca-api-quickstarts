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


__protobuf__ = proto.module(
    package='google.cloud.dataqna.v1alpha1',
    manifest={
        'Credentials',
        'OAuthCredentials',
    },
)


class Credentials(proto.Message):
    r"""Represents different forms of credential specification.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        oauth (google.cloud.dataqna_v1alpha1.types.OAuthCredentials):
            OAuth credentials.

            This field is a member of `oneof`_ ``kind``.
    """

    oauth: 'OAuthCredentials' = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof='kind',
        message='OAuthCredentials',
    )


class OAuthCredentials(proto.Message):
    r"""Represents OAuth credentials.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        secret (google.cloud.dataqna_v1alpha1.types.OAuthCredentials.SecretBased):
            Secret-based OAuth credentials.

            This field is a member of `oneof`_ ``kind``.
    """

    class SecretBased(proto.Message):
        r"""Represents secret-based OAuth credentials.

        Attributes:
            client_id (str):
                Required. An OAuth client ID.
            client_secret (str):
                Required. An OAuth client secret.
        """

        client_id: str = proto.Field(
            proto.STRING,
            number=2,
        )
        client_secret: str = proto.Field(
            proto.STRING,
            number=3,
        )

    secret: SecretBased = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof='kind',
        message=SecretBased,
    )


__all__ = tuple(sorted(__protobuf__.manifest))
