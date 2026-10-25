from django.db import migrations, models


OFFICIAL_STATUSES = [
    'Planificado',
    'En ejecución',
    'En validación técnica',
    'Listo para entrega',
    'Entregado',
]


def refuse_unapproved_existing_statuses(apps, schema_editor):
    Project = apps.get_model('clients', 'Project')
    invalid = list(
        Project.objects.using(schema_editor.connection.alias)
        .exclude(status__in=OFFICIAL_STATUSES)
        .values_list('id', 'status')[:20]
    )
    if invalid:
        examples = ', '.join(f'{project_id}={status!r}' for project_id, status in invalid)
        raise RuntimeError(
            'Migration 0009 stopped without changing project data: '
            f'statuses outside FUNC-001/PR-01 are present (up to 20 shown): {examples}. '
            'Resolve only with an explicitly approved data decision, then retry.'
        )


class Migration(migrations.Migration):
    dependencies = [('clients', '0008_project')]

    operations = [
        migrations.RunPython(refuse_unapproved_existing_statuses, migrations.RunPython.noop),
        # choices are Django-level metadata; this AlterField alone does not change a DB CHECK.
        migrations.AlterField(
            model_name='project',
            name='status',
            field=models.CharField(
                choices=[(status, status) for status in OFFICIAL_STATUSES],
                default='Planificado',
                max_length=24,
            ),
        ),
        # Replace the explicit database constraint created by 0008, separately from choices.
        migrations.RemoveConstraint(model_name='project', name='project_status_valid'),
        migrations.AddConstraint(
            model_name='project',
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=OFFICIAL_STATUSES),
                name='project_status_valid',
            ),
        ),
    ]
