from django.db import migrations, models


def map_existing_states(apps, schema_editor):
    Product = apps.get_model('catalog', 'Product')
    Product.objects.using(schema_editor.connection.alias).filter(is_active=False).update(editorial_state='draft')


class Migration(migrations.Migration):
    dependencies = [('catalog', '0006_productimage_file')]

    operations = [
        migrations.AddField(model_name='product', name='editorial_state', field=models.CharField(
            choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')],
            default='published', max_length=12,
        )),
        migrations.AddField(model_name='product', name='review_fingerprint',
                            field=models.CharField(blank=True, max_length=64)),
        migrations.AlterModelOptions(name='product', options={
            'ordering': ['pk'], 'permissions': [('publish_product', 'Can publish and withdraw products')],
        }),
        migrations.RunPython(map_existing_states, migrations.RunPython.noop),
    ]
