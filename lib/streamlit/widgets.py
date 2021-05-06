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

import json
import textwrap
from pprint import pprint
from typing import Any, Optional, Dict, Callable, Tuple, Set
from dataclasses import dataclass

from streamlit import util
from streamlit import report_thread
from streamlit.errors import DuplicateWidgetID
from streamlit.proto.ClientState_pb2 import ClientState
from streamlit.proto.WidgetStates_pb2 import WidgetStates, WidgetState


class NoValue:
    """Return this from DeltaGenerator.foo_widget() when you want the st.foo_widget()
    call to return None. This is needed because `DeltaGenerator._enqueue`
    replaces `None` with a `DeltaGenerator` (for use in non-widget elements).
    """

    pass


def register_widget(
    element_type: str,
    element_proto: Any,
    user_key: Optional[str] = None,
    widget_func_name: Optional[str] = None,
) -> Optional[Any]:
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

    Returns
    -------
    ui_value : Any or None
        The value of the widget set by the client or
        the default value passed. If the report context
        doesn't exist, None will be returned.

    """
    widget_id = _get_widget_id(element_type, element_proto, user_key)
    element_proto.id = widget_id

    ctx = report_thread.get_report_ctx()
    if ctx is None:
        # Early-out if we're not running inside a ReportThread (which
        # probably means we're running as a "bare" Python script, and
        # not via `streamlit run`).
        return None

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

    # Return the widget's current value.
    return ctx.widgets.get_widget_value(widget_id)


def coalesce_widget_states(
    old_states: WidgetStates, new_states: WidgetStates
) -> WidgetStates:
    """Coalesce an older WidgetStates into a newer one, and return a new
    WidgetStates containing the result.

    For most widget values, we just take the latest version.

    However, any trigger_values (the state set by buttons) that are True in
    `old_states` will be set to True in the coalesced result, so that button
    presses don't go missing.
    """
    states_by_id = {}  # type: Dict[str, WidgetState]
    for new_state in new_states.widgets:
        states_by_id[new_state.id] = new_state

    for old_state in old_states.widgets:
        if old_state.WhichOneof("value") == "trigger_value" and old_state.trigger_value:

            # Ensure the corresponding new_state is also a trigger;
            # otherwise, a widget that was previously a button but no longer is
            # could get a bad value.
            new_trigger_val = states_by_id.get(old_state.id)
            if (
                new_trigger_val
                and new_trigger_val.WhichOneof("value") == "trigger_value"
            ):
                states_by_id[old_state.id] = old_state

    coalesced = WidgetStates()
    coalesced.widgets.extend(states_by_id.values())

    return coalesced


@dataclass
class Args:
    args: Optional[Tuple[Any, ...]] = None
    kwargs: Optional[Dict[str, Any]] = None


class WidgetStateManager(object):
    def __init__(self):
        self._widget_states: Dict[str, WidgetState] = {}
        self._previous_widget_states: Dict[str, WidgetState] = {}
        self._widget_callbacks: Dict[str, Callable[..., None]] = {}
        self._widget_deserializers: Dict[str, Callable[..., Any]] = {}
        self._widget_args: Dict[str, Args] = {}

    def __repr__(self) -> str:
        return util.repr_(self)

    def get_widget_value(self, widget_id: str) -> Optional[Any]:
        """Return the value of a widget, or None if no value has been set."""
        wstate = self._widget_states.get(widget_id, None)
        return _get_widget_value(wstate)

    def get_previous_widget_value(self, widget_id: str) -> Optional[Any]:
        """Return the previous value of a widget, or None if no value was set."""
        wstate = self._previous_widget_states.get(widget_id, None)
        return _get_widget_value(wstate)

    def set_state(self, widget_states: WidgetStates) -> None:
        """Copy the state from a WidgetStates protobuf into our state dict."""
        self._previous_widget_states = self._widget_states
        self._widget_states = {}
        for wstate in widget_states.widgets:
            self._widget_states[wstate.id] = wstate

    def add_callback(
        self,
        widget_id: str,
        deserializer: Callable[..., Any],
        callback: Callable[..., None],
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a callback that will be called immediately before the app's
        next rerun if the given widget's value has changed.
        """
        self._widget_callbacks[widget_id] = callback
        self._widget_deserializers[widget_id] = deserializer
        self._widget_args[widget_id] = Args(args, kwargs)

    def get_callback(self, widget_id: str) -> Optional[Callable[..., None]]:
        return self._widget_callbacks.get(widget_id, None)

    def call_callbacks(self, new_widget_states: WidgetStates) -> None:
        """Call all callbacks based on changes in the widget state. We are
        assuming that widgets send the same state value each time if unchanged.
        """
        for new_state in new_widget_states.widgets:
            callback = self._widget_callbacks.get(new_state.id, None)
            if callback is None:
                # The widget does not have an on_change callback.
                continue

            if self.equivalent_values(new_state):
                continue

            arg = self._widget_args.get(new_state.id, None)
            if arg is not None:
                args = arg.args if arg.args is not None else ()
                kwargs = arg.kwargs if arg.kwargs is not None else dict()
                callback(*args, **kwargs)
            else:
                callback()

    def add_deserializer(
        self, widget_id: str, deserializer: Callable[..., Any]
    ) -> None:
        self._widget_deserializers[widget_id] = deserializer

    def equivalent_values(self, new_state: WidgetState) -> bool:
        old_value = self.get_previous_widget_value(new_state.id)
        new_value = _get_widget_value(new_state)
        deserializer = self._widget_deserializers.get(new_state.id, None)

        if deserializer is not None:
            old_value = deserializer(old_value)
            new_value = deserializer(new_value)

        return new_value == old_value

    def clear_callbacks(self) -> None:
        """Clear all registered callbacks"""
        self._widget_callbacks = {}

    def marshall(self, client_state: ClientState) -> None:
        """Populate a ClientState proto with the widget values stored in this
        object.
        """
        client_state.widget_states.widgets.extend(self._widget_states.values())

    def cull_nonexistent(self, widget_ids: Set[str]) -> None:
        """Removes items in state that aren't present in a set of provided
        widget_ids.
        """
        self._state = {k: v for k, v in self._state.items() if k in widget_ids}

    def reset_triggers(self) -> None:
        """Remove all trigger values in our state dictionary.

        (All trigger values default to False, so removing them is equivalent
        to resetting them from True to False.)

        """
        prev_state = self._widget_states
        self._widget_states = {}
        for wstate in prev_state.values():
            if wstate.WhichOneof("value") != "trigger_value":
                self._widget_states[wstate.id] = wstate

    def dump(self) -> None:
        """Pretty-print widget state to the console, for debugging."""
        pprint(self._widget_states)


def _get_widget_value(state: Optional[WidgetState]) -> Optional[Any]:
    """Return the value of a widget, or None if no value has been set."""
    if state is None:
        return None

    value_type = state.WhichOneof("value")
    if value_type == "json_value":
        return json.loads(getattr(state, value_type))

    return getattr(state, value_type)


def beta_widget_value(key: str) -> Any:
    """Returns the value of a widget with a given id, for use in
    state update callbacks.
    """
    import streamlit.report_thread as ReportThread
    from streamlit.server.server import Server
    import streamlit.elements.utils as utils

    ctx = ReportThread.get_report_ctx()

    if ctx is None:
        return None

    this_session = Server.get_current().get_session_by_id(ctx.session_id)
    widget_states: WidgetStateManager = this_session.get_widget_states()

    widget_id = utils._get_widget_id("", None, key)
    deserializer = widget_states._widget_deserializers.get(widget_id, lambda x: x)
    widget_value = widget_states.get_widget_value(widget_id)
    if widget_value is None:
        return None
    else:
        return deserializer(widget_value)


def widget_values() -> Dict[str, Any]:
    import streamlit.report_thread as ReportThread
    from streamlit.server.server import Server
    import streamlit.elements.utils as utils

    ctx = ReportThread.get_report_ctx()

    if ctx is None:
        return None

    this_session = Server.get_current().get_session_by_id(ctx.session_id)
    widget_states: WidgetStateManager = this_session.get_widget_states()
    return widget_states._widget_states


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
