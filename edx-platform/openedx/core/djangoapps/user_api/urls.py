"""
Defines the URL routes for this app.
"""

from django.conf import settings
from django.conf.urls import patterns, url

from ..profile_images.views import ProfileImageView
from .accounts.views import AccountDeactivationView, AccountViewSet
from .preferences.views import PreferencesView, PreferencesDetailView
from .verification_api.views import PhotoVerificationStatusView

ME = AccountViewSet.as_view({
    'get': 'get',
})

ACCOUNT_LIST = AccountViewSet.as_view({
    'get': 'list',
})

ACCOUNT_DETAIL = AccountViewSet.as_view({
    'get': 'retrieve',
    'patch': 'partial_update',
})

urlpatterns = patterns(
    '',
    url(r'^v1/me$', ME, name='own_username_api'),
    url(r'^v1/accounts/{}$'.format(settings.USERNAME_PATTERN), ACCOUNT_DETAIL, name='accounts_api'),
    url(r'^v1/accounts$', ACCOUNT_LIST, name='accounts_detail_api'),
    url(
        r'^v1/accounts/{}/image$'.format(settings.USERNAME_PATTERN),
        ProfileImageView.as_view(),
        name='accounts_profile_image_api'
    ),
    url(
        r'^v1/accounts/{}/deactivate/$'.format(settings.USERNAME_PATTERN),
        AccountDeactivationView.as_view(),
        name='accounts_deactivation'
    ),
    url(
        r'^v1/accounts/{}/verification_status/$'.format(settings.USERNAME_PATTERN),
        PhotoVerificationStatusView.as_view(),
        name='verification_status'
    ),
    url(
        r'^v1/preferences/{}$'.format(settings.USERNAME_PATTERN),
        PreferencesView.as_view(),
        name='preferences_api'
    ),
    url(
        r'^v1/preferences/{}/(?P<preference_key>[a-zA-Z0-9_]+)$'.format(settings.USERNAME_PATTERN),
        PreferencesDetailView.as_view(),
        name='preferences_detail_api'
    ),
)
