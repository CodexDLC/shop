import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0007_product_editorial_workflow")]
    operations = [
        migrations.AddField(model_name="category", name="parent", field=models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
            related_name="children", to="catalog.category")),
        *[migrations.AddField(model_name="category", name=name, field=models.CharField(max_length=160, blank=True))
          for name in ("name_de", "name_ru", "seo_title")],
        *[migrations.AddField(model_name="category", name=name, field=models.TextField(blank=True))
          for name in ("description_de", "description_ru")],
        migrations.AddField(model_name="category", name="seo_description", field=models.CharField(max_length=320, blank=True)),
        migrations.AddField(model_name="category", name="position", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="category", name="is_visible", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="category", name="image", field=models.FileField(upload_to="categories/", blank=True)),
        migrations.AddField(model_name="category", name="image_alt", field=models.CharField(max_length=200, blank=True)),
    ]
