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

from datetime import datetime, date, time
from typing import cast, Optional, Tuple, Any, Dict

import streamlit
from streamlit.errors import StreamlitAPIException
from streamlit.proto.DateInput_pb2 import DateInput as DateInputProto
from streamlit.proto.TimeInput_pb2 import TimeInput as TimeInputProto
from streamlit.session import get_session_state
from streamlit.widgets import register_widget, beta_widget_value
from .form import current_form_id, is_in_form


class TimeWidgetsMixin:
    def time_input(
        self,
        label,
        value=None,
        key=None,
        on_change=None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        help: Optional[str] = None,
    ) -> time:
        """Display a time input widget.

        Parameters
        ----------
        label : str
            A short label explaining to the user what this time input is for.
        value : datetime.time/datetime.datetime
            The value of this widget when it first renders. This will be
            cast to str internally. Defaults to the current time.
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
        datetime.time
            The current value of the time input widget.

        Example
        -------
        >>> t = st.time_input('Set an alarm for', datetime.time(8, 45))
        >>> st.write('Alarm is set for', t)

        """
        if (
            streamlit._is_running_with_streamlit
            and is_in_form(self.dg)
            and on_change is not None
        ):
            raise StreamlitAPIException

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

        default_value = datetime.now().time()

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

        # Ensure that the value is either datetime/time
        if not isinstance(value, datetime) and not isinstance(value, time):
            raise StreamlitAPIException(
                "The type of the value should be either datetime or time."
            )

        # Convert datetime to time
        if isinstance(value, datetime):
            value = value.time()

        time_input_proto = TimeInputProto()
        time_input_proto.label = label
        time_input_proto.default = time.strftime(value, "%H:%M")
        time_input_proto.form_id = current_form_id(self.dg)
        if help is not None:
            time_input_proto.help = help
        if force_set_value:
            time_input_proto.value = time.strftime(value, "%H:%M")
            time_input_proto.valueSet = True

        def deserialize_time_input(ui_value):
            return (
                datetime.strptime(ui_value, "%H:%M").time()
                if ui_value is not None
                else value
            )

        register_widget(
            "time_input",
            time_input_proto,
            user_key=key,
            on_change_handler=on_change,
            args=args,
            kwargs=kwargs,
            deserializer=deserialize_time_input,
        )
        self.dg._enqueue("time_input", time_input_proto)
        return value

    def date_input(
        self,
        label,
        value=None,
        min_value=None,
        max_value=None,
        key=None,
        on_change=None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        help: Optional[str] = None,
    ) -> date:
        """Display a date input widget.

        Parameters
        ----------
        label : str
            A short label explaining to the user what this date input is for.
        value : datetime.date or datetime.datetime or list/tuple of datetime.date or datetime.datetime or None
            The value of this widget when it first renders. If a list/tuple with
            0 to 2 date/datetime values is provided, the datepicker will allow
            users to provide a range. Defaults to today as a single-date picker.
        min_value : datetime.date or datetime.datetime
            The minimum selectable date. Defaults to today-10y.
        max_value : datetime.date or datetime.datetime
            The maximum selectable date. Defaults to today+10y.
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
        datetime.date
            The current value of the date input widget.

        Example
        -------
        >>> d = st.date_input(
        ...     "When\'s your birthday",
        ...     datetime.date(2019, 7, 6))
        >>> st.write('Your birthday is:', d)

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

        default_value = datetime.now().date()

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

        single_value = isinstance(value, (date, datetime))
        range_value = isinstance(value, (list, tuple)) and len(value) in (0, 1, 2)
        if not single_value and not range_value:
            raise StreamlitAPIException(
                "DateInput value should either be an date/datetime or a list/tuple of "
                "0 - 2 date/datetime values"
            )

        if single_value:
            value = [value]

        date_input_proto = DateInputProto()
        date_input_proto.is_range = range_value
        if help is not None:
            date_input_proto.help = help

        value = [v.date() if isinstance(v, datetime) else v for v in value]

        date_input_proto.label = label
        date_input_proto.default[:] = [date.strftime(v, "%Y/%m/%d") for v in value]

        if isinstance(min_value, datetime):
            min_value = min_value.date()
        elif min_value is None:
            today = date.today()
            min_value = date(today.year - 10, today.month, today.day)

        date_input_proto.min = date.strftime(min_value, "%Y/%m/%d")

        if max_value is None:
            today = date.today()
            max_value = date(today.year + 10, today.month, today.day)

        if isinstance(max_value, datetime):
            max_value = max_value.date()

        date_input_proto.max = date.strftime(max_value, "%Y/%m/%d")

        date_input_proto.form_id = current_form_id(self.dg)
        if force_set_value:
            date_input_proto.value = value
            date_input_proto.valueSet = True

        def deserialize_date_input(ui_value):
            if ui_value is not None:
                return_value = getattr(ui_value, "data")
                return_value = [
                    datetime.strptime(v, "%Y/%m/%d").date() for v in return_value
                ]
            else:
                return_value = value

            return return_value[0] if single_value else tuple(return_value)

        register_widget(
            "date_input",
            date_input_proto,
            user_key=key,
            on_change_handler=on_change,
            args=args,
            kwargs=kwargs,
            deserializer=deserialize_date_input,
        )
        self.dg._enqueue("date_input", date_input_proto)
        return value

    @property
    def dg(self) -> "streamlit.delta_generator.DeltaGenerator":
        """Get our DeltaGenerator."""
        return cast("streamlit.delta_generator.DeltaGenerator", self)
