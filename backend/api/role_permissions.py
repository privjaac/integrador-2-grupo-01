"""Backend capability ceilings for organizational roles.

The capability names mirror the approved action matrix in the frontend. The
functional level is immutable; an organizational role may only select a
subset of the capabilities allowed for that level.
"""

CAPABILITY_LEVELS = {
    'notifications.configure': {'L1', 'L2'},
    'clients.view': {'L1', 'L2', 'L3'},
    'clients.create': {'L1', 'L2'},
    'clients.edit': {'L1', 'L2', 'L3'},
    'clients.delete': {'L1', 'L2', 'L3'},
    'clients.resolveChange': {'L1', 'L2'},
    'clients.resolveDeactivation': {'L1'},
    'projects.view': {'L2', 'L3'},
    'projects.create': {'L2'},
    'projects.enterTechnicalValidation': {'L3'},
    'projects.returnProjectToExecution': {'L3'},
    'projects.classifyProjectTasks': {'L3'},
    'projects.evaluateProjectClosure': {'L3'},
    'projects.markProjectReadyForDelivery': {'L3'},
    'projects.authorizeProjectDelivery': {'L2'},
    'projects.recordProjectDelivery': {'L2'},
    'projects.formalizeProjectDelivery': {'L2'},
    'projects.reviewProjectDeliveryVersion': {'L3'},
    'projects.authorizeProjectStart': {'L2'},
    'projects.startProject': {'L3'},
    'projects.associateContractedServices': {'L3'},
    'projects.requestProjectCancellation': {'L2'},
    'projects.evaluateProjectCancellation': {'L3'},
    'projects.resolveProjectCancellation': {'L2'},
    'projects.manageSubstitutions': {'L1', 'L3'},
    'projects.viewSubstitutions': {'L1', 'L2', 'L3'},
    'tasks.view': {'L3', 'L4', 'L5'},
    'tasks.create': {'L3', 'L4'},
    'tasks.assign': {'L4'},
    'tasks.start': {'L5'},
    'tasks.submitReview': {'L5'},
    'tasks.review': {'L4'},
    'tasks.reassign': {'L3', 'L4'},
    'tasks.removeExecutor': {'L3', 'L4'},
    'tasks.blockTask': {'L3', 'L4'},
    'tasks.unblockTask': {'L3', 'L4'},
    'tasks.reportIncident': {'L5'},
    'tasks.reopen': {'L3'},
    'tasks.proposeCancellation': {'L4'},
    'tasks.evaluateCancellation': {'L3'},
    'tasks.reviewCancellationCommercial': {'L2'},
    'tasks.applyCancellation': {'L3'},
    'tasks.designate': {'L2'},
    'tasks.withdrawCoordination': {'L2'},
    'tasks.delegate': {'L3'},
    'tasks.withdrawLeadership': {'L3'},
    'tasks.manageTeam': {'L4'},
    'tasks.withdrawTeam': {'L4'},
    'users.view': {'L1', 'L2', 'L3', 'L4'},
    'users.create': {'L1', 'L2', 'L3', 'L4'},
    'users.edit': {'L1', 'L2'},
    'users.activate': {'L1', 'L2'},
    'users.deactivate': {'L1', 'L2'},
    'collaboratorPayments.view': {'L1', 'L2'},
    'collaboratorPayments.record': {'L1', 'L2'},
    'roles.view': {'L1', 'L2', 'L3', 'L4', 'L5'},
    'roles.create': {'L1'},
    'roles.edit': {'L1'},
    'roles.delete': {'L1'},
    'catalog.view': {'L1', 'L2', 'L3'},
    'catalog.create': {'L1'},
    'catalog.edit': {'L1'},
    'catalog.delete': {'L1'},
    'dashboard.view': {'L1', 'L2', 'L3'},
    'platforms.view': {'L1', 'L2', 'L3'},
    'platforms.manage': {'L1', 'L2'},
    'admin.view': {'L1'},
    'admin.create': {'L1'},
    'admin.edit': {'L1'},
    'admin.delete': {'L1'},
}


def default_permissions(level: str) -> list[str]:
    """Preserve the existing five-level capability matrix for legacy roles."""
    return sorted(key for key, levels in CAPABILITY_LEVELS.items() if level in levels)


def allowed_permissions(level: str) -> list[str]:
    return default_permissions(level)


def valid_permissions(level: str, permissions) -> bool:
    return isinstance(permissions, list) and len(permissions) == len(set(permissions)) and set(permissions) <= set(allowed_permissions(level))


def effective_permissions(role) -> list[str]:
    if role is None or not role.is_active:
        return []
    if role.permissions is None:
        return default_permissions(role.level)
    return role.permissions if valid_permissions(role.level, role.permissions) else []


ROUTE_CAPABILITIES = {
    'get_task_deadline_settings': 'notifications.configure',
    'update_task_deadline_settings': 'notifications.configure',
    'list_internal_notifications': 'tasks.view',
    'mark_internal_notification_read': 'tasks.view',
    # CRM and client operations.
    'get_clients': 'clients.view', 'get_client': 'clients.view',
    'create_client': 'clients.create', 'update_client': 'clients.edit',
    'delete_client': 'clients.delete', 'request_client_change': 'clients.edit',
    'request_client_deactivation': 'clients.delete', 'list_client_requests': 'clients.resolveChange',
    'get_client_history': 'clients.view',
    # Resolution checks the request-type-specific capability in the handler.
    'resolve_client_request': 'clients.resolveChange',
    'list_contracted_services': 'clients.view', 'record_contracted_service': 'clients.edit',
    'amend_contracted_service': 'clients.edit', 'list_client_payments': 'clients.view',
    'record_client_payment': 'clients.edit', 'confirm_client_payment': 'clients.edit',
    'record_payment_adjustment': 'clients.edit', 'confirm_payment_adjustment': 'clients.edit',
    'get_client_features': 'clients.view', 'assign_feature': 'clients.edit',
    'remove_feature': 'clients.edit',
    # Projects: retain every specifically named operation in the level matrix.
    'list_projects': 'projects.view', 'get_project': 'projects.view',
    'delivery_context': 'projects.view', 'list_project_commercial_authorizations': 'projects.view',
    'list_delivery_authorizations': 'projects.view', 'list_project_deliveries': 'projects.view',
    'list_project_contracted_services': 'projects.view', 'create_project': 'projects.create',
    'enter_technical_validation': 'projects.enterTechnicalValidation',
    'return_project_to_execution': 'projects.returnProjectToExecution',
    'authorize_project_start': 'projects.authorizeProjectStart',
    'withdraw_project_start_authorization': 'projects.authorizeProjectStart',
    'classify_project_task': 'projects.classifyProjectTasks',
    'record_project_technical_evaluation': 'projects.evaluateProjectClosure',
    'create_delivery_authorization': 'projects.authorizeProjectDelivery',
    'withdraw_delivery_authorization': 'projects.authorizeProjectDelivery',
    'mark_project_ready_for_delivery': 'projects.markProjectReadyForDelivery',
    'record_project_delivery': 'projects.recordProjectDelivery',
    'review_project_delivery_version': 'projects.reviewProjectDeliveryVersion',
    'formalize_project_delivery': 'projects.formalizeProjectDelivery',
    'start_project': 'projects.startProject', 'link_contracted_service': 'projects.associateContractedServices',
    'unlink_contracted_service': 'projects.associateContractedServices',
    'list_project_cancellations': 'projects.view',
    'open_project_cancellation': 'projects.requestProjectCancellation',
    'evaluate_project_cancellation': 'projects.evaluateProjectCancellation',
    'decide_project_cancellation': 'projects.resolveProjectCancellation',
    'evaluate_project_cancellation_commercially': 'projects.resolveProjectCancellation',
    'record_project_cancellation_l1_escalation': 'projects.resolveProjectCancellation',
    'record_project_cancellation_effectivity': 'projects.resolveProjectCancellation',
    # Tasks and project coordination.
    'get_task_context': 'tasks.view', 'list_tasks': 'tasks.view', 'get_task': 'tasks.view',
    'list_task_comments': 'tasks.view', 'create_task_comment': 'tasks.view',
    'create_task': 'tasks.create', 'assign_task': 'tasks.assign',
    'reassign_task': 'tasks.reassign', 'remove_task_executor': 'tasks.removeExecutor',
    'block_task': 'tasks.blockTask', 'unblock_task': 'tasks.unblockTask',
    'list_project_substitutions': 'projects.viewSubstitutions',
    'create_project_substitution': 'projects.manageSubstitutions',
    'end_project_substitution': 'projects.manageSubstitutions',
    'report_task_incident': 'tasks.reportIncident', 'start_task': 'tasks.start',
    'submit_task_for_review': 'tasks.submitReview', 'review_task': 'tasks.review',
    'reopen_task': 'tasks.reopen', 'propose_task_cancellation': 'tasks.proposeCancellation',
    'evaluate_task_cancellation': 'tasks.evaluateCancellation',
    'review_task_cancellation_commercially': 'tasks.reviewCancellationCommercial',
    'apply_task_cancellation': 'tasks.applyCancellation', 'designate_coordinator': 'tasks.designate',
    'designate_leader': 'tasks.delegate', 'add_team_member': 'tasks.manageTeam',
    'remove_coordinator': 'tasks.withdrawCoordination', 'remove_leader': 'tasks.withdrawLeadership',
    'remove_team_member': 'tasks.withdrawTeam',
    # Collaborators. The self-identity endpoint is intentionally not gated by module view.
    'get_collaborators': 'users.view', 'get_collaborator': 'users.view',
    'create_collaborator': 'users.create', 'update_collaborator': 'users.edit',
    'delete_collaborator': 'users.deactivate',
    'list_collaborator_payments': 'collaboratorPayments.view',
    'get_payment_collaborators': 'collaboratorPayments.view',
    'record_collaborator_payment': 'collaboratorPayments.record',
    # Role administration and catalogue.
    'get_roles': 'roles.view', 'get_role': 'roles.view', 'get_permission_catalog': 'roles.view',
    'get_role_history': 'roles.view', 'create_role': 'roles.create',
    'update_role': 'roles.edit', 'delete_role': 'roles.delete',
    'get_web_types': 'catalog.view', 'get_web_type': 'catalog.view',
    'create_web_type': 'catalog.create', 'update_web_type': 'catalog.edit', 'delete_web_type': 'catalog.delete',
    'get_web_features': 'catalog.view', 'get_web_feature': 'catalog.view',
    'create_web_feature': 'catalog.create', 'update_web_feature': 'catalog.edit', 'delete_web_feature': 'catalog.delete',
    # Administrative CUPE history and dashboard.
    'get_next_cupe': 'admin.view', 'get_cupe_logs': 'admin.view', 'get_cupe_log': 'admin.view',
    'change_cupe': 'admin.edit', 'get_dashboard_summary': 'dashboard.view',
    'list_elomux_platforms': 'platforms.view',
    'create_elomux_platform': 'platforms.manage',
    'update_elomux_platform': 'platforms.manage',
}


def permission_for_route(route_name: str) -> str | None:
    return ROUTE_CAPABILITIES.get(route_name)
