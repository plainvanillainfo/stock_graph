# Generated by Django 4.0.3 on 2023-01-25 13:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('volume', '0019_minute_slope'),
    ]

    operations = [
        migrations.AddField(
            model_name='chart',
            name='data_type',
            field=models.CharField(choices=[('V', 'Volume'), ('S', 'Slope')], default='V', max_length=1),
        ),
    ]
