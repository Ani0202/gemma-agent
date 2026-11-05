"""Per-task monotonic ADK tool timing, usable by the Kaggle timing kernel.

No harness dependencies are imported until installation. Call IDs, rather than
names or merged trace response timestamps, identify overlapping executions.
"""
from contextvars import ContextVar
from dataclasses import dataclass, field
import time

current_timing = ContextVar('current_tool_timing', default=None)


@dataclass
class ToolTiming:
    pending: dict = field(default_factory=dict)
    seconds: dict = field(default_factory=dict)
    unmatched: int = 0
    completed: set = field(default_factory=set)

    def before(self, call_id, name):
        if not call_id:
            self.unmatched += 1
            return
        if call_id in self.pending or call_id in self.completed:
            self.unmatched += 1
            return
        self.pending[call_id] = (name, time.monotonic())

    def after(self, call_id):
        # Error callbacks may be followed by after_tool_callback on recovery.
        if call_id in self.completed:
            return
        item = self.pending.pop(call_id, None)
        if item is None:
            self.unmatched += 1
            return
        name, start = item
        elapsed = time.monotonic() - start
        stat = self.seconds.setdefault(name, dict(n=0, total=0.0, max=0.0))
        stat['n'] += 1
        stat['total'] += elapsed
        stat['max'] = max(stat['max'], elapsed)
        self.completed.add(call_id)

    def metrics(self):
        return dict(tool_seconds=self.seconds,
                    tool_calls_timed=sum(s['n'] for s in self.seconds.values()),
                    tool_seconds_unmatched=self.unmatched + len(self.pending))


def make_timing_plugin():
    from google.adk.plugins.base_plugin import BasePlugin

    class TimingPlugin(BasePlugin):
        def __init__(self):
            super().__init__(name='eval_tool_timing')

        async def before_tool_callback(self, *, tool, tool_args, tool_context):
            state = current_timing.get()
            if state is not None:
                state.before(tool_context.function_call_id, tool.name)

        async def after_tool_callback(self, *, tool, tool_args, tool_context, result):
            state = current_timing.get()
            if state is not None:
                state.after(tool_context.function_call_id)

        async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
            state = current_timing.get()
            if state is not None:
                state.after(tool_context.function_call_id)

    return TimingPlugin()


def install_harness_timing():
    """Installed swegemma builds an App with plugins; prepend ours to that list.

    Prepending ensures timing runs before any error-recovery callback short
    circuits the plugin chain. It also covers MCP and agent_tool subclasses.
    Returns a restoration function for callers embedding the runner.
    """
    import swegemma.harness.agent_runner as ar
    original = ar.App

    def app(*args, **kwargs):
        kwargs['plugins'] = [make_timing_plugin(), *kwargs.get('plugins', [])]
        return original(*args, **kwargs)

    ar.App = app

    def restore():
        ar.App = original

    return restore
