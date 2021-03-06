# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2018-01-21 19:47
from __future__ import unicode_literals

import datetime
from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataPoint',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=datetime.date.today, editable=False, verbose_name='Date for the Data Point')),
                ('type', models.CharField(editable=False, max_length=255, verbose_name='Type of Data Point')),
                ('data', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
            ],
        ),
        migrations.CreateModel(
            name='DataProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(editable=False, max_length=255, verbose_name='Name of Data Provider')),
                ('auth_data', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('data', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_profiles', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='datapoint',
            name='data_profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_points', to='users.DataProfile'),
        ),
    ]
