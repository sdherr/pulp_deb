from gettext import gettext as _
from pulpcore.plugin.serializers import (
    RelatedField,
    RepositorySerializer,
    RepositorySyncURLSerializer,
    validate_unknown_fields,
)
from pulpcore.plugin.viewsets import NamedModelViewSet

from pulp_deb.app.models import AptReleaseSigningService, AptRepository

from jsonschema import Draft7Validator
from rest_framework import serializers
from pulp_deb.app.schema import COPY_CONFIG_SCHEMA


class AptRepositorySerializer(RepositorySerializer):
    """
    A Serializer for AptRepository.
    """

    signing_service = RelatedField(
        help_text="A reference to an associated signing service. Used if "
        "AptPublication.signing_service is not set",
        view_name="signing-services-detail",
        queryset=AptReleaseSigningService.objects.all(),
        many=False,
        required=False,
        allow_null=True,
    )
    signing_service_release_overrides = serializers.JSONField(
        required=False,
        default=dict,
        help_text=_(
            "A dictionary of Release distributions and the Signing Service URLs they should use."
            'Example: {"bionic": "/pulp/api/v3/signing-services/433a1f70-c589-4413-a803-c50b842ea9b5/"}'
        ),
    )

    class Meta:
        fields = RepositorySerializer.Meta.fields + (
            "signing_service",
            "signing_service_release_overrides",
        )
        model = AptRepository

    def validate(self, data):
        """
        Validate that the Serializer contains valid data.
        Ensure the signing services specified in signing_service_release_overrides exist, or error.
        """
        super().validate(data)

        field = "signing_service_release_overrides"
        if field in data:
            nmvs = NamedModelViewSet()
            for _, value in data[field].items():
                nmvs.get_resource(value, AptReleaseSigningService)

        return data


class AptRepositorySyncURLSerializer(RepositorySyncURLSerializer):
    """
    A Serializer for AptRepository Sync.
    """

    optimize = serializers.BooleanField(
        help_text=_(
            "Using optimize sync, will skip the processing of metadata if the checksum has not "
            "changed since the last sync. This greately improves re-sync performance in such "
            "situations. If you feel the sync is missing something that has changed about the "
            "remote repository you are syncing, try using optimize=False for a full re-sync. "
            "Consider opening an issue on why we should not optimize in your use case."
        ),
        required=False,
        default=True,
    )


class CopySerializer(serializers.Serializer):
    """
    A serializer for Content Copy API.
    """

    config = serializers.JSONField(
        help_text=_("A JSON document describing sources, destinations, and content to be copied")
    )

    structured = serializers.BooleanField(
        help_text=_(
            "Also copy any distributions, components, and releases as needed for any packages "
            "being copied. This will allow for structured publications of the target repository."
            "Default is set to True"
        ),
        default=True,
    )

    dependency_solving = serializers.BooleanField(
        help_text=_(
            "Also copy dependencies of any packages being copied. NOT YET"
            'IMPLEMENTED! You must keep this at "False"!'
        ),
        default=False,
    )

    def validate(self, data):
        """
        Validate that the Serializer contains valid data.
        Set the DebRepository based on the RepositoryVersion if only the latter is provided.
        Set the RepositoryVersion based on the DebRepository if only the latter is provided.
        Convert the human-friendly names of the content types into what Pulp needs to query on.
        """
        super().validate(data)

        if hasattr(self, "initial_data"):
            validate_unknown_fields(self.initial_data, self.fields)

        if "config" in data:
            validator = Draft7Validator(COPY_CONFIG_SCHEMA)

            err = []
            for error in sorted(validator.iter_errors(data["config"]), key=str):
                err.append(error.message)
            if err:
                raise serializers.ValidationError(
                    _("Provided copy criteria is invalid:'{}'".format(err))
                )

        return data
