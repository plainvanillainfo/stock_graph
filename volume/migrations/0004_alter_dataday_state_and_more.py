# Generated by Django 4.0.3 on 2022-03-29 16:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('volume', '0003_alter_symbol_symbol'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataday',
            name='state',
            field=models.CharField(choices=[('C', 'Complete'), ('P', 'Pending')], db_index=True, default='P', max_length=1),
        ),
        migrations.AddIndex(
            model_name='dataday',
            index=models.Index(fields=['symbol', 'day'], name='volume_data_symbol__9cc1ce_idx'),
        ),
        migrations.AddIndex(
            model_name='minute',
            index=models.Index(fields=['time', 'symbol'], name='volume_minu_time_c71f25_idx'),
        ),
    ]
