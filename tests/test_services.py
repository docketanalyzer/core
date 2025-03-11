from docketanalyzer_core import env, load_elastic


def test_elastic_connection():
    """Test the elasticsearch service."""

    assert bool(env.ELASTIC_URL), "ELASTIC_URL is not set"

    es = load_elastic()
    assert es.ping(), "Elasticsearch could not connect"
