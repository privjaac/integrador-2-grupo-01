from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('clients', '0017_b4_09_project_transition'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectCommercialAuthorization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('authorized_at', models.DateTimeField(auto_now_add=True)),
                ('effective_at', models.DateTimeField()),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('authorized_scope', models.TextField()),
                ('commitment_reference', models.CharField(max_length=200)),
                ('start_conditions', models.TextField()),
                ('start_conditions_accredited', models.BooleanField(default=False)),
                ('evidence_reference', models.CharField(max_length=300)),
                ('authorized_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='project_commercial_authorizations', to='clients.collaborator')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='commercial_authorizations', to='clients.project')),
            ],
            options={'db_table': 'project_commercial_authorizations', 'ordering': ['-authorized_at', '-id']},
        ),
        migrations.CreateModel(
            name='ProjectCommercialAuthorizationEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('retirada', 'Retirada'), ('sustituida', 'Sustituida')], max_length=12)),
                ('reason', models.TextField()),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='commercial_authorization_events', to='clients.collaborator')),
                ('authorization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='events', to='clients.projectcommercialauthorization')),
                ('replacement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='replaced_authorizations', to='clients.projectcommercialauthorization')),
            ],
            options={'db_table': 'project_commercial_authorization_events', 'ordering': ['occurred_at', 'id']},
        ),
        migrations.AddConstraint(
            model_name='projectcommercialauthorizationevent',
            constraint=models.UniqueConstraint(condition=models.Q(('event_type__in', ['retirada', 'sustituida'])), fields=('authorization',), name='project_auth_single_close_event'),
        ),
        migrations.AddField(
            model_name='projectevent',
            name='commercial_authorization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='project_transitions', to='clients.projectcommercialauthorization'),
        ),
    ]
