from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0006_alter_cupelog_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='webfeature',
            name='web_types',
            field=models.ManyToManyField(
                blank=True,
                related_name='available_features',
                to='clients.webcatalog',
            ),
        ),
    ]
