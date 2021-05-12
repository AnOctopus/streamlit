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

import numbers
from typing import cast, Optional, Tuple, Any, Dict, Union

import streamlit
from streamlit.errors import StreamlitAPIException
from streamlit.js_number import JSNumber, JSNumberBoundsException
from streamlit.proto.NumberInput_pb2 import NumberInput as NumberInputProto
from streamlit.session import get_session_state
from streamlit.widgets import register_widget, NoValue, beta_widget_value
from .form import current_form_id, is_in_form


class NumberInputMixin:
    def number_input(
        self,
        label,
        min_value=None,
        max_value=None,
        value=None,
        step=None,
        format=None,
        key=None,
        on_change=None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        help: Optional[str] = None,
    ) -> Union[int, float]:
        """Display a numeric input widget.

        Parameters
        ----------
        label : str
            A short label explaining to the user what this input is for.
        min_value : int or float or None
            The minimum permitted value.
            If None, there will be no minimum.
        max_value : int or float or None
            The maximum permitted value.
            If None, there will be no maximum.
        value : int or float or None
            The value of this widget when it first renders.
            Defaults to min_value, or 0.0 if min_value is None
        step : int or float or None
            The stepping interval.
            Defaults to 1 if the value is an int, 0.01 otherwise.
            If the value is not specified, the format parameter will be used.
        format : str or None
            A printf-style format string controlling how the interface should
            display numbers. Output must be purely numeric. This does not impact
            the return value. Valid formatters: %d %e %f %g %i %u
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
        int or float
            The current value of the numeric input widget. The return type
            will match the data type of the value parameter.

        Example
        -------
        >>> number = st.number_input('Insert a number')
        >>> st.write('The current number is ', number)
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

        # Ensure that all arguments are of the same type.
        argsl = [min_value, max_value, value, step]

        int_args = all(
            isinstance(a, (numbers.Integral, type(None), NoValue)) for a in argsl
        )

        float_args = all(isinstance(a, (float, type(None), NoValue)) for a in argsl)

        if not int_args and not float_args:
            raise StreamlitAPIException(
                "All numerical arguments must be of the same type."
                f"\n`value` has {type(value).__name__} type."
                f"\n`min_value` has {type(min_value).__name__} type."
                f"\n`max_value` has {type(max_value).__name__} type."
                f"\n`step` has {type(step).__name__} type."
            )

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

        if min_value is not None:
            default_value = min_value
        elif int_args and float_args:
            default_value = 0.0  # if no values are provided, defaults to float
        elif int_args:
            default_value = 0
        else:
            default_value = 0.0

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

        int_value = isinstance(value, numbers.Integral)
        float_value = isinstance(value, float)

        if format is None:
            format = "%d" if int_value else "%0.2f"

        # Warn user if they format an int type as a float or vice versa.
        if format in ["%d", "%u", "%i"] and float_value:
            import streamlit as st

            st.warning(
                "Warning: NumberInput value below has type float,"
                f" but format {format} displays as integer."
            )
        elif format[-1] == "f" and int_value:
            import streamlit as st

            st.warning(
                "Warning: NumberInput value below has type int so is"
                f" displayed as int despite format string {format}."
            )

        if step is None:
            step = 1 if int_value else 0.01

        try:
            float(format % 2)
        except (TypeError, ValueError):
            raise StreamlitAPIException(
                "Format string for st.number_input contains invalid characters: %s"
                % format
            )

        # Ensure that the value matches arguments' types.
        all_ints = int_value and int_args

        if (min_value and min_value > value) or (max_value and max_value < value):
            raise StreamlitAPIException(
                "The default `value` of %(value)s "
                "must lie between the `min_value` of %(min)s "
                "and the `max_value` of %(max)s, inclusively."
                % {"value": value, "min": min_value, "max": max_value}
            )

        # Bounds checks. JSNumber produces human-readable exceptions that
        # we simply re-package as StreamlitAPIExceptions.
        try:
            if all_ints:
                if min_value is not None:
                    JSNumber.validate_int_bounds(min_value, "`min_value`")
                if max_value is not None:
                    JSNumber.validate_int_bounds(max_value, "`max_value`")
                if step is not None:
                    JSNumber.validate_int_bounds(step, "`step`")
                JSNumber.validate_int_bounds(value, "`value`")
            else:
                if min_value is not None:
                    JSNumber.validate_float_bounds(min_value, "`min_value`")
                if max_value is not None:
                    JSNumber.validate_float_bounds(max_value, "`max_value`")
                if step is not None:
                    JSNumber.validate_float_bounds(step, "`step`")
                JSNumber.validate_float_bounds(value, "`value`")
        except JSNumberBoundsException as e:
            raise StreamlitAPIException(str(e))

        number_input_proto = NumberInputProto()
        number_input_proto.data_type = (
            NumberInputProto.INT if all_ints else NumberInputProto.FLOAT
        )
        number_input_proto.label = label
        number_input_proto.default = value
        number_input_proto.form_id = current_form_id(self.dg)
        if help is not None:
            number_input_proto.help = help

        if min_value is not None:
            number_input_proto.min = min_value
            number_input_proto.has_min = True

        if max_value is not None:
            number_input_proto.max = max_value
            number_input_proto.has_max = True

        if step is not None:
            number_input_proto.step = step

        if format is not None:
            number_input_proto.format = format

        if force_set_value:
            number_input_proto.value = value
            number_input_proto.valueSet = True

        def deserialize_number_input(ui_value):
            return ui_value if ui_value is not None else value

        register_widget(
            "number_input",
            number_input_proto,
            user_key=key,
            on_change_handler=on_change,
            args=args,
            kwargs=kwargs,
            deserializer=deserialize_number_input,
        )
        self.dg._enqueue("number_input", number_input_proto)
        return value

    @property
    def dg(self) -> "streamlit.delta_generator.DeltaGenerator":
        """Get our DeltaGenerator."""
        return cast("streamlit.delta_generator.DeltaGenerator", self)
