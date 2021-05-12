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

from typing import cast, Optional, Tuple, Any, Dict

import streamlit
from streamlit.errors import StreamlitAPIException
from streamlit.proto.Slider_pb2 import Slider as SliderProto
from streamlit.type_util import ensure_iterable
from streamlit.session import get_session_state
from streamlit.util import index_
from streamlit.widgets import register_widget, beta_widget_value
from .form import current_form_id, is_in_form


class SelectSliderMixin:
    def select_slider(
        self,
        label,
        options=[],
        value=None,
        format_func=str,
        key=None,
        on_change=None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        help: Optional[str] = None,
    ) -> Any:
        """
        Display a slider widget to select items from a list.

        This also allows you to render a range slider by passing a two-element
        tuple or list as the `value`.

        The difference between `st.select_slider` and `st.slider` is that
        `select_slider` accepts any datatype and takes an iterable set of
        options, while `slider` only accepts numerical or date/time data and
        takes a range as input.

        Parameters
        ----------
        label : str
            A short label explaining to the user what this slider is for.
        options : list, tuple, numpy.ndarray, pandas.Series, or pandas.DataFrame
            Labels for the slider options. All options will be cast to str
            internally by default. For pandas.DataFrame, the first column is
            selected.
        value : a supported type or a tuple/list of supported types or None
            The value of the slider when it first renders. If a tuple/list
            of two values is passed here, then a range slider with those lower
            and upper bounds is rendered. For example, if set to `(1, 10)` the
            slider will have a selectable range between 1 and 10.
            Defaults to first option.
        format_func : function
            Function to modify the display of the labels from the options.
            argument. It receives the option as an argument and its output
            will be cast to str.
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
        any value or tuple of any value
            The current value of the slider widget. The return type will match
            the data type of the value parameter.

        Examples
        --------
        >>> color = st.select_slider(
        ...     'Select a color of the rainbow',
        ...     options=['red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet'])
        >>> st.write('My favorite color is', color)

        And here's an example of a range select slider:

        >>> start_color, end_color = st.select_slider(
        ...     'Select a range of color wavelength',
        ...     options=['red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet'],
        ...     value=('red', 'blue'))
        >>> st.write('You selected wavelengths between', start_color, 'and', end_color)
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

        options = ensure_iterable(options)

        state = get_session_state()
        force_set_value = state.is_new_value(key)

        # TODO have an actual default
        default_value = None

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

        if len(options) == 0:
            raise StreamlitAPIException("The `options` argument needs to be non-empty")

        is_range_value = isinstance(value, (list, tuple))
        slider_value = value

        # Convert element to index of the elements
        if is_range_value:
            slider_value = list(map(lambda v: index_(options, v), value))
            start, end = slider_value
            if start > end:
                slider_value = [end, start]
        else:
            # Simplify future logic by always making value a list
            try:
                slider_value = [index_(options, value)]
            except ValueError:
                if value is not None:
                    raise

                slider_value = [0]

        slider_proto = SliderProto()
        slider_proto.label = label
        slider_proto.format = "%s"
        slider_proto.default[:] = slider_value
        slider_proto.min = 0
        slider_proto.max = len(options) - 1
        slider_proto.step = 1  # default for index changes
        slider_proto.data_type = SliderProto.INT
        slider_proto.options[:] = [str(format_func(option)) for option in options]
        slider_proto.form_id = current_form_id(self.dg)
        if help is not None:
            slider_proto.help = help
        if force_set_value:
            # TODO: make sure the right value is passed
            slider_proto.value[:] = slider_value
            slider_proto.valueSet = True

        def deserialize_select_slider(ui_value):
            if ui_value:
                current_value = getattr(ui_value, "data")
            else:
                # Widget has not been used; fallback to the original value,
                current_value = slider_value

            # The widget always returns floats, so convert to ints before indexing
            current_value = list(map(lambda x: options[int(x)], current_value))  # type: ignore[no-any-return]

            # If the original value was a list/tuple, so will be the output (and vice versa)
            return tuple(current_value) if is_range_value else current_value[0]

        register_widget(
            "slider",
            slider_proto,
            user_key=key,
            on_change_handler=on_change,
            args=args,
            kwargs=kwargs,
            deserializer=deserialize_select_slider,
        )
        self.dg._enqueue("slider", slider_proto)
        return value

    @property
    def dg(self) -> "streamlit.delta_generator.DeltaGenerator":
        """Get our DeltaGenerator."""
        return cast("streamlit.delta_generator.DeltaGenerator", self)
