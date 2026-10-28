"""Shared, time-bounded lookups for the approved temporary substitutions."""

from django.db.models import F, Q
from django.utils import timezone

from clients.models import OrganizationalSubstitution, ProjectCoordination, ProjectLeadership


def active_coordination_scope(actor_id: int, *, project_id: int | None = None):
    now = timezone.now()
    return ProjectCoordination.objects.filter(
        Q(coordinator_id=actor_id, coordinator__is_active=True, coordinator__role__level='L3')
        | Q(
            substitutions__absent_level='L3', substitutions__substitute_id=actor_id,
            substitutions__is_active=True, substitutions__valid_from__lte=now,
            substitutions__valid_until__gt=now,
            substitutions__substitute__is_active=True,
            substitutions__substitute__role__level='L3',
            substitutions__absent_person_id=F('coordinator_id'),
        ),
        is_active=True, coordinator__role__level='L3',
    ).filter(**({'project_id': project_id} if project_id is not None else {})).distinct()


def active_leadership_scope(actor_id: int, *, project_id: int | None = None, faculty: str = 'tasks.view'):
    now = timezone.now()
    return ProjectLeadership.objects.filter(
        Q(leader_id=actor_id, leader__is_active=True, leader__role__level='L4')
        | Q(
            substitutions__absent_level='L4', substitutions__substitute_id=actor_id,
            substitutions__is_active=True, substitutions__valid_from__lte=now,
            substitutions__valid_until__gt=now,
            substitutions__substitute__is_active=True,
            substitutions__substitute__role__level='L4',
            substitutions__absent_person_id=F('leader_id'),
            substitutions__coordination__coordinator__is_active=True,
        ),
        is_active=True, coordination__is_active=True,
        coordination__coordinator__role__level='L3',
    ).filter(**({'coordination__project_id': project_id} if project_id is not None else {})).distinct()


def has_active_substitution(actor_id: int, *, leadership_id: int | None = None,
                            coordination_id: int | None = None, faculty: str) -> bool:
    now = timezone.now()
    filters = {
        'substitute_id': actor_id, 'is_active': True,
        'valid_from__lte': now, 'valid_until__gt': now,
        'substitute__is_active': True, 'substitute__role__level': 'L4',
        'leadership_id': leadership_id,
        'leadership__is_active': True,
        'leadership__leader_id': F('absent_person_id'),
        'leadership__coordination__is_active': True,
        'leadership__coordination__coordinator__is_active': True,
    }
    if coordination_id is not None:
        filters['coordination_id'] = coordination_id
        filters['coordination__is_active'] = True
        filters['coordination__coordinator_id'] = F('absent_person_id')
    return any(faculty in item.faculties for item in OrganizationalSubstitution.objects.filter(**filters))
