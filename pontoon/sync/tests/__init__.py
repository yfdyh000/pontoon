import os.path

import factory
from mock import patch, PropertyMock

from pontoon.base.models import Project
from pontoon.base.tests import (
    EntityFactory,
    LocaleFactory,
    ProjectFactory,
    RepositoryFactory,
    ResourceFactory,
    TestCase,
    TranslationFactory,
)
from pontoon.base.utils import aware_datetime
from pontoon.sync.changeset import ChangeSet
from pontoon.sync.vcs_models import VCSEntity, VCSProject, VCSResource, VCSTranslation


FAKE_CHECKOUT_PATH = os.path.join(os.path.dirname(__file__), 'fake-checkout')


class VCSEntityFactory(factory.Factory):
    resource = None
    key = 'key'
    string = 'string'
    string_plural = ''
    comments = factory.List([])
    source = factory.List([])
    order = factory.Sequence(lambda n: n)

    class Meta:
        model = VCSEntity


class VCSTranslationFactory(factory.Factory):
    key = factory.Sequence(lambda n: 'key-{0}'.format(n))
    strings = factory.Dict({})
    comments = factory.List([])
    fuzzy = False

    class Meta:
        model = VCSTranslation


class FakeCheckoutTestCase(TestCase):
    """Parent class for tests that use the fake l10n repo checkout."""
    def setUp(self):
        timezone_patch = patch('pontoon.sync.core.timezone')
        self.mock_timezone = timezone_patch.start()
        self.addCleanup(timezone_patch.stop)
        self.mock_timezone.now.return_value = aware_datetime(1970, 1, 1)

        self.translated_locale = LocaleFactory.create(code='translated-locale')
        self.inactive_locale = LocaleFactory.create(code='inactive-locale')
        self.repository = RepositoryFactory()

        self.db_project = ProjectFactory.create(
            name='db-project',
            locales=[self.translated_locale],
            repositories=[self.repository]
        )
        self.main_db_resource = ResourceFactory.create(
            project=self.db_project,
            path='main.lang',
            format='lang'
        )
        self.other_db_resource = ResourceFactory.create(
            project=self.db_project,
            path='other.lang',
            format='lang'
        )
        self.missing_db_resource = ResourceFactory.create(
            project=self.db_project,
            path='missing.lang',
            format='lang'
        )
        self.main_db_entity = EntityFactory.create(
            resource=self.main_db_resource,
            string='Source String',
            key='Source String',
            obsolete=False
        )
        self.other_db_entity = EntityFactory.create(
            resource=self.other_db_resource,
            string='Other Source String',
            key='Other Source String',
            obsolete=False
        )
        self.main_db_translation = TranslationFactory.create(
            entity=self.main_db_entity,
            plural_form=None,
            locale=self.translated_locale,
            string='Translated String',
            date=aware_datetime(1970, 1, 1),
            approved=True,
            extra={'tags': []}
        )

        # Load paths from the fake locale directory.
        checkout_path_patch = patch.object(
            Project,
            'checkout_path',
            new_callable=PropertyMock,
            return_value=FAKE_CHECKOUT_PATH
        )
        checkout_path_patch.start()
        self.addCleanup(checkout_path_patch.stop)

        self.vcs_project = VCSProject(self.db_project)
        self.main_vcs_resource = self.vcs_project.resources[self.main_db_resource.path]
        self.other_vcs_resource = self.vcs_project.resources[self.other_db_resource.path]
        self.missing_vcs_resource = self.vcs_project.resources[self.missing_db_resource.path]
        self.main_vcs_entity = self.main_vcs_resource.entities['Source String']
        self.main_vcs_translation = self.main_vcs_entity.translations['translated-locale']

        # Mock VCSResource.save() for each resource to avoid altering
        # the filesystem.
        resource_save_patch = patch.object(VCSResource, 'save')
        resource_save_patch.start()
        self.addCleanup(resource_save_patch.stop)

        self.changeset = ChangeSet(
            self.db_project,
            self.vcs_project,
            aware_datetime(1970, 1, 1)
        )
