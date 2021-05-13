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

from streamlit.errors import StreamlitAPIException
from typing import cast, Optional, Tuple, Dict, Any

import streamlit
from streamlit.proto.Checkbox_pb2 import Checkbox as CheckboxProto
from streamlit.widgets import register_widget, beta_widget_value
from .form import current_form_id, is_in_form
from streamlit.session import get_session_state


class CheckboxMixin:
    def checkbox(
        self,
        label,
        value: Optional[bool] = None,
        key=None,
        on_change=None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        help: Optional[str] = None,
    ) -> bool:
        """Display a checkbox widget.

        Parameters
        ----------
        label : str
            A short label explaining to the user what this checkbox is for.
        value : bool
            Preselect the checkbox when it first renders. This will be
            cast to bool internally.
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
        bool
            Whether or not the checkbox is checked.

        Example
        -------
        >>> agree = st.checkbox('I agree')
        >>>
        >>> if agree:
        ...     st.write('Great!')

        """
        if (
            streamlit._is_running_with_streamlit
            and is_in_form(self.dg)
            and on_change is not None
        ):
            raise StreamlitAPIException(
                "Callbacks are not allowed on widgets in forms; put them on the submit button instead"
            )

        if key is None:
            key = f"internal:{label}"

        state = get_session_state()
        force_set_value = state.is_new_value(key) and not is_in_form(self.dg)
        if (
            value is not None
            and state.is_new_value(key)
            and beta_widget_value(key) is None
        ):
            streamlit.warning(
                """Created a widget with a passed in default value, whose widget value was already set through
            the session state api. The results of doing this are undefined behavior."""
            )

        default_value = False

        if is_in_form(self.dg):
            v = beta_widget_value(key)
            if v is not None:
                value = v
            elif value is None:
                value = default_value
        else:
            v = state.get(key, None)
            if v is None:
                if value is None:
                    value = default_value
            else:
                value = v

        state[key] = value

        value = bool(value)

        checkbox_proto = CheckboxProto()
        checkbox_proto.label = label
        checkbox_proto.default = value
        checkbox_proto.form_id = current_form_id(self.dg)
        if help is not None:
            checkbox_proto.help = help
        if force_set_value:
            checkbox_proto.value = value
            checkbox_proto.valueSet = True

        def deserialize_checkbox(ui_value):
            return bool(ui_value if ui_value is not None else value)

        register_widget(
            "checkbox",
            checkbox_proto,
            user_key=key,
            on_change_handler=on_change,
            args=args,
            kwargs=kwargs,
            deserializer=deserialize_checkbox,
        )
        self.dg._enqueue("checkbox", checkbox_proto)
        return value

    @property
    def dg(self) -> "streamlit.delta_generator.DeltaGenerator":
        """Get our DeltaGenerator."""
        return cast("streamlit.delta_generator.DeltaGenerator", self)
