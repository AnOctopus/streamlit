# Copyright 2018-2020 Streamlit Inc.
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

import streamlit.report_thread as ReportThread
from streamlit.errors import StreamlitAPIException
from streamlit.widgets import beta_widget_value, widget_values
from typing import Optional, Dict, Union, Any, TYPE_CHECKING, Iterator
from collections.abc import MutableMapping

if TYPE_CHECKING:
    from streamlit.report_session import ReportSession


class SessionState(MutableMapping):
    def __init__(self):
        """SessionState is just a mechanism for users to get and set properties
        based on their application.

        Parameters
        ----------
        **kwargs : any
            Default values for the session state.

        Example
        -------
        >>> session_state = SessionState(user_name='', favorite_color='black')
        >>> session_state.user_name = 'Mary'
        ''
        >>> session_state.favorite_color
        'black'
        """
        self._new_state: Dict[str, Any] = {}
        self._old_state: Dict[str, Any] = {}

    def __getattr__(self, key: str) -> Optional[Any]:
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def get_new_value(self, key: str) -> Optional[Any]:
        return self._new_state.get(key, None)

    def get_old_value(self, key: str) -> Optional[Any]:
        return self._old_state.get(key, None)

    def _get_merged(self) -> Dict[str, Any]:
        widgets = widget_values()
        merged = {**self._old_state, **widgets, **self._new_state}
        return merged

    def __len__(self) -> int:
        merged = self._get_merged()
        return len(merged)

    def __iter__(self) -> Iterator[Any]:
        merged = self._get_merged()
        return iter(merged)

    def __delitem__(self, v: str) -> None:
        del self._new_state[v]
        del self._old_state[v]

    def __setattr__(self, key: str, value: Any) -> None:
        # Initial setting of attributes must use the base method to avoid recursion
        if key in ["_new_state", "_old_state"]:
            super().__setattr__(key, value)
        else:
            ctx = ReportThread.get_report_ctx()
            if key in ctx.widget_ids_this_run:
                raise StreamlitAPIException(
                    "Setting the value of a widget after its creation is disallowed"
                )
            else:
                self._new_state[key] = value

    def has_var_set(self, key: str) -> bool:
        return key in self

    def init_value(self, key: str, default_value: Any) -> None:
        if not self.has_var_set(key):
            self._new_state[key] = default_value

    def init_values(self, **kwargs) -> None:
        for key, value in kwargs.items():
            self.init_value(key, value)

    def __str__(self):
        return str({**self._old_state, **self._new_state})

    def __getitem__(self, key: str) -> Any:
        try:
            return self._new_state[key]
        except KeyError:
            value = beta_widget_value(key)
            if value is not None:
                return value
            else:
                try:
                    return self._old_state[key]
                except KeyError:
                    raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        ctx = ReportThread.get_report_ctx()
        if key in ctx.widget_ids_this_run:
            raise StreamlitAPIException(
                "Setting the value of a widget after its creation is disallowed"
            )
        self._new_state[key] = value

    def make_state_old(self) -> None:
        self._old_state.update(self._new_state)
        self._new_state.clear()

    def is_new_value(self, key: str) -> bool:
        return key in self._new_state


def get_current_session() -> "ReportSession":
    # Getting the session id easily comes fromt he report context, which is
    # a little weird, but a precedent that has been set.
    ctx = ReportThread.get_report_ctx()
    this_session: Optional["ReportSession"] = None

    from streamlit.server.server import Server

    if ctx is not None:
        this_session = Server.get_current().get_session_by_id(ctx.session_id)

    if this_session is None:
        raise RuntimeError(
            "We were unable to retrieve your Streamlit session. "
            + "Is your application utilizing threads? It's possible that could "
            + "be conflicting with our system."
        )

    return this_session


def get_session_state(**kwargs) -> SessionState:
    """Gets a SessionState object for the current session.
    Creates a new object if necessary.

    Parameters
    ----------
    **kwargs : any
        Default values you want to add to the session state, if we're creating a
        new one.
    Example
    -------
    >>> session_state = st.beta_session_state(user_name='', favorite_color='black')
    >>> session_state.user_name
    ''
    >>> session_state.user_name = 'Mary'
    >>> session_state.favorite_color
    'black'
    Since you set user_name above, next time your script runs this will be the
    result:
    >>> session_state = st.beta_session_state(user_name='', favorite_color='black')
    >>> session_state.user_name
    'Mary'
    """
    this_session = get_current_session()
    this_session_state = this_session.get_session_state()
    if this_session_state is None:
        this_session_state = SessionState()
        this_session_state.init_values(**kwargs)
        this_session.initialize_session_state(this_session_state)
    else:
        this_session_state.init_values(**kwargs)

    return this_session_state
