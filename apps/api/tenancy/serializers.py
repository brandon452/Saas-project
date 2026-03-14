from django.contrib.auth import get_user_model
from rest_framework import serializers

from branches.models import Branch

from .models import Organization, OrganizationMember, ParentCompanyMember

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug"]
        read_only_fields = ["id", "name", "slug"]


class MemberUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = ["id", "username", "email"]


class BranchSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class MemberSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)
    assigned_branch = BranchSummarySerializer(read_only=True)

    class Meta:
        model = OrganizationMember
        fields = ["id", "user", "role", "is_active", "organization", "assigned_branch"]
        read_only_fields = ["id", "user", "organization"]


class MemberCreateSerializer(serializers.ModelSerializer):
    """
    Links an existing user to the current org as a new member.
    Does NOT create new user accounts.
    """

    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="user",
    )
    assigned_branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = OrganizationMember
        fields = ["user_id", "role", "assigned_branch"]

    def validate(self, data):
        org = self.context["request"].org
        user = data["user"]
        role = data.get("role")
        assigned_branch = data.get("assigned_branch")

        if OrganizationMember.all_objects.filter(
            user=user,
            organization=org,
        ).exists():
            raise serializers.ValidationError(
                {
                    "user_id": (
                        "Membership already exists for this user in this "
                        "organization. Reactivate the existing membership "
                        "via PATCH instead."
                    )
                }
            )

        if ParentCompanyMember.all_objects.filter(user=user).exists():
            raise serializers.ValidationError(
                {"user_id": "User already has a parent-company membership."}
            )

        if role in (OrganizationMember.ROLE_OWNER, OrganizationMember.ROLE_ADMIN):
            if assigned_branch:
                raise serializers.ValidationError(
                    {
                        "assigned_branch": (
                            "OWNER and ADMIN must not have an assigned branch. "
                            "They have access to all branches in the org."
                        )
                    }
                )

        if role == OrganizationMember.ROLE_STAFF:
            if not assigned_branch:
                raise serializers.ValidationError(
                    {"assigned_branch": "STAFF must have an assigned branch."}
                )
            if assigned_branch.organization_id != org.id:
                raise serializers.ValidationError(
                    {"assigned_branch": "Branch does not belong to this organization."}
                )

        return data


class MemberUpdateSerializer(serializers.ModelSerializer):
    assigned_branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = OrganizationMember
        fields = ["role", "is_active", "assigned_branch"]

    def validate(self, data):
        instance = self.instance
        org = self.context["request"].org

        new_role = data.get("role", instance.role)
        new_branch = data.get("assigned_branch", instance.assigned_branch)

        if ParentCompanyMember.all_objects.filter(user=instance.user).exists():
            raise serializers.ValidationError(
                {"detail": "User already has a parent-company membership."}
            )

        if new_role in (OrganizationMember.ROLE_OWNER, OrganizationMember.ROLE_ADMIN):
            if new_branch:
                raise serializers.ValidationError(
                    {
                        "assigned_branch": (
                            "OWNER and ADMIN must not have an assigned branch. "
                            "Set assigned_branch to null when changing role to OWNER or ADMIN."
                        )
                    }
                )

        if new_role == OrganizationMember.ROLE_STAFF:
            if not new_branch:
                raise serializers.ValidationError(
                    {
                        "assigned_branch": (
                            "STAFF must have an assigned branch. "
                            "Provide assigned_branch when setting role to STAFF."
                        )
                    }
                )
            if new_branch.organization_id != org.id:
                raise serializers.ValidationError(
                    {"assigned_branch": "Branch does not belong to this organization."}
                )

        return data


class ParentMemberUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = ["id", "username", "email"]


class ParentMemberSerializer(serializers.ModelSerializer):
    user = ParentMemberUserSerializer(read_only=True)
    created_by = ParentMemberUserSerializer(read_only=True)

    class Meta:
        model = ParentCompanyMember
        fields = ["id", "user", "role", "is_active", "created_at", "created_by"]
        read_only_fields = ["id", "user", "created_at", "created_by"]


class ParentMemberCreateSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="user")

    class Meta:
        model = ParentCompanyMember
        fields = ["user_id", "role"]

    def validate(self, data):
        user = data["user"]
        if ParentCompanyMember.all_objects.filter(user=user).exists():
            raise serializers.ValidationError({"user_id": "Parent membership already exists for this user."})
        if OrganizationMember.all_objects.filter(user=user).exists():
            raise serializers.ValidationError({"user_id": "User already has organization memberships."})
        return data


class ParentMemberUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentCompanyMember
        fields = ["role", "is_active"]

    def validate(self, data):
        instance = self.instance
        new_is_active = data.get("is_active", instance.is_active)
        if new_is_active and OrganizationMember.all_objects.filter(user=instance.user).exists():
            raise serializers.ValidationError({"detail": "User has organization memberships and cannot be parent-active."})
        return data
