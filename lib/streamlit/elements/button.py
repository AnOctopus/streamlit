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

from typing import Optional, cast

import streamlit
from streamlit.errors import StreamlitAPIException
from streamlit.proto.Button_pb2 import Button as ButtonProto
from streamlit.widgets import register_widget
from .form import current_form_id, is_in_form


FORM_DOCS_INFO = """

For more information, refer to the
[documentation for forms](https://docs.streamlit.io/api.html#form).
"""


class ButtonMixin:
    def button(
        self,
        label,
        key=None,
        on_change=None,
        args=None,
        kwargs=None,
        help=None,
    ) -> bool:
        """Display a button widget.

        Parameters
        ----------
        label : str
            A short label explaining to the user what this button is for.
        key : str
            An optional string to use as the unique key for the widget.
            If this is omitted, a key will be generated for the widget
            based on its content. Multiple widgets of the same type may
            not share the same key.
        on_click : callable
            The callable that is invoked when the button is clicked, not
            when the return value changes. The callable has no parameters.

        Returns
        -------
        bool
            If the button was clicked on the last run of the app.

        Example
        -------
        >>> if st.button('Say hello'):
        ...     st.write('Why hello there')
        ... else:
        ...     st.write('Goodbye')

        """
        return self.dg._button(
            label,
            key,
            help=help,
            is_form_submitter=False,
            on_change=on_change,
            args=args,
            kwargs=kwargs,
        )

    def _button(
        self,
        label: str,
        key: str,
        help: Optional[str],
        is_form_submitter: bool,
        on_change=None,
        args=None,
        kwargs=None,
    ) -> bool:
        button_proto = ButtonProto()

        # It doesn't make sense to create a button inside a form (except
        # for the "Form Submitter" button that's automatically created in
        # every form). We throw an error to warn the user about this.
        # We omit this check for scripts running outside streamlit, because
        # they will have no report_ctx.
        if streamlit._is_running_with_streamlit:
            if is_in_form(self.dg) and not is_form_submitter:
                raise StreamlitAPIException(
                    f"`st.button()` can't be used in an `st.form()`.{FORM_DOCS_INFO}"
                )
            elif not is_in_form(self.dg) and is_form_submitter:
                raise StreamlitAPIException(
                    f"`st.submit_button()` must be used inside an `st.form()`.{FORM_DOCS_INFO}"
                )

        button_proto.label = label
        button_proto.default = False
        button_proto.is_form_submitter = is_form_submitter
        button_proto.form_id = current_form_id(self.dg)
        if help is not None:
            button_proto.help = help

        def on_change_handler(*args, **kwargs):
            try:
                new_value = streamlit.session_state[key]
                if new_value and on_change is not None:
                    on_change(*args, **kwargs)
            except KeyError:
                pass

        def deserialize_button(ui_value):
            return ui_value if ui_value is not None else False

        current_value: bool = register_widget(
            "button",
            button_proto,
            user_key=key,
            on_change_handler=on_change_handler,
            args=args,
            kwargs=kwargs,
            deserializer=deserialize_button,
        )
        self.dg._enqueue("button", button_proto)
        return current_value

    @property
    def dg(self) -> "streamlit.delta_generator.DeltaGenerator":
        """Get our DeltaGenerator."""
        return cast("streamlit.delta_generator.DeltaGenerator", self)
