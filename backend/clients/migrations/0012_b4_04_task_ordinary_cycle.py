import django.db.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0011_b4_03_relationship_withdrawal'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='task',
            name='task_initial_status_valid',
        ),
        migrations.RemoveConstraint(
            model_name='task',
            name='task_assignment_matches_status',
        ),
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.CharField(
                choices=[
                    ('Pendiente', 'Pendiente'),
                    ('Asignada', 'Asignada'),
                    ('En proceso', 'En proceso'),
                    ('En revisión', 'En revisión'),
                    ('Observada', 'Observada'),
                    ('Finalizada', 'Finalizada'),
                ],
                default='Pendiente',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='taskevent',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('creada', 'Creada'),
                    ('asignada', 'Asignada'),
                    ('iniciada', 'Iniciada'),
                    ('resultado_presentado', 'Resultado presentado'),
                    ('observada', 'Observada'),
                    ('aprobada_revision', 'Aprobada en revisión'),
                    ('correccion_iniciada', 'Corrección iniciada'),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='taskevent',
            name='result_text',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='taskevent',
            name='reason',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddConstraint(
            model_name='task',
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=[
                    'Pendiente', 'Asignada', 'En proceso', 'En revisión', 'Observada', 'Finalizada',
                ]),
                name='task_status_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='task',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(status='Pendiente', assignee__isnull=True, assigned_at__isnull=True)
                    | models.Q(
                        status__in=['Asignada', 'En proceso', 'En revisión', 'Observada', 'Finalizada'],
                        assignee__isnull=False, assigned_at__isnull=False,
                    )
                ),
                name='task_assignment_matches_status',
            ),
        ),
    ]
