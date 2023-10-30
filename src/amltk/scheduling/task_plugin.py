"""This module contains the TaskPlugin class."""
from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from itertools import chain
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Generic, Iterable, TypeVar
from typing_extensions import ParamSpec, Self, override

from amltk.events import Event

if TYPE_CHECKING:
    from amltk.scheduling.task import Task

P = ParamSpec("P")
R = TypeVar("R")
TrialInfo = TypeVar("TrialInfo")


class TaskPlugin(ABC):
    """A plugin that can be attached to a Task.

    By inheriting from a `TaskPlugin`, you can hook into a
    [`Task`][amltk.scheduling.Task]. A plugin can affect, modify and extend its
    behaviours. Please see the documentation of the methods for more information.
    Creating a plugin is only necesary if you need to modify actual behaviour of
    the task. For siply hooking into the lifecycle of a task, you can use the events
    that a [`Task`][amltk.scheduling.Task] emits.

    For an example of a simple plugin, see the
    [`CallLimiter`][amltk.scheduling.CallLimiter] plugin which prevents
    the task being submitted if for example, it has already been submitted
    too many times.

    All methods are optional, and you can choose to implement only the ones
    you need. Most plugins will likely need to implement the
    [`attach_task()`][amltk.scheduling.TaskPlugin.attach_task] method, which is called
    when the plugin is attached to a task. In this method, you can for
    example subscribe to events on the task, create new subscribers for people
    to use or even store a reference to the task for later use.

    Plugins are also encouraged to utilize the events of a
    [`Task`][amltk.scheduling.Task] to further hook into the lifecycle of the task.
    For exampe, by saving a reference to the task in the `attach_task()` method, you
    can use the [`emit()`][amltk.scheduling.Task] method of the task to emit
    your own specialized events.

    !!! note "Methods"

        * [`attach_task()`][amltk.scheduling.TaskPlugin.attach_task]
        * [`pre_submit()`][amltk.scheduling.TaskPlugin.pre_submit]
    """

    name: ClassVar[str]
    """The name of the plugin.

    This is used to identify the plugin during logging.
    """

    def attach_task(self, task: Task) -> None:  # noqa: B027
        """Attach the plugin to a task.

        This method is called when the plugin is attached to a task. This
        is the place to subscribe to events on the task, create new subscribers
        for people to use or even store a reference to the task for later use.

        Args:
            task: The task the plugin is being attached to.
        """

    def pre_submit(
        self,
        fn: Callable[P, R],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> tuple[Callable[P, R], tuple, dict] | None:
        """Pre-submit hook.

        This method is called before the task is submitted.

        Args:
            fn: The task function.
            *args: The arguments to the task function.
            **kwargs: The keyword arguments to the task function.

        Returns:
            A tuple of the task function, arguments and keyword arguments
            if the task should be submitted, or `None` if the task should
            not be submitted.
        """
        return fn, args, kwargs

    def events(self) -> list[Event]:
        """Return a list of events that this plugin emits.

        Likely no need to override this method, as it will automatically
        return all events defined on the plugin.
        """
        inherited_attrs = chain.from_iterable(
            vars(cls).values() for cls in self.__class__.__mro__
        )
        return [attr for attr in inherited_attrs if isinstance(attr, Event)]

    @abstractmethod
    def copy(self) -> Self:
        """Return a copy of the plugin.

        This method is used to create a copy of the plugin when a task is
        copied. This is useful if the plugin stores a reference to the task
        it is attached to, as the copy will need to store a reference to the
        copy of the task.
        """
        ...


class CallLimiter(TaskPlugin):
    """A plugin that limits the submission of a task.

    Adds three new events to the task:

    * [`CALL_LIMIT_REACHED`][amltk.scheduling.CallLimiter.CALL_LIMIT_REACHED]
        - subscribe with `@task.on("call-limit-reached")`
    * [`CONCURRENT_LIMIT_REACHED`][amltk.scheduling.CallLimiter.CONCURRENT_LIMIT_REACHED]
        - subscribe with `@task.on("concurrent-limit-reached")`
    * [`DISABLED_DUE_TO_RUNNING_TASK`][amltk.scheduling.CallLimiter.DISABLED_DUE_TO_RUNNING_TASK]
        - subscribe with `@task.on("disabled-due-to-running-task")`
    """  # noqa: E501

    name: ClassVar = "call-limiter"
    """The name of the plugin."""

    CALL_LIMIT_REACHED: Event[...] = Event("call-limit-reached")
    """The event emitted when the task has reached its call limit.

    Will call any subscribers with the task as the first argument,
    followed by the arguments and keyword arguments that were passed to the task.

    ```python
    @task.on("call-limit-reached")
    def on_call_limit_reached(task: Task, *args, **kwargs):
        ...
    ```
    """

    CONCURRENT_LIMIT_REACHED: Event[...] = Event("concurrent-limit-reached")
    """The event emitted when the task has reached its concurrent call limit.

    Will call any subscribers with the task as the first argument, followed by the
    arguments and keyword arguments that were passed to the task.

    ```python
    @task.on("concurrent-limit-reached")
    def on_concurrent_limit_reached(task: Task, *args, **kwargs):
        ...
    ```
    """

    DISABLED_DUE_TO_RUNNING_TASK: Event[...] = Event("disabled-due-to-running-task")
    """The event emitter when the task was not submitted due to some other
    running task.

    Will call any subscribers with the task as first argument, followed by
    the arguments and keyword arguments that were passed to the task.

    ```python
    @task.on("disabled-due-to-running-task")
    def on_disabled_due_to_running_task(task: Task, *args, **kwargs):
        ...
    ```
    """

    def __init__(
        self,
        *,
        max_calls: int | None = None,
        max_concurrent: int | None = None,
        not_while_running: Task | Iterable[Task] | None = None,
    ):
        """Initialize the plugin.

        Args:
            max_calls: The maximum number of calls to the task.
            max_concurrent: The maximum number of calls of this task that can
                be in the queue.
            not_while_running: A task or iterable of tasks that if active, will prevent
                this task from being submitted.
        """
        super().__init__()

        if not_while_running is None:
            not_while_running = []
        elif isinstance(not_while_running, Iterable):
            not_while_running = list(not_while_running)
        else:
            not_while_running = [not_while_running]

        self.max_calls = max_calls
        self.max_concurrent = max_concurrent
        self.not_while_running = not_while_running
        self.task: Task | None = None

        if isinstance(max_calls, int) and not max_calls > 0:
            raise ValueError("max_calls must be greater than 0")

        if isinstance(max_concurrent, int) and not max_concurrent > 0:
            raise ValueError("max_concurrent must be greater than 0")

        self._calls = 0
        self._concurrent = 0

    @override
    def attach_task(self, task: Task) -> None:
        """Attach the plugin to a task."""
        self.task = task

        if self.task in self.not_while_running:
            raise ValueError(
                f"Task {self.task} was found in the {self.not_while_running=}"
                " list. This is disabled but please raise an issue if you think this"
                " has sufficient use case.",
            )

        task.emitter.add_event(
            self.CALL_LIMIT_REACHED,
            self.CONCURRENT_LIMIT_REACHED,
            self.DISABLED_DUE_TO_RUNNING_TASK,
        )

        # Make sure to increment the count when a task was submitted
        task.on_submitted(self._increment_call_count, hidden=True)

    @override
    def pre_submit(
        self,
        fn: Callable[P, R],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> tuple[Callable[P, R], tuple, dict] | None:
        """Pre-submit hook.

        Prevents submission of the task if it exceeds any of the set limits.
        """
        assert self.task is not None

        if self.max_calls is not None and self._calls >= self.max_calls:
            self.task.emitter.emit(self.CALL_LIMIT_REACHED, self.task, *args, **kwargs)
            return None

        if (
            self.max_concurrent is not None
            and len(self.task.queue) >= self.max_concurrent
        ):
            self.task.emitter.emit(
                self.CONCURRENT_LIMIT_REACHED,
                self.task,
                *args,
                **kwargs,
            )
            return None

        for other_task in self.not_while_running:
            if other_task.running():
                self.task.emitter.emit(
                    self.DISABLED_DUE_TO_RUNNING_TASK,
                    other_task,
                    self.task,
                    *args,
                    **kwargs,
                )
                return None

        return fn, args, kwargs

    @override
    def copy(self) -> Self:
        """Return a copy of the plugin."""
        return self.__class__(
            max_calls=self.max_calls,
            max_concurrent=self.max_concurrent,
        )

    def _increment_call_count(self, *_: Any, **__: Any) -> None:
        self._calls += 1


class _IgnoreWarningWrapper(Generic[P, R]):
    """A wrapper to ignore warnings."""

    def __init__(
        self,
        fn: Callable[P, R],
        *warning_args: Any,
        **warning_kwargs: Any,
    ):
        """Initialize the wrapper.

        Args:
            fn: The function to wrap.
            *warning_args: arguments to pass to
                [`warnings.filterwarnings`][warnings.filterwarnings].
            **warning_kwargs: keyword arguments to pass to
                [`warnings.filterwarnings`][warnings.filterwarnings].
        """
        super().__init__()
        self.fn = fn
        self.warning_args = warning_args
        self.warning_kwargs = warning_kwargs

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        with warnings.catch_warnings():
            warnings.filterwarnings(*self.warning_args, **self.warning_kwargs)
            return self.fn(*args, **kwargs)


class WarningFilterPlugin(TaskPlugin):
    """A plugin that disables warnings emitted from tasks."""

    name: ClassVar = "warning-filter"
    """The name of the plugin."""

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the plugin.

        Args:
            *args: arguments to pass to
                [`warnings.filterwarnings`][warnings.filterwarnings].
            **kwargs: keyword arguments to pass to
                [`warnings.filterwarnings`][warnings.filterwarnings].
        """
        super().__init__()
        self.task: Task | None = None
        self.warning_args = args
        self.warning_kwargs = kwargs

    @override
    def attach_task(self, task: Task) -> None:
        """Attach the plugin to a task."""
        self.task = task

    @override
    def pre_submit(
        self,
        fn: Callable[P, R],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> tuple[Callable[P, R], tuple, dict]:
        """Pre-submit hook.

        Wraps the function to ignore warnings.
        """
        wrapped_f = _IgnoreWarningWrapper(fn, *self.warning_args, **self.warning_kwargs)
        return wrapped_f, args, kwargs

    @override
    def copy(self) -> Self:
        """Return a copy of the plugin."""
        return self.__class__(*self.warning_args, **self.warning_kwargs)
