# Generated by Django 4.0.3 on 2022-05-11 11:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('volume', '0013_alter_indexweight_weight'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='symbol',
            name='slug',
        ),
        migrations.AddField(
            model_name='symbol',
            name='name',
            field=models.TextField(default=''),
        ),
    ]
