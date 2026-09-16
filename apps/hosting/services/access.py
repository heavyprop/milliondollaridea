from apps.hosting.models import Project, ProjectMembership


def can_access(user, project, *, write=False):
    if not user.is_authenticated or not user.is_active:
        return False
    if write and project.is_archived:
        return False
    if project.owner_id == user.pk:
        return True
    if not write and project.visibility == Project.Visibility.MEMBERS:
        return True
    memberships = ProjectMembership.objects.filter(project=project, user=user)
    if write:
        memberships = memberships.filter(role=ProjectMembership.Role.WRITER)
    return memberships.exists()
