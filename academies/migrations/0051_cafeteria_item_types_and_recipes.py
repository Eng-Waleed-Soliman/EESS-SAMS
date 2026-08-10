from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('academies', '0050_cafeteria_addons')]

    operations = [
        migrations.AddField(
            model_name='cafeteriaitem',
            name='item_type',
            field=models.CharField(
                choices=[('count', 'عددي'), ('weight', 'كمي (بالوزن)'), ('mixed', 'مختلط (وصفة)')],
                default='count',
                max_length=10,
                verbose_name='نوع الصنف',
            ),
        ),
        migrations.CreateModel(
            name='CafeteriaRecipeComponent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(verbose_name='الكمية المستخدمة في الحصة')),
                ('component', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='used_in_recipes', to='academies.cafeteriaitem', verbose_name='المكوّن')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipe_components', to='academies.cafeteriaitem', verbose_name='الصنف المختلط')),
            ],
            options={
                'verbose_name': 'مكوّن وصفة كافيتريا',
                'verbose_name_plural': 'مكونات وصفات الكافيتريا',
                'ordering': ['id'],
                'unique_together': {('product', 'component')},
            },
        ),
        migrations.CreateModel(
            name='CafeteriaIngredientUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(verbose_name='الكمية المستهلكة')),
                ('component', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ingredient_usages', to='academies.cafeteriaitem', verbose_name='المكوّن المستهلك')),
                ('hospitality_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ingredient_usages', to='academies.cafeteriahospitalityitem', verbose_name='حركة الضيافة')),
                ('sale', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ingredient_usages', to='academies.cafeteriasale', verbose_name='حركة البيع')),
            ],
            options={
                'verbose_name': 'استهلاك مكوّن كافيتريا',
                'verbose_name_plural': 'استهلاك مكونات الكافيتريا',
            },
        ),
    ]
