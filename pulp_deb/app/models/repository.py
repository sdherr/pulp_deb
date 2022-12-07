from django.db import models
from pulpcore.plugin.models import Repository
from pulpcore.plugin.repo_version_utils import remove_duplicates, validate_version_paths

from pulp_deb.app.models import (
    AptReleaseSigningService,
    AptRemote,
    GenericContent,
    InstallerFileIndex,
    InstallerPackage,
    Package,
    PackageIndex,
    PackageReleaseComponent,
    Release,
    ReleaseArchitecture,
    ReleaseComponent,
    ReleaseFile,
)


class AptRepository(Repository):
    """
    A Repository for DebContent.
    """

    TYPE = "deb"
    CONTENT_TYPES = [
        GenericContent,
        InstallerFileIndex,
        InstallerPackage,
        Package,
        PackageIndex,
        PackageReleaseComponent,
        Release,
        ReleaseArchitecture,
        ReleaseComponent,
        ReleaseFile,
    ]
    REMOTE_TYPES = [
        AptRemote,
    ]

    signing_service = models.ForeignKey(
        AptReleaseSigningService, on_delete=models.PROTECT, null=True
    )
    signing_service_release_overrides = models.JSONField(default=dict)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    def release_signing_service(self, release):
        """
        Resolve and return the Signing Service specified in the overrides if there is one for this
        release, else return self.signing_service.
        """
        from pulpcore.plugin.viewsets import NamedModelViewSet

        if release.distribution in self.signing_service_release_overrides:
            url = self.signing_service_release_overrides[release.distribution]
            return NamedModelViewSet().get_resource(url, AptReleaseSigningService)
        return self.signing_service

    def initialize_new_version(self, new_version):
        """
        Remove old metadata from the repo before performing anything else for the new version. This
        way, we ensure any syncs will re-add all metadata relevant for the latest sync, but old
        metadata (which may no longer be appropriate for the new RepositoryVersion is never
        retained.
        """
        new_version.remove_content(ReleaseFile.objects.all())
        new_version.remove_content(PackageIndex.objects.all())
        new_version.remove_content(InstallerFileIndex.objects.all())

    def finalize_new_version(self, new_version):
        """
        Finalize and validate the new repository version.

        Ensure there are no duplication of added package in debian repository.

        Args:
            new_version (pulpcore.app.models.RepositoryVersion): The incomplete RepositoryVersion to
                finalize.

        """
        from pulp_deb.app.tasks.exceptions import DuplicateDistributionException

        remove_duplicates(new_version)
        validate_version_paths(new_version)
        releases = new_version.get_content(Release.objects.all())
        distributions = []
        for release in releases:
            distribution = release.distribution
            if distribution in distributions:
                raise DuplicateDistributionException(distribution)
            distributions.append(distribution)
