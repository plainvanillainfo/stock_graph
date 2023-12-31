# Generated by Django 4.0.3 on 2022-05-11 09:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('volume', '0009_symbol_type_alter_dataday_last_tried'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='symbol',
            options={'ordering': ['type', 'active', 'symbol']},
        ),
        migrations.CreateModel(
            name='IndexWeight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weight', models.DecimalField(decimal_places=6, max_digits=8)),
                ('index', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='volume.symbol')),
                ('symbol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='volume.symbol')),
            ],
        ),
        migrations.CreateModel(
            name='Chart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField()),
                ('slug', models.SlugField()),
                ('system', models.BooleanField(default=True)),
                ('symbols', models.ManyToManyField(related_name='+', to='volume.symbol')),
            ],
        ),
    ]
