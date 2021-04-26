# Copyright 2018-2021 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
from typing import cast, Optional

import streamlit
from streamlit.errors import StreamlitAPIException
from streamlit.proto.ColorPicker_pb2 import ColorPicker as ColorPickerProto
from .utils import register_widget
from streamlit.session import get_session_state


class ColorPickerMixin:
    def color_picker(
        self, label, value: Optional[str] = None, key=None, on_change=None, context=None
    ):
        """Display a color picker widget.

        Parameters
        ----------
        label : str
            A short label explaining to the user what this input is for.
        value : str or None
            The hex value of this widget when it first renders. If None,
            defaults to black.
        key : str
            An optional string to use as the unique key for the widget.
            If this is omitted, a key will be generated for the widget
            based on its content. Multiple widgets of the same type may
            not share the same key.
        on_change : callable
            The callable that is invoked when the value changes. The callable
            only has one parameter, the new value.

        Returns
        -------
        str
            The selected color as a hex string.

        Example
        -------
        >>> color = st.color_picker('Pick A Color', '#00f900')
        >>> st.write('The current color is', color)

        """
        if key is None:
            key = label

        state = get_session_state()
        force_set_value = value is not None or state.is_new_value(key)

        if value is None:
            # Value not passed in, try to get it from state
            value = state.get(key, None)
        # set value default
        if value is None:
            value = "#000000"

        state[key] = value

        # make sure the value is a string
        if not isinstance(value, str):
            raise StreamlitAPIException(
                """
                Color Picker Value has invalid type: %s. Expects a hex string
                like '#00FFAA' or '#000'.
                """
                % type(value).__name__
            )

        # validate the value and expects a hex string
        match = re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", value)

        if not match:
            raise StreamlitAPIException(
                """
                '%s' is not a valid hex code for colors. Valid ones are like
                '#00FFAA' or '#000'.
                """
                % value
            )

        color_picker_proto = ColorPickerProto()
        color_picker_proto.label = label
        color_picker_proto.default = str(value)

        def deserialize_color_picker(ui_value) -> str:
            return str(ui_value if ui_value is not None else value)

        register_widget(
            "color_picker",
            color_picker_proto,
            user_key=key,
            on_change_handler=on_change,
            context=context,
            deserializer=deserialize_color_picker,
        )
        self.dg._enqueue("color_picker", color_picker_proto)
        return value

    @property
    def dg(self) -> "streamlit.delta_generator.DeltaGenerator":
        """Get our DeltaGenerator."""
        return cast("streamlit.delta_generator.DeltaGenerator", self)
