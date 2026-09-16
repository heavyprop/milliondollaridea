from django.contrib import admin

from .models import (
    AccessToken,
    DownloadGrant,
    Project,
    ProjectFile,
    ProjectMembership,
    ProjectUpload,
    TransferEvent,
    VerificationRequest,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "visibility", "is_archived", "updated_at"]
    list_filter = ["visibility", "is_archived"]
    search_fields = ["name", "slug", "owner__username"]
    readonly_fields = ["id", "current_upload", "created_at", "updated_at"]


@admin.register(ProjectMembership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["project", "user", "role"]
    list_filter = ["role"]


class ReadOnlyRecordAdmin(admin.ModelAdmin):
    """Operational state and token hashes cannot be forged through admin forms."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccessToken)
class TokenAdmin(ReadOnlyRecordAdmin):
    list_display = ["name", "user", "can_write", "expires_at", "revoked_at"]
    exclude = ["token_hash"]
    actions = ["revoke_tokens"]

    @admin.action(description="Revoke selected CLI tokens", permissions=["revoke"])
    def revoke_tokens(self, request, queryset):
        from django.utils import timezone

        queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())

    def has_revoke_permission(self, request):
        return request.user.is_superuser


for model in [
    ProjectUpload,
    ProjectFile,
    VerificationRequest,
    DownloadGrant,
    TransferEvent,
]:
    admin.site.register(model, ReadOnlyRecordAdmin)
