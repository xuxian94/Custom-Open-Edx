"""Tests covering edX API utilities."""
# pylint: disable=missing-docstring
import json

from django.core.cache import cache
from django.test.utils import override_settings
import httpretty
import mock
from nose.plugins.attrib import attr
from edx_oauth2_provider.tests.factories import ClientFactory
from provider.constants import CONFIDENTIAL

from openedx.core.djangoapps.catalog.models import CatalogIntegration
from openedx.core.djangoapps.catalog.tests.mixins import CatalogIntegrationMixin
from openedx.core.djangoapps.catalog.utils import create_catalog_api_client
from openedx.core.djangoapps.credentials.models import CredentialsApiConfig
from openedx.core.djangoapps.credentials.tests.mixins import CredentialsApiConfigMixin
from openedx.core.djangolib.testing.utils import CacheIsolationTestCase, skip_unless_lms
from openedx.core.lib.edx_api_utils import get_edx_api_data
from student.tests.factories import UserFactory


UTILITY_MODULE = 'openedx.core.lib.edx_api_utils'
TEST_API_URL = 'http://www-internal.example.com/api'


@skip_unless_lms
@attr(shard=2)
@httpretty.activate
class TestGetEdxApiData(CatalogIntegrationMixin, CredentialsApiConfigMixin, CacheIsolationTestCase):
    """Tests for edX API data retrieval utility."""
    ENABLED_CACHES = ['default']

    def setUp(self):
        super(TestGetEdxApiData, self).setUp()

        self.user = UserFactory()

        cache.clear()

    def _mock_catalog_api(self, responses, url=None):
        self.assertTrue(httpretty.is_enabled(), msg='httpretty must be enabled to mock Catalog API calls.')

        url = url if url else CatalogIntegration.current().internal_api_url.strip('/') + '/programs/'

        httpretty.register_uri(httpretty.GET, url, responses=responses)

    def _assert_num_requests(self, count):
        """DRY helper for verifying request counts."""
        self.assertEqual(len(httpretty.httpretty.latest_requests), count)

    def test_get_unpaginated_data(self):
        """Verify that unpaginated data can be retrieved."""
        catalog_integration = self.create_catalog_integration()
        api = create_catalog_api_client(self.user, catalog_integration)

        expected_collection = ['some', 'test', 'data']
        data = {
            'next': None,
            'results': expected_collection,
        }

        self._mock_catalog_api(
            [httpretty.Response(body=json.dumps(data), content_type='application/json')]
        )

        with mock.patch('openedx.core.lib.edx_api_utils.EdxRestApiClient.__init__') as mock_init:
            actual_collection = get_edx_api_data(catalog_integration, self.user, 'programs', api=api)

            # Verify that the helper function didn't initialize its own client.
            self.assertFalse(mock_init.called)
            self.assertEqual(actual_collection, expected_collection)

        # Verify the API was actually hit (not the cache)
        self._assert_num_requests(1)

    def test_get_paginated_data(self):
        """Verify that paginated data can be retrieved."""
        catalog_integration = self.create_catalog_integration()
        api = create_catalog_api_client(self.user, catalog_integration)

        expected_collection = ['some', 'test', 'data']
        url = CatalogIntegration.current().internal_api_url.strip('/') + '/programs/?page={}'

        responses = []
        for page, record in enumerate(expected_collection, start=1):
            data = {
                'next': url.format(page + 1) if page < len(expected_collection) else None,
                'results': [record],
            }

            body = json.dumps(data)
            responses.append(
                httpretty.Response(body=body, content_type='application/json')
            )

        self._mock_catalog_api(responses)

        actual_collection = get_edx_api_data(catalog_integration, self.user, 'programs', api=api)
        self.assertEqual(actual_collection, expected_collection)

        self._assert_num_requests(len(expected_collection))

    def test_get_specific_resource(self):
        """Verify that a specific resource can be retrieved."""
        catalog_integration = self.create_catalog_integration()
        api = create_catalog_api_client(self.user, catalog_integration)

        resource_id = 1
        url = '{api_root}/programs/{resource_id}/'.format(
            api_root=CatalogIntegration.current().internal_api_url.strip('/'),
            resource_id=resource_id,
        )

        expected_resource = {'key': 'value'}

        self._mock_catalog_api(
            [httpretty.Response(body=json.dumps(expected_resource), content_type='application/json')],
            url=url
        )

        actual_resource = get_edx_api_data(catalog_integration, self.user, 'programs', api=api, resource_id=resource_id)
        self.assertEqual(actual_resource, expected_resource)

        self._assert_num_requests(1)

    def test_cache_utilization(self):
        """Verify that when enabled, the cache is used."""
        catalog_integration = self.create_catalog_integration(cache_ttl=5)
        api = create_catalog_api_client(self.user, catalog_integration)

        expected_collection = ['some', 'test', 'data']
        data = {
            'next': None,
            'results': expected_collection,
        }

        self._mock_catalog_api(
            [httpretty.Response(body=json.dumps(data), content_type='application/json')],
        )

        resource_id = 1
        url = '{api_root}/programs/{resource_id}/'.format(
            api_root=CatalogIntegration.current().internal_api_url.strip('/'),
            resource_id=resource_id,
        )

        expected_resource = {'key': 'value'}

        self._mock_catalog_api(
            [httpretty.Response(body=json.dumps(expected_resource), content_type='application/json')],
            url=url
        )

        cache_key = CatalogIntegration.current().CACHE_KEY

        # Warm up the cache.
        get_edx_api_data(catalog_integration, self.user, 'programs', api=api, cache_key=cache_key)
        get_edx_api_data(
            catalog_integration, self.user, 'programs', api=api, resource_id=resource_id, cache_key=cache_key
        )

        # Hit the cache.
        actual_collection = get_edx_api_data(catalog_integration, self.user, 'programs', api=api, cache_key=cache_key)
        self.assertEqual(actual_collection, expected_collection)

        actual_resource = get_edx_api_data(
            catalog_integration, self.user, 'programs', api=api, resource_id=resource_id, cache_key=cache_key
        )
        self.assertEqual(actual_resource, expected_resource)

        # Verify that only two requests were made, not four.
        self._assert_num_requests(2)

    @mock.patch(UTILITY_MODULE + '.log.warning')
    def test_api_config_disabled(self, mock_warning):
        """Verify that no data is retrieved if the provided config model is disabled."""
        catalog_integration = self.create_catalog_integration(enabled=False)

        actual = get_edx_api_data(catalog_integration, self.user, 'programs')

        self.assertTrue(mock_warning.called)
        self.assertEqual(actual, [])

    @mock.patch('edx_rest_api_client.client.EdxRestApiClient.__init__')
    @mock.patch(UTILITY_MODULE + '.log.exception')
    def test_client_initialization_failure(self, mock_exception, mock_init):
        """Verify that an exception is logged when the API client fails to initialize."""
        mock_init.side_effect = Exception

        catalog_integration = self.create_catalog_integration()

        actual = get_edx_api_data(catalog_integration, self.user, 'programs')

        self.assertTrue(mock_exception.called)
        self.assertEqual(actual, [])

    @mock.patch(UTILITY_MODULE + '.log.exception')
    def test_data_retrieval_failure(self, mock_exception):
        """Verify that an exception is logged when data can't be retrieved."""
        catalog_integration = self.create_catalog_integration()
        api = create_catalog_api_client(self.user, catalog_integration)

        self._mock_catalog_api(
            [httpretty.Response(body='clunk', content_type='application/json', status_code=500)]
        )

        actual = get_edx_api_data(catalog_integration, self.user, 'programs', api=api)

        self.assertTrue(mock_exception.called)
        self.assertEqual(actual, [])

    def test_api_client_not_provided(self):
        """Verify that an API client doesn't need to be provided."""
        ClientFactory(name=CredentialsApiConfig.OAUTH2_CLIENT_NAME, client_type=CONFIDENTIAL)

        credentials_api_config = self.create_credentials_config()

        with mock.patch('openedx.core.lib.edx_api_utils.EdxRestApiClient.__init__') as mock_init:
            get_edx_api_data(credentials_api_config, self.user, 'credentials')
            self.assertTrue(mock_init.called)
