"""Offline Docker-order and wheel-cache contracts using fake harness modules."""
import importlib.metadata
import io
import sys
import tarfile
from types import ModuleType, SimpleNamespace

import pytest

from eval import sandbox_env as env


@pytest.fixture
def local_setup(tmp_path, monkeypatch):
    events = []
    original = lambda *args, **kwargs: events.append(('docker', args, kwargs))
    names = ['swegemma', 'swegemma.harness', 'swegemma.harness.container_setup',
             'swegemma.harness.verification', 'swegemma.harness.sample_verification',
             'swegemma.evaluate', 'swegemma.cli', 'swegemma.harness.agent_runner']
    for name in names:
        module = ModuleType(name)
        monkeypatch.setitem(sys.modules, name, module)
        if '.' in name:
            parent, attr = name.rsplit('.', 1)
            setattr(sys.modules[parent], attr, module)
    cs = sys.modules['swegemma.harness.container_setup']
    cs.install_test_dependencies = original
    monkeypatch.setattr(importlib.metadata, 'version', lambda name: 'fake-0.2.11')
    monkeypatch.delenv('GOLD_PROBE_LOG', raising=False)
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    (wheels / 'a-1-py3-none-any.whl').write_bytes(b'wheel a')
    site = tmp_path / 'venv/lib/python3.13/site-packages'
    site.mkdir(parents=True)
    cs._WHEEL_INDEX_CACHE = {str(wheels.resolve()): 'stale index'}

    def inspect(path):
        assert path == wheels
        assert str(wheels.resolve()) not in cs._WHEEL_INDEX_CACHE
        events.append(('inspect',))
        return sorted(path.glob('*.whl')), {}, {}, {}

    def build(selected, cache_key, marker_name):
        events.append(('build', cache_key, tuple(p.name for p in selected)))
        archive = tmp_path / (cache_key + '.tar')
        if not archive.exists():
            with tarfile.open(archive, 'w') as tf:
                for name, content in [(p.name + '.payload', p.read_bytes()) for p in selected] + [(marker_name, b'ok\n')]:
                    info = tarfile.TarInfo(name)
                    info.size = len(content)
                    tf.addfile(info, io.BytesIO(content))
        return archive

    cs._inspect_wheels_dir = inspect
    cs._build_unpacked_wheels_tar = build

    class SubprocessManager:
        sandboxes = {'id': {'venv': tmp_path / 'venv'}}

        def exec(self, sid, command, **kwargs):
            events.append(('exec', command, kwargs))
            # Even a failed editable attempt must be followed by injection.
            return SimpleNamespace(exit_code=1)

        def copy_to(self, sid, source, destination):
            events.append(('copy', destination))

    install = env.patch_subprocess_deps(tmp_path)
    return SimpleNamespace(install=install, manager=SubprocessManager(), cs=cs,
                           wheels=wheels, site=site, events=events)


def test_editable_precedes_injection_and_setup_without_pip_environment(local_setup):
    s = local_setup
    s.install(s.manager, 'id', 'org/package')
    assert [e[0] for e in s.events] == ['exec', 'inspect', 'build', 'copy', 'exec']
    assert s.events[0] == ('exec',
        'pip install --no-index --find-links=/wheels --no-build-isolation --no-deps -e /workspace 2>/dev/null || true', {})
    assert s.events[-1] == ('exec', 'python3 /tmp/setup.py --fast-path org/package', {'timeout': 280})
    assert all('PIP_' not in e[1] for e in s.events if e[0] == 'exec')
    assert (s.site / 'a-1-py3-none-any.whl.payload').read_bytes() == b'wheel a'


def test_base_cache_key_is_stable_and_tracks_wheel_identity(tmp_path):
    a, b = tmp_path / 'a.whl', tmp_path / 'b.whl'
    a.write_bytes(b'a')
    b.write_bytes(b'bb')
    key = env.base_cache_key([a, b], 'v1')
    assert key == env.base_cache_key([b, a], 'v1')
    assert key == env.base_cache_key([a, b], 'v1')
    assert key != env.base_cache_key([a, b], 'v2')
    a.write_bytes(b'aa')
    assert key != env.base_cache_key([a, b], 'v1')
    a.write_bytes(b'a')
    a = a.rename(tmp_path / 'renamed.whl')
    assert key != env.base_cache_key([a, b], 'v1')


def test_matching_marker_skips_archive_and_extraction(local_setup):
    s = local_setup
    key = env.base_cache_key(list(s.wheels.glob('*.whl')), 'fake-0.2.11')
    (s.site / '.swegemma_base_injected').write_text(key)
    s.install(s.manager, 'id')
    assert [e[0] for e in s.events] == ['exec', 'inspect', 'copy', 'exec']
    assert not list(s.site.glob('*.payload'))


@pytest.mark.parametrize('marker_value', ['ok\n', 'different-wheel-set'])
def test_stale_marker_is_replaced_after_injection(local_setup, marker_value):
    s = local_setup
    marker = s.site / '.swegemma_base_injected'
    marker.write_text(marker_value)
    s.install(s.manager, 'id')
    assert marker.read_text() == env.base_cache_key(list(s.wheels.glob('*.whl')), 'fake-0.2.11')
    assert any(e[0] == 'build' for e in s.events)


@pytest.mark.parametrize('change', ['size', 'name'])
def test_changed_wheelhouse_uses_new_archive_and_reinjects(local_setup, change):
    s = local_setup
    s.install(s.manager, 'id')
    first_key = (s.site / '.swegemma_base_injected').read_text()
    wheel = next(s.wheels.glob('*.whl'))
    if change == 'size':
        wheel.write_bytes(b'new larger wheel')
    else:
        wheel = wheel.rename(s.wheels / 'renamed-1-py3-none-any.whl')
    s.cs._WHEEL_INDEX_CACHE[str(s.wheels.resolve())] = 'stale index'
    s.install(s.manager, 'id')
    builds = [e for e in s.events if e[0] == 'build']
    assert len(builds) == 2 and builds[0][1] != builds[1][1]
    assert (s.site / '.swegemma_base_injected').read_text() != first_key
    assert (s.site / (wheel.name + '.payload')).read_bytes() == wheel.read_bytes()


def test_docker_manager_still_uses_original_hook(local_setup):
    s = local_setup
    manager = object()
    s.install(manager, 'docker-id', 'org/package', fast_path=False, config='config')
    assert s.events == [('docker', (manager, 'docker-id', 'org/package'),
                         {'fast_path': False, 'config': 'config'})]
