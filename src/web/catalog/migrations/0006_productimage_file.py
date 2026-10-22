from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_material_productproperty_product_published_at_and_more")]

    operations = [
        migrations.AddField(model_name="productimage", name="file",
                            field=models.ImageField(blank=True, max_length=200, upload_to="products/")),
        migrations.AddField(model_name="productimage", name="alt_text",
                            field=models.CharField(blank=True, max_length=300)),
        migrations.AlterField(model_name="productimage", name="image_url",
                              field=models.URLField(blank=True, max_length=1000)),
        migrations.AlterField(model_name="productimage", name="alt_key",
                              field=models.CharField(blank=True, max_length=160)),
    ]
