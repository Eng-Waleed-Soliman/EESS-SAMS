from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0081_shareholder_monthly_salary'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExpenseCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True, verbose_name='اسم فئة المصروف')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'فئة مصروف',
                'verbose_name_plural': 'فئات المصاريف',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='monthlyexpense',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='expenses', to='academies.expensecategory', verbose_name='فئة المصروف'),
        ),
    ]
