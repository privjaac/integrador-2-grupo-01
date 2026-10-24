from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('clients', '0007_webfeature_web_types')]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('objective', models.TextField(blank=True, null=True)),
                ('scope', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('Planificado', 'Planificado'), ('En progreso', 'En progreso'), ('En pausa', 'En pausa'), ('Completado', 'Completado'), ('Cancelado', 'Cancelado')], default='Planificado', max_length=20)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='projects', to='clients.client')),
            ],
            options={'db_table': 'projects', 'ordering': ['id']},
        ),
        migrations.AddConstraint(
            model_name='project',
            constraint=models.CheckConstraint(condition=models.Q(('status__in', ['Planificado', 'En progreso', 'En pausa', 'Completado', 'Cancelado'])), name='project_status_valid'),
        ),
    ]
