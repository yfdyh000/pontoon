import os
import tempfile

from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.test import TestCase as BaseTestCase

import factory
from django_browserid.tests import mock_browserid
from django_nose.tools import assert_equal
from factory import LazyAttribute, Sequence, SubFactory, SelfAttribute
from factory.django import DjangoModelFactory
from mock import patch

from pontoon.base.models import (
    ChangedEntityLocale,
    Entity,
    Locale,
    Project,
    Repository,
    Resource,
    Stats,
    Subpage,
    Translation,
)


class TestCase(BaseTestCase):
    def client_login(self, user=None):
        """
        Authenticate the test client as the given user. If no user is
        given, a test user is created and returned.
        """
        if user is None:
            user = UserFactory.create()

        with mock_browserid(user.email):
            self.client.login(assertion='asdf', audience='asdf')

        return user

    def patch(self, *args, **kwargs):
        """
        Wrapper around mock.patch that automatically cleans up the patch
        in the test cleanup phase.
        """
        patch_obj = patch(*args, **kwargs)
        self.addCleanup(patch_obj.stop)
        return patch_obj.start()

    def patch_object(self, *args, **kwargs):
        """
        Wrapper around mock.patch.object that automatically cleans up
        the patch in the test cleanup phase.
        """
        patch_obj = patch.object(*args, **kwargs)
        self.addCleanup(patch_obj.stop)
        return patch_obj.start()


class UserFactory(DjangoModelFactory):
    username = Sequence(lambda n: 'test%s' % n)
    email = Sequence(lambda n: 'test%s@example.com' % n)

    class Meta:
        model = User


class ProjectFactory(DjangoModelFactory):
    name = Sequence(lambda n: 'Project {0}'.format(n))
    slug = LazyAttribute(lambda p: slugify(p.name))
    links = False

    class Meta:
        model = Project

    @factory.post_generation
    def locales(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for locale in extracted:
                self.locales.add(locale)

    @factory.post_generation
    def repositories(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted is not None:
            for repository in extracted:
                self.repositories.add(repository)
        else:  # Default to a single valid repo.
            self.repositories.add(RepositoryFactory.build())


class RepositoryFactory(DjangoModelFactory):
    project = SubFactory(ProjectFactory)
    type = Repository.GIT
    url = Sequence(lambda n: 'https://example.com/url_{0}.git'.format(n))

    class Meta:
        model = Repository


class ResourceFactory(DjangoModelFactory):
    project = SubFactory(ProjectFactory)
    path = '/fake/path.po'
    format = 'po'
    entity_count = 1

    class Meta:
        model = Resource


class LocaleFactory(DjangoModelFactory):
    code = Sequence(lambda n: 'en-{0}'.format(n))
    name = Sequence(lambda n: 'English #{0}'.format(n))

    class Meta:
        model = Locale


class EntityFactory(DjangoModelFactory):
    resource = SubFactory(ResourceFactory)
    string = Sequence(lambda n: 'string {0}'.format(n))

    class Meta:
        model = Entity


class ChangedEntityLocaleFactory(DjangoModelFactory):
    entity = SubFactory(EntityFactory)
    locale = SubFactory(LocaleFactory)

    class Meta:
        model = ChangedEntityLocale


class TranslationFactory(DjangoModelFactory):
    entity = SubFactory(EntityFactory)
    locale = SubFactory(LocaleFactory)
    string = Sequence(lambda n: 'translation {0}'.format(n))
    user = SubFactory(UserFactory)

    class Meta:
        model = Translation


class IdenticalTranslationFactory(TranslationFactory):
    entity = SubFactory(EntityFactory, string=SelfAttribute('..string'))


class StatsFactory(DjangoModelFactory):
    resource = SubFactory(ResourceFactory)
    locale = SubFactory(LocaleFactory)

    class Meta:
        model = Stats


class SubpageFactory(DjangoModelFactory):
    project = SubFactory(ProjectFactory)
    name = Sequence(lambda n: 'subpage {0}'.format(n))

    class Meta:
        model = Subpage

    @factory.post_generation
    def resources(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for resource in extracted:
                self.resources.add(resource)


def assert_redirects(response, expected_url, status_code=302, host=None):
    """
    Assert that the given response redirects to the expected URL.

    The main difference between this and TestCase.assertRedirects is
    that this version doesn't follow the redirect.
    """
    host = host or 'http://testserver'
    assert_equal(response.status_code, status_code)
    assert_equal(response['Location'], host + expected_url)


def assert_attributes_equal(original, **expected_attrs):
    """
    Assert that the given object has attributes matching the given
    values.
    """
    if not expected_attrs:
        raise ValueError('Expected some attributes to check.')
    for key, value in expected_attrs.items():
        original_value = getattr(original, key)
        assert_equal(
            original_value,
            value,
            ('Attribute `{key}` does not match: {original_value} != {value}'
             .format(key=key, original_value=original_value, value=value)),
        )

class NOT(object):
    """
    A helper class that compares equal to everything except its given
    values.

    >>> mock_function('foobarbaz')
    >>> mock_function.assert_called_with(NOT('fizzbarboff'))  # Passes
    >>> mock_function.assert_called_with(NOT('foobarbaz'))  # Fails
    """
    def __init__(self, *values):
        self.values = values

    def __eq__(self, other):
        return other not in self.values

    def __ne__(self, other):
        return other in self.values

    def __repr__(self):
        return '<NOT %r>' % self.values


class CONTAINS(object):
    """
    Helper class that is considered equal to any object that contains
    elements the elements passed to it.

    Used mostly in conjunction with Mock.assert_called_with to test if
    a string argument contains certain substrings:

    >>> mock_function('foobarbaz')
    >>> mock_function.assert_called_with(CONTAINS('bar'))  # Passes
    """
    def __init__(self, *args):
        self.items = args

    def __eq__(self, other):
        return all(item in other for item in self.items)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '<CONTAINS {0}>'.format(','.join(repr(item) for item in self.items))


def create_tempfile(contents):
    """
    Create a temporary file with the given contents, and return the path
    to the created file.
    """
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as f:
        f.write(contents)
    return path
