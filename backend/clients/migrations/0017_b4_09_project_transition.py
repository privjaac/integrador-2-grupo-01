from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('clients', '0016_b4_08_task_cancellation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(max_length=40)),
                ('previous_status', models.CharField(max_length=24)),
                ('new_status', models.CharField(max_length=24)),
                ('reason', models.TextField()),
                ('evidence', models.TextField()),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='project_events', to='clients.collaborator')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='events', to='clients.project')),
            ],
            options={'db_table': 'project_events', 'ordering': ['occurred_at', 'id']},
        ),
    ]
