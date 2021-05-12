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

from typing import cast, Any, Optional, Set, Iterable, List, Tuple, Dict

import streamlit
from streamlit.errors import StreamlitAPIException
from streamlit.proto.MultiSelect_pb2 import MultiSelect as MultiSelectProto
from streamlit.type_util import is_type, ensure_iterable
from streamlit.session import get_session_state
from streamlit.widgets import register_widget, beta_widget_value
from .form import current_form_id, is_in_form


class MultiSelectMixin:
    def multiselect(
        self,
        label,
        options: List[str],
        default: Optional[List[str]] = None,
        format_func=str,
        key=None,
        on_change=None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        help: Optional[str] = None,
    ) -> List[str]:
        """Display a multiselect widget.
        The multiselect widget starts as empty.

        Parameters
        ----------
        label : str
            A short label explaining to the user what this select widget is for.
        options : list, tuple, numpy.ndarray, pandas.Series, or pandas.DataFrame
            Labels for the select options. This will be cast to str internally
            by default. For pandas.DataFrame, the first column is selected.
        default: [str] or None
            List of default values.
        format_func : function
            Function to modify the display of selectbox options. It receives
            the raw option as an argument and should output the label to be
            shown for that option. This has no impact on the return value of
            the selectbox.
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
        [str]
            A list with the selected options

        Example
        -------
        >>> options = st.multiselect(
        ...     'What are your favorite colors',
        ...     ['Green', 'Yellow', 'Red', 'Blue'],
        ...     ['Yellow', 'Red'])
        >>>
        >>> st.write('You selected:', options)

        .. note::
           User experience can be degraded for large lists of `options` (100+), as this widget
           is not designed to handle arbitrary text search efficiently. See this
           `thread <https://discuss.streamlit.io/t/streamlit-loading-column-data-takes-too-much-time/1791>`_
           on the Streamlit community forum for more information and
           `GitHub issue #1059 <https://github.com/streamlit/streamlit/issues/1059>`_ for updates on the issue.

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

        options: List[str] = ensure_iterable(options)

        value: Set[str] = set() if default is None else set(default)
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

        default_value = set()

        if is_in_form(self.dg):
            v = beta_widget_value(key)
            if v is not None:
                value = v
            elif value is None:
                value = default_value

            state[key] = value
        else:
            v = state.get(key, None)
            if v is None:
                if value is None:
                    value = default_value

                state[key] = value
            else:
                value = v

        # Perform validation checks and return indices base on the default values.
        def _check_and_convert_to_indices(
            options, default_values
        ) -> Optional[List[int]]:
            if default_values is None and None not in options:
                return None

            if not isinstance(default_values, list):
                # This if is done before others because calling if not x (done
                # right below) when x is of type pd.Series() or np.array() throws a
                # ValueError exception.
                if is_type(default_values, "numpy.ndarray") or is_type(
                    default_values, "pandas.core.series.Series"
                ):
                    default_values = list(default_values)
                elif not default_values or default_values in options:
                    default_values = [default_values]
                else:
                    default_values = list(default_values)

            for value in default_values:
                if value not in options:
                    raise StreamlitAPIException(
                        "Every Multiselect default value must exist in options"
                    )

            return [options.index(value) for value in default_values]

        indices = _check_and_convert_to_indices(options, value)
        multiselect_proto = MultiSelectProto()
        multiselect_proto.label = label
        default_value_indices = [] if indices is None else indices
        multiselect_proto.default[:] = default_value_indices
        multiselect_proto.options[:] = [str(format_func(option)) for option in options]
        multiselect_proto.form_id = current_form_id(self.dg)
        if help is not None:
            multiselect_proto.help = help
        if force_set_value:
            # multiselect values are indices
            multiselect_proto.value[:] = default_value_indices
            multiselect_proto.valueSet = True
        # TODO(amanda): file ticket for supporting sets in addition to lists, and use sets internally for semantic clarity?

        def deserialize_multiselect(ui_value: Any) -> List[str]:
            current_value = ui_value.data if ui_value is not None else value
            return [options[i] for i in current_value]

        register_widget(
            "multiselect",
            multiselect_proto,
            user_key=key,
            on_change_handler=on_change,
            args=args,
            kwargs=kwargs,
            deserializer=deserialize_multiselect,
        )
        self.dg._enqueue("multiselect", multiselect_proto, value)
        return list(value)

    @property
    def dg(self) -> "streamlit.delta_generator.DeltaGenerator":
        """Get our DeltaGenerator."""
        return cast("streamlit.delta_generator.DeltaGenerator", self)
