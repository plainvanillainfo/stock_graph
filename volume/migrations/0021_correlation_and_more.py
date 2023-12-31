# Generated by Django 4.0.3 on 2023-02-01 13:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('volume', '0020_chart_data_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='Correlation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField(db_index=True)),
                ('data_type', models.CharField(choices=[('V', 'Volume'), ('S', 'Slope')], max_length=1)),
                ('value', models.FloatField()),
                ('symbol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='volume.symbol')),
            ],
            options={
                'ordering': ['day'],
            },
        ),
        migrations.AddIndex(
            model_name='correlation',
            index=models.Index(fields=['symbol', 'day', 'data_type'], name='volume_corr_symbol__10cc7c_idx'),
        ),
    ]
