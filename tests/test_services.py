from datetime import datetime
import pandas as pd
import peewee as pw
import pytest
from docketanalyzer_core import env, load_elastic, DatabaseModel, load_psql


@pytest.fixture(scope='session')
def dummy_data():
    """Create dummy data for testing."""

    data = pd.DataFrame({
        'email': ['alice@example.com', 'bob@example.com'],
        'age': [30, 25],
        'registration_date': [datetime(2020, 1, 1), datetime(2021, 1, 15)],
    })

    return data


@pytest.fixture(scope='session')
def db_with_test_table():
    """Create a test table in the database."""

    db = load_psql()

    try:
        db.drop_table('test_schemaless', confirm=False)
    except KeyError:
        pass

    db.create_table('test_schemaless')

    yield db

    db.drop_table('test_schemaless', confirm=False)
    db.close()


@pytest.fixture(scope='session')
def test_table_schema():
    """Create a test table schema."""

    class TestTable(DatabaseModel):
        email = pw.TextField(unique=True)
        age = pw.IntegerField()
        registration_date = pw.DateTimeField()

        class Meta:
            table_name = 'test_standard'
    
    db = load_psql()

    try:
        db.drop_table('test_standard', confirm=False)
    except KeyError:
        pass

    yield TestTable

    db.reload()
    db.drop_table('test_standard', confirm=False)
    db.close()


def test_elastic_connection():
    """Test the elasticsearch service."""

    assert bool(env.ELASTIC_URL), "ELASTIC_URL is not set"

    es = load_elastic()
    assert es.ping(), "Elasticsearch could not connect"


def test_psql_connection():
    """Test the Postgres service."""

    assert bool(env.POSTGRES_URL), "POSTGRES_URL is not set"
    
    db = load_psql()

    assert db.status(), "Postgres could not connect"


def test_psql_schemaless_table(dummy_data, db_with_test_table):
    """Test the schemaless table functionality."""

    db = db_with_test_table
    table = db.t.test_schemaless

    # Add columns to the table and reload
    table.add_column('email', column_type='TextField', unique=True)
    table.add_column('age', column_type='IntegerField')
    table.add_column('registration_date', column_type='DateTimeField')
    table = db.t.test_schemaless

    # Add data to the table
    table.add_data(dummy_data)

    # Make sure that adding duplicate data raises an IntegrityError
    error = None
    try:
        table.add_data(dummy_data)
    except Exception as e:
        error = e

    assert isinstance(error, pw.IntegrityError)

    # Test pandas functionality
    data = table.pandas()

    assert len(data) == 2

    # Test sample functionality
    data = table.sample(1).pandas()

    assert len(data) == 1

    # Test delete functionality
    table.where(table.email == 'bob@example.com').delete()

    data = table.pandas('email')['email'].tolist()

    assert len(data) == 1
    assert data[0] == 'alice@example.com'


def test_psql_standard_table(dummy_data, test_table_schema):
    """Test the standard table functionality."""

    TestTable = test_table_schema
    db = load_psql()

    # Register and create the table
    db.register_model(TestTable)
    db.create_table(TestTable)
    table = db.t.test_standard

    # Add data to the table using copy
    table.add_data(dummy_data, copy=True)

    data = table.pandas()

    assert len(data) == 2
    assert data['registration_date'].dtype == 'datetime64[ns]'
    assert data['age'].dtype == 'int64'
    assert data['email'].dtype == 'object'

    # Test batching functionality
    n = 0
    for batch in table.batch(1):
        assert len(batch) == 1
        n += 1
    assert n == 2

    db.close()
