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

import textwrap

from streamlit import type_util
from streamlit.report_thread import get_report_ctx
from streamlit.errors import DuplicateWidgetID
from typing import Optional, Any, Callable


class NoValue:
    """Return this from DeltaGenerator.foo_widget() when you want the st.foo_widget()
    call to return None. This is needed because `DeltaGenerator._enqueue`
    replaces `None` with a `DeltaGenerator` (for use in non-widget elements).
    """

    pass


def clean_text(text: Any) -> str:
    """Convert an object to text, dedent it, and strip whitespace."""
    return textwrap.dedent(str(text)).strip()


def _build_duplicate_widget_message(
    widget_func_name: str, user_key: Optional[str] = None
) -> str:
    if user_key is not None:
        message = textwrap.dedent(
            """
            There are multiple identical `st.{widget_type}` widgets with
            `key='{user_key}'`.

            To fix this, please make sure that the `key` argument is unique for
            each `st.{widget_type}` you create.
            """
        )
    else:
        message = textwrap.dedent(
            """
            There are multiple identical `st.{widget_type}` widgets with the
            same generated key.

            When a widget is created, it's assigned an internal key based on
            its structure. Multiple widgets with an identical structure will
            result in the same internal key, which causes this error.

            To fix this error, please pass a unique `key` argument to
            `st.{widget_type}`.
            """
        )

    return message.strip("\n").format(widget_type=widget_func_name, user_key=user_key)


def _get_widget_id(
    element_type: str, element_proto: Any, user_key: Optional[str] = None
) -> str:
    """Generate the widget id for the given widget.

    Does not mutate the element_proto object.
    """
    if user_key is not None:
        widget_id = user_key
    else:
        # Identify the widget with a hash of type + contents
        widget_id = str(hash((element_type, element_proto.SerializeToString())))

    return widget_id


def register_widget(
    element_type: str,
    element_proto: Any,
    user_key: Optional[str] = None,
    widget_func_name: Optional[str] = None,
    on_change_handler: Optional[Callable[..., None]] = None,
    context: Optional[Any] = None,
    deserializer: Callable[[Any], Any] = lambda x: x,
) -> Any:
    """Register a widget with Streamlit, and return its current ui_value.
    NOTE: This function should be called after the proto has been filled.

    Parameters
    ----------
    element_type : str
        The type of the element as stored in proto.
    element_proto : proto
        The proto of the specified type (e.g. Button/Multiselect/Slider proto)
    user_key : str
        Optional user-specified string to use as the widget ID.
        If this is None, we'll generate an ID by hashing the element.
    widget_func_name : str or None
        The widget's DeltaGenerator function name, if it's different from
        its element_type. Custom components are a special case: they all have
        the element_type "component_instance", but are instantiated with
        dynamically-named functions.
    on_change_handler: callable or None
        An optional callback invoked when the widget's value changes.
    deserializer: callable
        Called to convert a widget's protobuf value to the value returned by
        its st.foo function.

    Returns
    -------
    ui_value : any
        The value of the widget set by the client or
        the default value passed. If the report context
        doesn't exist, None will be returned.

    """
    if user_key is not None:
        key: Optional[str] = user_key
    elif hasattr(element_proto, "label"):
        key = element_proto.label
    else:
        key = None
    widget_id = _get_widget_id(element_type, element_proto, key)
    element_proto.id = widget_id

    ctx = get_report_ctx()
    if ctx is None:
        # Early-out if we're not running inside a ReportThread (which
        # probably means we're running as a "bare" Python script, and
        # not via `streamlit run`).
        return deserializer(None)

    # Register the widget, and ensure another widget with the same id hasn't
    # already been registered.
    added = ctx.widget_ids_this_run.add(widget_id)
    if not added:
        raise DuplicateWidgetID(
            _build_duplicate_widget_message(
                widget_func_name if widget_func_name is not None else element_type,
                user_key,
            )
        )

    if on_change_handler is not None:
        ctx.widgets.add_callback(element_proto.id, deserializer, on_change_handler)
    else:
        ctx.widgets.add_deserializer(element_proto.id, deserializer)

    if key is not None:
        ctx.widgets.add_signal(element_proto.id, key, context)

    # Return the widget's current value.
    return deserializer(ctx.widgets.get_widget_value(widget_id))


def last_index_for_melted_dataframes(data):
    if type_util.is_dataframe_compatible(data):
        data = type_util.convert_anything_to_df(data)

        if data.index.size > 0:
            return data.index[-1]

    return None
