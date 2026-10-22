from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("staff", "0002_staffauditevent")]
    operations = [migrations.AddField(model_name="cabinetpreferences", name="revision",
                                     field=models.PositiveBigIntegerField(default=0, editable=False))]
