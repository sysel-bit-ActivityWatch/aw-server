from concurrent.futures import ThreadPoolExecutor
from functools import partial

import pytest
from aw_datastore.storages.peewee import PeeweeStorage
from aw_server.server import AWFlask


@pytest.fixture
def sqlite_app(tmp_path, monkeypatch):
    monkeypatch.setattr('aw_datastore.storages.peewee.get_data_dir', lambda *args: str(tmp_path))
    application = AWFlask(
        '127.0.0.1', testing=True,
        storage_method=partial(PeeweeStorage, filepath=str(tmp_path / 'events.db')),
    )
    database = application.api.db.storage_strategy.db
    database.close()
    return application, database


def test_request_threads_release_sqlite_connections(sqlite_app):
    app, database = sqlite_app

    def request(_):
        with app.test_client() as client:
            assert client.get('/api/0/buckets/').status_code == 200
        assert database.is_closed()

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(request, range(80)))


def test_failed_request_releases_sqlite_connection(sqlite_app):
    app, database = sqlite_app

    @app.route('/failure')
    def failure():
        database.execute_sql('SELECT 1')
        raise RuntimeError('request failed')

    app.config['PROPAGATE_EXCEPTIONS'] = False
    with app.test_client() as client:
        assert client.get('/failure').status_code == 500
    assert database.is_closed()
